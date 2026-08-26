"""auto_crop.py - 自动美学裁剪与构图优化引擎"""

import logging
from typing import List, Optional, Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _saliency_map(img_bgr: np.ndarray) -> np.ndarray:
    """生成显著性图，优先使用 OpenCV saliency，失败时退化为边缘密度图。"""
    h, w = img_bgr.shape[:2]
    small = cv2.resize(img_bgr, (max(64, w // 2), max(64, h // 2)),
                       interpolation=cv2.INTER_AREA)
    try:
        sal = cv2.saliency.StaticSaliencySpectralResidual_create()
        ok, saliency = sal.computeSaliency(small)
        if ok and saliency is not None:
            return cv2.resize(saliency, (w, h), interpolation=cv2.INTER_LINEAR)
    except Exception as e:
        logger.info("saliency unavailable: %s", e)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    blur = cv2.GaussianBlur(edges.astype(np.float32), (0, 0), 8)
    blur = cv2.normalize(blur, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.resize(blur, (w, h), interpolation=cv2.INTER_LINEAR)


def _candidate_boxes(h: int, w: int, aspect: Optional[float],
                     original_aspect: float) -> List[Dict[str, float]]:
    if aspect is None:
        aspect = original_aspect
    aspect = max(0.1, aspect)
    box_h = min(h, int(w / aspect))
    box_w = int(box_h * aspect)
    if box_w <= 0 or box_h <= 0:
        box_w, box_h = w, h
    boxes = []
    step_x = max(1, box_w // 5)
    step_y = max(1, box_h // 5)
    for y in range(0, h - box_h + 1, step_y):
        for x in range(0, w - box_w + 1, step_x):
            boxes.append({"x": float(x), "y": float(y),
                          "w": float(box_w), "h": float(box_h)})
    if not boxes:
        x = max(0, (w - box_w) // 2)
        y = max(0, (h - box_h) // 2)
        boxes.append({"x": float(x), "y": float(y),
                      "w": float(min(box_w, w)), "h": float(min(box_h, h))})
    return boxes


def _iou(a: Dict[str, float], b: Dict[str, float]) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def gaic_crop_candidates(img_bgr: np.ndarray, aspect_ratio: Optional[float] = None,
                         top_k: int = 3) -> List[Dict[str, float]]:
    """返回 Top-K 美学裁剪候选框，候选间 IoU < 0.5。"""
    h, w = img_bgr.shape[:2]
    saliency = _saliency_map(img_bgr).astype(np.float32)
    saliency = cv2.GaussianBlur(saliency, (0, 0), 16)
    boxes = _candidate_boxes(h, w, aspect_ratio, w / h)
    scored = []
    center_x, center_y = w / 2.0, h / 2.0
    for box in boxes:
        x, y = int(box["x"]), int(box["y"])
        bw, bh = int(box["w"]), int(box["h"])
        region = saliency[y:y + bh, x:x + bw]
        score = float(region.mean()) if region.size else 0.0
        box_cx = x + bw / 2.0
        box_cy = y + bh / 2.0
        center_bonus = 0.25 * (1.0 - min(abs(box_cx - center_x) / max(w, 1),
                                         abs(box_cy - center_y) / max(h, 1)))
        scored.append((box, score + center_bonus))
    scored.sort(key=lambda item: item[1], reverse=True)
    result = []
    for box, score in scored:
        if any(_iou(box, r) >= 0.5 for r in result):
            continue
        item = dict(box)
        item["score"] = round(float(score), 4)
        result.append(item)
        if len(result) >= top_k:
            break
    return result


def _center_crop(img_bgr: np.ndarray, aspect_ratio: Optional[float]) -> Dict[str, float]:
    h, w = img_bgr.shape[:2]
    aspect = aspect_ratio or (w / h)
    aspect = max(0.1, aspect)
    box_h = min(h, int(w / aspect))
    box_w = int(box_h * aspect)
    x = max(0, (w - box_w) // 2)
    y = max(0, (h - box_h) // 2)
    return {"x": float(x), "y": float(y), "w": float(box_w), "h": float(box_h),
            "score": 0.5}


def _find_face(img_bgr: np.ndarray) -> Optional[Dict[str, float]]:
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return None
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                         minSize=(max(40, gray.shape[0] // 12),)*2)
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}
    except Exception as e:
        logger.info("face detect unavailable: %s", e)
        return None


def portrait_crop(img_bgr: np.ndarray, aspect_ratio: Optional[float] = None) -> Dict[str, float]:
    """人像构图：眼睛落在上三分线，面部朝向留白；无人脸时回退中心裁剪。"""
    h, w = img_bgr.shape[:2]
    face = _find_face(img_bgr)
    if face is None:
        return _center_crop(img_bgr, aspect_ratio)
    aspect = aspect_ratio or (w / h)
    aspect = max(0.1, aspect)
    box_h = min(h, int(w / aspect))
    box_w = int(box_h * aspect)
    face_cx = face["x"] + face["w"] / 2.0
    eye_y = face["y"] + face["h"] * 0.32
    left_candidates = [face_cx - box_w * (2.0 / 3.0), face_cx - box_w * (1.0 / 3.0)]
    best = None
    for x in left_candidates:
        if 0.0 <= x <= w - box_w:
            best = x
            break
    if best is None:
        best = float(np.clip(face_cx - box_w / 2.0, 0.0, max(0, w - box_w)))
    y = eye_y - box_h / 3.0
    y = float(np.clip(y, 0.0, max(0, h - box_h)))
    return {"x": best, "y": y, "w": float(box_w), "h": float(box_h), "score": 0.8}

"""geometric_correction.py - 几何校正引擎（镜头畸变/透视/水平）"""

import math
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def detect_horizon_angle(img_bgr: np.ndarray) -> float:
    """检测接近水平的线段，返回需要旋转的角度（度），无明显直线时返回 0。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=max(60, min(gray.shape) // 5),
                            maxLineGap=20)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if abs(angle) <= 30.0:
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))


def correct_horizon(img_bgr: np.ndarray, angle: float = 0.0,
                    strength: float = 1.0) -> Tuple[np.ndarray, float]:
    """旋转扶正。angle=0 表示自动检测；|角度|<0.1 度不旋转。"""
    auto = angle == 0.0
    if auto:
        angle = detect_horizon_angle(img_bgr)
    if abs(angle) < 0.1:
        return img_bgr.copy(), 0.0
    applied = angle * float(np.clip(strength, 0.0, 1.0))
    h, w = img_bgr.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), applied, 1.0)
    result = cv2.warpAffine(img_bgr, matrix, (w, h),
                            flags=cv2.INTER_LANCZOS4,
                            borderMode=cv2.BORDER_REPLICATE)
    return result, applied


def _detect_lines(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                            minLineLength=max(60, min(gray.shape) // 6),
                            maxLineGap=30)
    if lines is None:
        return np.zeros((0, 4), dtype=np.float32)
    return lines.reshape(-1, 4).astype(np.float32)


def _vanishing_point(lines: np.ndarray, axis: str) -> Optional[Tuple[float, float]]:
    """用接近指定轴向的线段，两两求交点后取中位数作为消失点。"""
    selected = []
    for x1, y1, x2, y2 in lines:
        dx, dy = x2 - x1, y2 - y1
        length = max(math.hypot(dx, dy), 1e-6)
        if axis == "vertical":
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if 60.0 <= angle <= 120.0:
                selected.append((x1, y1, x2, y2))
        else:
            angle = abs(math.degrees(math.atan2(dy, dx)))
            if angle <= 30.0 or angle >= 150.0:
                selected.append((x1, y1, x2, y2))
    if len(selected) < 3:
        return None
    points = []
    for i in range(len(selected)):
        x1, y1, x2, y2 = selected[i]
        a1, b1 = y2 - y1, x1 - x2
        c1 = a1 * x1 + b1 * y1
        for j in range(i + 1, len(selected)):
            x3, y3, x4, y4 = selected[j]
            a2, b2 = y4 - y3, x3 - x4
            c2 = a2 * x3 + b2 * y3
            det = a1 * b2 - a2 * b1
            if abs(det) < 1e-8:
                continue
            px = (b2 * c1 - b1 * c2) / det
            py = (a1 * c2 - a2 * c1) / det
            if math.isfinite(px) and math.isfinite(py):
                points.append((px, py))
    if not points:
        return None
    arr = np.asarray(points)
    return (float(np.median(arr[:, 0])), float(np.median(arr[:, 1])))


def _warp_keystone(img_bgr: np.ndarray, vp: Tuple[float, float],
                   axis: str, strength: float) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    vx, vy = vp
    strength = float(np.clip(strength, 0.0, 1.0))
    if axis == "vertical":
        if 0.0 <= vy <= float(h):
            return img_bgr.copy()
        top_denom = 0.0 - vy if vy < 0.0 else float(h) - vy
        base_y = 0.0 if vy < 0.0 else float(h)
        x_tl = vx + (base_y - vy) * (0.0 - vx) / top_denom
        x_tr = vx + (base_y - vy) * (float(w) - vx) / top_denom
        x_tl = x_tl + (0.0 - x_tl) * strength
        x_tr = x_tr + (float(w) - x_tr) * strength
        if vy < 0.0:
            src = np.float32([[x_tl, 0.0], [x_tr, 0.0],
                              [w, h], [0.0, h]])
        else:
            src = np.float32([[0.0, 0.0], [w, 0.0],
                              [x_tr, h], [x_tl, h]])
        dst = np.float32([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])
    else:
        if 0.0 <= vx <= float(w):
            return img_bgr.copy()
        left_denom = 0.0 - vx if vx < 0.0 else float(w) - vx
        base_x = 0.0 if vx < 0.0 else float(w)
        y_tl = vy + (base_x - vx) * (0.0 - vy) / left_denom
        y_bl = vy + (base_x - vx) * (float(h) - vy) / left_denom
        y_tl = y_tl + (0.0 - y_tl) * strength
        y_bl = y_bl + (float(h) - y_bl) * strength
        if vx < 0.0:
            src = np.float32([[0.0, y_tl], [w, 0.0],
                              [w, h], [0.0, y_bl]])
        else:
            src = np.float32([[0.0, 0.0], [w, y_tl],
                              [w, y_bl], [0.0, h]])
        dst = np.float32([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img_bgr, matrix, (w, h),
                               flags=cv2.INTER_LANCZOS4,
                               borderMode=cv2.BORDER_REPLICATE)


def correct_perspective(img_bgr: np.ndarray, mode: str = "vertical",
                        strength: float = 1.0) -> Tuple[np.ndarray, bool]:
    """透视校正：根据消失点计算单应性矩阵。无可靠消失点时返回原图。"""
    lines = _detect_lines(img_bgr)
    result = img_bgr.copy()
    changed = False
    vp_v = _vanishing_point(lines, "vertical") if mode in ("vertical", "both") else None
    if vp_v is not None:
        result = _warp_keystone(result, vp_v, "vertical", strength)
        changed = True
    if mode == "both":
        vp_h = _vanishing_point(lines, "horizontal")
        if vp_h is not None:
            result = _warp_keystone(result, vp_h, "horizontal", strength)
            changed = True
    return result, changed


def correct_lens_distortion(img_bgr: np.ndarray, exif_info: Optional[dict],
                            strength: float = 1.0) -> Tuple[np.ndarray, str]:
    """使用 lensfunpy 校正镜头畸变；依赖或镜头数据缺失时优雅跳过。"""
    if not exif_info:
        return img_bgr.copy(), "未读取到 EXIF，已跳过镜头校正"
    make = (exif_info.get("make") or "").strip()
    model = (exif_info.get("model") or "").strip()
    lens = (exif_info.get("lens") or "").strip()
    focal = exif_info.get("focal_length")
    aperture = exif_info.get("aperture")
    if not (make and model and lens and focal):
        return img_bgr.copy(), "未识别到镜头信息，已跳过镜头校正"
    try:
        import lensfunpy
    except Exception as e:
        logger.info("lensfunpy unavailable: %s", e)
        return img_bgr.copy(), "lensfunpy 未安装，已跳过镜头校正"
    try:
        db = lensfunpy.Database()
        cameras = db.find_cameras(make, model)
        if not cameras:
            return img_bgr.copy(), "镜头数据库未匹配相机，已跳过镜头校正"
        cam = cameras[0]
        lenses = db.find_lenses(cam, lens)
        if not lenses:
            return img_bgr.copy(), "镜头数据库未匹配镜头，已跳过镜头校正"
        lens_obj = lenses[0]
        h, w = img_bgr.shape[:2]
        modifier = lensfunpy.Modifier(lens_obj, cam.crop_factor, w, h)
        modifier.initialize(float(focal), float(aperture or 1.0), 1.0)
        map_x, map_y = modifier.apply_geometry_distortion()
        result = cv2.remap(img_bgr, map_x, map_y, cv2.INTER_LANCZOS4)
        if strength < 1.0:
            result = cv2.addWeighted(img_bgr, 1.0 - strength, result, strength, 0)
        return result, ""
    except Exception as e:
        logger.warning("lens correction failed: %s", e)
        return img_bgr.copy(), "镜头校正失败，已跳过"

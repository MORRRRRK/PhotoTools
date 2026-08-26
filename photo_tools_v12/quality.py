import logging
logger = logging.getLogger(__name__)

"""quality.py - 照片/视频质量评估引擎 (V2.0 评分尺度)"""

import os, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from PIL import Image

cv2 = None
def _import_cv2():
    global cv2
    if cv2 is None:
        try:
            import cv2 as _cv2
            cv2 = _cv2
        except ImportError:
            pass

# ===== 评分尺度 =====
SCORING_SCALES = {
    "strict": {
        "sharpness_divisor": 1500,
        "exposure_ideal": 128,
        "exposure_tolerance": 30,
        "shadow_penalty_at": 3,
        "highlight_penalty_at": 3,
        "color_low": 25,
        "color_high": 60,
        "noise_divisor": 120,
    },
    "normal": {
        "sharpness_divisor": 1000,
        "exposure_ideal": 128,
        "exposure_tolerance": 50,
        "shadow_penalty_at": 5,
        "highlight_penalty_at": 5,
        "color_low": 10,
        "color_high": 80,
        "noise_divisor": 200,
    },
    "loose": {
        "sharpness_divisor": 600,
        "exposure_ideal": 128,
        "exposure_tolerance": 70,
        "shadow_penalty_at": 10,
        "highlight_penalty_at": 10,
        "color_low": 5,
        "color_high": 100,
        "noise_divisor": 350,
    },
}

SCORING_SCALE_NAMES = {"strict": "严格", "normal": "普通", "loose": "宽松"}

def scale_params(scale: str) -> dict:
    return SCORING_SCALES.get(scale, SCORING_SCALES["normal"])


# ===== 数据结构 =====

@dataclass
class PhotoScore:
    file: str = ""
    filename: str = ""
    width: int = 0
    height: int = 0
    total_score: float = 0.0
    composition: float = 0.0
    exposure: float = 0.0
    sharpness: float = 0.0
    color_score: float = 0.0
    noise_score: float = 0.0
    ai_score: float = 0.0
    sharpness_value: float = 0.0
    brightness_mean: float = 0.0
    contrast: float = 0.0
    colorfulness: float = 0.0
    shadow_clip_pct: float = 0.0
    highlight_clip_pct: float = 0.0
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {k: round(v, 1) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


@dataclass
class VideoScore:
    file: str = ""
    filename: str = ""
    duration_sec: float = 0.0
    frame_count: int = 0
    avg_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    frame_scores: List[PhotoScore] = field(default_factory=list)
    recommendation: str = ""


# ===== 内部工具 =====

def _norm_score(value: float, ideal: float, tolerance: float) -> float:
    return max(0.0, min(100.0, 100 - abs(value - ideal) / tolerance * 100))

def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))

def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.mean(rgb, axis=2).astype(np.uint8)

def _convolve2d(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    kh, kw = kernel.shape
    ph, pw = kh // 2, kw // 2
    pad = np.pad(img, ((ph, ph), (pw, pw)), mode="edge")
    try:
        from scipy.signal import convolve2d
        return convolve2d(pad, kernel, mode="valid")
    except Exception as _exc: logger.warning("handled exception", exc_info=True)
    try:
        view = np.lib.stride_tricks.sliding_window_view(pad, (kh, kw))
        return np.tensordot(view, kernel, axes=((2, 3), (0, 1)))
    except Exception as _exc:
        out = np.zeros_like(img)
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                out[i, j] = np.sum(pad[i:i+kh, j:j+kw] * kernel)
        return out


# ===== 加载图片 =====

def load_image(path: str) -> Optional[np.ndarray]:
    try:
        img = Image.open(path)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception as _exc: logger.warning("handled exception", exc_info=True)
        return np.array(img.convert("RGB"))
    except Exception as _exc:
        return None


# ===== 1. 清晰度 =====

def evaluate_sharpness(img: np.ndarray, sp: dict) -> tuple:
    _import_cv2()
    gray = _gray(img)
    if cv2:
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(lap.var())
    else:
        kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
        lap = _convolve2d(gray.astype(np.float64), kernel)
        lap_var = float(np.var(lap))

    divisor = sp.get("sharpness_divisor", 1000)
    score = _clamp((lap_var / divisor) * 100)
    return score, lap_var


# ===== 2. 曝光 =====

def evaluate_exposure(img: np.ndarray, sp: dict) -> tuple:
    gray = _gray(img)
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = gray.size

    shadow_cut = np.sum(hist[:30]) / total * 100
    highlight_cut = np.sum(hist[226:]) / total * 100
    mean_bright = float(np.mean(gray))
    contrast_val = float(np.std(gray))

    ideal = sp.get("exposure_ideal", 128)
    tol = sp.get("exposure_tolerance", 50)
    bright_score = _norm_score(mean_bright, ideal, tol)

    sh_at = sp.get("shadow_penalty_at", 5)
    hl_at = sp.get("highlight_penalty_at", 5)
    penalty = max(0, shadow_cut - sh_at) * 2 + max(0, highlight_cut - hl_at) * 2
    bonus = min(20, contrast_val / 10)

    score = _clamp(bright_score - penalty + bonus)
    return score, mean_bright, contrast_val, shadow_cut, highlight_cut


# ===== 3. 构图 =====

def evaluate_composition(img: np.ndarray, sp: dict) -> float:
    _import_cv2()
    h, w, _ = img.shape
    gray = _gray(img)
    score = 50.0
    tw, th = w / 3, h / 3

    if cv2:
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)
    else:
        sx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
        sy = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)
        mag = np.sqrt(_convolve2d(gray.astype(np.float64), sx)**2 +
                       _convolve2d(gray.astype(np.float64), sy)**2)

    mask = np.zeros((h, w), dtype=bool)
    for x in [int(tw), int(2*tw)]:
        x0, x1 = max(0, x-int(w*0.02)), min(w, x+int(w*0.02))
        mask[:, x0:x1] = True
    for y in [int(th), int(2*th)]:
        y0, y1 = max(0, y-int(h*0.02)), min(h, y+int(h*0.02))
        mask[y0:y1, :] = True

    total_e = np.sum(mag)
    if total_e > 0:
        ratio = np.sum(mag[mask]) / total_e
        if 0.15 < ratio < 0.5:
            score += 20

    mid = w // 2
    left = gray[:, :mid].astype(float)
    right = gray[:, mid:mid+left.shape[1]].astype(float)
    if left.shape == right.shape:
        diff = np.mean(np.abs(left - right[:, ::-1]))
        if max(0, 100 - diff/2.5) > 70:
            score += 10

    if cv2:
        edges = cv2.Canny(gray, 50, 150)
        er = np.sum(edges > 0) / (h * w)
        if er < 0.01:
            score -= 15
        elif er > 0.3:
            score -= 10

    return _clamp(score)


# ===== 4. 色彩 =====

def evaluate_color(img: np.ndarray, sp: dict) -> tuple:
    _import_cv2()
    if cv2:
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
        sat = hsv[:, :, 1].astype(float)
    else:
        r, g, b = img[:, :, 0].astype(float), img[:, :, 1].astype(float), img[:, :, 2].astype(float)
        sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)

    m, s = float(np.mean(sat)), float(np.std(sat))
    cf = math.sqrt(m**2 + s**2)

    low = sp.get("color_low", 10)
    high = sp.get("color_high", 80)

    if cf < low:
        score = 30.0
    elif cf < (low + high) / 2:
        score = 50 + (cf - low) * 1.5
    elif cf < high:
        score = 80.0
    else:
        score = max(0, 80 - (cf - high) * 0.2)

    return _clamp(score), cf


# ===== 5. 噪点 =====

def evaluate_noise(img: np.ndarray, sp: dict) -> float:
    gray = _gray(img).astype(float)
    h, w = gray.shape
    variances = []
    for y in range(0, h - 8, 32):
        for x in range(0, w - 8, 32):
            block = gray[y:y+8, x:x+8]
            if block.shape[0] >= 4 and block.shape[1] >= 4:
                variances.append(float(np.var(block)))
    if not variances:
        return 50.0
    variances.sort()
    nd = sp.get("noise_divisor", 200)
    est = float(np.mean(variances[:max(1, len(variances)//5)]))
    return _clamp(100 - (est / nd) * 100)


# ===== 综合评估 =====

def evaluate_photo(path: str, scale: str = "normal") -> Optional[PhotoScore]:
    """对单张照片进行综合质量评估。"""
    img = load_image(path)
    if img is None:
        return None
    h, w, _ = img.shape
    sp = scale_params(scale)

    sharp_s, sharp_v = evaluate_sharpness(img, sp)
    exp_s, bright, contrast, sh, hl = evaluate_exposure(img, sp)
    comp_s = evaluate_composition(img, sp)
    col_s, col_v = evaluate_color(img, sp)
    noise_s = evaluate_noise(img, sp)
    ai_s = evaluate_quality_ai(path)

    total = (sharp_s*0.18 + exp_s*0.23 + comp_s*0.23 + col_s*0.13 +
             noise_s*0.13 + ai_s*0.10)

    issues = []
    if sharp_s < 40: issues.append("清晰度不足")
    if sh > 15: issues.append("暗部细节丢失")
    if hl > 15: issues.append("高光过曝")
    if comp_s < 40: issues.append("构图需改善")
    if col_s < 40: issues.append("色彩表现欠佳")
    if noise_s < 40: issues.append("噪点较多")

    if not issues:
        rec = "优秀，推荐保留" if total >= 80 else ("良好，可保留" if total >= 60 else "一般")
    else:
        rec = "；".join(issues)

    return PhotoScore(
        file=path, filename=os.path.basename(path),
        width=w, height=h, total_score=total,
        composition=comp_s, exposure=exp_s,
        sharpness=sharp_s, color_score=col_s, noise_score=noise_s,
        ai_score=ai_s,
        sharpness_value=sharp_v, brightness_mean=bright,
        contrast=contrast, colorfulness=col_v,
        shadow_clip_pct=sh, highlight_clip_pct=hl,
        recommendation=rec,
    )


def evaluate_quality_ai(path: str) -> float:
    """使用 BRISQUE 计算无参考图像质量分（0-100，越高越好）。"""
    try:
        from brisque import BRISQUE
        img = load_image(path)
        if img is None:
            return 0.0
        _import_cv2()
        if cv2 is not None:
            h, w = img.shape[:2]
            if max(h, w) > 1024:
                scale = 1024 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)),
                                 interpolation=cv2.INTER_AREA)
        score = float(BRISQUE().score(img))
        if not math.isfinite(score):
            return 0.0
        return max(0.0, min(100.0, 100.0 - score))
    except Exception as _exc:
        return 0.0


def evaluate_photos_batch(paths: List[str], max_workers: int = 4,
                           scale: str = "normal") -> List[PhotoScore]:
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut = {ex.submit(evaluate_photo, p, scale): p for p in paths}
        for f in as_completed(fut):
            try:
                r = f.result()
                if r: results.append(r)
            except Exception as _exc: logger.warning("handled exception", exc_info=True)
    return results


def evaluate_video(path: str, sample_interval: float = 2.0,
                    scale: str = "normal") -> Optional[VideoScore]:
    _import_cv2()
    if not cv2:
        return None
    fname = os.path.basename(path)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 and total_frames > 0 else 0
        step = max(1, int(fps * sample_interval))
        sp = scale_params(scale)
        scores = []
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % step == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                ss, _ = evaluate_sharpness(rgb, sp)
                es, _, _, _, _ = evaluate_exposure(rgb, sp)
                cs = evaluate_composition(rgb, sp)
                cl, _ = evaluate_color(rgb, sp)
                ns = evaluate_noise(rgb, sp)
                t = ss*0.20 + es*0.25 + cs*0.25 + cl*0.15 + ns*0.15
                scores.append(PhotoScore(file=path, filename=f"{fname}[{idx}]",
                    width=w, height=h, total_score=t,
                    composition=cs, exposure=es, sharpness=ss,
                    color_score=cl, noise_score=ns))
            idx += 1
        cap.release()
        if not scores:
            return None
        sv = [s.total_score for s in scores]
        avg = float(np.mean(sv))
        rec = "视频质量较好" if avg >= 60 else "视频质量一般"
        return VideoScore(file=path, filename=fname, duration_sec=duration,
            frame_count=len(scores), avg_score=avg,
            min_score=float(min(sv)), max_score=float(max(sv)),
            frame_scores=scores, recommendation=rec)
    except Exception as e:
        cap.release()
        return None

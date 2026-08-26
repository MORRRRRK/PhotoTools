"""image_pipeline.py - 模块化 AI 图像增强流水线引擎 (V12.1)"""

import json
import logging
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

from .auto_crop import gaic_crop_candidates, portrait_crop
from .auto_color import AutoColorEngine, imread_unicode, imwrite_unicode
from .content_fill import fill_black_borders
from .geometric_correction import (
    correct_horizon,
    correct_lens_distortion,
    correct_perspective,
)
from .lut_loader import LUT3D, ensure_lut_dir

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

ASPECT_LABELS = {
    "自由": None,
    "原始比例": "original",
    "1:1": 1.0,
    "4:3": 4.0 / 3.0,
    "3:2": 3.0 / 2.0,
    "16:9": 16.0 / 9.0,
    "9:16": 9.0 / 16.0,
    "2:3": 2.0 / 3.0,
    "4:5": 4.0 / 5.0,
}

LUT_DISPLAY_NAMES = {
    "arri_logc": "阿莱 LogC",
    "black_white": "黑白电影",
    "bleach_bypass": "漂白旁路",
    "ektar_100": "柯达 Ektar 100",
    "fuji_velvia": "富士 Velvia",
    "kodak_2383": "柯达 2383",
    "portra_400": "柯达 Portra 400",
    "teal_orange": "青橙电影",
    "vintage_film": "复古胶片",
    "none": "无",
}


@dataclass
class PipelineConfig:
    """流水线配置：所有模块的开关与参数。"""
    lens_correction_enabled: bool = True
    lens_correction_strength: float = 1.0
    perspective_correction_enabled: bool = True
    perspective_correction_mode: str = "vertical"
    perspective_correction_strength: float = 1.0
    horizon_correction_enabled: bool = True
    horizon_correction_angle: float = 0.0
    sci_enabled: bool = True
    sci_strength: float = 1.0
    sci_shadow_only: bool = False
    hdrnet_enabled: bool = True
    hdrnet_strength: float = 1.0
    hdrnet_style: str = "自然"
    lut_enabled: bool = True
    lut_name: str = "none"
    lut_strength: float = 0.7
    crop_mode: str = "none"
    crop_aspect_ratio: Optional[float] = None
    gaic_top_k: int = 3
    gaic_selected_idx: int = 0
    manual_crop: Optional[Dict] = None
    content_aware_fill_enabled: bool = True
    fill_quality: str = "fast"


@dataclass
class PipelineResult:
    image: np.ndarray
    notes: List[str] = field(default_factory=list)
    modules_applied: List[str] = field(default_factory=list)
    crop_box: Optional[Dict] = None
    elapsed_ms: int = 0


BUILTIN_PRESETS = {
    "风景出片": PipelineConfig(
        lens_correction_enabled=True, perspective_correction_enabled=True,
        horizon_correction_enabled=True, sci_enabled=True, hdrnet_enabled=True,
        lut_enabled=True, lut_name="富士 Velvia", lut_strength=0.7,
        crop_mode="gaic", crop_aspect_ratio=3.0 / 2.0, gaic_top_k=3,
        content_aware_fill_enabled=True),
    "人像出片": PipelineConfig(
        lens_correction_enabled=True, perspective_correction_enabled=False,
        horizon_correction_enabled=False, sci_enabled=True, hdrnet_enabled=True,
        lut_enabled=True, lut_name="柯达 Portra 400", lut_strength=0.6,
        crop_mode="portrait", crop_aspect_ratio=2.0 / 3.0,
        content_aware_fill_enabled=True),
    "建筑出片": PipelineConfig(
        lens_correction_enabled=True, perspective_correction_enabled=True,
        perspective_correction_mode="vertical", horizon_correction_enabled=True,
        sci_enabled=True, hdrnet_enabled=True, lut_enabled=False,
        crop_mode="gaic", crop_aspect_ratio=4.0 / 5.0, gaic_top_k=3,
        content_aware_fill_enabled=True),
    "快速增强": PipelineConfig(
        lens_correction_enabled=False, perspective_correction_enabled=False,
        horizon_correction_enabled=False, sci_enabled=True, hdrnet_enabled=True,
        lut_enabled=False, crop_mode="none", content_aware_fill_enabled=False),
    "仅调色": PipelineConfig(
        lens_correction_enabled=False, perspective_correction_enabled=False,
        horizon_correction_enabled=False, sci_enabled=True, hdrnet_enabled=True,
        lut_enabled=True, lut_name="none", crop_mode="none",
        content_aware_fill_enabled=False),
    "仅校正": PipelineConfig(
        lens_correction_enabled=True, perspective_correction_enabled=True,
        horizon_correction_enabled=True, sci_enabled=False, hdrnet_enabled=False,
        lut_enabled=False, crop_mode="none", content_aware_fill_enabled=True),
    "全流程": PipelineConfig(),
}


def default_presets_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "PhotoTools")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return os.path.join(folder, "pipeline_presets.json")


def default_extra_luts_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "PhotoTools", "luts")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        pass
    return folder


def load_custom_presets(path: Optional[str] = None) -> Dict[str, dict]:
    path = path or default_presets_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("presets", {})
    except Exception:
        return {}


def save_custom_preset(name: str, config: PipelineConfig,
                       path: Optional[str] = None) -> None:
    path = path or default_presets_path()
    presets = load_custom_presets(path)
    presets[name] = asdict(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"presets": presets}, f, ensure_ascii=False, indent=2)


def delete_custom_preset(name: str, path: Optional[str] = None) -> None:
    path = path or default_presets_path()
    presets = load_custom_presets(path)
    if name in presets:
        del presets[name]
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"presets": presets}, f, ensure_ascii=False, indent=2)


def _to_float(value) -> Optional[float]:
    try:
        text = str(value)
        if "/" in text:
            a, b = text.split("/", 1)
            return float(a) / float(b)
        return float(text)
    except Exception:
        return None


def read_exif_info(path: str) -> Dict:
    """读取相机、镜头、焦距等 EXIF 信息，缺失字段返回空值。"""
    info = {"make": "", "model": "", "lens": "", "focal_length": None,
            "aperture": None, "orientation": 1}
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        for key, value in tags.items():
            low = key.lower()
            if "make" in low and not info["make"]:
                info["make"] = str(value)
            elif "lensmodel" in low:
                info["lens"] = str(value)
            elif "focallength" in low and info["focal_length"] is None:
                info["focal_length"] = _to_float(value)
            elif "fnumber" in low and info["aperture"] is None:
                info["aperture"] = _to_float(value)
            elif low.endswith("orientation") and key.startswith("Image"):
                try:
                    info["orientation"] = int(value)
                except Exception:
                    pass
            elif key.startswith("Image") and "model" in low and not info["model"]:
                info["model"] = str(value)
    except Exception as e:
        logger.info("EXIF read failed %s: %s", path, e)
    return info


def load_image_bgr(path: str) -> np.ndarray:
    """读取图片并应用 EXIF 方向；兼容中文路径。"""
    try:
        from PIL import Image, ImageOps
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            rgb = img.convert("RGB")
            arr = np.asarray(rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception:
        bgr = imread_unicode(path)
        if bgr is None:
            raise ValueError("无法读取图片")
        return bgr


def _next_output_path(output_dir: str, stem: str) -> str:
    """返回不覆盖已有文件的版本化输出路径（name_enhanced-1.png, -2.png ...）。"""
    max_version = 0
    prefix = stem + "_enhanced-"
    for name in os.listdir(output_dir):
        if name.lower().endswith(".png") and name.lower().startswith(prefix.lower()):
            match = re.search(r"-(\d+)\.png$", name, re.IGNORECASE)
            if match:
                max_version = max(max_version, int(match.group(1)))
    return os.path.join(output_dir, f"{prefix}{max_version + 1}.png")


class ImagePipeline:
    """模块化图像处理流水线：几何校正 → 调色增强 → 构图裁剪。"""

    def __init__(self, models_dir: str, luts_dir: str, use_gpu: bool = False,
                 extra_luts_dir: Optional[str] = None):
        self.models_dir = models_dir
        self.luts_dir = luts_dir
        self.extra_luts_dir = extra_luts_dir
        self.use_gpu = use_gpu
        self._sci = None
        self._hdrnet_session = None
        self._hdrnet_input = None
        self._luts: Dict[str, LUT3D] = {}
        self._lens_db = None
        self._lens_error = ""

    def _ensure_luts(self):
        if self._luts:
            return
        ensure_lut_dir(self.luts_dir)
        dirs = [self.luts_dir]
        if self.extra_luts_dir:
            try:
                os.makedirs(self.extra_luts_dir, exist_ok=True)
                dirs.insert(0, self.extra_luts_dir)
            except OSError:
                pass
        for lut_dir in dirs:
            for name in sorted(os.listdir(lut_dir)):
                if name.lower().endswith(".cube"):
                    key = os.path.splitext(name)[0]
                    try:
                        self._luts[key] = LUT3D(os.path.join(lut_dir, name))
                    except Exception as e:
                        logger.warning("load lut %s failed: %s", name, e)
        if "none" not in self._luts:
            self._luts["none"] = None

    def get_lut_names(self) -> List[str]:
        self._ensure_luts()
        names = sorted(k for k in self._luts if k != "none")
        display = [LUT_DISPLAY_NAMES.get(k, k) for k in names]
        return display + ["无"]

    def _lut_key(self, name: str) -> str:
        if name == "无":
            return "none"
        for key, display in LUT_DISPLAY_NAMES.items():
            if display == name:
                return key
        return name

    def _ensure_sci(self):
        if self._sci is not None:
            return
        self._sci = AutoColorEngine(
            sci_model_path=os.path.join(self.models_dir, "sci.onnx"),
            hdrnet_model_path=os.path.join(self.models_dir, "hdrnet.onnx"),
            lut_dir=self.luts_dir, use_gpu=self.use_gpu)

    def _ensure_hdrnet(self):
        if self._hdrnet_session is not None:
            return
        path = os.path.join(self.models_dir, "hdrnet.onnx")
        if os.path.exists(path):
            try:
                import onnxruntime as ort
                self._hdrnet_session = ort.InferenceSession(
                    path, providers=["CPUExecutionProvider"])
                self._hdrnet_input = self._hdrnet_session.get_inputs()[0].name
            except Exception as e:
                logger.warning("hdrnet load failed: %s", e)
                self._hdrnet_session = False
        else:
            self._hdrnet_session = False

    def _apply_lens_correction(self, img, config, exif_info, notes):
        if not config.lens_correction_enabled:
            return img
        result, note = correct_lens_distortion(
            img, exif_info, config.lens_correction_strength)
        if note:
            notes.append(note)
        else:
            notes.append("镜头畸变校正完成")
        return result

    def _apply_perspective_correction(self, img, config, notes):
        if not config.perspective_correction_enabled:
            return img
        result, changed = correct_perspective(
            img, config.perspective_correction_mode,
            config.perspective_correction_strength)
        notes.append("透视校正完成" if changed else "未检测到明显透视，已跳过")
        return result

    def _apply_horizon_correction(self, img, config, notes):
        if not config.horizon_correction_enabled:
            return img
        result, angle = correct_horizon(
            img, config.horizon_correction_angle)
        if abs(angle) >= 0.1:
            notes.append(f"水平校正完成（{angle:.2f}°）")
        else:
            notes.append("画面无需水平校正")
        return result

    def _apply_sci(self, img, config, notes):
        self._ensure_sci()
        if self._sci.sci_session is None:
            notes.append("SCI 模型缺失，曝光校正已跳过")
            return img
        sci_out = AutoColorEngine._run_session(
            self._sci.sci_session, self._sci.sci_input, img)
        alpha = AutoColorEngine._sci_blend_alpha(img) * float(
            np.clip(config.sci_strength, 0.0, 1.0))
        if config.sci_shadow_only:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            mask = np.clip(1.0 - (gray - 60.0) / 120.0, 0.0, 1.0)
            mask = cv2.GaussianBlur(mask, (0, 0), 21)[..., None]
            alpha = alpha * mask
        result = cv2.addWeighted(img, 1.0 - alpha, sci_out, alpha, 0)
        notes.append("曝光校正完成（SCI）")
        return result

    @staticmethod
    def _hdrnet_fallback(img, strength, style):
        strength = float(np.clip(strength, 0.0, 1.0))
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        if style == "鲜艳":
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[..., 1] = np.clip(hsv[..., 1] * 1.25, 0, 255)
            out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        elif style == "柔和":
            clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[..., 1] = np.clip(hsv[..., 1] * 0.92, 0, 255)
            out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[..., 1] = np.clip(hsv[..., 1] * 1.12, 0, 255)
            out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        return cv2.addWeighted(img, 1.0 - strength, out, strength, 0)

    def _apply_hdrnet(self, img, config, notes):
        if not config.hdrnet_enabled:
            return img
        self._ensure_hdrnet()
        if self._hdrnet_session:
            try:
                out = AutoColorEngine._run_session(
                    self._hdrnet_session, self._hdrnet_input, img)
                alpha = float(np.clip(config.hdrnet_strength, 0.0, 1.0))
                result = cv2.addWeighted(img, 1.0 - alpha, out, alpha, 0)
                notes.append("综合调色完成（HDRNet）")
                return result
            except Exception as e:
                logger.warning("hdrnet inference failed: %s", e)
        result = self._hdrnet_fallback(
            img, config.hdrnet_strength, config.hdrnet_style)
        notes.append("综合调色完成（传统增强，HDRNet 模型未内置）")
        return result

    def _apply_lut(self, img, config, notes):
        if not config.lut_enabled or not config.lut_name:
            return img
        self._ensure_luts()
        lut = self._luts.get(self._lut_key(config.lut_name))
        if lut is None:
            notes.append("LUT 预设不存在，已跳过风格化")
            return img
        notes.append(f"风格化完成（{config.lut_name}）")
        return lut.apply(img, float(config.lut_strength))

    def _get_crop(self, img, config):
        if config.crop_mode == "none":
            return None
        if config.crop_mode == "gaic":
            candidates = gaic_crop_candidates(
                img, config.crop_aspect_ratio, config.gaic_top_k)
            if not candidates:
                return None
            idx = int(np.clip(config.gaic_selected_idx, 0, len(candidates) - 1))
            return candidates[idx]
        if config.crop_mode == "portrait":
            return portrait_crop(img, config.crop_aspect_ratio)
        if config.crop_mode == "manual" and config.manual_crop:
            box = config.manual_crop
            h, w = img.shape[:2]
            x = int(np.clip(box.get("x", 0), 0, max(0, w - 1)))
            y = int(np.clip(box.get("y", 0), 0, max(0, h - 1)))
            bw = int(np.clip(box.get("w", w), 1, w - x))
            bh = int(np.clip(box.get("h", h), 1, h - y))
            return {"x": float(x), "y": float(y), "w": float(bw), "h": float(bh)}
        return None

    @staticmethod
    def _apply_crop(img, crop):
        if crop is None:
            return img
        x = int(crop["x"]); y = int(crop["y"])
        w = int(crop["w"]); h = int(crop["h"])
        return img[y:y + h, x:x + w].copy()

    def _apply_fill(self, img, config, notes):
        if not config.content_aware_fill_enabled:
            return img
        result, filled = fill_black_borders(img, config.fill_quality)
        notes.append("内容感知填充完成" if filled else "无黑边需要填充")
        return result

    def process(self, img_bgr: np.ndarray, config: PipelineConfig,
                exif_info: Optional[Dict] = None) -> PipelineResult:
        start = time.time()
        result = img_bgr.copy()
        notes: List[str] = []
        applied: List[str] = []

        if config.lens_correction_enabled:
            result = self._apply_lens_correction(result, config, exif_info, notes)
            applied.append("镜头畸变校正")
        if config.perspective_correction_enabled:
            result = self._apply_perspective_correction(result, config, notes)
            applied.append("透视校正")
        if config.horizon_correction_enabled:
            result = self._apply_horizon_correction(result, config, notes)
            applied.append("水平校正")

        if config.sci_enabled:
            result = self._apply_sci(result, config, notes)
            applied.append("曝光校正")
        if config.hdrnet_enabled:
            result = self._apply_hdrnet(result, config, notes)
            applied.append("综合调色")
        if config.lut_enabled and config.lut_name:
            result = self._apply_lut(result, config, notes)
            applied.append("风格化 LUT")

        crop = self._get_crop(result, config)
        if crop is not None:
            result = self._apply_crop(result, crop)
            applied.append("构图裁剪")
        if config.content_aware_fill_enabled:
            result = self._apply_fill(result, config, notes)
            applied.append("内容感知填充")

        elapsed = int((time.time() - start) * 1000)
        return PipelineResult(image=result, notes=notes,
                              modules_applied=applied, crop_box=crop,
                              elapsed_ms=elapsed)

    def process_batch(self, paths: List[str], output_dir: str,
                      config: PipelineConfig,
                      cancel_event: Optional[threading.Event] = None,
                      progress_cb: Optional[Callable[[dict], None]] = None) -> dict:
        cancel_event = cancel_event or threading.Event()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            return {"ok": 0, "failed": len(paths), "failed_files": [],
                    "output_dir": output_dir, "error": str(e)}
        ok = failed = 0
        failed_files = []
        outputs = {}
        total = len(paths)
        for index, path in enumerate(paths):
            if cancel_event.is_set():
                break
            if progress_cb:
                progress_cb({"type": "start", "index": index, "total": total,
                             "path": path})
            try:
                img = load_image_bgr(path)
                exif = read_exif_info(path)
                result = self.process(img, config, exif)
                stem = os.path.splitext(os.path.basename(path))[0]
                out_path = _next_output_path(output_dir, stem)
                if not imwrite_unicode(out_path, result.image,
                                       [cv2.IMWRITE_PNG_COMPRESSION, 3]):
                    raise ValueError("写入输出文件失败")
                ok += 1
                outputs[path] = out_path
            except Exception as e:
                failed += 1
                failed_files.append((path, str(e)))
                logger.warning("pipeline failed %s: %s", path, e)
            if progress_cb:
                progress_cb({"type": "done", "index": index, "total": total,
                             "path": path, "ok": ok, "failed": failed})
        return {"ok": ok, "failed": failed, "failed_files": failed_files,
                "output_dir": output_dir, "error": "", "outputs": outputs}

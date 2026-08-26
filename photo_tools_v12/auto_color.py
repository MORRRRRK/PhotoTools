"""auto_color.py - AI 自动调色引擎核心 (V12)"""

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np

from .lut_loader import LUT3D, ensure_lut_dir

logger = logging.getLogger(__name__)
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
MAX_INFER_SIDE = 1920


def _load_ort_session(path: str, use_gpu: bool = False):
    try:
        import onnxruntime as ort
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if use_gpu else [
            "CPUExecutionProvider"]
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = 4
        return ort.InferenceSession(path, providers=providers, sess_options=session_options)
    except Exception as e:
        logger.warning("ONNX session load failed (%s): %s", path, e)
        return None


class AutoColorEngine:
    """自动调色引擎：SCI 曝光校正 + HDRNet 综合调色 + 3D LUT 风格化。"""

    def __init__(self, sci_model_path: Optional[str] = None,
                 hdrnet_model_path: Optional[str] = None,
                 lut_dir: Optional[str] = None,
                 use_gpu: bool = False):
        self.use_gpu = use_gpu
        self.sci_session = None
        self.hdrnet_session = None
        self.sci_input = None
        self.hdrnet_input = None
        if sci_model_path and os.path.exists(sci_model_path):
            self.sci_session = _load_ort_session(sci_model_path, use_gpu)
            if self.sci_session:
                self.sci_input = self.sci_session.get_inputs()[0].name
        if hdrnet_model_path and os.path.exists(hdrnet_model_path):
            self.hdrnet_session = _load_ort_session(hdrnet_model_path, use_gpu)
            if self.hdrnet_session:
                self.hdrnet_input = self.hdrnet_session.get_inputs()[0].name
        self.lut_dir = lut_dir
        self.luts: Dict[str, LUT3D] = {}
        self.lut_names: List[str] = []
        if lut_dir:
            ensure_lut_dir(lut_dir)
            self._load_luts(lut_dir)

    def _load_luts(self, lut_dir: str):
        for name in sorted(os.listdir(lut_dir)):
            if name.lower().endswith(".cube"):
                key = os.path.splitext(name)[0]
                try:
                    self.luts[key] = LUT3D(os.path.join(lut_dir, name))
                    self.lut_names.append(key)
                except Exception as e:
                    logger.warning("load lut %s failed: %s", name, e)

    def get_lut_names(self) -> List[str]:
        return self.lut_names or ["none"]

    def sci_available(self) -> bool:
        return self.sci_session is not None

    def hdrnet_available(self) -> bool:
        return self.hdrnet_session is not None

    @staticmethod
    def _run_session(session, input_name: str, img_bgr: np.ndarray) -> np.ndarray:
        h, w = img_bgr.shape[:2]
        h_pad = (16 - h % 16) % 16
        w_pad = (16 - w % 16) % 16
        if h_pad or w_pad:
            img = cv2.copyMakeBorder(img_bgr, 0, h_pad, 0, w_pad, cv2.BORDER_REFLECT)
        else:
            img = img_bgr
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.transpose(rgb, (2, 0, 1))[np.newaxis]
        out = session.run(None, {input_name: blob})[0][0]
        out = np.transpose(out, (1, 2, 0))
        # 模型输出可能是 [0,1] 或 [0,255] 两种约定，按实际数值范围自动判断。
        if out.size and out.max() <= 1.05:
            out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
        else:
            out = np.clip(out, 0, 255).astype(np.uint8)
        out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        if h_pad or w_pad:
            out_bgr = out_bgr[:h, :w]
        return out_bgr

    @staticmethod
    def _sci_blend_alpha(img_bgr: np.ndarray) -> float:
        """按画面平均亮度计算 SCI 混合强度，亮图少提亮、暗图多提亮。"""
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        mean_v = float(hsv[..., 2].mean()) / 255.0
        return float(np.clip(1.0 - (mean_v - 0.25) / 0.45, 0.0, 1.0))

    @staticmethod
    def _traditional_enhance(img_bgr: np.ndarray) -> np.ndarray:
        """传统快速增强：CLAHE 曝光校正 + 对比度/饱和度优化。"""
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * 1.1, 0, 255)
        hsv[..., 2] = np.clip((hsv[..., 2] - 128) * 1.05 + 128, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    def process_image(self, img_bgr: np.ndarray, use_sci: bool = True,
                      use_hdrnet: bool = True,
                      lut_name: str = "none",
                      lut_intensity: float = 1.0) -> np.ndarray:
        """对单张 BGR 图像执行自动调色。"""
        result = img_bgr
        h, w = img_bgr.shape[:2]
        scale = 1.0
        if max(h, w) > MAX_INFER_SIDE:
            scale = MAX_INFER_SIDE / max(h, w)
            result = cv2.resize(result, (int(w * scale), int(h * scale)),
                                interpolation=cv2.INTER_AREA)
        if use_sci and self.sci_session:
            sci_in = result
            sci_out = self._run_session(self.sci_session, self.sci_input, sci_in)
            alpha = self._sci_blend_alpha(sci_in)
            result = cv2.addWeighted(sci_in, 1.0 - alpha, sci_out, alpha, 0)
        elif use_sci or use_hdrnet:
            result = self._traditional_enhance(result)
        if use_hdrnet and self.hdrnet_session:
            result = self._run_session(self.hdrnet_session, self.hdrnet_input, result)
        lut = self.luts.get(lut_name)
        if lut is not None:
            result = lut.apply(result, float(lut_intensity))
        if scale != 1.0:
            result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LANCZOS4)
        return result

    def process_batch(self, paths: List[str], output_dir: str,
                      use_sci: bool = True, use_hdrnet: bool = True,
                      lut_name: str = "none", lut_intensity: float = 1.0,
                      cancel_event: Optional[threading.Event] = None,
                      progress_cb: Optional[Callable[[dict], None]] = None) -> dict:
        """批量处理，返回统计结果。"""
        cancel_event = cancel_event or threading.Event()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            return {"ok": 0, "failed": len(paths), "failed_files": [],
                    "output_dir": output_dir, "error": str(e)}
        ok = failed = 0
        failed_files = []
        total = len(paths)
        for index, path in enumerate(paths):
            if cancel_event.is_set():
                break
            if progress_cb:
                progress_cb({"type": "start", "index": index, "total": total, "path": path})
            try:
                img = cv2.imread(path)
                if img is None:
                    raise ValueError("无法读取图片")
                result = self.process_image(img, use_sci, use_hdrnet,
                                            lut_name, lut_intensity)
                out_name = os.path.splitext(os.path.basename(path))[0] + "_autocolor.jpg"
                out_path = os.path.join(output_dir, out_name)
                cv2.imwrite(out_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
                ok += 1
            except Exception as e:
                failed += 1
                failed_files.append((path, str(e)))
                logger.warning("auto color failed %s: %s", path, e)
            if progress_cb:
                progress_cb({"type": "done", "index": index, "total": total,
                             "path": path, "ok": ok, "failed": failed})
        return {"ok": ok, "failed": failed, "failed_files": failed_files,
                "output_dir": output_dir, "error": ""}

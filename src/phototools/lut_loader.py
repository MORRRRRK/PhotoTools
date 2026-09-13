"""lut_loader.py - 3D LUT (.cube) 解析、生成与应用 (V12)"""

import logging
import os
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def generate_identity_lut(size: int = 33) -> np.ndarray:
    """生成恒等 3D LUT（无效果）。"""
    lut = np.zeros((size, size, size, 3), dtype=np.float32)
    for r in range(size):
        for g in range(size):
            for b in range(size):
                lut[r, g, b] = [r / (size - 1), g / (size - 1), b / (size - 1)]
    return lut


def save_cube(lut: np.ndarray, filepath: str, title: str = "Custom LUT") -> None:
    """保存 3D LUT 为 .cube 格式。"""
    size = lut.shape[0]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f'TITLE "{title}"\n')
        f.write(f"LUT_3D_SIZE {size}\n")
        f.write("DOMAIN_MIN 0.0 0.0 0.0\n")
        f.write("DOMAIN_MAX 1.0 1.0 1.0\n")
        for r in range(size):
            for g in range(size):
                for b in range(size):
                    rv, gv, bv = lut[r, g, b]
                    f.write(f"{rv:.6f} {gv:.6f} {bv:.6f}\n")


def apply_teal_orange(lut: np.ndarray) -> np.ndarray:
    """青橙电影色调：阴影偏青，高光偏橙。"""
    result = lut.copy()
    lum = 0.299 * lut[..., 0] + 0.587 * lut[..., 1] + 0.114 * lut[..., 2]
    dark = lum < 0.5
    light = ~dark
    result[dark] = result[dark] * np.array([0.85, 0.95, 1.15], dtype=np.float32)
    result[light] = result[light] * np.array([1.15, 1.05, 0.85], dtype=np.float32)
    return np.clip(result, 0, 1)


def apply_vintage(lut: np.ndarray) -> np.ndarray:
    """复古胶片：轻微褪色、暖调。"""
    result = lut.copy()
    result[..., 0] = result[..., 0] * 1.08 + 0.02
    result[..., 1] = result[..., 1] * 0.96 + 0.01
    result[..., 2] = result[..., 2] * 0.88 + 0.02
    return np.clip(result, 0, 1)


def apply_black_white(lut: np.ndarray) -> np.ndarray:
    """黑白电影。"""
    result = lut.copy()
    lum = 0.299 * lut[..., 0] + 0.587 * lut[..., 1] + 0.114 * lut[..., 2]
    for i in range(3):
        result[..., i] = lum
    return result


def apply_bleach_bypass(lut: np.ndarray) -> np.ndarray:
    """漂白旁路：高对比、低饱和。"""
    result = lut.copy()
    gray = np.mean(lut, axis=3, keepdims=True)
    result = result * 0.7 + gray * 0.6
    return np.clip(result, 0, 1)


def apply_portra(lut: np.ndarray) -> np.ndarray:
    """Portra 400：柔和暖调人像。"""
    result = lut.copy()
    result[..., 0] = result[..., 0] * 1.05 + 0.015
    result[..., 1] = result[..., 1] * 0.99
    result[..., 2] = result[..., 2] * 0.95 + 0.01
    return np.clip(result, 0, 1)


def apply_ektar(lut: np.ndarray) -> np.ndarray:
    """Ektar 100：高饱和风景。"""
    result = lut.copy()
    result = (result - 0.5) * 1.18 + 0.5
    return np.clip(result, 0, 1)


def apply_kodak(lut: np.ndarray) -> np.ndarray:
    """柯达 2383 电影胶片近似。"""
    result = lut.copy()
    result[..., 0] = result[..., 0] * 1.12
    result[..., 1] = result[..., 1] * 1.0
    result[..., 2] = result[..., 2] * 0.92
    result = np.clip(result, 0, 1)
    return result


def apply_arri_logc(lut: np.ndarray) -> np.ndarray:
    """阿莱 LogC 风格：低饱和、广动态范围。"""
    result = np.clip(lut, 0, 1)
    result = np.power(result, 1.25) * 0.9 + 0.02
    return np.clip(result, 0, 1)


def build_default_luts() -> dict:
    """生成内置 LUT 预设。"""
    identity = generate_identity_lut()
    return {
        "none": identity,
        "kodak_2383": apply_kodak(identity.copy()),
        "fuji_velvia": apply_ektar(identity.copy()),
        "arri_logc": apply_arri_logc(identity.copy()),
        "teal_orange": apply_teal_orange(identity.copy()),
        "vintage_film": apply_vintage(identity.copy()),
        "portra_400": apply_portra(identity.copy()),
        "ektar_100": apply_ektar(identity.copy()),
        "black_white": apply_black_white(identity.copy()),
        "bleach_bypass": apply_bleach_bypass(identity.copy()),
    }


def ensure_lut_dir(lut_dir: str) -> None:
    """确保 LUT 目录存在并生成缺失的预设文件。"""
    os.makedirs(lut_dir, exist_ok=True)
    titles = {
        "none": "无效果",
        "kodak_2383": "Kodak 2383",
        "fuji_velvia": "Fuji Velvia",
        "arri_logc": "Arri LogC",
        "teal_orange": "Teal & Orange",
        "vintage_film": "Vintage Film",
        "portra_400": "Kodak Portra 400",
        "ektar_100": "Kodak Ektar 100",
        "black_white": "Black & White",
        "bleach_bypass": "Bleach Bypass",
    }
    for name, lut in build_default_luts().items():
        path = os.path.join(lut_dir, f"{name}.cube")
        if not os.path.exists(path):
            try:
                save_cube(lut, path, titles.get(name, name))
            except OSError as e:
                logger.warning("generate lut %s failed: %s", name, e)


class LUT3D:
    """加载并应用 .cube 3D LUT。"""

    def __init__(self, cube_path: str):
        self.size = 0
        self.title = ""
        self.lut = None
        self._load(cube_path)

    def _load(self, cube_path: str):
        with open(cube_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        data = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            upper = line.upper()
            if upper.startswith("TITLE"):
                self.title = line.split('"')[1] if '"' in line else line.split(None, 1)[1]
            elif upper.startswith("LUT_3D_SIZE"):
                self.size = int(line.split()[-1])
            elif upper.startswith("DOMAIN"):
                continue
            else:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        data.append([float(parts[0]), float(parts[1]), float(parts[2])])
                    except ValueError:
                        continue
        if not data or self.size == 0:
            raise ValueError(f"无效的 LUT 文件: {cube_path}")
        self.lut = np.array(data, dtype=np.float32).reshape(
            self.size, self.size, self.size, 3)

    def apply(self, img_bgr: np.ndarray, intensity: float = 1.0) -> np.ndarray:
        """对 BGR 图像应用 3D LUT，支持强度混合。"""
        if intensity <= 0 or self.lut is None:
            return img_bgr.copy()
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        size = self.size
        scale = size - 1
        idx = img_rgb * scale
        r_idx, g_idx, b_idx = idx[..., 0], idx[..., 1], idx[..., 2]
        r0 = np.floor(r_idx).astype(np.int32)
        g0 = np.floor(g_idx).astype(np.int32)
        b0 = np.floor(b_idx).astype(np.int32)
        r1 = np.clip(r0 + 1, 0, size - 1)
        g1 = np.clip(g0 + 1, 0, size - 1)
        b1 = np.clip(b0 + 1, 0, size - 1)
        rf = (r_idx - r0)[..., np.newaxis]
        gf = (g_idx - g0)[..., np.newaxis]
        bf = (b_idx - b0)[..., np.newaxis]
        lut = self.lut
        c000 = lut[r0, g0, b0]
        c001 = lut[r0, g0, b1]
        c010 = lut[r0, g1, b0]
        c011 = lut[r0, g1, b1]
        c100 = lut[r1, g0, b0]
        c101 = lut[r1, g0, b1]
        c110 = lut[r1, g1, b0]
        c111 = lut[r1, g1, b1]
        c00 = c000 * (1 - bf) + c001 * bf
        c01 = c010 * (1 - bf) + c011 * bf
        c10 = c100 * (1 - bf) + c101 * bf
        c11 = c110 * (1 - bf) + c111 * bf
        c0 = c00 * (1 - gf) + c01 * gf
        c1 = c10 * (1 - gf) + c11 * gf
        result = c0 * (1 - rf) + c1 * rf
        if intensity < 1.0:
            result = img_rgb * (1 - intensity) + result * intensity
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
        return cv2.cvtColor(result, cv2.COLOR_RGB2BGR)

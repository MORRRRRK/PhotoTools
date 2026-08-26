"""content_fill.py - 内容感知填充引擎（黑边检测 + OpenCV inpaint）"""

import logging
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _border_mask(img_bgr: np.ndarray) -> np.ndarray:
    """找出与图像边缘相连的近黑区域作为填充蒙版。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    black = (gray < 10).astype(np.uint8) * 255
    num, labels, stats, _ = cv2.connectedComponentsWithStats(black, connectivity=8)
    h, w = black.shape[:2]
    keep = np.zeros_like(black)
    for i in range(1, num):
        x, y, bw, bh, _ = stats[i]
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h:
            keep[labels == i] = 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    return cv2.dilate(keep, kernel, iterations=1)


def fill_black_borders(img_bgr: np.ndarray,
                       quality: str = "fast") -> Tuple[np.ndarray, bool]:
    """对黑边做内容感知填充，返回 (结果, 是否有黑边被填充)。"""
    mask = _border_mask(img_bgr)
    if cv2.countNonZero(mask) < max(200, img_bgr.shape[0] * img_bgr.shape[1] // 2000):
        return img_bgr.copy(), False
    result = cv2.inpaint(img_bgr, mask, 3, cv2.INPAINT_TELEA)
    return result, True

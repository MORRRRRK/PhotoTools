# PhotoTools V5.1 — 摄影素材管理工具箱

## 概述

PhotoTools 是一款面向摄影爱好者的 Windows 桌面工具，解决摄影素材管理中的三个核心问题：

1. **冗余文件清理** — 自动识别 JPG 已删除但同名 RAW/PNG/TIFF 仍残留的文件，支持并行扫描和批量移入回收站。
2. **照片质量评估** — 从构图、曝光、清晰度、色彩、噪点五个维度评分，帮助判断照片保留价值。
3. **视频代理生成** — 为 4K/6K/8K 高码率原片批量生成 1080p / 2.7K / 4K 低码率代理，支持帧率选择、预估大小、取消、重试和一键删除。
4. **一键生成延时视频** — 将 JPG 序列按自然顺序合成为延时视频，支持分辨率、帧率、CRF 画质和 vidstab 增稳。

运行环境：Windows 10/11，Python 3.12+

技术栈：Python 3.12 · OpenCV · numpy · Pillow · rawpy · exifread · CustomTkinter · ffmpeg · PyInstaller

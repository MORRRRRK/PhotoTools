# PhotoTools V11 重构记录

本次重构在 V10.1（Qt/PySide6）基础上完成，原始 V10.1 已备份到 `photo_tools_v10_1_backup_20260826/`。

## 已修复缺陷

- P0-2：`run.py` 不再硬编码开发者路径，改为动态查找 `sys.executable`、PATH 与常见安装目录。
- P1-2：`utils.find_jpg_orphans()` 改为按目录分组匹配，跨目录同名不再误判。
- P2-1：清理源码文件 UTF-8 BOM。
- P2-2：`convert_batch()` 新增 `quality` 参数，`ConvertPage` 增加 JPG 质量滑块。
- P2-3：`quality._convolve2d()` 使用 scipy/NumPy 向量化，保留纯 Python 兜底。
- P2-4：安装器版本号统一为 11.0.0。
- P2-5：新增统一日志模块 `logging_config.py`，批量清除裸 `except:`，关键异常写入日志。
- P2-6：`timelapse.py` 使用 `os.devnull` 替代硬编码 `NUL`。
- P2-7：`dynamic_extract.py` 支持 `.mov` 动态视频。

## 成熟库替换（可选回退）

- `gallery.py` 优先使用 pyvips 生成缩略图/预览，失败自动回退 Pillow。
- `gallery.py` 尝试使用 ExifTool 读取完整元数据，失败自动回退 exifread。
- `quality.py` 新增 `evaluate_quality_ai()`，使用 BRISQUE 输出 AI 质量分并加入 `PhotoScore.ai_score`；BRISQUE 不可用时返回 0。
- `requirements.txt` 已加入 `pyvips`、`pyexiftool`、`brisque`、`scipy` 与 `opencv-contrib-python-headless`。

## 未完成 / 说明

- P0-1、P1-1、P1-3 属于旧 CustomTkinter `main.py` 的问题，V10.1 已迁移到 Qt，对应缺陷不存在。
- P1-4 的虚拟列表优化在 Qt 版作品展示中尚未完全实现；当前仍使用 `QListWidget` + 卡片，缩略图为后台异步加载。
- 4.2 ExifTool 需要外部 `exiftool.exe`，未随仓库提供二进制；无 ExifTool 时自动回退 exifread。
- 4.1 libvips 需要系统 DLL，未随仓库提供；pyvips 导入失败时自动回退 Pillow。
- 4.4 ffmpeg-python 为可选重构，未替换现有稳定的 subprocess 实现。
- 历史版本目录与备份目录未改动。

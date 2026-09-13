# AI 自动调色模型说明

## V12.1 模块化流水线模型状态

| 模块 | 模型文件 | 状态 |
|------|----------|------|
| 2.1 曝光校正 | `sci.onnx` | 已内置（MIT，约 4KB 动态 HxW） |
| 2.2 综合调色 | `hdrnet.onnx` | 未内置，缺失时降级为传统增强 |
| 3.1 GAIC 自动裁剪 | `gaic.onnx` | 未内置，缺失时使用显著性启发式裁剪 |
| 1.2 透视校正 | `letr.onnx` | 未内置，缺失时使用霍夫变换消失点校正 |
| 3.4 高质量填充 | `lama.onnx` | 未内置，缺失时使用 OpenCV inpaint |
| 1.1 镜头校正 | LensFun 数据库 | lensfunpy 未安装时自动跳过 |
| 3.2 人像构图 | OpenCV Haar | 未检测到人脸时回退中心裁剪 |

所有模块在模型缺失时优雅降级，不会导致批量任务崩溃。

## SCI（曝光校正）

- 论文：Toward Fast, Flexible, and Robust Low-Light Image Enhancement (CVPR 2022)
- 官方代码：https://github.com/vis-opt-group/SCI
- 已内置模型：`sci.onnx`（约 4KB，动态 HxW）
- 来源：PINTO Model Zoo `286_SCI` 转换的 `sci_medium_HxW.onnx`
  https://github.com/PINTO0309/PINTO_model_zoo/tree/main/286_SCI
- 许可证：MIT（SCI 作者 Tengyu Ma）
- 输入：`(1, 3, H, W)` RGB float32，归一化到 [0,1]，支持动态尺寸
- 输出：`(1, 3, H, W)` RGB float32，PINTO 转换版输出范围为 [0,255]，引擎会按数值范围自动识别，无需手动换算
- 引擎会按画面平均亮度自动调整混合强度：暗光照片完整应用 SCI，正常曝光照片只做轻度提亮，避免过曝

## HDRNet（综合调色）

- 论文：Deep Bilateral Learning for Real-Time Image Enhancement (SIGGRAPH 2017)
- 参考实现：https://github.com/creotiv/hdrnet-pytorch
- 现状：未内置。官方仓库只提供 TensorFlow 权重，且双边网格切片属于自定义算子，社区暂无可直接使用的标准 `hdrnet.onnx`。
- 后续接入：需要先获得预训练权重并导出完整前向 ONNX（opset >= 16），放入本目录后引擎会自动加载。

## 使用说明

- `sci.onnx` 已随软件内置，AI 专业调色的曝光校正开箱即用，无需联网下载。
- `hdrnet.onnx` 缺失时，综合调色使用传统 CLAHE + 饱和度增强，其余流程正常执行。
- 若模型文件被误删，流水线各模块自动降级，不会崩溃。

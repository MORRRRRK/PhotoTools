# AI 自动调色模型说明

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
- `hdrnet.onnx` 缺失时，引擎会跳过综合调色阶段，其余流程（SCI + 3D LUT）正常执行，不会崩溃。
- 若模型文件被误删，自动调色引擎会降级为传统增强算法（CLAHE 曝光校正 + 对比度/饱和度增强）。

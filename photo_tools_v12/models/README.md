# AI 自动调色模型说明

## SCI（曝光校正）

- 论文：Toward Fast, Flexible, and Robust Low-Light Image Enhancement (CVPR 2022)
- 官方代码：https://github.com/vis-opt-group/SCI
- 推荐权重：`lol_v2_real`
- 导出：将 PyTorch 权重导出为 `sci.onnx`，输入输出均为 `(1, 3, H, W)` RGB float32 [0,1]，使用动态尺寸。

## HDRNet（综合调色）

- 论文：Deep Bilateral Learning for Real-Time Image Enhancement (SIGGRAPH 2017)
- 参考实现：https://github.com/creotiv/hdrnet-pytorch
- 导出：完整前向（低分辨率特征 + 双边网格 + 全分辨率引导）导出为 `hdrnet.onnx`，opset >= 16。

## 使用说明

- 模型文件不存在时，自动调色引擎会降级为传统增强算法（CLAHE 曝光校正 + 对比度/饱和度增强），不会崩溃。
- 模型文件约 25MB，未随源码提交；可将导出的 ONNX 放入本目录，或按需接入自动下载机制。

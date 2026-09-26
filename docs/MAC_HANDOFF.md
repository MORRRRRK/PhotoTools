# Mac 端交接说明（让 Mac 上的 Codex 帮你构建）

> 目的：Mac 上不需要重新开发，只需要把仓库拉下来、装一次环境、跑构建脚本，产出 `PhotoTools.app` 与 DMG。

## 现状

- 仓库：https://github.com/MORRRRRK/PhotoTools.git（可公开读取，clone 不需要凭据）
- 分支：main；最新提交：c70f866（单一源码目录重构 + 跨平台适配层 + macOS 打包配置）
- 源码目录：src/phototools（Windows 与 macOS 共用同一份代码）
- 版本号唯一来源：src/phototools/_version.py（当前 13.0.0）
- 目标平台：Apple Silicon（arm64），macOS 14+；未签名交付
- macOS 首版功能：单一文件类型筛选、照片质量评估、AI 图像增强、作品展示、设置、关于

## 人工操作（三步）

1. 打开终端，克隆仓库（或已有仓库则 git pull）：

       git clone https://github.com/MORRRRRK/PhotoTools.git
       cd PhotoTools

2. 一次性环境准备（会自动装 Xcode 命令行工具提示、创建 .venv、安装依赖）：

       bash scripts/mac_setup.sh

3. 构建并打包：

       ./scripts/build_macos.sh

   产物：

       dist/PhotoTools.app
       dist/PhotoTools-13.0.0-arm64.dmg

首次打开未签名应用：右键点击 PhotoTools → 打开；或执行

       xattr -dr com.apple.quarantine /Applications/PhotoTools.app

## 直接交给 Mac 上的 Codex 操作

在 Mac 的 Codex 里新建任务，把下面整段粘贴进去即可（它会自己拉代码、装环境、构建、验收）：

```
请在这台 Mac（Apple Silicon）上构建并验收 PhotoTools，仓库：https://github.com/MORRRRRK/PhotoTools.git，分支 main。

任务要求：
1. 若本地没有仓库，先 git clone；已有则 git pull，确认 HEAD 提交是 c70f866 或更新。
2. 阅读 docs/BUILD_AND_SYNC.md 与 docs/MAC_HANDOFF.md，严格按文档执行。
3. 运行 bash scripts/mac_setup.sh 完成一次性环境准备（需要 Xcode Command Line Tools 与 Python 3.12+，脚本会给出提示）。
4. 运行 ./scripts/build_macos.sh，产出 dist/PhotoTools.app 与 dist/PhotoTools-13.0.0-arm64.dmg。
5. 验收（逐项确认并记录结果）：
   - 双击/右键打开 .app 能进入主界面；侧栏只显示 单一文件类型筛选、照片质量评估、AI 图像增强、作品展示、设置、关于。
   - 设置页切换 深色/浅色、四档字号、四种主题色 立即生效；重启后保持（配置写在 ~/Library/Application Support/PhotoTools）。
   - 单一文件类型筛选：批量添加父目录后能扫描出未配对文件，点击结果行右侧等比预览正常，删除走废纸篓。
   - 照片质量评估：能添加图片、评分、预览按比例完整显示。
   - AI 图像增强：预览原片/结果对比正常；批量生成输出 文件名_enhanced-1.png、-2.png 递增且不覆盖原图。
   - 作品展示：缩略图与灯箱预览按比例完整显示。
   - 设置页“卸载”可把应用移入废纸篓并清理配置缓存（测试时请先用副本验证，避免误删正式安装）。
6. 若发现 macOS 专属问题（路径、shell 调用、打包配置、依赖缺失），请直接修复：只允许改 src/phototools/ 与 packaging/、scripts/，不要新建平台分支，不要把旧版本目录 photo_tools_v* 当作源码修改。
7. 修复后重新构建验证，并向我报告：失败的原始报错、修改的文件、最终 .app 与 DMG 的绝对路径、以及验收清单的逐项结果。
8. 如需把修复推回仓库，请用 gh auth login 或我提供的 GitHub Token 完成推送；不要把我给你的任何 Token 写进代码或提交记录。

注意：这台 Mac 上没有现成的开发环境，你可以自行安装 Python、创建虚拟环境、安装依赖；但构建产物必须是自包含的 .app，用户机器不需要装 Python。
```

## 验收清单（给你自己核对）

- [ ] dist/PhotoTools.app 存在，双击可启动（首次需右键打开）
- [ ] 关于页显示的版本号为 13.0.0
- [ ] 深/浅主题、字号、主题色切换并持久化
- [ ] 单一文件类型筛选可扫描、可预览、可移入废纸篓
- [ ] AI 图像增强输出 _enhanced-1.png / -2.png，原图不被覆盖
- [ ] 设置页卸载可移除 .app 与 ~/Library/Application Support/PhotoTools，作品输出不受影响

## 注意事项

- 当前构建未做 Apple 签名与公证：首次打开需要右键“打开”，属预期行为，不是 Bug。
- .app 体积较大（含 Python 运行时 + Qt + ffmpeg），约 500MB 解包体积，属预期。
- macOS 上不安装 pyvips / pyexiftool，程序自动回退 Pillow + exifread；如需加速可 `brew install vips` 后 `pip install pyvips`。
- 若需要把 macOS 修复推回仓库，Mac 端需要一次 GitHub 认证（gh auth login 或新的 PAT）；不要提交任何凭据。

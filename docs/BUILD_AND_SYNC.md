# 构建与跨平台同步（Windows / macOS）

> 从 V13 起，仓库改为**单一源码目录**：所有代码只在 src/phototools/ 内修改，Windows 与 macOS 共用同一份源码与版本号。
> 旧的 photo_tools_v1 … v13 目录已冻结，仅作历史留存，不再参与构建。

## 目录约定

| 路径 | 用途 |
|------|------|
| src/phototools/ | 唯一源码目录（包名固定为 phototools） |
| src/phototools/_version.py | 版本号唯一来源，Windows / macOS / 关于页共用 |
| src/phototools/platform/ | 平台适配层：路径、shell、子进程、ffmpeg、安装卸载 |
| packaging/ | PyInstaller 打包配置（win / mac 各一份） |
| scripts/ | 构建脚本：build_windows.py、build_macos.sh、make_dmg.sh |
| dist/ | 打包产物（已在 .gitignore 中忽略） |

## Windows：日常开发与打包

1. 一次性准备（开发机）：

       python -m venv .venv
       .venv\Scripts\pip install -r requirements.txt

   可选增强（pyvips / pyexiftool / customtkinter）：

       .venv\Scripts\pip install -r requirements-optional.txt

2. 开发运行：

       python run.py          # 或直接双击 run.bat

3. 打包：

       python scripts/build_windows.py

   产物：dist/PhotoTools.exe

## macOS（Apple Silicon）：一次性准备

1. 安装 Python 3.12（python.org 官方安装包即可，**不需要** Homebrew）。
2. 在仓库根目录创建虚拟环境并安装依赖：

       python3 -m venv .venv
       .venv/bin/pip install -r requirements.txt

   requirements-optional.txt 里的 pyvips/pyexiftool 在 macOS 默认不装，程序会自动回退 Pillow + exifread。
3. 若开发机是 macOS 13，改用旧版本约束：

       .venv/bin/pip install "numpy<2.2" "scipy<1.15" "onnxruntime<1.21"

## macOS：每次版本升级的同步流程

在 Mac 上执行两条命令即可：

    cd <仓库目录>
    git pull
    ./scripts/build_macos.sh

产物：

- dist/PhotoTools.app —— 自包含：内置 Python 运行时、PySide6、模型、LUT、ffmpeg
- dist/PhotoTools-<版本号>-arm64.dmg —— 拖进“应用程序”即可安装

只构建 .app 不打包 DMG：

    ./scripts/build_macos.sh --no-dmg

## 未签名应用的首次打开

当前版本**未做 Apple 签名与公证**（没有开发者账号），首次打开会被 Gatekeeper 拦截，二选一：

1. 在“应用程序”里右键点击 PhotoTools → 选择“打开” → 再次确认“打开”。
2. 或在终端执行一次：

       xattr -dr com.apple.quarantine /Applications/PhotoTools.app

后续若购买 Apple Developer 账号，只需在 scripts/build_macos.sh 里把 ad-hoc 签名替换为 Developer ID 签名 + notarytool 公证，流程不变。

## 卸载（macOS）

设置 → 卸载：把 /Applications/PhotoTools.app 移入废纸篓，并删除 ~/Library/Application Support/PhotoTools（配置、缓存、日志、自定义预设）。
**不会删除**你生成的图片、视频、代理与导出文件。

手动卸载等价操作：把 PhotoTools.app 拖到废纸篓，并删除上述 Application Support 目录。

## 版本号与发布约定

- 只修改 src/phototools/_version.py 一处；Windows exe、macOS 的 Info.plist、关于页版本自动一致。
- 跨平台发版打同一个 git tag，例如 v13.0.0。
- 平台差异只允许出现在 src/phototools/platform/ 与 packaging/；不要新建平台分支。

## macOS 首版功能范围

- 已支持：单一文件类型筛选、照片质量评估、AI 图像增强、作品展示、设置、关于。
- 后续版本支持：视频代理、音频提取、一键生成延时视频、动态照片提取、RAW/PNG 转 JPG（macOS 构建中这些入口会自动隐藏）。

## 常见问题

- **找不到 ffmpeg**：程序优先使用 imageio-ffmpeg 自带的静态 ffmpeg；如果被误删，重装 imageio-ffmpeg 即可，无需系统安装。
- **缩略图很慢**：未装 pyvips 时会回退 Pillow，功能正常、只是速度略慢。
- **打包体积大**：.app 内含 Python 运行时与 Qt，解包体积约 500MB；这是“用户机器零依赖”的代价。

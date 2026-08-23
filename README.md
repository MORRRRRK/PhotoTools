# 摄影素材管理工具箱 (PhotoTools V9.2)

一站式处理相机与手机素材：清理残留 RAW/PNG、评估照片/视频质量、为高规格视频生成低码率代理、生成延时摄影，并新增手机动态照片（Live Photo）提取。

## 功能

### 1. 单一文件类型筛选

- 支持批量添加扫描文件夹，分文件夹单独扫描并汇总
- 自动找出同名 JPG 已删除的 RAW/PNG/TIFF 残留文件
- 列表支持多列显示、列宽拖动、路径点击跳转与预览
- 批量移入回收站，不直接删除，降低误删风险

### 2. 照片质量评估

- 从构图、曝光、清晰度、色彩、噪点五个维度评分
- 严格/普通/宽松评分尺度，右侧显示评分细则
- 支持照片批量评估和视频逐帧采样评估
- 评估历史记忆，可查看测试时间、文件名、格式与建议

### 3. 视频代理生成

- 为 4K/6K/8K 高码率视频批量生成 1080p/2.7K/4K 代理
- 支持 60/30/24fps，预估输出大小，后台队列，取消/重试
- 代理文件存放在原片旁 `_proxies/`，原片不改动
- 支持一键删除代理文件，软件内预览自动优先使用代理

### 4. 一键生成延时视频

- JPG 序列按文件名自然排序生成 H.264 MP4
- 1080P/2K/4K、24/25/30/60fps、CRF 质量档位
- EXIF 方向自动摆正，LANCZOS 缩放，支持 vidstab 增稳
- 实时进度、剩余时间、停止生成与输出校验

### 5. 动态照片提取（V6 新增）

- 批量导入手机动态照片文件夹（JPG + MP4）
- 一键把 JPG 照片提取到动态图文件夹的上一级
- 所有 MP4 统一提取到“动态视频存储”文件夹，不存在时自动创建
- 支持勾选/全选、移动（剪切）或复制、自定义视频存储目录
- 同名文件自动跳过，避免覆盖
- 可选删除已清空的原始动态图文件夹，删除前自动校验全部 JPG/MP4 已正确生成
- V6.2：默认剪切并默认删除已清空的原始文件夹，删除前逐项确认文件夹为空
- V6.2：文件夹列表改用轻量多选列表，3000 级文件夹导入不再卡顿
- V6.3：重复执行时自动比对文件名，目标已有同名且大小一致的文件即清理源文件并删除原始文件夹
- V6.4：回收站批量清理改为无窗口后台执行，不再弹出 PowerShell 终端
- V7.0：新增“音频提取”，从视频中提取完整音轨为 48kHz/24bit 无损 WAV
- V8.0：全新首页，功能以圆角卡片集中展示，悬停放大并显示说明，左上角可返回首页
- V9.0：新增“作品展示”，本地照片缩略图、大图预览与 EXIF 拍摄参数展示
- V9.0：设置页新增一键安装/一键卸载，注册系统卸载信息，卸载时自动清理本机缓存
- V9.1：独立安装器 PhotoToolsSetup.exe（自定义安装路径）与独立卸载器 PhotoToolsUninstall.exe（保留/删除缓存），缓存改存安装目录
- V9.2：新增“RAW/PNG 转 JPG”，支持主流相机 RAW、PNG、TIFF 批量转换并显示生成位置

### 6. 设置

- 字号（小/中/大/特大）、外观模式、PushPlus Token、并行扫描数
- 代理输出目录、动态视频存储目录
- 更新日志栏

## 运行

```bash
pip install -r photo_tools_v9_2/requirements.txt
python run.py
```

或直接双击 `run.bat`。

## 打包为 exe

```bash
python photo_tools_v9_2/build_installer.py
# 输出: photo_tools_v9_2/dist/PhotoToolsSetup.exe / PhotoTools.exe / PhotoToolsUninstall.exe
```

## 项目结构

```
photo_tools_v9_2/
├── __init__.py           # 包信息
├── main.py               # GUI 主界面
├── installer.py          # 安装状态识别与安装/卸载器定位
├── installer_gui.py      # 独立安装器入口（PhotoToolsSetup.exe）
├── uninstaller.py        # 独立卸载器入口（PhotoToolsUninstall.exe）
├── build_installer.py    # 一键构建 安装器/主程序/卸载器
├── convert.py            # RAW/PNG 快速转 JPG 引擎
├── convert_ui.py         # RAW/PNG 转 JPG 界面
├── scanner.py            # 单一文件类型筛选（并行）
├── quality.py            # 照片/视频质量评估引擎
├── proxy.py              # 视频代理生成引擎
├── proxy_ui.py           # 视频代理界面
├── timelapse.py          # 延时视频生成引擎
├── timelapse_ui.py       # 延时视频界面
├── dynamic_extract.py    # 动态照片提取引擎
├── dynamic_extract_ui.py # 动态照片提取界面
├── pushplus_client.py    # PushPlus 推送客户端
├── utils.py              # 工具函数
├── config.json           # 用户配置
├── requirements.txt      # 依赖
├── assets/ffmpeg.exe     # 内置 ffmpeg
└── build.py              # PyInstaller 打包脚本
```

## 技术栈

Python 3.12+ | CustomTkinter | OpenCV | numpy | Pillow | rawpy | exifread | ffmpeg | PyInstaller

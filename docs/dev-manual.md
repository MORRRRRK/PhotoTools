# PhotoTools V5.1 — 开发手册

## 项目结构

```
photo_tools_v5_1/
├── __init__.py           # 包信息
├── main.py               # GUI 入口
├── scanner.py            # 非双格式扫描器
├── quality.py            # 照片/视频质量评估引擎
├── proxy.py              # 视频代理生成引擎
├── proxy_ui.py           # 视频代理界面
├── timelapse.py          # 延时视频生成引擎
├── timelapse_ui.py       # 延时视频界面
├── pushplus_client.py    # PushPlus 推送客户端
├── utils.py              # 工具函数
├── config.json           # 用户配置
├── requirements.txt      # 依赖
├── assets/ffmpeg.exe     # 内置 ffmpeg
└── build.py              # PyInstaller 打包脚本
```

## 模块说明

### proxy.py
- `find_ffmpeg()` — 定位内置 ffmpeg
- `get_proxy_path()` — 按分辨率/帧率生成代理路径
- `get_proxy_output_dir()` — 获取代理输出目录，支持自定义路径
- `estimate_proxy_size()` — 预估代理文件大小
- `build_ffmpeg_cmd()` — 构造 ffmpeg 命令
- `generate_proxy_one()` / `generate_proxy_batch()` — 单文件/队列生成
- `find_proxy()` — 预览时查找可用代理
- `delete_proxies()` — 移入回收站并清理映射
- `proxy_map.json` — 记录原片与代理文件映射

### proxy_ui.py
- 视频文件/文件夹添加
- 分辨率、帧率、并行数选择
- 列表状态、预估大小、生成进度
- 取消、重试失败、删除代理

### main.py
- CustomTkinter 四 Tab 布局
- `_to_proxy_from_quality()` — 质量评估页视频可转入代理页
- 视频预览自动优先使用代理文件

## 打包

```bash
pip install pyinstaller
python photo_tools_v5_1/build.py
```

输出：`photo_tools_v5_1/dist/PhotoTools.exe`

打包会包含 `assets/ffmpeg.exe`、`tcl/`、`customtkinter`、`PIL`、OpenCV 和 rawpy，exe 运行时不依赖额外安装 ffmpeg。

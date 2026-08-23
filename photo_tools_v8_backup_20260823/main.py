"""main.py - PhotoTools V2.3 GUI 主界面"""

import os, sys, json, threading, tkinter as tk
import tkinter.font as tkfont
FONT_SCALE = 1.0
def SF(size, *a):
    s = max(1, int(size * FONT_SCALE))
    if a: return ("", s, *a)
    return ("", s)
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import List, Optional
from datetime import datetime

if getattr(sys, "frozen", False):
    _meipass = getattr(sys, "_MEIPASS", "")
    if _meipass:
        os.environ.setdefault("TCL_LIBRARY", os.path.join(_meipass, "tcl", "tcl8.6"))
        os.environ.setdefault("TK_LIBRARY", os.path.join(_meipass, "tcl", "tk8.6"))

import customtkinter as ctk

from .scanner import scan_folders_parallel, delete_orphans, ScanProgress
from .quality import (
    evaluate_photo, evaluate_photos_batch, evaluate_video, PhotoScore,
    SCORING_SCALES, SCORING_SCALE_NAMES, scale_params,
)
from .pushplus_client import PushPlusClient
from .utils import format_size, open_file_in_explorer, format_datetime
from .proxy import VIDEO_EXTENSIONS, find_proxy
from .proxy_ui import ProxyTab
from .audio_extract_ui import AudioExtractTab
from .timelapse_ui import TimelapseTab
from .dynamic_extract_ui import DynamicExtractTab

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")
CONFIG_FILE = Path(__file__).parent / "config.json"
HISTORY_FILE = Path(__file__).parent / "eval_history.json"

# ===== 配置管理 =====
def load_config() -> dict:
    cfg = {"pushplus_token": "",
           "max_workers": 4,
           "font_scale": 1.0,
           "appearance": "system",
           "proxy_max_workers": 1,
           "proxy_resolution": "1080p",
           "proxy_fps": "60",
           "proxy_crf": 23,
           "proxy_preset": "veryfast",
           "proxy_lut": "",
           "proxy_output_dir": "",
           "dynamic_video_dir": "",
           "audio_output_dir": "",
           "accent_color": "blue"}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ===== 历史记录 =====
class HistoryManager:
    def __init__(self):
        self.records = []
        self._load()

    def _load(self):
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def _save(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    def add_result(self, score: PhotoScore, scale: str):
        self.records.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scale": SCORING_SCALE_NAMES.get(scale, scale),
            "filename": score.filename,
            "ext": os.path.splitext(score.filename)[1] or "N/A",
            "format": f"{score.width}x{score.height}",
            "total_score": round(score.total_score, 1),
            "composition": round(score.composition, 1),
            "exposure": round(score.exposure, 1),
            "sharpness": round(score.sharpness, 1),
            "color_score": round(score.color_score, 1),
            "noise_score": round(score.noise_score, 1),
            "recommendation": score.recommendation,
        })
        self._save()

    def add_batch(self, scores: List[PhotoScore], scale: str):
        for s in scores:
            self.add_result(s, scale)


# ===== 评分细则卡片 =====
SCORING_CRITERIA = """┌─ 评分尺度说明 ──────────────────────────────────────┐

 构图（权重 25%）         曝光（权重 25%）
 • 基础分 50               • 平均亮度偏离 128 越小越好
 • 三分线边缘加分           • 暗部/高光剪切越少越好
 • 对称性好加分             • 对比度适中加分
 • 太空/太杂乱扣分

 清晰度（权重 20%）       色彩（权重 15%）
 • Laplacian 方差检测       • 基于饱和度分布
 • 值越高越锐利             • 过淡/过艳都扣分
 • 可检测对焦/抖动模糊      • 中间范围最佳

 噪点（权重 15%）
 • 平滑区域方差采样

 • 方差越低越干净
 视频评分说明：逐帧采样分析，每 2 秒评估一帧，取全部帧平均值
 └──────────────────────────────────────────────────┘"""

def build_scale_detail(scale_key: str) -> str:
    sp = scale_params(scale_key)
    name = SCORING_SCALE_NAMES.get(scale_key, scale_key)
    lines = [f"┌─ [{name}] 评分阈值 ──────────────────────┐",
             f" 清晰度得分线:  Laplacian > {sp['sharpness_divisor']:.0f} → 100分",
             f" 曝光容忍度:    ±{sp['exposure_tolerance']} 偏离理想值",
             f" 暗部扣分线:    > {sp['shadow_penalty_at']}% 开始扣分",
             f" 高光扣分线:    > {sp['highlight_penalty_at']}% 开始扣分",
             f" 色彩低限:      {sp['color_low']} 以下→低分",
             f" 色彩高限:      {sp['color_high']} 以上→扣分",
             f" 噪点得分线:    方差 {sp['noise_divisor']:.0f} → 0分",
             "└────────────────────────────────────┘"]
    return "\n".join(lines)


# ===== 更新日志 =====
UPDATE_LOG = """V8.0（2026-08-16）
- 全新首页：所有功能以圆角卡片形式集中展示，点击卡片进入对应功能
- 左上角新增“返回首页”，取消顶部 Tab 切换栏
- 鼠标悬停功能卡片时高亮放大文字并显示该功能的具体说明，不再抖动
- 设置页新增主题颜色：蓝色 / 深蓝 / 金色 / 绿色，保存后自动刷新界面

V7.0（2026-08-16）
- 新增“音频提取”：从 MP4/MKV/MOV 等视频中提取完整音轨
- 输出 48kHz / 24bit 无损 WAV（pcm_s24le），兼容达芬奇、剪映、PR
- 支持批量添加、文件夹扫描、全选、停止、已存在跳过、无音轨提示
- 默认输出到原视频旁 _audio 文件夹，可在设置页配置音频输出目录

V6.4（2026-08-15）
- 修复执行导出时反复弹出 PowerShell 终端窗口的问题
- 所有回收站操作改为无窗口后台执行，不影响其他操作

V6.3（2026-08-15）
- 修复重复执行时原始文件夹仍未删除的问题：重新执行时自动对比原始文件名与已导出的 JPG/MP4 文件名
- 若目标位置已存在同名且大小一致的文件，视为已导出，自动清理源文件并删除已清空的原始文件夹
- 同名但大小不一致时保留源文件并提示人工确认，避免误删

V6.2（2026-08-15）
- 动态照片提取流程调整为：导入动态图文件夹 → 导出 JPG 到上一级、MP4 到“动态视频存储” → 确认原始文件夹已完全清空后自动删除空文件夹
- 修复原始文件夹未删除的问题：默认剪切文件并默认删除空文件夹，删除前逐项校验全部 JPG/MP4 已正确生成且文件夹为空
- 文件夹列表改用轻量多选列表，大幅提升三千级文件夹导入时的响应速度，不再卡死未响应
- 导出按钮更名为“开始导出”，流程更清晰

V6.1（2026-08-15）
- 动态照片提取：新增“提取后删除原始动态图文件夹”选项，删除时移入回收站，失败即停止并提示
- 删除原始文件夹前会自动校验全部 JPG/MP4 是否已正确生成且大小一致，校验失败不删除并停止
- 添加文件夹逻辑修正：直接选择内含 JPG 和 MP4 的动态图文件夹即可导入，也支持自动识别其子目录
- 文件夹列表改为多列展示，完整显示文件夹名称、文件列表和完整路径
- 修复设置页文字大小（小/中/大/特大）无法生效的问题，选择后立即应用并随设置保存

V6.0（2026-08-15）
- 新增“动态照片提取”：批量导入手机动态照片文件夹（JPG + MP4）
- 一键把 JPG 照片提取到动态图文件夹的上一级
- 一键把所有 MP4 视频提取到“动态视频存储”文件夹，不存在时自动创建
- 支持批量添加、单个添加、勾选、全选/全不选、移除选中
- 支持移动（剪切）或复制模式，目标文件已存在时自动跳过避免覆盖
- 支持自定义视频存储目录并自动保存，新增“打开目录”入口
- 设置页新增“更新日志”栏

V5.1
- 优化延时摄影画质：PNG 无损中间帧、CRF 14/12/10 高质量档位、慢速预设
- 增稳流程优化：tripod 模式 + 自动 deflicker，输出校验

V5.0
- 新增“一键生成延时视频”：JPG 序列按自然排序生成 H.264 MP4
- 支持 1080P/2K/4K、24/25/30/60fps、质量档位与 vidstab 增稳
- 实时进度、剩余时间、取消与临时文件清理

V4.0
- 新增“视频代理”：为 4K/6K/8K 高码率视频批量生成 1080P/2.7K/4K 代理
- 支持帧率组合、预估大小、后台队列、取消重试、代理删除
- 原片不改动，软件内预览自动优先使用代理

V3.0
- 新增照片/视频质量评估、历史记忆、设置页字号与外观
- 单一文件类型筛选增加右侧预览、结果行高亮

V2.0
- 单一文件类型筛选：批量添加、分文件夹扫描汇总、列宽可调、路径可点击
- 照片质量评估：严格/普通/宽松评分尺度、评分细则说明、记忆功能

V1.0
- 初始版本：JPG 缺失后清理残留 RAW/PNG、照片质量评估、PushPlus 推送
"""


# ===== 历史记录对话框 =====
class HistoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, records: list):
        super().__init__(parent)
        self.title("评估历史记录")
        self.geometry("800x500")
        self.minsize(600, 300)

        if not records:
            ctk.CTkLabel(self, text="暂无历史记录", font=("", 16)).pack(expand=True)
            return

        # 搜索框
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(top, text="搜索:", font=("", 12)).pack(side="left", padx=5)
        search_entry = ctk.CTkEntry(top, width=200, placeholder_text="文件名...")
        search_entry.pack(side="left", padx=5)

        # 表头
        cols = ["时间", "文件名", "格式", "综合", "构图", "曝光", "清晰度", "色彩", "噪点", "建议", "尺度"]
        widths = [140, 200, 80, 60, 55, 55, 55, 55, 55, 160, 50]
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=10)
        for col, w in zip(cols, widths):
            ctk.CTkLabel(hdr, text=col, font=("", 11, "bold"), width=w).pack(side="left")

        # 列表
        frame = ctk.CTkScrollableFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.row_widgets = []

        def populate(filter_text=""):
            for w in self.row_widgets:
                w.destroy()
            self.row_widgets.clear()
            for r in reversed(records):
                if filter_text and filter_text not in r.get("filename", ""):
                    continue
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", pady=1)
                vals = [
                    r.get("timestamp", "")[-16:],
                    r.get("filename", ""),
                    r.get("format", ""),
                    str(r.get("total_score", "")),
                    str(r.get("composition", "")),
                    str(r.get("exposure", "")),
                    str(r.get("sharpness", "")),
                    str(r.get("color_score", "")),
                    str(r.get("noise_score", "")),
                    r.get("recommendation", "")[:18],
                    r.get("scale", ""),
                ]
                for v, w in zip(vals, widths):
                    ctk.CTkLabel(row, text=v, width=w, anchor="w").pack(side="left")
                self.row_widgets.append(row)

        populate()
        search_entry.configure(command=lambda: populate(search_entry.get()))


# ===== 文件夹列表组件（V5.1 批量添加） =====
class FolderListFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.folders: List[str] = []

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=5, pady=(5, 2))
        ctk.CTkLabel(hdr, text="扫描文件夹列表", font=("", 13, "bold")).pack(side="left")
        self.cnt_lb = ctk.CTkLabel(hdr, text="0 个文件夹", font=("", 11))
        self.cnt_lb.pack(side="right", padx=5)

        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.pack(fill="x", padx=5, pady=2)
        ctk.CTkButton(btn, text="+ 添加文件夹", width=130, command=self.add_folder).pack(side="left", padx=2)
        ctk.CTkButton(btn, text="+ 批量添加", width=130, command=self.add_batch).pack(side="left", padx=2)
        self.del_btn = ctk.CTkButton(btn, text="− 移除选中", width=130,
                                       command=self.remove_selected, state="disabled")
        self.del_btn.pack(side="left", padx=2)

        self.box = tk.Listbox(self, selectmode=tk.EXTENDED, bg="#2b2b2b",
                               fg="#e0e0e0", selectbackground="#1f538d",
                               height=6, font=("Microsoft YaHei", 10))
        self.box.pack(fill="both", expand=True, padx=5, pady=5)
        self.box.bind("<<ListboxSelect>>", lambda e: self._update_btn())

    def add_folder(self):
        f = filedialog.askdirectory(title="选择素材文件夹")
        if f and f not in self.folders:
            self.folders.append(f)
            self.box.insert(tk.END, f)
            self.cnt_lb.configure(text=f"{len(self.folders)} 个文件夹")

    def add_batch(self):
        """批量添加：可多选文件夹。"""
        folder = filedialog.askdirectory(title="选择包含子文件夹的根目录，或直接点取消")
        if not folder:
            return
        # 先添加根目录本身
        if folder not in self.folders:
            self.folders.append(folder)
            self.box.insert(tk.END, folder)
        # 再添加子文件夹
        try:
            subs = sorted([os.path.join(folder, d) for d in os.listdir(folder)
                          if os.path.isdir(os.path.join(folder, d))])
            for s in subs:
                if s not in self.folders:
                    self.folders.append(s)
                    self.box.insert(tk.END, s)
        except Exception:
            pass
        self.cnt_lb.configure(text=f"{len(self.folders)} 个文件夹")

    def remove_selected(self):
        sel = self.box.curselection()
        for i in reversed(sel):
            self.folders.pop(i)
            self.box.delete(i)
        self.cnt_lb.configure(text=f"{len(self.folders)} 个文件夹")
        self._update_btn()

    def _update_btn(self):
        self.del_btn.configure(state="normal" if self.box.curselection() else "disabled")

    def get_folders(self):
        return list(self.folders)


# ===== 孤儿文件结果列表（V5.1 支持打开文件） =====
class OrphanResultFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.orphan_items = []
        self.check_vars = []
        self.row_frames = []
        self.sel_all_var = tk.BooleanVar(value=False)
        self._parent = master

        hdr = ctk.CTkFrame(self, fg_color="transparent", height=30)
        hdr.pack(fill="x", padx=5, pady=2)
        ctk.CTkCheckBox(hdr, text="全选", variable=self.sel_all_var,
                         command=self._toggle_all, width=55).pack(side="left", padx=5)
        for col, w in [("文件路径", 300), ("类型", 50), ("大小", 70), ("来源文件夹", 200)]:
            ctk.CTkLabel(hdr, text=col, font=("", 11, "bold"), width=w).pack(side="left", padx=2)
        self.info_lb = ctk.CTkLabel(self, text="", font=("", 11))
        self.info_lb.pack(anchor="w", padx=10, pady=(0, 5))

    def clear(self):
        for f in self.row_frames:
            f.destroy()
        self.orphan_items.clear()
        self.check_vars.clear()
        self.row_frames.clear()
        self.info_lb.configure(text="")

    def populate(self, results):
        self.clear()
        total_c, total_sz = 0, 0
        folder_of = {}
        for r in results:
            if not r.success:
                continue
            for o in r.orphans:
                self.orphan_items.append(o)
                folder_of[id(o)] = r.folder
            total_c += len(r.orphans)
            total_sz += r.total_size_bytes

        self.info_lb.configure(text=f"发现 {total_c} 个孤儿文件，总计 {format_size(total_sz)}")

        for i, o in enumerate(self.orphan_items):
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=1)

            ctk.CTkCheckBox(row, text="", variable=var, width=35).pack(side="left", padx=(5, 0))

            # 文件名可点击打开
            fname_lb = ctk.CTkLabel(row, text=os.path.basename(o["path"]),
                                     anchor="w", width=300,
                                     text_color="#4a9eff", cursor="hand2")
            fname_lb.pack(side="left", padx=2)
            fname_lb.bind("<Button-1>", lambda e, p=o["path"]: open_file_in_explorer(p))

            ctk.CTkLabel(row, text=o["ext"], width=50).pack(side="left")
            ctk.CTkLabel(row, text=format_size(o["size_bytes"]), width=70).pack(side="left")
            ctk.CTkLabel(row, text=folder_of.get(id(o), ""), anchor="w",
                          width=200).pack(side="left")

            self.row_frames.append(row)

    def get_selected(self):
        return [it for it, v in zip(self.orphan_items, self.check_vars) if v.get()]

    def get_all(self):
        return list(self.orphan_items)

    def _toggle_all(self):
        v = self.sel_all_var.get()
        for var in self.check_vars:
            var.set(v)


# ===== 评分卡片 + 右侧细则面板 =====
class ScoreViewFrame(ctk.CTkFrame):
    def __init__(self,master,**kwargs):
        super().__init__(master,**kwargs)
        self.grid_columnconfigure(0,weight=3)
        self.grid_columnconfigure(1,weight=1)
        self.grid_rowconfigure(0,weight=1)
        self.scroll=ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        self.detail_frame=ctk.CTkFrame(self,width=520)
        self.detail_frame.grid(row=0,column=1,sticky="nsew")
        self.detail_frame.grid_columnconfigure(0,weight=1)
        self.detail_frame.grid_rowconfigure(0,weight=1)
        self.detail_frame.grid_rowconfigure(1,weight=3)
        tf=ctk.CTkFrame(self.detail_frame)
        tf.grid(row=0,column=0,sticky="nsew",pady=(0,4))
        tf.grid_columnconfigure(0,weight=1);tf.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(tf,text="细则",font=SF(13,"bold")).grid(row=0,column=0,pady=(6,2))
        self.detail_text=ctk.CTkTextbox(tf,font=("Consolas",12),wrap="word")
        self.detail_text.grid(row=1,column=0,sticky="nsew",padx=5,pady=(0,5))
        self.detail_text.insert("0.0",SCORING_CRITERIA)
        self.detail_text.configure(state="disabled")
        self.preview_frame=ctk.CTkFrame(self.detail_frame)
        self.preview_frame.grid(row=1,column=0,sticky="nsew")
        self.preview_frame.grid_columnconfigure(0,weight=1)
        self.preview_frame.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(self.preview_frame,text="预览",font=SF(13,"bold")).grid(row=0,column=0,pady=(6,4))
        self.preview_label=ctk.CTkLabel(self.preview_frame,text="点击左侧结果查看预览",font=SF(12))
        self.preview_label.grid(row=1,column=0,sticky="nsew",padx=5,pady=(0,2))
        self.preview_info=ctk.CTkLabel(self.preview_frame,text="",font=SF(10))
        self.preview_info.grid(row=2,column=0,pady=(0,4))
        self.cards=[]
    def set_scale_detail(self,k):
        d=build_scale_detail(k)
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0","end")
        self.detail_text.insert("0.0",SCORING_CRITERIA+"\n\n"+d)
        self.detail_text.configure(state="disabled")
    def clear(self):
        for w in self.cards: w.destroy()
        self.cards.clear()
        self.preview_label.configure(image="",text="点击左侧结果查看预览")
        self.preview_label.image=None;self.preview_info.configure(text="")
    def _fmt_dur(self,s):
        h=int(s//3600);m=int((s%3600)//60);se=int(s%60)
        return f"{h}:{m:02d}:{se:02d}" if h else f"{m}:{se:02d}"
    def _fmt_br(self,bps):
        return f"{bps//1000}kbps" if bps>=1000 else f"{bps}bps"
    def _get_info(self,fp):
        ve={".mp4",".mov",".avi",".mkv"}
        ext=os.path.splitext(fp)[1].lower()
        inf={"type":"照片","w":"-","h":"-","fps":"-","dur":"-","br":"-","sz":"-","path":fp}
        try:inf["sz"]=format_size(os.path.getsize(fp))
        except:pass
        if ext in ve:
            inf["type"]="视频"
            try:
                import cv2
                c=cv2.VideoCapture(fp)
                inf["w"]=str(int(c.get(cv2.CAP_PROP_FRAME_WIDTH)))
                inf["h"]=str(int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                fps=c.get(cv2.CAP_PROP_FPS)
                inf["fps"]=f"{fps:.2f}" if fps>0 else "-"
                fc=int(c.get(cv2.CAP_PROP_FRAME_COUNT))
                if fps>0 and fc>0:
                    dur=fc/fps;inf["dur"]=self._fmt_dur(dur)
                    try:inf["br"]=self._fmt_br(int(os.path.getsize(fp)*8/dur))
                    except:pass
                c.release()
            except:pass
        else:
            try:
                from PIL import Image as PI
                im=PI.open(fp);inf["w"]=str(im.width);inf["h"]=str(im.height)
            except:pass
        return inf
    def add_scores(self,scores,scale="normal"):
        self.clear();self.set_scale_detail(scale)
        for s in scores:
            inf=self._get_info(s.file)
            card=ctk.CTkFrame(self.scroll,corner_radius=6)
            card.pack(fill="x",padx=10,pady=6)
            card.filepath=s.file
            # 悬停效果
            card.bind("<Enter>",lambda e,cd=card:cd.configure(border_width=2,border_color="#4a9eff"))
            card.bind("<Leave>",lambda e,cd=card:cd.configure(border_width=0))
            tr=ctk.CTkFrame(card,fg_color="transparent")
            tr.pack(fill="x",padx=8,pady=(6,2))
            fnl=ctk.CTkLabel(tr,text=os.path.basename(s.file)[:50],font=SF(16,"bold"),anchor="w")
            fnl.pack(side="left",fill="x",expand=True)
            fnl.bind("<Button-1>",lambda e,fp=s.file:self._show_preview(fp))
            ctk.CTkButton(tr,text="预览",width=46,height=26,font=SF(11),
                command=lambda fp=s.file:self._show_preview(fp)).pack(side="right",padx=(2,0))
            ctk.CTkButton(tr,text="X",width=26,height=26,fg_color="#c0392b",hover_color="#96281b",font=SF(11,"bold"),
                command=lambda p=s.file,cd=card:self._delete_file(p,cd)).pack(side="right",padx=(2,0))
            ai=ctk.CTkFrame(card,fg_color="transparent")
            ai.pack(fill="x",padx=12,pady=2)
            parts=[]
            if inf["type"]=="视频":
                if inf["dur"]!="-":parts.append(inf["dur"])
                if inf["w"]!="-":parts.append(f"{inf["w"]}x{inf["h"]}")
                if inf["fps"]!="-":parts.append(f"{inf["fps"]}fps")
                if inf["br"]!="-":parts.append(inf["br"])
            else:
                if inf["w"]!="-":parts.append(f"{inf["w"]}x{inf["h"]}")
            if inf["sz"]!="-":parts.append(inf["sz"])
            ctk.CTkLabel(ai,text=" | ".join(parts),font=SF(13)).pack(anchor="w")
            ctk.CTkLabel(ai,text=inf["path"],font=SF(11),anchor="w").pack(anchor="w")
            sc=ctk.CTkFrame(card,fg_color="transparent")
            sc.pack(fill="x",padx=12,pady=3)
            clr="#2ecc71" if s.total_score>=70 else("#f39c12" if s.total_score>=40 else"#e74c3c")
            ctk.CTkLabel(sc,text=f"{s.total_score:.0f}",font=SF(18,"bold"),text_color=clr,width=40).pack(side="left")
            for lbl,val in[("构图",s.composition),("曝光",s.exposure),("清晰度",s.sharpness),("色彩",s.color_score),("噪点",s.noise_score)]:
                ctk.CTkLabel(sc,text=f"{lbl}{val:.0f}",font=SF(13),width=56).pack(side="left")
            if s.recommendation:
                rc="#2ecc71" if "优秀"in s.recommendation or "良好"in s.recommendation else"#f39c12"
                ctk.CTkLabel(card,text=s.recommendation[:25],font=SF(13),text_color=rc,anchor="w").pack(anchor="w",padx=12,pady=(0,4))
            self.cards.append(card)
    def _find_jpg(self,fp):
        b=os.path.splitext(fp)[0]
        for e in[".jpg",".jpeg"]:
            p=b+e
            if os.path.exists(p):return p
        return None
    def _show_preview(self,fp):
        # 标记当前卡片（加黄边框）
        for cd in self.cards:
            if hasattr(cd,"filepath") and cd.filepath==fp:
                cd.configure(border_width=2,border_color="#FFD700")
            else:
                cd.configure(border_width=0)
        ve={".mp4",".mov",".avi",".mkv"}
        ext=os.path.splitext(fp)[1].lower()
        if ext in ve:
            try:
                proxy = find_proxy(fp)
                play = proxy or fp
                os.startfile(play)
                tag = " (代理)" if proxy else ""
                self.preview_info.configure(text="已打开默认播放器: "+os.path.basename(play)+tag)
            except Exception as e:
                self.preview_info.configure(text=f"无法打开: {e}")
        else:
            self._show_image(fp)
    def _show_image(self,fp):
        from PIL import Image,ImageTk
        jpg=self._find_jpg(fp)or fp
        try:
            img=Image.open(jpg)
            from PIL import ImageOps
            try:img=ImageOps.exif_transpose(img)
            except:pass
            pw=max(self.preview_frame.winfo_width()-20,200)
            ph=max(self.preview_frame.winfo_height()-60,100)
            img.thumbnail((pw,ph),Image.LANCZOS)
            photo=ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo,text="")
            self.preview_label.image=photo
            self.preview_info.configure(text=os.path.basename(jpg)+f" {img.width}x{img.height}")
            return
        except:pass
        self.preview_label.configure(image="",text="无法预览")
        self.preview_label.image=None;self.preview_info.configure(text="")
    def _delete_file(self,fp,card):
        from tkinter import messagebox
        from .utils import send_to_trash
        if messagebox.askyesno("确认","移入回收站？\n"+os.path.basename(fp)):
            send_to_trash(fp);card.destroy();self.cards.remove(card)
class PhotoToolsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PhotoTools V8.0 — 摄影素材管理工具箱")
        self.geometry("1200x780")
        self.minsize(1000, 650)

        self.config = load_config()
        self.pushplus_token = self.config.get("pushplus_token", "")
        self.max_workers = self.config.get("max_workers", 4)
        self._quality_scale = "normal"
        ctk.set_appearance_mode(self.config.get("appearance", "system"))
        ctk.set_default_color_theme(self.config.get("accent_color", "blue"))
        fs = self.config.get("font_scale",1.0)
        global FONT_SCALE; FONT_SCALE = fs
        try:
            tkfont.nametofont("TkDefaultFont").configure(size=int(13*fs))
            ctk.FontManager.windows_font_size = int(13*fs)
        except: pass
        self.scan_busy = False
        self.quality_busy = False
        self._quality_files = []
        self.history = HistoryManager()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_home(self):
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 6))
        ctk.CTkLabel(header, text="PhotoTools V8.0", font=SF(26, "bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="摄影素材管理工具箱 · 功能总览", font=SF(14)).pack(anchor="w", pady=(2, 0))

        body = ctk.CTkScrollableFrame(self.home_frame)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=8)
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="homecard")

        modules = [
            ("单一文件类型筛选",
             "扫描素材文件夹，清理同名 JPG 已删除后残留的 RAW/PNG/TIFF 文件"),
            ("照片质量评估",
             "从构图、曝光、清晰度、色彩、噪点五个维度评估照片与视频质量"),
            ("视频代理",
             "为 4K/6K/8K 高码率视频批量生成 1080p/2.7K/4K 流畅预览代理"),
            ("音频提取",
             "提取视频完整音轨为 48kHz/24bit 无损 WAV，供达芬奇、剪映、PR 使用"),
            ("一键生成延时视频",
             "将 JPG 序列按自然排序生成延时摄影视频，支持增稳与多档画质"),
            ("动态照片提取",
             "提取手机动态照片中的 JPG 与 MP4，并自动清理已清空的原始文件夹"),
            ("设置",
             "字号、外观模式、输出目录、PushPlus 推送与更新日志"),
        ]
        self.home_cards = []
        for idx, (name, desc) in enumerate(modules):
            row, col = divmod(idx, 3)
            btn = ctk.CTkButton(
                body, text=name, width=230, height=110,
                font=SF(16, "bold"), corner_radius=16,
                command=lambda n=name: self.show_page(n))
            btn.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
            btn.bind("<Enter>", lambda e, n=name, d=desc, b=btn: self._home_enter(b, n, d))
            btn.bind("<Leave>", lambda e, n=name, b=btn: self._home_leave(b, n))
            self.home_cards.append((btn, name, desc))

        footer = ctk.CTkFrame(self.home_frame, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(6, 16))
        self.home_desc_lb = ctk.CTkLabel(
            footer, text="将鼠标移到功能按钮上查看说明", font=SF(13),
            text_color="#7f8c8d", anchor="w")
        self.home_desc_lb.pack(fill="x")

    def _home_enter(self, btn, name, desc):
        self.home_desc_lb.configure(
            text=f"{name}：{desc}", text_color="#e0e0e0")
        btn.configure(font=SF(17, "bold"), border_width=2)

    def _home_leave(self, btn, name):
        self.home_desc_lb.configure(
            text="将鼠标移到功能按钮上查看说明", text_color="#7f8c8d")
        btn.configure(font=SF(16, "bold"), border_width=0)

    def _rebuild_ui(self):
        try:
            self.page_container.destroy()
        except Exception:
            pass
        self._build_ui()

    def show_page(self, name):
        for frame in self.pages.values():
            frame.grid_remove()
        self.home_frame.grid_remove()
        page = self.pages.get(name)
        if not page:
            self._show_home()
            return
        page.grid()
        self.page_title_lb.configure(text=name)
        self.topbar.grid()

    def _show_home(self):
        for frame in self.pages.values():
            frame.grid_remove()
        self.home_frame.grid()
        self.topbar.grid_remove()

    def _build_ui(self):
        self.pages = {}
        self.page_container = ctk.CTkFrame(self)
        self.page_container.pack(fill="both", expand=True, padx=10, pady=10)
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(1, weight=1)

        self.topbar = ctk.CTkFrame(self.page_container, fg_color="transparent")
        self.topbar.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 4))
        self.topbar.grid_columnconfigure(1, weight=1)
        self.back_btn = ctk.CTkButton(self.topbar, text="← 返回首页", width=110, height=32,
                                      font=("", 13), command=self._show_home)
        self.back_btn.grid(row=0, column=0, sticky="w", padx=4)
        self.page_title_lb = ctk.CTkLabel(self.topbar, text="", font=("", 15, "bold"))
        self.page_title_lb.grid(row=0, column=1, sticky="w", padx=8)
        self.topbar.grid_remove()

        self.page_area = ctk.CTkFrame(self.page_container)
        self.page_area.grid(row=1, column=0, sticky="nsew")
        self.page_area.grid_columnconfigure(0, weight=1)
        self.page_area.grid_rowconfigure(0, weight=1)

        self.home_frame = ctk.CTkFrame(self.page_area)
        self.home_frame.grid(row=0, column=0, sticky="nsew")
        self.home_frame.grid_columnconfigure(0, weight=1)
        self.home_frame.grid_rowconfigure(1, weight=1)
        self._build_home()

        def make_page(name):
            frame = ctk.CTkFrame(self.page_area)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)
            self.pages[name] = frame
            return frame

        # ========== Tab 1: 单一文件类型筛选 ==========
        t1 = make_page("单一文件类型筛选")

        top = ctk.CTkFrame(t1)
        top.pack(fill="x", padx=10, pady=(10, 5))
        self.folders = FolderListFrame(top)
        self.folders.pack(fill="x", padx=5, pady=5)

        ctrl = ctk.CTkFrame(t1, fg_color="transparent")
        ctrl.pack(fill="x", padx=10, pady=5)
        self.scan_btn = ctk.CTkButton(ctrl, text="开始扫描", width=120,
                                       command=self._start_scan, height=32)
        self.scan_btn.pack(side="left", padx=5)
        self.scan_pb = ctk.CTkProgressBar(ctrl, width=350)
        self.scan_pb.pack(side="left", padx=10)
        self.scan_pb.set(0)
        self.scan_lb = ctk.CTkLabel(ctrl, text="就绪", font=("", 11))
        self.scan_lb.pack(side="left", padx=5)

        self.results = OrphanResultFrame(t1)
        self.main_area = ctk.CTkFrame(t1)
        self.main_area.pack(fill="both",expand=True,padx=10,pady=5)
        self.main_area.grid_columnconfigure(0,weight=3)
        self.main_area.grid_columnconfigure(1,weight=1)
        self.main_area.grid_rowconfigure(0,weight=1)
        self.results = OrphanResultFrame(self.main_area)
        self.results.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        self.results.preview_callback = self._t1_preview
        self.t1_pf = ctk.CTkFrame(self.main_area)
        self.t1_pf.grid(row=0,column=1,sticky="nsew")
        self.t1_pf.grid_columnconfigure(0,weight=1)
        self.t1_pf.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(self.t1_pf,text="预览",font=SF(13,"bold")).grid(row=0,column=0,pady=(6,4))
        self.t1_pl = ctk.CTkLabel(self.t1_pf,text="点击运行结果预览",font=SF(12))
        self.t1_pl.grid(row=1,column=0,sticky="nsew",padx=5)
        self.t1_pi = ctk.CTkLabel(self.t1_pf,text="",font=SF(10))
        self.t1_pi.grid(row=2,column=0)
        bot = ctk.CTkFrame(t1, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkButton(bot, text="打开选中文件预览", width=150,
                       command=self._open_selected).pack(side="left", padx=5)
        ctk.CTkButton(bot, text="删除选中 (移入回收站)", width=180,
                       command=self._do_delete, height=36,
                       fg_color="#c0392b", hover_color="#96281b").pack(side="right", padx=5)
        ctk.CTkButton(bot, text="评估选中照片质量", width=160,
                       command=self._eval_selected, height=36).pack(side="right", padx=5)

        # ========== Tab 2: 照片质量评估 ==========
        t2 = make_page("照片质量评估")

        ctrl2 = ctk.CTkFrame(t2)
        ctrl2.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(ctrl2, text="评分尺度:", font=("", 12)).pack(side="left", padx=5)
        self.scale_opt = ctk.CTkOptionMenu(ctrl2, values=["严格", "普通", "宽松"],
                                             command=self._set_scale)
        self.scale_opt.set("普通")
        self.scale_opt.pack(side="left", padx=5)
        ctk.CTkLabel(ctrl2, text="  ", font=("", 12)).pack(side="left")

        ctk.CTkButton(ctrl2, text="选择照片/视频", width=130,
                       command=self._sel_qual_files).pack(side="left", padx=3)
        ctk.CTkButton(ctrl2, text="选择文件夹批量", width=130,
                       command=self._sel_qual_folder).pack(side="left", padx=3)
        ctk.CTkButton(ctrl2, text="生成代理", width=90,
                       command=self._to_proxy_from_quality).pack(side="left", padx=3)
        self.qual_lb = ctk.CTkLabel(ctrl2, text="未选择文件", font=("", 11))
        self.qual_lb.pack(side="left", padx=10)

        self.qual_btn = ctk.CTkButton(ctrl2, text="开始评估", width=100,
                                       command=self._start_qual)
        self.qual_btn.pack(side="right", padx=5)

        self.history_btn = ctk.CTkButton(ctrl2, text="📋 记忆", width=80,
                                          command=self._show_history)
        self.history_btn.pack(side="right", padx=5)

        self.qual_pb = ctk.CTkProgressBar(t2, width=400)
        self.qual_pb.pack(fill="x", padx=10, pady=5)
        self.qual_pb.set(0)

        # 质量评估：双栏布局（评分卡片 + 细则面板）
        self.score_view = ScoreViewFrame(t2)
        self.score_view.pack(fill="both", expand=True, padx=10, pady=5)
        self.score_view.set_scale_detail("normal")

        # ========== Tab 4: 视频代理 ==========
        t4 = make_page("视频代理")
        self.proxy_tab = ProxyTab(t4, self)
        self.proxy_tab.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== Tab 5: 音频提取 ==========
        t5 = make_page("音频提取")
        self.audio_tab = AudioExtractTab(t5, self)
        self.audio_tab.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== Tab 5: 一键生成延时视频 ==========
        t5b = make_page("一键生成延时视频")
        self.timelapse_tab = TimelapseTab(t5b, self)
        self.timelapse_tab.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== Tab 6: 动态照片提取 ==========
        t6 = make_page("动态照片提取")
        self.dynamic_tab = DynamicExtractTab(t6, self)
        self.dynamic_tab.pack(fill="both", expand=True, padx=10, pady=10)

        # ========== Tab 3: 设置 ==========
        t3 = make_page("设置")
        sf = ctk.CTkFrame(t3)
        sf.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(sf, text="设置", font=("", 16, "bold")).pack(anchor="w", pady=10)

        r1 = ctk.CTkFrame(sf, fg_color="transparent")
        r1.pack(fill="x", pady=5)
        r0 = ctk.CTkFrame(sf,fg_color="transparent")
        r0.pack(fill="x",pady=5)
        ctk.CTkLabel(r0,text="字体大小:",width=120,anchor="w").pack(side="left")
        self.fm_opt = ctk.CTkOptionMenu(r0,values=["小","中","大","特大"],
            command=self._set_font_size)
        cur = self.config.get("font_scale",1.0)
        _scale_names = {1.0:"小",1.25:"中",1.5:"大",2.0:"特大"}
        self.fm_opt.set(_scale_names.get(cur, "小"))
        self.fm_opt.pack(side="left",padx=5)
        self._font_scale = cur
        ctk.CTkLabel(r1, text="PushPlus Token:", width=120, anchor="w").pack(side="left")
        self.pp_entry = ctk.CTkEntry(r1, width=350)
        self.pp_entry.insert(0, self.pushplus_token)
        self.pp_entry.pack(side="left", padx=5)

        r2 = ctk.CTkFrame(sf, fg_color="transparent")
        r2.pack(fill="x", pady=5)
        ctk.CTkLabel(r2, text="并行扫描数:", width=120, anchor="w").pack(side="left")
        self.w_spin = ctk.CTkEntry(r2, width=60)
        self.w_spin.insert(0, str(self.max_workers))
        self.w_spin.pack(side="left", padx=5)

        r3 = ctk.CTkFrame(sf, fg_color="transparent")
        r3.pack(fill="x", pady=5)
        ctk.CTkLabel(r3, text="外观模式:", width=120, anchor="w").pack(side="left")
        self.ap_opt = ctk.CTkOptionMenu(r3, values=["system", "light", "dark"],
                                          command=self._set_theme)
        self.ap_opt.set(self.config.get("appearance", "system"))
        self.ap_opt.pack(side="left", padx=5)

        r4 = ctk.CTkFrame(sf, fg_color="transparent")
        r4.pack(fill="x", pady=5)
        ctk.CTkLabel(r4, text="代理输出目录:", width=120, anchor="w").pack(side="left")
        self.proxy_dir_entry = ctk.CTkEntry(r4, width=350)
        self.proxy_dir_entry.insert(0, self.config.get("proxy_output_dir", ""))
        self.proxy_dir_entry.pack(side="left", padx=5)
        ctk.CTkButton(r4, text="浏览", width=70, command=self._browse_proxy_dir).pack(side="left", padx=5)

        r5 = ctk.CTkFrame(sf, fg_color="transparent")
        r5.pack(fill="x", pady=5)
        ctk.CTkLabel(r5, text="音频输出目录:", width=120, anchor="w").pack(side="left")
        self.audio_dir_entry = ctk.CTkEntry(r5, width=350)
        self.audio_dir_entry.insert(0, self.config.get("audio_output_dir", ""))
        self.audio_dir_entry.pack(side="left", padx=5)
        ctk.CTkButton(r5, text="浏览", width=70, command=self._browse_audio_dir).pack(side="left", padx=5)

        self.accent_map = {"蓝色": "blue", "深蓝": "dark-blue", "金色": "gold", "绿色": "green"}
        r6 = ctk.CTkFrame(sf, fg_color="transparent")
        r6.pack(fill="x", pady=5)
        ctk.CTkLabel(r6, text="主题颜色:", width=120, anchor="w").pack(side="left")
        self.accent_opt = ctk.CTkOptionMenu(r6, values=list(self.accent_map.keys()), width=120)
        cur_accent = self.config.get("accent_color", "blue")
        cur_label = next((k for k, v in self.accent_map.items() if v == cur_accent), "蓝色")
        self.accent_opt.set(cur_label)
        self.accent_opt.pack(side="left", padx=5)

        ctk.CTkButton(sf, text="保存设置", command=self._save_cfg).pack(anchor="w", pady=10)

        upd = ctk.CTkFrame(t3)
        upd.pack(fill="both", expand=True, padx=20, pady=10)
        ctk.CTkLabel(upd, text="更新日志", font=("", 14, "bold")).pack(anchor="w", pady=(5, 3))
        self.update_box = ctk.CTkTextbox(upd, height=260, font=("", 12))
        self.update_box.pack(fill="both", expand=True, padx=2, pady=(0, 5))
        self.update_box.insert("0.0", UPDATE_LOG)
        self.update_box.configure(state="disabled")

        ab = ctk.CTkFrame(t3)
        ab.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(ab, text="关于 PhotoTools V8.0", font=("", 14, "bold")).pack(anchor="w", pady=5)
        ctk.CTkLabel(ab, text="版本 8.0.0 | 摄影素材管理工具箱").pack(anchor="w")
        ctk.CTkLabel(ab, text="功能: 文件类型筛选 / 照片视频质量评估 / 视频代理生成 / 音频提取 / 一键生成延时视频 / 动态照片提取 / PushPlus 推送").pack(anchor="w")

        for frame in self.pages.values():
            frame.grid_remove()
        self._show_home()

    # ----- Tab 1: 扫描逻辑 -----
    def _start_scan(self):
        if self.scan_busy:
            return
        folders = self.folders.get_folders()
        if not folders:
            messagebox.showwarning("提示", "请先添加要扫描的文件夹")
            return
        self.scan_busy = True
        self.scan_btn.configure(text="扫描中...", state="disabled")
        self.scan_pb.set(0)
        self.results.clear()
        try:
            workers = int(self.w_spin.get())
        except ValueError:
            workers = 4

        def cb(p):
            self.after(0, lambda: self._scan_progress(p))

        def worker():
            try:
                r = scan_folders_parallel(folders, max_workers=workers, progress_callback=cb)
                self.after(0, lambda: self._scan_done(r))
            except Exception as e:
                self.after(0, lambda: self._scan_err(str(e)))

        threading.Thread(target=worker, daemon=True).start()


    def _t1_preview(self,fp):
        from photo_tools_v8.preview import load_image
        from PIL import ImageTk
        try:
            img,info,exif = load_image(fp)
            if img:
                pw=max(self.t1_pf.winfo_width()-20,150)
                ph=max(self.t1_pf.winfo_height()-60,100)
                img.thumbnail((pw,ph),Image.LANCZOS)
                photo=ImageTk.PhotoImage(img)
                self.t1_pl.configure(image=photo,text="")
                self.t1_pl.image=photo
                self.t1_pi.configure(text=os.path.basename(fp))
                return
        except:pass
        self.t1_pl.configure(text="无法预览"); self.t1_pi.configure(text="")
    def _scan(self):
        if self.scan_busy: return
        folders = self.folders.get_folders()
        if not folders: messagebox.showwarning("提示", "请先添加要扫描的文件夹"); return
        self.scan_busy = True
        self.scan_btn.configure(text="扫描中...", state="disabled")
        self.scan_pb.set(0); self.results.clear()
        try: workers = int(self.ws.get())
        except: workers = 4
        def cb(p): self.after(0, lambda: self.scan_pb.set(p.folders_completed/max(p.folders_total,1)) or self.scan_lb.configure(text=f"扫描 {os.path.basename(p.current_folder)}..."))
        def worker():
            try:
                r = scan_folders_parallel(folders, max_workers=workers, progress_callback=cb)
                self.after(0, lambda: self._scan_done(r))
            except Exception as e: self.after(0, lambda: self._scan_err(str(e)))
        threading.Thread(target=worker, daemon=True).start()

    def _t1_preview(self,fp):
        from photo_tools_v8.preview import load_image
        from PIL import ImageTk
        try:
            img,info,exif = load_image(fp)
            if img:
                pw=max(self.t1_pf.winfo_width()-20,150)
                ph=max(self.t1_pf.winfo_height()-60,100)
                img.thumbnail((pw,ph),Image.LANCZOS)
                photo=ImageTk.PhotoImage(img)
                self.t1_pl.configure(image=photo,text="")
                self.t1_pl.image=photo
                self.t1_pi.configure(text=os.path.basename(fp))
                return
        except:pass
        self.t1_pl.configure(text="无法预览"); self.t1_pi.configure(text="")

    def _scan_progress(self, p):
        self.scan_pb.set(p.folders_completed / max(p.folders_total, 1))
        self.scan_lb.configure(text=f"扫描 {os.path.basename(p.current_folder)}...")

    def _scan_done(self, results):
        self.scan_busy = False
        self.scan_btn.configure(text="开始扫描", state="normal")
        self.scan_pb.set(1)
        self.scan_lb.configure(text="扫描完成")
        self.results.populate(results)
        total = sum(len(r.orphans) for r in results if r.success)
        sz = sum(r.total_size_bytes for r in results if r.success)
        # 分组统计
        folder_counts = [(r.folder, len(r.orphans)) for r in results if r.success and r.orphans]
        detail = ""
        if folder_counts:
            detail = "\n" + "\n".join(f"  {os.path.basename(f)}: {n} 个" for f, n in folder_counts)
        if total > 0:
            messagebox.showinfo("扫描完成",
                f"{len(results)} 个文件夹扫描完成\n发现 {total} 个孤儿文件{detail}\n总计 {format_size(sz)}")
        else:
            messagebox.showinfo("扫描完成", "没有发现孤儿文件，素材库干净！")

    def _scan_err(self, msg):
        self.scan_busy = False
        self.scan_btn.configure(text="开始扫描", state="normal")
        self.scan_pb.set(0)
        self.scan_lb.configure(text="扫描失败")
        messagebox.showerror("错误", msg)

    def _open_selected(self):
        sel = self.results.get_selected()
        if not sel:
            messagebox.showinfo("提示", "请先勾选要预览的文件")
            return
        for o in sel:
            try:
                open_file_in_explorer(o["path"])
            except Exception:
                pass

    def _do_delete(self):
        sel = self.results.get_selected()
        if not sel:
            messagebox.showinfo("提示", "请先勾选要删除的文件")
            return
        sz = sum(o["size_bytes"] for o in sel)
        if not messagebox.askyesno("确认", f"将 {len(sel)} 个文件移入回收站？\n总计 {format_size(sz)}"):
            return
        ok, fail, fails = delete_orphans(sel)
        self.results.clear()
        messagebox.showinfo("删除结果", f"成功: {ok} 个\n失败: {fail} 个")
        if fail > 0:
            messagebox.showwarning("删除失败", "\n".join(fails[:10]))

    def _eval_selected(self):
        sel = self.results.get_selected()
        if not sel:
            messagebox.showinfo("提示", "请先勾选要评估的照片")
            return
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        paths = [o["path"] for o in sel if Path(o["path"]).suffix.lower() in exts]
        if not paths:
            messagebox.showinfo("提示", "选中文件中没有图片")
            return
        self.show_page("照片质量评估")
        self._quality_files = paths
        self.qual_lb.configure(text=f"已选 {len(paths)} 个文件")
        self._start_qual()

    # ----- Tab 2: 质量评估 -----
    def _set_scale(self, choice: str):
        mapping = {"严格": "strict", "普通": "normal", "宽松": "loose"}
        self._quality_scale = mapping.get(choice, "normal")

    def _sel_qual_files(self):
        p = filedialog.askopenfilenames(
            title="选择文件",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),
                       ("视频", "*.mp4 *.mov *.avi *.mkv"),
                       ("所有支持", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp *.mp4 *.mov *.avi *.mkv")])
        if p:
            self._quality_files = list(p)
            self.qual_lb.configure(text=f"已选 {len(p)} 个文件")

    def _sel_qual_folder(self):
        folder = filedialog.askdirectory(title="选择照片文件夹")
        if not folder:
            return
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
        paths = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in exts:
                    paths.append(os.path.join(root, f))
        self._quality_files = paths
        self.qual_lb.configure(text=f"已选 {len(paths)} 个文件")

    def _start_qual(self):
        if self.quality_busy or not self._quality_files:
            return
        self.quality_busy = True
        self.qual_btn.configure(text="评估中...", state="disabled")
        self.qual_pb.set(0)
        self.score_view.clear()
        files = list(self._quality_files)
        n = len(files)
        scale = self._quality_scale

        def worker():
            scores = []
            for i, f in enumerate(files):
                ext = Path(f).suffix.lower()
                try:
                    if ext in {".mp4", ".mov", ".avi", ".mkv"}:
                        vs = evaluate_video(f, scale=scale)
                        if vs and vs.frame_scores:
                            fs_l=vs.frame_scores
                            def _avg(k): return sum(getattr(fs,k) for fs in fs_l)/len(fs_l)
                            scores.append(PhotoScore(
                                file=f, filename=os.path.basename(f),
                                total_score=vs.avg_score,
                                composition=_avg("composition"),exposure=_avg("exposure"),
                                sharpness=_avg("sharpness"),color_score=_avg("color_score"),
                                noise_score=_avg("noise_score"),
                                recommendation=vs.recommendation))
                    else:
                        ps = evaluate_photo(f, scale=scale)
                        if ps:
                            scores.append(ps)
                except Exception:
                    pass
                self.after(0, lambda v=(i+1)/n: self.qual_pb.set(v))
            self.history.add_batch(scores, scale)
            self.after(0, lambda: self._qual_done(scores))

        threading.Thread(target=worker, daemon=True).start()

    def _qual_done(self, scores):
        self.quality_busy = False
        self.qual_btn.configure(text="开始评估", state="normal")
        self.qual_pb.set(1)
        self.score_view.add_scores(scores, self._quality_scale)
        if scores:
            avg = sum(s.total_score for s in scores) / len(scores)
            messagebox.showinfo("评估完成",
                f"评估 {len(scores)} 个文件\n平均评分: {avg:.1f}/100\n评分尺度: {self.scale_opt.get()}")

    def _show_history(self):
        HistoryDialog(self, self.history.records)

    def _to_proxy_from_quality(self):
        videos = [p for p in self._quality_files
                  if Path(p).suffix.lower() in VIDEO_EXTENSIONS]
        if not videos:
            messagebox.showinfo("提示", "当前选择中没有视频文件")
            return
        self.show_page("视频代理")
        self.proxy_tab.add_files(videos)

    # ----- Tab 3: 设置 -----
    def _set_font_size(self, label):
        new_scale = {"小": 1.0, "中": 1.25, "大": 1.5, "特大": 2.0}.get(label, 1.0)
        self._apply_font_scale(new_scale)

    def _apply_font_scale(self, new_scale):
        old_scale = float(getattr(self, "_font_scale", 1.0) or 1.0)
        if old_scale <= 0:
            old_scale = 1.0
        global FONT_SCALE
        FONT_SCALE = new_scale
        self._font_scale = new_scale
        self.config["font_scale"] = new_scale
        try:
            tkfont.nametofont("TkDefaultFont").configure(size=max(8, int(13 * new_scale)))
            ctk.FontManager.windows_font_size = max(8, int(13 * new_scale))
        except Exception:
            pass

        def scale_child(widget):
            for child in widget.winfo_children():
                try:
                    font = child.cget("font")
                except Exception:
                    font = None
                if font is not None:
                    try:
                        if isinstance(font, tuple):
                            family = font[0] if len(font) > 0 else ""
                            size = font[1] if len(font) > 1 else 13
                            weight = font[2] if len(font) > 2 else "normal"
                            base = (int(size) or 1) / old_scale
                            child.configure(font=(family, max(1, int(round(base * new_scale))), weight))
                        elif hasattr(font, "cget"):
                            size = font.cget("size")
                            base = (int(size) or 1) / old_scale
                            font.configure(size=max(1, int(round(base * new_scale))))
                    except Exception:
                        pass
                scale_child(child)

        scale_child(self)

    def _set_theme(self, mode):
        ctk.set_appearance_mode(mode)

    def _browse_proxy_dir(self):
        folder = filedialog.askdirectory(title="选择代理输出目录")
        if folder:
            self.proxy_dir_entry.delete(0, "end")
            self.proxy_dir_entry.insert(0, folder)

    def _browse_audio_dir(self):
        folder = filedialog.askdirectory(title="选择音频输出目录")
        if folder:
            self.audio_dir_entry.delete(0, "end")
            self.audio_dir_entry.insert(0, folder)

    def _save_cfg(self):
        new_accent = self.accent_map.get(self.accent_opt.get(), "blue")
        cfg = {"pushplus_token": self.pp_entry.get().strip(),
               "max_workers": int(self.w_spin.get()) if self.w_spin.get().isdigit() else 4,
               "appearance": self.ap_opt.get(),
               "font_scale": float(getattr(self, "_font_scale", 1.0) or 1.0),
               "accent_color": new_accent,
               "proxy_max_workers": int(self.proxy_tab.worker_opt.get()),
               "proxy_resolution": self.proxy_tab.res_opt.get(),
               "proxy_fps": self.proxy_tab.fps_opt.get(),
               "proxy_crf": self.config.get("proxy_crf", 23),
               "proxy_preset": self.config.get("proxy_preset", "veryfast"),
               "proxy_lut": self.config.get("proxy_lut", ""),
               "proxy_output_dir": self.proxy_dir_entry.get().strip(),
               "dynamic_video_dir": self.dynamic_tab.video_dir_entry.get().strip(),
               "audio_output_dir": self.audio_dir_entry.get().strip()}
        save_config(cfg)
        self.pushplus_token = cfg["pushplus_token"]
        self.max_workers = cfg["max_workers"]
        self.config["proxy_output_dir"] = cfg["proxy_output_dir"]
        old_accent = self.config.get("accent_color")
        self.config["accent_color"] = new_accent
        if old_accent != new_accent:
            ctk.set_default_color_theme(new_accent)
            messagebox.showinfo("主题已应用", "主题颜色已保存，正在刷新界面")
            self.after(300, self._rebuild_ui)
        else:
            messagebox.showinfo("已保存", f"配置已保存到 {CONFIG_FILE.name}")

    def _on_close(self):
        self.destroy()
        sys.exit(0)


def main():
    app = PhotoToolsApp()
    app.mainloop()

if __name__ == "__main__":
    main()


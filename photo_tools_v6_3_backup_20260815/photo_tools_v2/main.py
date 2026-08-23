import sys, os, json, threading, tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

import customtkinter as ctk

from .scanner import scan_folders_parallel, delete_orphans, ScanProgress
from .quality import (
    evaluate_photo, evaluate_photos_batch, evaluate_video, PhotoScore,
    SCORING_SCALES, SCORING_SCALE_NAMES, scale_params,
)
from .pushplus_client import PushPlusClient
from .utils import format_size, open_file_in_explorer, format_datetime
from .preview import show_preview

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")
CONFIG_FILE = Path(__file__).parent / "config.json"
HISTORY_FILE = Path(__file__).parent / "eval_history.json"

def load_config():
    cfg = {"pushplus_token":"","max_workers":4,"appearance":"system"}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE,"r",encoding="utf-8") as f:
                cfg.update(json.load(f))
        except: pass
    return cfg

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True,exist_ok=True)
    with open(CONFIG_FILE,"w",encoding="utf-8") as f:
        json.dump(cfg,f,ensure_ascii=False,indent=2)


class HistoryManager:
    def __init__(self):
        self.records = []; self._load()
    def _load(self):
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE,"r",encoding="utf-8") as f:
                    self.records = json.load(f)
            except: self.records = []
    def _save(self):
        HISTORY_FILE.parent.mkdir(parents=True,exist_ok=True)
        with open(HISTORY_FILE,"w",encoding="utf-8") as f:
            json.dump(self.records,f,ensure_ascii=False,indent=2)
    def add_result(self,score,scale):
        self.records.append({"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scale":SCORING_SCALE_NAMES.get(scale,scale),"filename":score.filename,
            "ext":os.path.splitext(score.filename)[1] or "N/A","format":f"{score.width}x{score.height}",
            "total_score":round(score.total_score,1),"composition":round(score.composition,1),
            "exposure":round(score.exposure,1),"sharpness":round(score.sharpness,1),
            "color_score":round(score.color_score,1),"noise_score":round(score.noise_score,1),
            "recommendation":score.recommendation})
        self._save()
    def add_batch(self,scores,scale):
        for s in scores: self.add_result(s,scale)


def _style_treeview():
    """Configure ttk.Treeview to match CTk dark theme."""
    s = ttk.Style()
    if "CTk.Treeview" in s.theme_names(): return
    s.theme_use("clam")
    s.configure("CTk.Treeview",background="#2b2b2b",foreground="#e0e0e0",
        fieldbackground="#2b2b2b",rowheight=30,borderwidth=0,font=("Microsoft YaHei",10))
    s.map("CTk.Treeview",background=[("selected","#1f538d")],foreground=[("selected","white")])
    s.configure("CTk.Treeview.Heading",background="#1e3a5f",foreground="white",
        font=("Microsoft YaHei",11,"bold"),borderwidth=0,relief="flat")
    s.map("CTk.Treeview.Heading",background=[("active","#2a6db5")])


def build_scale_detail(scale_key):
    sp = scale_params(scale_key); name = SCORING_SCALE_NAMES.get(scale_key,scale_key)
    return (f"\u250c\u2500 [{name}] \u8bc4\u5206\u9608\u503c \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510\n"
        f" \u6e05\u6670\u5ea6: Laplacian > {sp['sharpness_divisor']:.0f} \u2192 100\u5206\n"
        f" \u66dd\u5149\u5bb9\u5fcd\u5ea6: \u00b1{sp['exposure_tolerance']}\n"
        f" \u6697\u90e8\u6263\u5206: > {sp['shadow_penalty_at']}% \u5f00\u59cb\n"
        f" \u9ad8\u5149\u6263\u5206: > {sp['highlight_penalty_at']}% \u5f00\u59cb\n"
        f" \u8272\u5f69\u4f4e\u9650: {sp['color_low']} \u4ee5\u4e0b\u2192\u4f4e\u5206\n"
        f" \u566a\u70b9\u5f97\u5206\u7ebf: \u65b9\u5dee {sp['noise_divisor']:.0f} \u2192 0\u5206\n"
        f"\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518")


SCORING_CRITERIA = """\u250c\u2500 \u8bc4\u5206\u5c3a\u5ea6\u8bf4\u660e \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510
 \u6784\u56fe(25%): \u57fa\u7840\u520650+\u4e09\u5206\u7ebf+\u5bf9\u79f0\u6027+\u5185\u5bb9\u5bc6\u5ea6
 \u66dd\u5149(25%): \u4eae\u5ea6\u504f\u79bb128+\u6697\u90e8/\u9ad8\u5149\u526a\u5207+\u5bf9\u6bd4\u5ea6
 \u6e05\u6670\u5ea6(20%): Laplacian\u65b9\u5dee+\u8d8a\u9ad8\u8d8a\u9510\u5229
 \u8272\u5f69(15%): \u9971\u548c\u5ea6\u5206\u5e03+\u8fc7\u6de1/\u8fc7\u8273\u90fd\u6263\u5206
 \u566a\u70b9(15%): \u5e73\u6ed1\u533a\u57df\u65b9\u5dee\u91c7\u6837
\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518"""


class HistoryDialog(ctk.CTkToplevel):
    def __init__(self,parent,records):
        super().__init__(parent)
        self.title("\u8bc4\u4f30\u5386\u53f2\u8bb0\u5f55")
        self.geometry("850x500"); self.minsize(600,300)
        if not records:
            ctk.CTkLabel(self,text="\u6682\u65e0\u5386\u53f2\u8bb0\u5f55",font=("",16)).pack(expand=True)
            return
        top = ctk.CTkFrame(self,fg_color="transparent")
        top.pack(fill="x",padx=10,pady=(10,5))
        ctk.CTkLabel(top,text="\u641c\u7d22:",font=("",12)).pack(side="left",padx=5)
        se = ctk.CTkEntry(top,width=200,placeholder_text="\u6587\u4ef6\u540d...")
        se.pack(side="left",padx=5)
        cols = ["\u65f6\u95f4","\u6587\u4ef6\u540d","\u683c\u5f0f","\u7efc\u5408","\u6784\u56fe","\u66dd\u5149",
                "\u6e05\u6670\u5ea6","\u8272\u5f69","\u566a\u70b9","\u5efa\u8bae","\u5c3a\u5ea6"]
        widths = [130,180,70,55,55,55,55,55,55,140,50]
        _style_treeview()
        tree = ttk.Treeview(self,columns=cols,style="CTk.Treeview",show="headings",height=15)
        for c,w in zip(cols,widths):
            tree.heading(c,text=c); tree.column(c,width=w,minwidth=40)
        vsb = ttk.Scrollbar(self,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(fill="both",expand=True,padx=10,pady=5); vsb.pack(side="right",fill="y")
        def populate(flt=""):
            for i in tree.get_children(): tree.delete(i)
            for r in reversed(records):
                if flt and flt not in r.get("filename",""): continue
                tree.insert("","end",values=[r.get("timestamp","")[-16:],r.get("filename",""),
                    r.get("format",""),r.get("total_score",""),r.get("composition",""),
                    r.get("exposure",""),r.get("sharpness",""),r.get("color_score",""),
                    r.get("noise_score",""),r.get("recommendation","")[:18],r.get("scale","")])
        populate()
        se.configure(command=lambda: populate(se.get()))


# ===== 文件夹列表（三列 + 可勾选 + 可调列宽） =====
class FolderListFrame(ctk.CTkFrame):
    def __init__(self,master,**kwargs):
        super().__init__(master,**kwargs)
        self.folders = []
        _style_treeview()
        cols = ["#0","\u6587\u4ef6\u5939\u8def\u5f84","\u6587\u4ef6\u6570","\u6dfb\u52a0\u65f6\u95f4"]
        self.tree = ttk.Treeview(self,columns=cols[1:],style="CTk.Treeview",show="tree headings",
            selectmode="extended",height=5)
        self.tree.heading("#0",text=""); self.tree.column("#0",width=40,minwidth=30,stretch=False)
        for c in cols[1:]:
            self.tree.heading(c,text=c)
        self.tree.column("\u6587\u4ef6\u5939\u8def\u5f84",width=400,minwidth=100)
        self.tree.column("\u6587\u4ef6\u6570",width=80,minwidth=50,stretch=False)
        self.tree.column("\u6dfb\u52a0\u65f6\u95f4",width=140,minwidth=60,stretch=False)
        self.tree.pack(fill="both",expand=True,padx=5,pady=2)
        self.tree.bind("<ButtonRelease-1>",self._toggle_check)
        btn = ctk.CTkFrame(self,fg_color="transparent")
        btn.pack(fill="x",padx=5,pady=2)
        ctk.CTkButton(btn,text="+ \u6dfb\u52a0\u6587\u4ef6\u5939",width=130,command=self.add).pack(side="left",padx=2)
        ctk.CTkButton(btn,text="+ \u6279\u91cf\u6dfb\u52a0",width=130,command=self.add_batch).pack(side="left",padx=2)
        self.del_btn = ctk.CTkButton(btn,text="\u2212 \u79fb\u9664\u9009\u4e2d",width=130,command=self.remove_selected)
        self.del_btn.pack(side="left",padx=2)
        self.cnt = ctk.CTkLabel(btn,text="0 \u4e2a\u6587\u4ef6\u5939",font=("",11))
        self.cnt.pack(side="right",padx=5)

    def add(self):
        f = filedialog.askdirectory(title="\u9009\u62e9\u7d20\u6750\u6587\u4ef6\u5939")
        if f and f not in self.folders:
            self.folders.append(f); now = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.tree.insert("","end",iid=f,text="☐",values=[f,"-",now])
            self.cnt.configure(text=f"{len(self.folders)} \u4e2a\u6587\u4ef6\u5939")

    def add_batch(self):
        folder = filedialog.askdirectory(title="\u9009\u62e9\u5305\u542b\u5b50\u6587\u4ef6\u5939\u7684\u6839\u76ee\u5f55")
        if not folder: return
        dirs = [folder]
        try:
            dirs += sorted([os.path.join(folder,d) for d in os.listdir(folder)
                          if os.path.isdir(os.path.join(folder,d))])
        except: pass
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for d in dirs:
            if d not in self.folders:
                self.folders.append(d)
                self.tree.insert("","end",iid=d,text="☐",values=[d,"-",now])
        self.cnt.configure(text=f"{len(self.folders)} \u4e2a\u6587\u4ef6\u5939")

    def _toggle_check(self,event):
        item = self.tree.identify_row(event.y)
        if item:
            current = self.tree.item(item,"text")
            self.tree.item(item,text="☑" if current=="\u2610" else "\u2610")

    def remove_selected(self):
        to_remove = [i for i in self.tree.get_children() if self.tree.item(i,"text")=="\u2611"]
        if not to_remove: messagebox.showinfo("\u63d0\u793a","\u8bf7\u5148\u52fe\u9009\u8981\u79fb\u9664\u7684\u6587\u4ef6\u5939"); return
        for i in to_remove:
            self.folders = [f for f in self.folders if f != i]
            self.tree.delete(i)
        self.cnt.configure(text=f"{len(self.folders)} \u4e2a\u6587\u4ef6\u5939")

    def get_folders(self):
        return list(self.folders)


# ===== 扫描结果列表（可调列宽 + 可点击路径） =====
class OrphanResultFrame(ctk.CTkFrame):
    """扫描结果列表（可调列宽 + 可点击路径）"""
    def __init__(self,master,**kwargs):
        super().__init__(master,**kwargs)
        self.items = []
        self.checked = set()  # 勾选状态存储在内存中
        self._parent = master
        _style_treeview()
        cols = ["#0","文件路径","类型","大小","来源文件夹"]
        self.tree = ttk.Treeview(self,columns=cols[1:],style="CTk.Treeview",show="tree headings",
            selectmode="extended",height=8)
        self.tree.heading("#0",text=""); self.tree.column("#0",width=40,minwidth=30,stretch=False)
        for c2 in cols[1:]:
            self.tree.heading(c2,text=c2)
        self.tree.column("文件路径",width=350,minwidth=80)
        self.tree.column("类型",width=60,minwidth=40,stretch=False)
        self.tree.column("大小",width=80,minwidth=50,stretch=False)
        self.tree.column("来源文件夹",width=250,minwidth=80)
        vsb = ttk.Scrollbar(self,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left",fill="both",expand=True,padx=5,pady=2)
        vsb.pack(side="right",fill="y")
        self.after(50, self._center_columns)
        self.tree.bind("<Button-1>",self._on_click)
        top = ctk.CTkFrame(self,fg_color="transparent",height=28)
        top.pack(fill="x",padx=(5,0))
        ctk.CTkCheckBox(top,text="",variable=tk.BooleanVar(value=False),
                         command=self._toggle_all,width=35).pack(side="left",padx=(5,0))
        ctk.CTkLabel(top,text="全选",font=("",11)).pack(side="left",padx=(0,10))
        self.info = ctk.CTkLabel(top,text="",font=("",11))
        self.info.pack(side="left",padx=10)

    def _center_columns(self):
        for col in self.tree["columns"]:
            self.tree.column(col, anchor="center")
            self.tree.heading(col, text=self.tree.heading(col)["text"], anchor="center")
        self.tree.column("#0", anchor="center")

    def clear(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.items.clear()
        self.checked.clear()
        self.info.configure(text="")

    def populate(self,results):
        self.clear()
        total_c=total_sz=0; folder_of={}
        for r in results:
            if not r.success: continue
            for o in r.orphans:
                self.items.append(o); folder_of[id(o)]=r.folder
            total_c+=len(r.orphans); total_sz+=r.total_size_bytes
        self.info.configure(text="发现 %d 个孤儿文件，总计 %s" % (total_c, format_size(total_sz)))
        for i,o in enumerate(self.items):
            self.tree.insert("","end",iid=str(i),text="",values=[os.path.basename(o["path"]),o["ext"],format_size(o["size_bytes"]),folder_of.get(id(o),"")])

    def _on_click(self,event):
        item = self.tree.identify_row(event.y)
        if not item or not item.isdigit(): return
        # 只切换复选框，不自动打开文件
        if item in self.checked:
            self.checked.discard(item)
            self.tree.item(item, text="")
        else:
            self.checked.add(item)
            self.tree.item(item, text="☑")  # ☑ = ☑

    def get_selected(self):
        return [self.items[int(i)] for i in self.checked if i.isdigit()]

    def get_all(self):
        return list(self.items)

    def get_checked_values(self):
        return self.get_selected()

    def _toggle_all(self):
        all_items = set(self.tree.get_children())
        if len(self.checked) < len(all_items):
            self.checked = all_items
            for i in all_items:
                self.tree.item(i, text="☑")
        else:
            self.checked = set()
            for i in all_items:
                self.tree.item(i, text="☐")

# ===== 质量评估结果显示（扩展全宽 + 大字体） =====
class ScoreViewFrame(ctk.CTkFrame):
    def __init__(self,master,**kwargs):
        super().__init__(master,**kwargs)
        self.grid_columnconfigure(0,weight=3)
        self.grid_columnconfigure(1,weight=1)
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        self.detail_frame = ctk.CTkScrollableFrame(self,width=520)
        self.detail_frame.grid(row=0,column=1,sticky="nsew")
        self.detail_frame.configure(width=520)
        ctk.CTkLabel(self.detail_frame,text="\u25b8 \u8bc4\u5206\u7ec6\u5219 \u25c2",
                      font=("",16,"bold")).pack(pady=(12,8))
        self.detail_text = ctk.CTkTextbox(self.detail_frame,width=500,height=500,
                                           font=("Consolas",12),wrap="word")
        self.detail_text.pack(fill="both",expand=True,padx=5,pady=5)
        self.detail_text.insert("0.0",SCORING_CRITERIA)
        self.detail_text.configure(state="disabled")
        self.cards = []

    def set_scale_detail(self,scale_key):
        detail = build_scale_detail(scale_key)
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0","end")
        self.detail_text.insert("0.0",SCORING_CRITERIA + "\n\n" + detail)
        self.detail_text.configure(state="disabled")

    def clear(self):
        for w in self.cards: w.destroy()
        self.cards.clear()

    def add_scores(self,scores,scale="normal"):
        self.clear(); self.set_scale_detail(scale)
        for s in scores:
            card = ctk.CTkFrame(self.scroll,corner_radius=8)
            card.pack(fill="x",padx=10,pady=5)
            ctk.CTkLabel(card,text=s.filename,font=("",14,"bold"),
                          anchor="w").pack(anchor="w",padx=12,pady=(6,3))
            info = ctk.CTkFrame(card,fg_color="transparent")
            info.pack(fill="x",padx=12,pady=3)
            color = "#2ecc71" if s.total_score>=70 else ("#f39c12" if s.total_score>=40 else "#e74c3c")
            ctk.CTkLabel(info,text=f"\u7efc\u5408: {s.total_score:.1f}",
                          font=("",18,"bold"),text_color=color).pack(side="left",padx=10)
            fs = 14
            ctk.CTkLabel(info,text=f"\u6784\u56fe: {s.composition:.0f}",font=("",fs)).pack(side="left",padx=8)
            ctk.CTkLabel(info,text=f"\u66dd\u5149: {s.exposure:.0f}",font=("",fs)).pack(side="left",padx=8)
            ctk.CTkLabel(info,text=f"\u6e05\u6670\u5ea6: {s.sharpness:.0f}",font=("",fs)).pack(side="left",padx=8)
            ctk.CTkLabel(info,text=f"\u8272\u5f69: {s.color_score:.0f}",font=("",fs)).pack(side="left",padx=8)
            ctk.CTkLabel(info,text=f"\u566a\u70b9: {s.noise_score:.0f}",font=("",fs)).pack(side="left",padx=8)
            rc = "#2ecc71" if "\u4f18\u79c0" in s.recommendation or "\u826f\u597d" in s.recommendation else "#f39c12"
            if s.recommendation:
                ctk.CTkLabel(card,text=f"\u5efa\u8bae: {s.recommendation}",
                              font=("",12),text_color=rc,
                              anchor="w").pack(anchor="w",padx=12,pady=(0,6))
            self.cards.append(card)


# ===== 主窗口 =====
class PhotoToolsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PhotoTools V2.2 \u2014 \u6444\u5f71\u7d20\u6750\u7ba1\u7406\u5de5\u5177\u7bb1")
        self.geometry("1250x800"); self.minsize(1000,650)
        self.config = load_config()
        self.pushplus_token = self.config.get("pushplus_token","")
        self.max_workers = self.config.get("max_workers",4)
        self._quality_scale = "normal"
        ctk.set_appearance_mode(self.config.get("appearance","system"))
        self.scan_busy = self.quality_busy = False
        self._quality_files = []
        self.history = HistoryManager()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW",self._on_close)

    def _build_ui(self):
        self.tab = ctk.CTkTabview(self)
        self.tab.pack(fill="both",expand=True,padx=10,pady=10)

        # ---- Tab 1: 单一文件类型筛选 ----
        t1 = self.tab.add("\u5355\u4e00\u6587\u4ef6\u7c7b\u578b\u7b5b\u9009")
        # 文件夹列表
        top = ctk.CTkFrame(t1); top.pack(fill="x",padx=10,pady=(10,5))
        self.folders = FolderListFrame(top); self.folders.pack(fill="x",padx=5,pady=5)
        # 扫描控制
        ctrl = ctk.CTkFrame(t1,fg_color="transparent"); ctrl.pack(fill="x",padx=10,pady=5)
        self.scan_btn = ctk.CTkButton(ctrl,text="\u5f00\u59cb\u626b\u63cf",width=120,
                                       command=self._scan,height=32)
        self.scan_btn.pack(side="left",padx=5)
        self.scan_pb = ctk.CTkProgressBar(ctrl,width=350)
        self.scan_pb.pack(side="left",padx=10); self.scan_pb.set(0)
        self.scan_lb = ctk.CTkLabel(ctrl,text="\u5c31\u7eea",font=("",11))
        self.scan_lb.pack(side="left",padx=5)
        # 结果
        self.results = OrphanResultFrame(t1)
        self.results.pack(fill="both",expand=True,padx=10,pady=5)
        # 底部操作按钮
        bot = ctk.CTkFrame(t1,fg_color="transparent"); bot.pack(fill="x",padx=10,pady=(5,10))
        ctk.CTkButton(bot,text="\u6253\u5f00\u9009\u4e2d\u6587\u4ef6\u9884\u89c8",width=150,
                       command=self._open_selected).pack(side="left",padx=5)
        ctk.CTkButton(bot,text="\u5220\u9664\u9009\u4e2d (\u79fb\u5165\u56de\u6536\u7ad9)",width=200,
                       command=self._del,height=36,
                       fg_color="#c0392b",hover_color="#96281b").pack(side="right",padx=5)
        ctk.CTkButton(bot,text="\u8bc4\u4f30\u9009\u4e2d\u7167\u7247\u8d28\u91cf",width=160,
                       command=self._eval_sel,height=36).pack(side="right",padx=5)

        # ---- Tab 2: 照片质量评估 ----
        t2 = self.tab.add("\u7167\u7247\u8d28\u91cf\u8bc4\u4f30")
        ctrl2 = ctk.CTkFrame(t2); ctrl2.pack(fill="x",padx=10,pady=(10,5))
        ctk.CTkLabel(ctrl2,text="\u8bc4\u5206\u5c3a\u5ea6:",font=("",12)).pack(side="left",padx=5)
        self.scale_opt = ctk.CTkOptionMenu(ctrl2,values=["\u4e25\u683c","\u666e\u901a","\u5bbd\u677e"],
                                             command=self._set_scale)
        self.scale_opt.set("\u666e\u901a"); self.scale_opt.pack(side="left",padx=5)
        ctk.CTkButton(ctrl2,text="\u9009\u62e9\u7167\u7247/\u89c6\u9891",width=130,
                       command=self._sel_files).pack(side="left",padx=3)
        ctk.CTkButton(ctrl2,text="\u9009\u62e9\u6587\u4ef6\u5939\u6279\u91cf",width=130,
                       command=self._sel_folder).pack(side="left",padx=3)
        self.qual_lb = ctk.CTkLabel(ctrl2,text="\u672a\u9009\u62e9\u6587\u4ef6",font=("",11))
        self.qual_lb.pack(side="left",padx=10)
        self.history_btn = ctk.CTkButton(ctrl2,text="\U0001f4cb \u8bb0\u5fc6",width=80,
                                          command=self._show_history)
        self.history_btn.pack(side="right",padx=5)
        self.qual_btn = ctk.CTkButton(ctrl2,text="\u5f00\u59cb\u8bc4\u4f30",width=100,
                                       command=self._start_qual)
        self.qual_btn.pack(side="right",padx=5)
        self.qual_pb = ctk.CTkProgressBar(t2,width=400)
        self.qual_pb.pack(fill="x",padx=10,pady=5); self.qual_pb.set(0)
        self.score_view = ScoreViewFrame(t2)
        self.score_view.pack(fill="both",expand=True,padx=10,pady=5)
        self.score_view.set_scale_detail("normal")

        # ---- Tab 3: 设置 ----
        t3 = self.tab.add("\u8bbe\u7f6e")
        sf = ctk.CTkFrame(t3); sf.pack(fill="x",padx=20,pady=20)
        ctk.CTkLabel(sf,text="\u8bbe\u7f6e",font=("",16,"bold")).pack(anchor="w",pady=10)
        r1 = ctk.CTkFrame(sf,fg_color="transparent"); r1.pack(fill="x",pady=5)
        ctk.CTkLabel(r1,text="PushPlus Token:",width=120,anchor="w").pack(side="left")
        self.pp = ctk.CTkEntry(r1,width=350); self.pp.insert(0,self.pushplus_token); self.pp.pack(side="left",padx=5)
        r2 = ctk.CTkFrame(sf,fg_color="transparent"); r2.pack(fill="x",pady=5)
        ctk.CTkLabel(r2,text="\u5e76\u884c\u626b\u63cf\u6570:",width=120,anchor="w").pack(side="left")
        self.ws = ctk.CTkEntry(r2,width=60); self.ws.insert(0,str(self.max_workers)); self.ws.pack(side="left",padx=5)
        r3 = ctk.CTkFrame(sf,fg_color="transparent"); r3.pack(fill="x",pady=5)
        ctk.CTkLabel(r3,text="\u5916\u89c2\u6a21\u5f0f:",width=120,anchor="w").pack(side="left")
        self.ap = ctk.CTkOptionMenu(r3,values=["system","light","dark"],command=ctk.set_appearance_mode)
        self.ap.set(self.config.get("appearance","system")); self.ap.pack(side="left",padx=5)
        ctk.CTkButton(sf,text="\u4fdd\u5b58\u8bbe\u7f6e",command=self._save).pack(anchor="w",pady=10)
        ab = ctk.CTkFrame(t3); ab.pack(fill="x",padx=20,pady=10)
        ctk.CTkLabel(ab,text="\u5173\u4e8e PhotoTools V2.2",font=("",14,"bold")).pack(anchor="w",pady=5)
        ctk.CTkLabel(ab,text="\u7248\u672c 2.1.0 | \u6444\u5f71\u7d20\u6750\u7ba1\u7406\u5de5\u5177\u7bb1").pack(anchor="w")
        ctk.CTkLabel(ab,text="\u529f\u80fd: \u6587\u4ef6\u7c7b\u578b\u7b5b\u9009 / \u7167\u7247\u89c6\u9891\u8d28\u91cf\u8bc4\u4f30 / PushPlus \u63a8\u9001").pack(anchor="w")

    # ===== Tab 1 =====
    def _scan(self):
        if self.scan_busy: return
        fds = self.folders.get_folders()
        if not fds: messagebox.showwarning("\u63d0\u793a","\u8bf7\u5148\u6dfb\u52a0\u8981\u626b\u63cf\u7684\u6587\u4ef6\u5939"); return
        self.scan_busy=True; self.scan_btn.configure(text="\u626b\u63cf\u4e2d...",state="disabled")
        self.scan_pb.set(0); self.results.clear()
        try: workers=int(self.ws.get())
        except: workers=4
        def cb(p): self.after(0,lambda: self.scan_pb.set(p.folders_completed/max(p.folders_total,1)) or self.scan_lb.configure(text=f"\u626b\u63cf {os.path.basename(p.current_folder)}..."))
        def worker():
            try:
                r = scan_folders_parallel(fds,max_workers=workers,progress_callback=cb)
                self.after(0,lambda: self._scan_done(r))
            except Exception as e: self.after(0,lambda: self._scan_err(str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def _scan_done(self,results):
        self.scan_busy=False; self.scan_btn.configure(text="\u5f00\u59cb\u626b\u63cf",state="normal"); self.scan_pb.set(1); self.scan_lb.configure(text="\u626b\u63cf\u5b8c\u6210")
        self.results.populate(results)
        t=sum(len(r.orphans) for r in results if r.success); sz=sum(r.total_size_bytes for r in results if r.success)
        if t>0: messagebox.showinfo("\u626b\u63cf\u5b8c\u6210",f"{len(results)} \u4e2a\u6587\u4ef6\u5939\n\u53d1\u73b0 {t} \u4e2a\u5b64\u513f\u6587\u4ef6\n\u603b\u8ba1 {format_size(sz)}")
        else: messagebox.showinfo("\u626b\u63cf\u5b8c\u6210","\u6ca1\u6709\u53d1\u73b0\u5b64\u513f\u6587\u4ef6\uff0c\u7d20\u6750\u5e93\u5e72\u51c0\uff01")
    def _scan_err(self,msg):
        self.scan_busy=False; self.scan_btn.configure(text="\u5f00\u59cb\u626b\u63cf",state="normal"); self.scan_pb.set(0); self.scan_lb.configure(text="\u626b\u63cf\u5931\u8d25")
        messagebox.showerror("\u9519\u8bef",msg)
    def _open_selected(self):
        sel = self.results.get_selected()
        if not sel: messagebox.showinfo("提示","请先勾选要预览的文件"); return
        show_preview(self, [o["path"] for o in sel])
    def _del(self):
        sel = self.results.get_selected()
        if not sel: messagebox.showinfo("\u63d0\u793a","\u8bf7\u5148\u52fe\u9009\u8981\u5220\u9664\u7684\u6587\u4ef6"); return
        if not messagebox.askyesno("\u786e\u8ba4",f"\u5c06 {len(sel)} \u4e2a\u6587\u4ef6\u79fb\u5165\u56de\u6536\u7ad9\uff1f\n\u603b\u8ba1 {format_size(sum(o['size_bytes'] for o in sel))}"): return
        ok,fail,fails = delete_orphans(sel); self.results.clear()
        messagebox.showinfo("\u5220\u9664\u7ed3\u679c",f"\u6210\u529f: {ok} \u4e2a\n\u5931\u8d25: {fail} \u4e2a")
        if fail>0: messagebox.showwarning("\u5220\u9664\u5931\u8d25","\n".join(fails[:10]))
    def _eval_sel(self):
        sel = self.results.get_selected()
        if not sel: messagebox.showinfo("\u63d0\u793a","\u8bf7\u5148\u52fe\u9009\u8981\u8bc4\u4f30\u7684\u7167\u7247"); return
        exts={".jpg",".jpeg",".png",".bmp",".tiff",".webp"}
        p = [o["path"] for o in sel if Path(o["path"]).suffix.lower() in exts]
        if not p: messagebox.showinfo("\u63d0\u793a","\u9009\u4e2d\u6587\u4ef6\u4e2d\u6ca1\u6709\u56fe\u7247"); return
        self.tab.set("\u7167\u7247\u8d28\u91cf\u8bc4\u4f30"); self._quality_files=p; self.qual_lb.configure(text=f"\u5df2\u9009 {len(p)} \u4e2a\u6587\u4ef6"); self._start_qual()
    # ===== Tab 2 =====
    def _set_scale(self,choice):
        self._quality_scale = {"\u4e25\u683c":"strict","\u666e\u901a":"normal","\u5bbd\u677e":"loose"}.get(choice,"normal")
    def _sel_files(self):
        p = filedialog.askopenfilenames(title="\u9009\u62e9\u6587\u4ef6",filetypes=[("\u56fe\u7247","*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),("\u89c6\u9891","*.mp4 *.mov *.avi *.mkv"),("\u6240\u6709\u652f\u6301","*.jpg *.jpeg *.png *.bmp *.tiff *.webp *.mp4 *.mov *.avi *.mkv")])
        if p: self._quality_files=list(p); self.qual_lb.configure(text=f"\u5df2\u9009 {len(p)} \u4e2a\u6587\u4ef6")
    def _sel_folder(self):
        f = filedialog.askdirectory(title="\u9009\u62e9\u7167\u7247\u6587\u4ef6\u5939")
        if not f: return
        exts={".jpg",".jpeg",".png",".bmp",".tiff",".webp"}; p=[]
        for root,dirs,files in os.walk(f):
            for fn in files:
                if Path(fn).suffix.lower() in exts: p.append(os.path.join(root,fn))
        self._quality_files=p; self.qual_lb.configure(text=f"\u5df2\u9009 {len(p)} \u4e2a\u6587\u4ef6")
    def _start_qual(self):
        if self.quality_busy or not self._quality_files: return
        self.quality_busy=True; self.qual_btn.configure(text="\u8bc4\u4f30\u4e2d...",state="disabled")
        self.qual_pb.set(0); self.score_view.clear()
        files=list(self._quality_files); n=len(files); scale=self._quality_scale
        def worker():
            scores=[]
            for i,f in enumerate(files):
                ext=Path(f).suffix.lower()
                try:
                    if ext in {".mp4",".mov",".avi",".mkv"}:
                        vs=evaluate_video(f,scale=scale)
                        if vs: scores.append(PhotoScore(file=f,filename=os.path.basename(f),total_score=vs.avg_score,recommendation=vs.recommendation))
                    else:
                        ps=evaluate_photo(f,scale=scale)
                        if ps: scores.append(ps)
                except: pass
                self.after(0,lambda v=(i+1)/n: self.qual_pb.set(v))
            self.history.add_batch(scores,scale)
            self.after(0,lambda: self._qual_done(scores))
        threading.Thread(target=worker,daemon=True).start()
    def _qual_done(self,scores):
        self.quality_busy=False; self.qual_btn.configure(text="\u5f00\u59cb\u8bc4\u4f30",state="normal"); self.qual_pb.set(1)
        self.score_view.add_scores(scores,self._quality_scale)
        if scores: messagebox.showinfo("\u8bc4\u4f30\u5b8c\u6210",f"\u8bc4\u4f30 {len(scores)} \u4e2a\u6587\u4ef6\n\u5e73\u5747\u8bc4\u5206: {sum(s.total_score for s in scores)/len(scores):.1f}/100\n\u8bc4\u5206\u5c3a\u5ea6: {self.scale_opt.get()}")
    def _show_history(self):
        HistoryDialog(self,self.history.records)
    # ===== Tab 3 =====
    def _save(self):
        cfg={"pushplus_token":self.pp.get().strip(),"max_workers":int(self.ws.get()) if self.ws.get().isdigit() else 4,"appearance":self.ap.get()}
        save_config(cfg); self.pushplus_token=cfg["pushplus_token"]; self.max_workers=cfg["max_workers"]
        messagebox.showinfo("\u5df2\u4fdd\u5b58",f"\u914d\u7f6e\u5df2\u4fdd\u5b58\u5230 {CONFIG_FILE.name}")
    def _on_close(self):
        self.destroy(); sys.exit(0)

def main():
    app = PhotoToolsApp(); app.mainloop()

if __name__ == "__main__":
    main()

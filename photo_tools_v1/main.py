"""main.py - PhotoTools V1.0 GUI"""

import os, json, threading, tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import customtkinter as ctk

from .scanner import scan_folders_parallel, delete_orphans, ScanProgress
from .quality import evaluate_photo, evaluate_photos_batch, evaluate_video, PhotoScore
from .pushplus_client import PushPlusClient
from .utils import format_size

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")
CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    cfg = {"pushplus_token": "", "max_workers": 4, "appearance": "system"}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except: pass
    return cfg

def save_config(cfg):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class FolderListFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.folders = []
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=5, pady=(5,2))
        ctk.CTkLabel(hdr, text="扫描文件夹列表", font=("",13,"bold")).pack(side="left")
        self.cnt = ctk.CTkLabel(hdr, text="0 个文件夹", font=("",11))
        self.cnt.pack(side="right", padx=5)
        btn = ctk.CTkFrame(self, fg_color="transparent")
        btn.pack(fill="x", padx=5, pady=2)
        ctk.CTkButton(btn, text="+ 添加文件夹", width=120, command=self.add).pack(side="left", padx=2)
        self.del_btn = ctk.CTkButton(btn, text="− 移除选中", width=120, command=self.remove, state="disabled")
        self.del_btn.pack(side="left", padx=2)
        self.box = tk.Listbox(self, selectmode=tk.EXTENDED, bg="#2b2b2b", fg="#e0e0e0",
                              selectbackground="#1f538d", height=6, font=("Microsoft YaHei",10))
        self.box.pack(fill="both", expand=True, padx=5, pady=5)
        self.box.bind("<<ListboxSelect>>", lambda e: self._upd())

    def add(self):
        f = filedialog.askdirectory(title="选择素材文件夹")
        if f and f not in self.folders:
            self.folders.append(f); self.box.insert(tk.END, f)
            self.cnt.configure(text=f"{len(self.folders)} 个文件夹")
    def remove(self):
        sel = self.box.curselection()
        for i in reversed(sel):
            self.folders.pop(i); self.box.delete(i)
        self.cnt.configure(text=f"{len(self.folders)} 个文件夹"); self._upd()
    def _upd(self):
        self.del_btn.configure(state="normal" if self.box.curselection() else "disabled")
    def get_folders(self):
        return list(self.folders)


class OrphanResultFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.items = []; self.vars = []; self.rows = []
        self.sel_all = tk.BooleanVar(value=False)
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=30)
        hdr.pack(fill="x", padx=5, pady=2)
        ctk.CTkCheckBox(hdr, text="全选", variable=self.sel_all, command=self._toggle, width=60).pack(side="left", padx=5)
        for col,w in [("文件路径",350),("类型",60),("大小",80),("来源文件夹",200)]:
            ctk.CTkLabel(hdr, text=col, font=("",11,"bold"), width=w).pack(side="left", padx=2)
        self.info = ctk.CTkLabel(self, text="", font=("",11))
        self.info.pack(anchor="w", padx=10, pady=(0,5))
    def clear(self):
        for r in self.rows: r.destroy()
        self.items.clear(); self.vars.clear(); self.rows.clear()
        self.info.configure(text="")
    def populate(self, results):
        self.clear()
        total_c = total_sz = 0; folder_of = {}
        for r in results:
            if not r.success: continue
            for o in r.orphans:
                self.items.append(o); folder_of[id(o)] = r.folder
            total_c += len(r.orphans); total_sz += r.total_size_bytes
        self.info.configure(text=f"发现 {total_c} 个孤儿文件，总计 {format_size(total_sz)}")
        for i,o in enumerate(self.items):
            v = tk.BooleanVar(value=False); self.vars.append(v)
            row = ctk.CTkFrame(self, fg_color="transparent"); row.pack(fill="x", padx=5, pady=1)
            ctk.CTkCheckBox(row, text="", variable=v, width=40).pack(side="left", padx=(5,0))
            ctk.CTkLabel(row, text=os.path.basename(o["path"]), anchor="w", width=350).pack(side="left", padx=2)
            ctk.CTkLabel(row, text=o["ext"], width=60).pack(side="left")
            ctk.CTkLabel(row, text=format_size(o["size_bytes"]), width=80).pack(side="left")
            ctk.CTkLabel(row, text=folder_of.get(id(o),""), anchor="w", width=200).pack(side="left")
            self.rows.append(row)
    def get_selected(self):
        return [it for it,v in zip(self.items,self.vars) if v.get()]
    def _toggle(self):
        v = self.sel_all.get()
        for var in self.vars: var.set(v)


class ScoreViewFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.cards = []
    def clear(self):
        for w in self.cards: w.destroy()
        self.cards.clear()
    def add_scores(self, scores):
        self.clear()
        for s in scores:
            card = ctk.CTkFrame(self, corner_radius=8); card.pack(fill="x", padx=10, pady=4)
            ctk.CTkLabel(card, text=s.filename, font=("",12,"bold"), anchor="w").pack(anchor="w", padx=10, pady=(5,2))
            info = ctk.CTkFrame(card, fg_color="transparent"); info.pack(fill="x", padx=10, pady=2)
            c = "#2ecc71" if s.total_score>=70 else ("#f39c12" if s.total_score>=40 else "#e74c3c")
            ctk.CTkLabel(info, text=f"综合: {s.total_score:.1f}", font=("",14,"bold"), text_color=c).pack(side="left", padx=5)
            for lbl in [f"构图: {s.composition:.0f}", f"曝光: {s.exposure:.0f}",
                        f"清晰度: {s.sharpness:.0f}", f"色彩: {s.color_score:.0f}", f"噪点: {s.noise_score:.0f}"]:
                ctk.CTkLabel(info, text=lbl).pack(side="left", padx=4)
            rc = "#2ecc71" if "优秀" in s.recommendation or "良好" in s.recommendation else "#f39c12"
            if s.recommendation:
                ctk.CTkLabel(card, text=f"建议: {s.recommendation}", font=("",11), text_color=rc, anchor="w").pack(anchor="w", padx=10, pady=(0,5))
            self.cards.append(card)


class PhotoToolsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PhotoTools — 摄影素材管理工具箱")
        self.geometry("1100x720"); self.minsize(900,600)
        self.config = load_config()
        self.pushplus_token = self.config.get("pushplus_token","")
        self.max_workers = self.config.get("max_workers",4)
        ctk.set_appearance_mode(self.config.get("appearance","system"))
        self.scan_busy = self.qual_busy = False
        self._qual_files = []
        self._build(); self.protocol("WM_DELETE_WINDOW", lambda: (self.destroy(), sys.exit(0)))

    def _build(self):
        self.tab = ctk.CTkTabview(self); self.tab.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab1: 孤儿文件清理
        t1 = self.tab.add("孤儿文件清理")
        top = ctk.CTkFrame(t1); top.pack(fill="x", padx=10, pady=(10,5))
        self.folders = FolderListFrame(top); self.folders.pack(fill="x", padx=5, pady=5)
        ctrl = ctk.CTkFrame(t1, fg_color="transparent"); ctrl.pack(fill="x", padx=10, pady=5)
        self.scan_btn = ctk.CTkButton(ctrl, text="开始扫描", width=120, command=self._scan, height=32)
        self.scan_btn.pack(side="left", padx=5)
        self.scan_pb = ctk.CTkProgressBar(ctrl, width=300); self.scan_pb.pack(side="left", padx=10); self.scan_pb.set(0)
        self.scan_lb = ctk.CTkLabel(ctrl, text="就绪", font=("",11)); self.scan_lb.pack(side="left", padx=5)
        self.results = OrphanResultFrame(t1); self.results.pack(fill="both", expand=True, padx=10, pady=5)
        bot = ctk.CTkFrame(t1, fg_color="transparent"); bot.pack(fill="x", padx=10, pady=(5,10))
        ctk.CTkButton(bot, text="删除选中 (移入回收站)", command=self._del, height=36,
                       fg_color="#c0392b", hover_color="#96281b").pack(side="right", padx=5)
        ctk.CTkButton(bot, text="评估选中照片质量", command=self._eval_sel, height=36).pack(side="right", padx=5)

        # Tab2: 照片质量评估
        t2 = self.tab.add("照片质量评估")
        ctrl2 = ctk.CTkFrame(t2); ctrl2.pack(fill="x", padx=10, pady=(10,5))
        ctk.CTkButton(ctrl2, text="选择照片/视频", width=150, command=self._sel_files).pack(side="left", padx=3)
        ctk.CTkButton(ctrl2, text="选择文件夹批量", width=150, command=self._sel_folder).pack(side="left", padx=3)
        self.qual_lb = ctk.CTkLabel(ctrl2, text="未选择文件", font=("",11)); self.qual_lb.pack(side="left", padx=10)
        self.qual_btn = ctk.CTkButton(ctrl2, text="开始评估", width=100, command=self._start_qual)
        self.qual_btn.pack(side="right", padx=5)
        self.qual_pb = ctk.CTkProgressBar(t2, width=400); self.qual_pb.pack(fill="x", padx=10, pady=5); self.qual_pb.set(0)
        self.score_view = ScoreViewFrame(t2); self.score_view.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab3: 设置
        t3 = self.tab.add("设置")
        sf = ctk.CTkFrame(t3); sf.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(sf, text="设置", font=("",16,"bold")).pack(anchor="w", pady=10)
        r1 = ctk.CTkFrame(sf, fg_color="transparent"); r1.pack(fill="x", pady=5)
        ctk.CTkLabel(r1, text="PushPlus Token:", width=120, anchor="w").pack(side="left")
        self.pp = ctk.CTkEntry(r1, width=350); self.pp.pack(side="left", padx=5)
        r2 = ctk.CTkFrame(sf, fg_color="transparent"); r2.pack(fill="x", pady=5)
        ctk.CTkLabel(r2, text="并行扫描数:", width=120, anchor="w").pack(side="left")
        self.ws = ctk.CTkEntry(r2, width=60); self.ws.insert(0,str(self.max_workers)); self.ws.pack(side="left", padx=5)
        r3 = ctk.CTkFrame(sf, fg_color="transparent"); r3.pack(fill="x", pady=5)
        ctk.CTkLabel(r3, text="外观模式:", width=120, anchor="w").pack(side="left")
        self.ap = ctk.CTkOptionMenu(r3, values=["system","light","dark"], command=ctk.set_appearance_mode)
        self.ap.set(self.config.get("appearance","system")); self.ap.pack(side="left", padx=5)
        ctk.CTkButton(sf, text="保存设置", command=self._save).pack(anchor="w", pady=10)
        ab = ctk.CTkFrame(t3); ab.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(ab, text="关于 PhotoTools", font=("",14,"bold")).pack(anchor="w", pady=5)
        ctk.CTkLabel(ab, text="版本 0.1.0 | 摄影素材管理工具箱").pack(anchor="w")
        ctk.CTkLabel(ab, text="孤儿文件清理 / 照片质量评估 / PushPlus 推送").pack(anchor="w")

    def _scan(self):
        if self.scan_busy: return
        folders = self.folders.get_folders()
        if not folders: messagebox.showwarning("提示", "请先添加要扫描的文件夹"); return
        self.scan_busy = True; self.scan_btn.configure(text="扫描中...", state="disabled")
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

    def _scan_done(self, results):
        self.scan_busy=False; self.scan_btn.configure(text="开始扫描", state="normal"); self.scan_pb.set(1); self.scan_lb.configure(text="扫描完成")
        self.results.populate(results)
        total=sum(len(r.orphans) for r in results if r.success)
        sz=sum(r.total_size_bytes for r in results if r.success)
        if total>0: messagebox.showinfo("扫描完成", f"{len(results)} 个文件夹\n发现 {total} 个孤儿文件\n可释放 {format_size(sz)}")
        else: messagebox.showinfo("扫描完成", "没有发现孤儿文件，素材库干净！")

    def _scan_err(self, msg):
        self.scan_busy=False; self.scan_btn.configure(text="开始扫描",state="normal"); self.scan_pb.set(0); self.scan_lb.configure(text="扫描失败")
        messagebox.showerror("错误", msg)

    def _del(self):
        sel = self.results.get_selected()
        if not sel: messagebox.showinfo("提示", "请先勾选要删除的文件"); return
        if not messagebox.askyesno("确认", f"将 {len(sel)} 个文件移入回收站？\n总计 {format_size(sum(o['size_bytes'] for o in sel))}"): return
        ok,fail,fails = delete_orphans(sel); self.results.clear()
        messagebox.showinfo("删除结果", f"成功: {ok} 个\n失败: {fail} 个")
        if fail>0: messagebox.showwarning("删除失败", "\n".join(fails[:10]))

    def _eval_sel(self):
        sel = self.results.get_selected()
        if not sel: messagebox.showinfo("提示", "请先勾选要评估的照片"); return
        exts={".jpg",".jpeg",".png",".bmp",".tiff",".webp"}
        p = [o["path"] for o in sel if Path(o["path"]).suffix.lower() in exts]
        if not p: messagebox.showinfo("提示", "选中文件中没有图片"); return
        self.tab.set("照片质量评估"); self._qual_files = p; self.qual_lb.configure(text=f"已选 {len(p)} 个文件"); self._start_qual()

    def _sel_files(self):
        p = filedialog.askopenfilenames(title="选择文件", filetypes=[("图片","*.jpg *.jpeg *.png *.bmp *.tiff *.webp"),("视频","*.mp4 *.mov *.avi *.mkv"),("所有支持","*.jpg *.jpeg *.png *.bmp *.tiff *.webp *.mp4 *.mov *.avi *.mkv")])
        if p: self._qual_files=list(p); self.qual_lb.configure(text=f"已选 {len(p)} 个文件")

    def _sel_folder(self):
        f = filedialog.askdirectory(title="选择照片文件夹")
        if not f: return
        exts={".jpg",".jpeg",".png",".bmp",".tiff",".webp"}
        p = []
        for root,dirs,files in os.walk(f):
            for fn in files:
                if Path(fn).suffix.lower() in exts: p.append(os.path.join(root,fn))
        self._qual_files=p; self.qual_lb.configure(text=f"已选 {len(p)} 个文件")

    def _start_qual(self):
        if self.qual_busy or not self._qual_files: return
        self.qual_busy=True; self.qual_btn.configure(text="评估中...",state="disabled"); self.qual_pb.set(0); self.score_view.clear()
        files=list(self._qual_files); n=len(files)
        def worker():
            scores=[]
            for i,f in enumerate(files):
                ext=Path(f).suffix.lower()
                try:
                    if ext in {".mp4",".mov",".avi",".mkv"}:
                        vs=evaluate_video(f)
                        if vs: scores.append(PhotoScore(file=f,filename=os.path.basename(f),total_score=vs.avg_score,recommendation=vs.recommendation))
                    else:
                        ps=evaluate_photo(f)
                        if ps: scores.append(ps)
                except: pass
                self.after(0,lambda v=(i+1)/n: self.qual_pb.set(v))
            self.after(0,lambda: self._qual_done(scores))
        threading.Thread(target=worker, daemon=True).start()

    def _qual_done(self, scores):
        self.qual_busy=False; self.qual_btn.configure(text="开始评估",state="normal"); self.qual_pb.set(1)
        self.score_view.add_scores(scores)
        if scores: messagebox.showinfo("评估完成", f"评估 {len(scores)} 个文件\n平均评分: {sum(s.total_score for s in scores)/len(scores):.1f}/100")

    def _save(self):
        save_config({"pushplus_token":self.pp.get().strip(),"max_workers":int(self.ws.get()) if self.ws.get().isdigit() else 4,"appearance":self.ap.get()})
        messagebox.showinfo("已保存", f"配置已保存到 {CONFIG_FILE.name}")

def main():
    app = PhotoToolsApp(); app.mainloop()

if __name__ == "__main__":
    main()

"""audio_extract_ui.py - 视频无损音频提取界面 (V7)"""

import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .audio_extract import (
    AUDIO_EXTENSIONS,
    extract_audio_batch,
    get_audio_output_dir,
)
from .proxy import find_ffmpeg
from .utils import open_file_in_explorer


class AudioExtractTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.items = []
        self.busy = False
        self.cancel_event = threading.Event()
        self.done_count = 0
        self.total_count = 0
        fs = float(self.app.config.get("font_scale", 1.0) or 1.0)

        def F(size, bold=False):
            s = max(8, int(size * fs))
            return ("", s, "bold") if bold else ("", s)

        self.F = F
        self._build_ui()

    def _build_ui(self):
        F = self.F
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=8, pady=(8, 5))

        self.add_file_btn = ctk.CTkButton(top, text="添加视频文件", width=120, height=32,
                                          font=F(13), command=self._add_files)
        self.add_file_btn.pack(side="left", padx=5)
        self.add_folder_btn = ctk.CTkButton(top, text="添加文件夹", width=110, height=32,
                                            font=F(13), command=self._add_folder)
        self.add_folder_btn.pack(side="left", padx=5)
        self.sel_all_btn = ctk.CTkButton(top, text="全选", width=70, height=32,
                                         font=F(13), command=self._select_all)
        self.sel_all_btn.pack(side="left", padx=5)
        self.sel_none_btn = ctk.CTkButton(top, text="全不选", width=70, height=32,
                                          font=F(13), command=self._select_none)
        self.sel_none_btn.pack(side="left", padx=5)
        self.clear_btn = ctk.CTkButton(top, text="清空列表", width=90, height=32,
                                       font=F(13), command=self._clear)
        self.clear_btn.pack(side="left", padx=5)
        self.count_lb = ctk.CTkLabel(top, text="未添加视频", font=F(12))
        self.count_lb.pack(side="left", padx=12)

        out = ctk.CTkFrame(self)
        out.pack(fill="x", padx=8, pady=4)
        out.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out, text="音频输出目录:", font=F(13)).grid(row=0, column=0, padx=6, pady=5, sticky="w")
        self.out_dir_entry = ctk.CTkEntry(out, height=30)
        self.out_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.out_dir_entry.insert(0, self.app.config.get("audio_output_dir", ""))
        self.browse_btn = ctk.CTkButton(out, text="浏览", width=70, height=30,
                                        font=F(13), command=self._browse_output_dir)
        self.browse_btn.grid(row=0, column=2, padx=5, pady=5)
        self.open_dir_btn = ctk.CTkButton(out, text="打开音频文件夹", width=120, height=30,
                                          font=F(13), command=self._open_audio_dir)
        self.open_dir_btn.grid(row=0, column=3, padx=5, pady=5)

        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(list_frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        head.grid_columnconfigure(1, weight=1)
        self.sel_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(head, text="", variable=self.sel_all_var, width=34,
                        command=self._toggle_all).grid(row=0, column=0, padx=(6, 2))
        ctk.CTkLabel(head, text="视频文件", width=280, anchor="w",
                     font=F(13, True)).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(head, text="状态", width=120, anchor="w",
                     font=F(13, True)).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(head, text="输出 WAV", width=280, anchor="w",
                     font=F(13, True)).grid(row=0, column=3, padx=4)

        self.scroll = ctk.CTkScrollableFrame(list_frame)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.scroll.grid_columnconfigure(1, weight=1)

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        bottom.grid_columnconfigure(0, weight=1)

        self.pb = ctk.CTkProgressBar(bottom, height=14)
        self.pb.grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=(4, 2))
        self.pb.set(0)
        self.current_lb = ctk.CTkLabel(bottom, text="当前: -", anchor="w", font=F(12))
        self.current_lb.grid(row=1, column=0, columnspan=4, sticky="ew", padx=8)
        self.status_lb = ctk.CTkLabel(bottom, text="就绪", anchor="w", font=F(12))
        self.status_lb.grid(row=2, column=0, columnspan=4, sticky="ew", padx=8)

        self.start_btn = ctk.CTkButton(bottom, text="开始提取", width=120, height=32,
                                       font=F(14, True), command=self._start,
                                       fg_color="#1f6feb", hover_color="#1750a9")
        self.start_btn.grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.cancel_btn = ctk.CTkButton(bottom, text="停止提取", width=100, height=32,
                                        font=F(13), command=self._cancel,
                                        state="disabled", fg_color="#c0392b",
                                        hover_color="#96281b")
        self.cancel_btn.grid(row=3, column=1, sticky="w", padx=5, pady=4)

    @staticmethod
    def _item_key(path):
        return os.path.normcase(os.path.abspath(path))

    def _add_files(self):
        exts = " ".join(f"*.{e.lstrip('.')}" for e in sorted(AUDIO_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频文件", exts), ("所有文件", "*.*")],
        )
        if paths:
            self._add_paths(paths)

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择视频文件夹")
        if not folder:
            return
        found = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in AUDIO_EXTENSIONS:
                    found.append(os.path.join(root, f))
        if not found:
            messagebox.showinfo("提示", "该文件夹中没有找到视频文件")
            return
        self._add_paths(found)

    def _add_paths(self, paths):
        existing = {self._item_key(i["path"]) for i in self.items}
        added = 0
        for p in paths:
            path = str(p)
            key = self._item_key(path)
            if key in existing or not Path(path).exists():
                continue
            if Path(path).suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            existing.add(key)
            item = {
                "path": path,
                "var": ctk.BooleanVar(value=False),
                "row": None,
                "status_lb": None,
                "output_lb": None,
                "output": "",
                "status": "待提取",
            }
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkCheckBox(row, text="", variable=item["var"], width=34,
                            font=self.F(12)).grid(row=0, column=0, padx=(4, 2))
            ctk.CTkLabel(row, text=os.path.basename(path), width=280,
                         anchor="w", font=self.F(12)).grid(row=0, column=1, sticky="ew", padx=2)
            item["status_lb"] = ctk.CTkLabel(row, text="待提取", width=120,
                                             anchor="w", font=self.F(12))
            item["status_lb"].grid(row=0, column=2, padx=4)
            item["output_lb"] = ctk.CTkLabel(row, text="-", width=280,
                                             anchor="w", font=self.F(11))
            item["output_lb"].grid(row=0, column=3, padx=4)
            item["row"] = row
            self.items.append(item)
            added += 1
        self._update_count()
        self.status_lb.configure(text=f"已添加 {added} 个视频" if added else "没有新增视频")

    def _update_count(self):
        total = len(self.items)
        selected = sum(1 for i in self.items if i["var"].get())
        self.count_lb.configure(text=f"共 {total} 个视频，已选择 {selected} 个")

    def _toggle_all(self):
        v = self.sel_all_var.get()
        for item in self.items:
            item["var"].set(v)
        self._update_count()

    def _select_all(self):
        for item in self.items:
            item["var"].set(True)
        self.sel_all_var.set(True)
        self._update_count()

    def _select_none(self):
        for item in self.items:
            item["var"].set(False)
        self.sel_all_var.set(False)
        self._update_count()

    def _clear(self):
        if self.busy:
            return
        for item in self.items:
            item["row"].destroy()
        self.items.clear()
        self.pb.set(0)
        self.current_lb.configure(text="当前: -")
        self.status_lb.configure(text="就绪")
        self._update_count()

    def _browse_output_dir(self):
        folder = filedialog.askdirectory(title="选择音频输出目录")
        if folder:
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, folder)
            self.app.config["audio_output_dir"] = folder

    def _open_audio_dir(self):
        items = [i for i in self.items if i["var"].get()] or list(self.items)
        if not items:
            messagebox.showinfo("提示", "请先添加视频文件")
            return
        output_dir = str(self.out_dir_entry.get().strip() or "")
        if output_dir and Path(output_dir).exists():
            open_file_in_explorer(output_dir)
            return
        item = items[0]
        if item["output"] and Path(item["output"]).parent.exists():
            open_file_in_explorer(str(Path(item["output"]).parent))
            return
        target = get_audio_output_dir(item["path"], self.app.config)
        if target.exists():
            open_file_in_explorer(str(target))
        else:
            messagebox.showinfo("提示", "音频文件夹尚未生成")

    def _start(self):
        if self.busy:
            return
        paths = [i["path"] for i in self.items if i["var"].get()]
        if not paths:
            messagebox.showinfo("提示", "请先勾选要提取音频的视频")
            return
        if not find_ffmpeg():
            messagebox.showerror("缺少 ffmpeg", "未找到 ffmpeg.exe，请将 ffmpeg 放到 assets 目录后重试")
            return

        self.busy = True
        self.done_count = 0
        self.total_count = len(paths)
        self.cancel_event.clear()
        self.start_btn.configure(state="disabled", text="提取中...")
        self.cancel_btn.configure(state="normal")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.browse_btn, self.open_dir_btn):
            w.configure(state="disabled")
        self.pb.set(0)
        self.status_lb.configure(text=f"队列: {self.total_count} 个文件")
        self.out_dir_entry.configure(state="disabled")

        for item in self.items:
            if item["path"] in paths:
                item["status"] = "排队中"
                item["status_lb"].configure(text="排队中")

        def worker():
            def cb(event):
                self.after(0, lambda: self._on_event(event))
            results = extract_audio_batch(paths, self.app.config, self.cancel_event, cb)
            self.after(0, lambda: self._done(results))

        threading.Thread(target=worker, daemon=True).start()

    def _cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.cancel_btn.configure(state="disabled")
            self.status_lb.configure(text="正在停止，等待当前任务停止...")

    def _on_event(self, event):
        kind = event.get("type")
        path = event.get("path", "")
        item = next((i for i in self.items if self._item_key(i["path"]) == self._item_key(path)), None)
        if kind == "start":
            if item:
                item["status"] = "提取中"
                item["status_lb"].configure(text="提取中 0%")
            self.current_lb.configure(text="当前: " + os.path.basename(path))
        elif kind == "progress":
            pct = int(float(event.get("percent", 0) or 0) * 100)
            if item:
                item["status"] = "提取中"
                item["status_lb"].configure(text=f"提取中 {pct}%")
        elif kind == "done":
            self.done_count += 1
            self.pb.set(self.done_count / max(1, self.total_count))
            res = event.get("result", {})
            status = res.get("status", "failed")
            if item:
                item["status"] = {
                    "done": "完成", "skipped": "已存在", "failed": "失败",
                    "no_audio": "无音轨", "cancelled": "已取消",
                }.get(status, status)
                if status == "done":
                    item["output"] = res.get("output", "")
                    item["output_lb"].configure(text=os.path.basename(res.get("output", "")))
                elif status in ("failed", "no_audio", "cancelled") and res.get("error"):
                    item["output_lb"].configure(text=res["error"][:120])
                elif status == "skipped":
                    item["output"] = res.get("output", "")
                    item["output_lb"].configure(text=os.path.basename(res.get("output", "")))
                item["status_lb"].configure(text=item["status"])
            remaining = max(0, self.total_count - self.done_count)
            self.status_lb.configure(text=f"进度 {self.done_count}/{self.total_count}，剩余 {remaining}")

    def _done(self, results):
        self.busy = False
        self.start_btn.configure(state="normal", text="开始提取")
        self.cancel_btn.configure(state="disabled")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.browse_btn, self.open_dir_btn):
            w.configure(state="normal")
        self.out_dir_entry.configure(state="normal")
        ok = sum(1 for r in results if r.get("status") == "done")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        failed = sum(1 for r in results if r.get("status") == "failed")
        no_audio = sum(1 for r in results if r.get("status") == "no_audio")
        cancelled = sum(1 for r in results if r.get("status") == "cancelled")
        self.status_lb.configure(
            text=f"完成: 成功 {ok}，已存在 {skipped}，无音轨 {no_audio}，失败 {failed}，取消 {cancelled}")
        self.pb.set(self.done_count / max(1, self.total_count))
        if failed:
            messagebox.showwarning("部分失败", f"成功 {ok} 个，失败 {failed} 个，无音轨 {no_audio} 个")
        elif no_audio:
            messagebox.showinfo("完成", f"完成：成功 {ok} 个，无音轨 {no_audio} 个")
        elif cancelled:
            messagebox.showinfo("已停止", f"已取消 {cancelled} 个任务")

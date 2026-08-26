"""convert_ui.py - RAW/PNG 快速转 JPG 界面 (V12.0)"""

import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .convert import (
    CONVERT_EXTENSIONS,
    DEFAULT_OUTPUT_DIR,
    convert_batch,
)
from .utils import open_file_in_explorer


class ConvertTab(ctk.CTkFrame):
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

        self.add_file_btn = ctk.CTkButton(top, text="添加文件", width=100, height=32,
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
        self.count_lb = ctk.CTkLabel(top, text="未添加文件", font=F(12))
        self.count_lb.pack(side="left", padx=12)

        out = ctk.CTkFrame(self)
        out.pack(fill="x", padx=8, pady=4)
        out.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(out, text="JPG 输出目录:", font=F(13)).grid(row=0, column=0, padx=6, pady=5, sticky="w")
        self.out_dir_entry = ctk.CTkEntry(out, height=30)
        self.out_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.out_dir_entry.insert(0, DEFAULT_OUTPUT_DIR)
        ctk.CTkButton(out, text="浏览", width=70, height=30,
                      font=F(13), command=self._browse_output).grid(row=0, column=2, padx=5, pady=5)
        self.open_dir_btn = ctk.CTkButton(out, text="打开输出文件夹", width=120, height=30,
                                          font=F(13), command=self._open_output)
        self.open_dir_btn.grid(row=0, column=3, padx=5, pady=5)

        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, padx=8, pady=4)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(list_frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, text="", width=34).grid(row=0, column=0)
        ctk.CTkLabel(head, text="源文件", width=280, anchor="w",
                     font=F(13, True)).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(head, text="状态", width=120, anchor="w",
                     font=F(13, True)).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(head, text="生成 JPG 位置", width=360, anchor="w",
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

        self.start_btn = ctk.CTkButton(bottom, text="开始转换", width=120, height=32,
                                       font=F(14, True), command=self._start,
                                       fg_color="#1f6feb", hover_color="#1750a9")
        self.start_btn.grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.cancel_btn = ctk.CTkButton(bottom, text="停止转换", width=100, height=32,
                                        font=F(13), command=self._cancel,
                                        state="disabled", fg_color="#c0392b",
                                        hover_color="#96281b")
        self.cancel_btn.grid(row=3, column=1, sticky="w", padx=5, pady=4)

    @staticmethod
    def _item_key(path):
        return os.path.normcase(os.path.abspath(path))

    def _add_files(self):
        if self.busy:
            return
        exts = " ".join(f"*.{e.lstrip('.')}" for e in sorted(CONVERT_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="选择 PNG / RAW 文件",
            filetypes=[("PNG/RAW 文件", exts), ("所有文件", "*.*")],
        )
        if paths:
            self._add_paths(paths)

    def _add_folder(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if not folder:
            return
        found = []
        for root, _dirs, files in os.walk(folder):
            for f in files:
                if Path(f).suffix.lower() in CONVERT_EXTENSIONS:
                    found.append(os.path.join(root, f))
        if not found:
            messagebox.showinfo("提示", "该文件夹中没有找到 PNG / RAW 文件")
            return
        self._add_paths(found)

    def _add_paths(self, paths):
        existing = {self._item_key(i["path"]) for i in self.items}
        added = 0
        for p in paths:
            path = str(p)
            key = self._item_key(path)
            if key in existing or not os.path.exists(path):
                continue
            if Path(path).suffix.lower() not in CONVERT_EXTENSIONS:
                continue
            existing.add(key)
            item = {
                "path": path,
                "var": ctk.BooleanVar(value=False),
                "row": None,
                "status_lb": None,
                "output_lb": None,
                "output": "",
                "status": "待转换",
            }
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=1)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkCheckBox(row, text="", variable=item["var"], width=34,
                            font=self.F(12)).grid(row=0, column=0, padx=(4, 2))
            ctk.CTkLabel(row, text=os.path.basename(path), width=280,
                         anchor="w", font=self.F(12)).grid(row=0, column=1, sticky="ew", padx=2)
            item["status_lb"] = ctk.CTkLabel(row, text="待转换", width=120,
                                             anchor="w", font=self.F(12))
            item["status_lb"].grid(row=0, column=2, padx=4)
            item["output_lb"] = ctk.CTkLabel(row, text="-", width=360,
                                             anchor="w", font=self.F(11))
            item["output_lb"].grid(row=0, column=3, padx=4)
            item["row"] = row
            self.items.append(item)
            added += 1
        self._update_count()
        self.status_lb.configure(text=f"已添加 {added} 个文件" if added else "没有新增文件")

    def _update_count(self):
        total = len(self.items)
        selected = sum(1 for i in self.items if i["var"].get())
        self.count_lb.configure(text=f"共 {total} 个文件，已选择 {selected} 个")

    def _select_all(self):
        for item in self.items:
            item["var"].set(True)
        self._update_count()

    def _select_none(self):
        for item in self.items:
            item["var"].set(False)
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

    def _browse_output(self):
        folder = filedialog.askdirectory(title="选择 JPG 输出目录")
        if folder:
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, folder)

    def _open_output(self):
        output_dir = self.out_dir_entry.get().strip().strip('"') or DEFAULT_OUTPUT_DIR
        if os.path.isdir(output_dir):
            open_file_in_explorer(output_dir)
        else:
            messagebox.showinfo("提示", "输出文件夹尚未生成")

    def _start(self):
        if self.busy:
            return
        paths = [i["path"] for i in self.items if i["var"].get()]
        if not paths:
            messagebox.showinfo("提示", "请先勾选要转换的文件")
            return
        output_dir = self.out_dir_entry.get().strip().strip('"') or DEFAULT_OUTPUT_DIR
        self.busy = True
        self.done_count = 0
        self.total_count = len(paths)
        self.cancel_event.clear()
        self.start_btn.configure(state="disabled", text="转换中...")
        self.cancel_btn.configure(state="normal")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.open_dir_btn):
            w.configure(state="disabled")
        self.pb.set(0)
        self.status_lb.configure(text=f"队列: {self.total_count} 个文件")
        for item in self.items:
            if item["path"] in paths:
                item["status"] = "排队中"
                item["status_lb"].configure(text="排队中")

        def worker():
            def cb(event):
                self.after(0, lambda: self._on_event(event))
            results = convert_batch(paths, output_dir, self.cancel_event, cb)
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
                item["status"] = "转换中"
                item["status_lb"].configure(text="转换中")
            self.current_lb.configure(text="当前: " + os.path.basename(path))
        elif kind == "done":
            self.done_count += 1
            self.pb.set(self.done_count / max(1, self.total_count))
            res = event.get("result", {})
            status = res.get("status", "failed")
            if item:
                item["status"] = {
                    "done": "已生成", "skipped": "已存在", "failed": "失败",
                    "cancelled": "已取消",
                }.get(status, status)
                if res.get("output"):
                    item["output"] = res["output"]
                    item["output_lb"].configure(text=res["output"])
                elif res.get("error"):
                    item["output_lb"].configure(text=res["error"][:120])
                item["status_lb"].configure(text=item["status"])
            remaining = max(0, self.total_count - self.done_count)
            self.status_lb.configure(text=f"进度 {self.done_count}/{self.total_count}，剩余 {remaining}")

    def _done(self, results):
        self.busy = False
        self.start_btn.configure(state="normal", text="开始转换")
        self.cancel_btn.configure(state="disabled")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.open_dir_btn):
            w.configure(state="normal")
        ok = sum(1 for r in results if r.get("status") == "done")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        failed = sum(1 for r in results if r.get("status") == "failed")
        cancelled = sum(1 for r in results if r.get("status") == "cancelled")
        output_dir = self.out_dir_entry.get().strip().strip('"') or DEFAULT_OUTPUT_DIR
        self.status_lb.configure(
            text=f"完成: 生成 {ok}，已存在 {skipped}，失败 {failed}，取消 {cancelled}")
        self.pb.set(self.done_count / max(1, self.total_count))
        if failed:
            messagebox.showwarning(
                "部分失败",
                f"生成 {ok} 个，已存在 {skipped} 个，失败 {failed} 个\n\n"
                f"生成的 JPG 位于:\n{output_dir}")
        elif ok or skipped:
            messagebox.showinfo(
                "转换完成",
                f"生成 {ok} 个，已存在 {skipped} 个\n\n"
                f"生成的 JPG 位于:\n{output_dir}\n\n"
                "审图完成后可删除该文件夹释放空间。")
        elif cancelled:
            messagebox.showinfo("已停止", f"已取消 {cancelled} 个任务")

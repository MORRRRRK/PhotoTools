"""proxy_ui.py - 视频代理生成界面 (V5)"""

import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .proxy import (
    FPS_OPTIONS,
    VIDEO_EXTENSIONS,
    delete_proxies,
    estimate_proxy_size,
    find_ffmpeg,
    find_proxy,
    generate_proxy_batch,
    get_proxy_output_dir,
    get_proxy_path,
)
from .utils import format_size, open_file_in_explorer


class ProxyTab(ctk.CTkFrame):
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
        self.clear_btn = ctk.CTkButton(top, text="清空列表", width=90, height=32,
                                       font=F(13), command=self._clear)
        self.clear_btn.pack(side="left", padx=5)

        ctk.CTkLabel(top, text="分辨率:", font=F(13)).pack(side="left", padx=(20, 4))
        self.res_opt = ctk.CTkOptionMenu(
            top, values=["1080p", "2.7K", "4K"], width=90,
            command=lambda _: self._on_format_change())
        self.res_opt.set(self.app.config.get("proxy_resolution", "1080p"))
        self.res_opt.pack(side="left", padx=3)

        ctk.CTkLabel(top, text="帧率:", font=F(13)).pack(side="left", padx=(12, 4))
        self.fps_opt = ctk.CTkOptionMenu(
            top, values=FPS_OPTIONS, width=80,
            command=lambda _: self._on_format_change())
        self.fps_opt.set(str(self.app.config.get("proxy_fps", "60")))
        self.fps_opt.pack(side="left", padx=3)

        ctk.CTkLabel(top, text="并行:", font=F(13)).pack(side="left", padx=(12, 4))
        self.worker_opt = ctk.CTkOptionMenu(top, values=["1", "2"], width=60)
        self.worker_opt.set(str(self.app.config.get("proxy_max_workers", 1)))
        self.worker_opt.pack(side="left", padx=3)

        self.start_btn = ctk.CTkButton(top, text="生成代理", width=110, height=32,
                                       font=F(14, True), command=self._start,
                                       fg_color="#1f6feb", hover_color="#1750a9")
        self.start_btn.pack(side="right", padx=5)
        self.cancel_btn = ctk.CTkButton(top, text="停止生成", width=100, height=32,
                                        font=F(13), command=self._cancel,
                                        state="disabled", fg_color="#c0392b",
                                        hover_color="#96281b")
        self.cancel_btn.pack(side="right", padx=5)

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
        ctk.CTkLabel(head, text="视频文件", width=260, anchor="w",
                     font=F(13, True)).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(head, text="状态", width=140, anchor="w",
                     font=F(13, True)).grid(row=0, column=2, padx=4)
        ctk.CTkLabel(head, text="代理文件", width=260, anchor="w",
                     font=F(13, True)).grid(row=0, column=3, padx=4)
        ctk.CTkLabel(head, text="预计大小", width=100, anchor="w",
                     font=F(13, True)).grid(row=0, column=4, padx=4)

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
        self.total_est_lb = ctk.CTkLabel(bottom, text="预计总大小: -", anchor="w", font=F(12))
        self.total_est_lb.grid(row=3, column=0, columnspan=4, sticky="ew", padx=8)

        self.open_dir_btn = ctk.CTkButton(bottom, text="打开代理文件夹", width=130, height=30,
                                          font=F(12), command=self._open_proxy_dir)
        self.open_dir_btn.grid(row=4, column=0, sticky="w", padx=8, pady=4)
        ctk.CTkButton(bottom, text="代理生成失败点击重试", width=210, height=30,
                      font=F(12), command=self._retry_failed).grid(
                          row=4, column=1, sticky="w", padx=5, pady=4)
        ctk.CTkButton(bottom, text="删除选中代理", width=130, height=30,
                      font=F(12), fg_color="#c0392b", hover_color="#96281b",
                      command=self._delete_selected).grid(
                          row=4, column=2, sticky="e", padx=5, pady=4)
        ctk.CTkButton(bottom, text="删除全部代理", width=130, height=30,
                      font=F(12), fg_color="#c0392b", hover_color="#96281b",
                      command=self._delete_all).grid(
                          row=4, column=3, sticky="e", padx=8, pady=4)

    def add_files(self, paths):
        self._add_paths(paths)

    def _add_files(self):
        exts = " ".join(f"*.{e.lstrip('.')}" for e in sorted(VIDEO_EXTENSIONS))
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
                if Path(f).suffix.lower() in VIDEO_EXTENSIONS:
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
            if Path(path).suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            existing.add(key)
            item = {
                "path": path,
                "var": ctk.BooleanVar(value=False),
                "row": None,
                "status_lb": None,
                "proxy_lb": None,
                "size_lb": None,
                "proxy": "",
                "status": "待生成",
            }
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=1)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkCheckBox(row, text="", variable=item["var"], width=34,
                             font=self.F(12)).grid(row=0, column=0, padx=(4, 2))
            name_lb = ctk.CTkLabel(row, text=os.path.basename(path), width=260,
                                   anchor="w", font=self.F(12))
            name_lb.grid(row=0, column=1, sticky="ew", padx=2)
            item["status_lb"] = ctk.CTkLabel(row, text="待生成", width=140,
                                             anchor="w", font=self.F(12))
            item["status_lb"].grid(row=0, column=2, padx=4)
            item["proxy_lb"] = ctk.CTkLabel(row, text="-", width=260,
                                            anchor="w", font=self.F(11))
            item["proxy_lb"].grid(row=0, column=3, padx=4)
            item["size_lb"] = ctk.CTkLabel(row, text="-", width=100,
                                           anchor="w", font=self.F(11))
            item["size_lb"].grid(row=0, column=4, padx=4)
            item["row"] = row
            self.items.append(item)
            self._refresh_item(item)
            added += 1
        if added:
            self.status_lb.configure(text=f"已添加 {added} 个视频")
            self._refresh_estimates()
        else:
            self.status_lb.configure(text="没有新增视频")

    @staticmethod
    def _item_key(path):
        return os.path.normcase(os.path.abspath(path))

    def _refresh_item(self, item):
        proxy = find_proxy(item["path"])
        item["proxy"] = proxy or ""
        if proxy:
            item["status"] = "已有代理"
        elif not item.get("status") or item["status"] in ("待生成", "已有代理"):
            item["status"] = "待生成"
        item["status_lb"].configure(text=item["status"])
        item["proxy_lb"].configure(text=os.path.basename(proxy) if proxy else "-")

    def _refresh_proxy_paths(self):
        for item in self.items:
            self._refresh_item(item)

    def _on_format_change(self):
        self._refresh_proxy_paths()
        self._refresh_estimates()

    def _refresh_estimates(self):
        items = list(self.items)
        res = self.res_opt.get()
        fps = self.fps_opt.get()
        seq = getattr(self, "_est_seq", 0) + 1
        self._est_seq = seq

        def worker():
            rows = []
            total = 0
            for item in items:
                if getattr(self, "_est_seq", 0) != seq:
                    return
                est = estimate_proxy_size(item["path"], res, fps)
                rows.append((item, est))
                total += est

            def apply():
                if getattr(self, "_est_seq", 0) != seq:
                    return
                for item, est in rows:
                    item["size_lb"].configure(text=format_size(est) if est else "-")
                self.total_est_lb.configure(
                    text=f"预计总大小: {format_size(total) if total else '-'}")

            self.after(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_all(self):
        v = self.sel_all_var.get()
        for item in self.items:
            item["var"].set(v)

    def _clear(self):
        if self.busy:
            return
        for item in self.items:
            item["row"].destroy()
        self.items.clear()
        self.pb.set(0)
        self.current_lb.configure(text="当前: -")
        self.status_lb.configure(text="就绪")
        self.total_est_lb.configure(text="预计总大小: -")

    def _start(self):
        if self.busy:
            return
        paths = [i["path"] for i in self.items if i["var"].get()]
        if not paths:
            messagebox.showinfo("提示", "请先勾选要生成代理的视频")
            return
        if not find_ffmpeg():
            messagebox.showerror("缺少 ffmpeg", "未找到 ffmpeg.exe，请将 ffmpeg 放到 assets 目录后重试")
            return

        self.busy = True
        self.done_count = 0
        self.total_count = len(paths)
        self.cancel_event.clear()
        self.start_btn.configure(state="disabled", text="生成中...")
        self.cancel_btn.configure(state="normal")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.res_opt, self.fps_opt, self.worker_opt):
            w.configure(state="disabled")
        self.pb.set(0)
        self.status_lb.configure(text=f"队列: {self.total_count} 个文件")
        resolution = self.res_opt.get()
        fps = self.fps_opt.get()
        self.app.config["proxy_max_workers"] = int(self.worker_opt.get())
        self.app.config["proxy_resolution"] = resolution
        self.app.config["proxy_fps"] = fps

        for item in self.items:
            if item["path"] in paths:
                item["status"] = "排队中"
                item["status_lb"].configure(text="排队中")

        def worker():
            def cb(event):
                self.after(0, lambda: self._on_event(event))

            results = generate_proxy_batch(
                paths, resolution, fps, self.app.config, self.cancel_event, cb)
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
                item["status"] = "生成中"
                item["status_lb"].configure(text="生成中 0%")
            self.current_lb.configure(text="当前: " + os.path.basename(path))
        elif kind == "progress":
            pct = int(float(event.get("percent", 0) or 0) * 100)
            if item:
                item["status"] = "生成中"
                item["status_lb"].configure(text=f"生成中 {pct}%")
        elif kind == "done":
            self.done_count += 1
            self.pb.set(self.done_count / max(1, self.total_count))
            res = event.get("result", {})
            status = res.get("status", "failed")
            if item:
                item["status"] = {
                    "done": "完成", "failed": "失败", "cancelled": "已取消",
                    "skipped": "完成",
                }.get(status, status)
                if status == "done":
                    item["proxy"] = res.get("proxy", "")
                    item["proxy_lb"].configure(
                        text=os.path.basename(res.get("proxy", "")) if res.get("proxy") else "-")
                elif status == "failed" and res.get("error"):
                    item["proxy_lb"].configure(text=res["error"][:120])
                item["status_lb"].configure(text=item["status"])
            remaining = max(0, self.total_count - self.done_count)
            self.status_lb.configure(
                text=f"进度 {self.done_count}/{self.total_count}，剩余 {remaining}")

    def _done(self, results):
        self.busy = False
        self.start_btn.configure(state="normal", text="生成代理")
        self.cancel_btn.configure(state="disabled")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.res_opt, self.fps_opt, self.worker_opt):
            w.configure(state="normal")
        ok = sum(1 for r in results if r.get("status") == "done")
        failed = sum(1 for r in results if r.get("status") == "failed")
        cancelled = sum(1 for r in results if r.get("status") == "cancelled")
        if ok == 0 and failed == 0 and cancelled > 0:
            self.status_lb.configure(text=f"已停止: 已取消 {cancelled} 个任务")
        else:
            self.status_lb.configure(text=f"完成: 成功 {ok}，失败 {failed}，取消 {cancelled}")
        self.pb.set(self.done_count / max(1, self.total_count))
        if failed:
            messagebox.showwarning("部分失败", f"成功 {ok} 个，失败 {failed} 个\n可点击“代理生成失败点击重试”重新生成")

    def _open_proxy_dir(self):
        items = [i for i in self.items if i["var"].get()] or list(self.items)
        if not items:
            messagebox.showinfo("提示", "请先添加视频文件")
            return
        item = items[0]
        if item["proxy"] and Path(item["proxy"]).parent.exists():
            target = Path(item["proxy"]).parent
        else:
            target = get_proxy_output_dir(item["path"], self.app.config)
        if not target.exists():
            messagebox.showinfo("提示", "代理文件夹尚未生成")
            return
        open_file_in_explorer(str(target))

    def _retry_failed(self):
        if self.busy:
            return
        failed = [i for i in self.items if i["status"] == "失败"]
        if not failed:
            messagebox.showinfo("提示", "没有失败项")
            return
        for item in failed:
            item["var"].set(True)
        self._start()

    def _delete_selected(self):
        self._delete_items([i for i in self.items if i["var"].get() and i["proxy"]])

    def _delete_all(self):
        self._delete_items([i for i in self.items if i["proxy"]])

    def _delete_items(self, items):
        if not items or self.busy:
            return
        paths = [i["proxy"] for i in items]
        if not messagebox.askyesno(
                "确认删除代理",
                f"将 {len(paths)} 个代理文件移入回收站？\n原片不会被删除。"):
            return
        ok, fail, fails = delete_proxies(paths)
        for item in items:
            item["proxy"] = ""
            item["status"] = "代理已删除"
            item["status_lb"].configure(text="代理已删除")
            item["proxy_lb"].configure(text="-")
        self.status_lb.configure(text=f"删除完成: 成功 {ok}，失败 {fail}")
        self._refresh_estimates()
        if fail:
            messagebox.showwarning("删除失败", "\n".join(fails[:8]))

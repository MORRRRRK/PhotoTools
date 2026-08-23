"""dynamic_extract_ui.py - 动态照片提取界面 (V6)"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .dynamic_extract import (
    VIDEO_FOLDER_NAME,
    collect_dynamic_folders,
    extract_dynamic_batch,
    is_dynamic_folder,
    list_media,
)


class DynamicExtractTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.folder_items = []
        self.row_widgets = []
        self.busy = False
        fs = float(self.app.config.get("font_scale", 1.0) or 1.0)

        def F(size, bold=False):
            s = max(8, int(size * fs))
            return ("", s, "bold") if bold else ("", s)

        self.F = F
        self._build_ui()

    def _build_ui(self):
        F = self.F
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 5))

        self.batch_btn = ctk.CTkButton(top, text="批量添加文件夹", width=130, height=32,
                                        font=F(13), command=self._batch_add)
        self.batch_btn.pack(side="left", padx=5)
        self.add_btn = ctk.CTkButton(top, text="添加单个文件夹", width=120, height=32,
                                     font=F(13), command=self._add_single)
        self.add_btn.pack(side="left", padx=5)
        self.sel_all_btn = ctk.CTkButton(top, text="全选", width=70, height=32,
                                         font=F(13), command=self._select_all)
        self.sel_all_btn.pack(side="left", padx=5)
        self.sel_none_btn = ctk.CTkButton(top, text="全不选", width=70, height=32,
                                          font=F(13), command=self._select_none)
        self.sel_none_btn.pack(side="left", padx=5)
        self.remove_btn = ctk.CTkButton(top, text="移除选中", width=90, height=32,
                                        font=F(13), command=self._remove_selected)
        self.remove_btn.pack(side="left", padx=5)
        self.clear_btn = ctk.CTkButton(top, text="清空列表", width=90, height=32,
                                       font=F(13), command=self._clear)
        self.clear_btn.pack(side="left", padx=5)
        self.count_lb = ctk.CTkLabel(top, text="未添加文件夹", font=F(12))
        self.count_lb.pack(side="left", padx=15)

        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="x", padx=10, pady=5)
        header = ctk.CTkFrame(list_frame, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=(6, 2))
        ctk.CTkLabel(header, text="文件夹名称", font=F(12, True), width=270, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="文件数", font=F(12, True), width=100, anchor="w").pack(side="left")
        ctk.CTkLabel(header, text="完整路径", font=F(12, True), anchor="w").pack(side="left", fill="x", expand=True)
        self.list_body = ctk.CTkScrollableFrame(list_frame, height=170)
        self.list_body.pack(fill="x", padx=6, pady=(0, 6))

        opt = ctk.CTkFrame(self)
        opt.pack(fill="x", padx=10, pady=5)
        opt.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(opt, text="动态视频存储目录:", font=F(13)).grid(row=0, column=0, padx=6, pady=5, sticky="w")
        self.video_dir_entry = ctk.CTkEntry(opt, height=30)
        self.video_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.video_dir_entry.insert(0, self.app.config.get("dynamic_video_dir", ""))
        self.browse_btn = ctk.CTkButton(opt, text="浏览", width=70, height=30,
                                        font=F(13), command=self._browse_video_dir)
        self.browse_btn.grid(row=0, column=2, padx=5, pady=5)
        self.open_dir_btn = ctk.CTkButton(opt, text="打开目录", width=80, height=30,
                                          font=F(13), command=self._open_video_dir)
        self.open_dir_btn.grid(row=0, column=3, padx=5, pady=5)

        self.move_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt, text="移动文件（剪切，源文件夹中不保留）", variable=self.move_var,
                        font=F(12)).grid(row=1, column=0, columnspan=2, padx=6, pady=4, sticky="w")
        ctk.CTkLabel(opt, text="照片提取到动态图文件夹的上一级，视频统一放入“动态视频存储”",
                     font=F(11), text_color="#7f8c8d").grid(row=1, column=2, columnspan=2,
                                                            padx=6, pady=4, sticky="w")

        action = ctk.CTkFrame(self)
        action.pack(fill="x", padx=10, pady=5)
        self.start_btn = ctk.CTkButton(action, text="提取照片", width=140, height=34,
                                       font=F(15, True), command=self._start_extract,
                                       fg_color="#1f6feb", hover_color="#1750a9")
        self.start_btn.pack(side="left", padx=8)
        self.pb = ctk.CTkProgressBar(action, width=320, height=14)
        self.pb.pack(side="left", padx=10)
        self.pb.set(0)
        self.status_lb = ctk.CTkLabel(action, text="就绪", font=F(12))
        self.status_lb.pack(side="left", padx=8)

        result = ctk.CTkFrame(self)
        result.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        result.grid_columnconfigure(0, weight=1)
        result.grid_rowconfigure(0, weight=1)
        self.result_text = ctk.CTkTextbox(result, wrap="word", font=F(12))
        self.result_text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.result_text.insert("0.0", "提取结果将在这里显示")
        self.result_text.configure(state="disabled")

        self._render_list()

    def _selected_count(self):
        return sum(1 for item in self.folder_items if item["var"].get())

    def _render_list(self):
        for w in self.row_widgets:
            w.destroy()
        self.row_widgets.clear()
        F = self.F
        for item in self.folder_items:
            row = ctk.CTkFrame(self.list_body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            name = os.path.basename(item["path"]) or item["path"]
            ctk.CTkCheckBox(row, text=name, variable=item["var"], font=F(12),
                            width=270, anchor="w").pack(side="left", padx=(6, 4))
            jpgs, mp4s = list_media(item["path"])
            ctk.CTkLabel(row, text=f"JPG {len(jpgs)} / MP4 {len(mp4s)}",
                         font=F(11), width=100).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=item["path"], font=F(11), anchor="w").pack(
                side="left", fill="x", expand=True, padx=4)
            self.row_widgets.append(row)
        self.count_lb.configure(text=f"共 {len(self.folder_items)} 个文件夹，已勾选 {self._selected_count()} 个")

    def _add_common(self, folders, parent):
        existing = {os.path.normcase(os.path.abspath(f["path"])) for f in self.folder_items}
        added = 0
        for folder in folders:
            key = os.path.normcase(os.path.abspath(folder))
            if key not in existing:
                self.folder_items.append({"path": folder, "var": tk.BooleanVar(value=True)})
                existing.add(key)
                added += 1
        self._render_list()
        if not self.video_dir_entry.get().strip():
            self._set_video_dir(os.path.join(parent, VIDEO_FOLDER_NAME))
        return added

    def _batch_add(self):
        parent = filedialog.askdirectory(title="选择包含动态照片文件夹的目录")
        if not parent:
            return
        folders = collect_dynamic_folders(parent)
        if not folders:
            messagebox.showinfo("提示", "所选目录下没有找到同时包含 JPG 和 MP4 的动态照片文件夹")
            return
        added = self._add_common(folders, parent)
        messagebox.showinfo("添加完成", f"找到 {len(folders)} 个动态照片文件夹，本次新增 {added} 个")

    def _add_single(self):
        folder = filedialog.askdirectory(title="选择动态照片文件夹（包含 JPG 和 MP4）")
        if not folder:
            return
        if not is_dynamic_folder(folder):
            messagebox.showwarning("提示", "该文件夹内未同时找到 JPG 和 MP4，可能不是动态照片文件夹")
            return
        self._add_common([folder], os.path.dirname(os.path.abspath(folder)) or folder)

    def _select_all(self):
        for item in self.folder_items:
            item["var"].set(True)
        self._render_list()

    def _select_none(self):
        for item in self.folder_items:
            item["var"].set(False)
        self._render_list()

    def _remove_selected(self):
        self.folder_items = [item for item in self.folder_items if not item["var"].get()]
        self._render_list()

    def _clear(self):
        self.folder_items = []
        self._render_list()

    def _set_video_dir(self, path):
        self.video_dir_entry.delete(0, "end")
        self.video_dir_entry.insert(0, path)
        try:
            from .main import save_config
            self.app.config["dynamic_video_dir"] = path
            save_config(self.app.config)
        except Exception:
            pass

    def _browse_video_dir(self):
        folder = filedialog.askdirectory(title="选择动态视频存储目录")
        if folder:
            self._set_video_dir(folder)

    def _open_video_dir(self):
        video_dir = self.video_dir_entry.get().strip().strip('"')
        if not video_dir:
            messagebox.showinfo("提示", "请先设置动态视频存储目录")
            return
        if os.path.isdir(video_dir):
            os.startfile(video_dir)
        else:
            messagebox.showwarning("提示", "目录不存在，请先执行提取照片")

    def _set_result_text(self, text):
        self.result_text.configure(state="normal")
        self.result_text.delete("0.0", "end")
        self.result_text.insert("0.0", text)
        self.result_text.configure(state="disabled")

    def _set_buttons_state(self, state):
        for btn in (self.batch_btn, self.add_btn, self.sel_all_btn, self.sel_none_btn,
                    self.remove_btn, self.clear_btn, self.browse_btn, self.open_dir_btn):
            btn.configure(state=state)
        self.start_btn.configure(state=state)

    def _on_progress(self, done, total, folder):
        self.pb.set(done / max(total, 1))
        self.status_lb.configure(text=f"正在提取 {done}/{total}: {os.path.basename(folder)}")

    def _start_extract(self):
        if self.busy:
            return
        selected = [item["path"] for item in self.folder_items if item["var"].get()]
        if not selected:
            messagebox.showwarning("提示", "请先勾选要提取的动态照片文件夹")
            return
        video_dir = self.video_dir_entry.get().strip().strip('"')
        if not video_dir:
            video_dir = os.path.join(os.path.dirname(os.path.abspath(selected[0])), VIDEO_FOLDER_NAME)
            self._set_video_dir(video_dir)
        move = self.move_var.get()
        try:
            os.makedirs(video_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建动态视频存储目录:\n{e}")
            return
        self.busy = True
        self._set_buttons_state("disabled")
        self.pb.set(0)
        self.status_lb.configure(text="正在提取...")
        self._set_result_text("正在提取，请稍候...")

        def worker():
            def cb(done, total, folder):
                self.after(0, lambda: self._on_progress(done, total, folder))
            try:
                result = extract_dynamic_batch(selected, video_dir, move=move, progress_callback=cb)
                self.after(0, lambda: self._on_done(result))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, result):
        self.busy = False
        self._set_buttons_state("normal")
        self.pb.set(1)
        self.status_lb.configure(text="提取完成")
        ok, skip, error = result["ok"], result["skip"], result["error"]
        text = (f"完成：成功 {ok}，跳过 {skip}，失败 {error}"
                f"（共 {result['folders']} 个文件夹）\n"
                f"视频存储目录: {result['video_dir']}\n\n")
        for r in result["results"]:
            text += f"== {os.path.basename(r['folder'])} ==\n"
            for item in r["items"]:
                text += f"[{item['status']}] {item['kind']}: {os.path.basename(item['source'])} -> {item['dest']}"
                if item["message"]:
                    text += f"（{item['message']}）"
                text += "\n"
        self._set_result_text(text)
        messagebox.showinfo("提取完成", f"成功 {ok} 个文件，跳过 {skip} 个，失败 {error} 个")

    def _on_error(self, msg):
        self.busy = False
        self._set_buttons_state("normal")
        self.pb.set(0)
        self.status_lb.configure(text="提取失败")
        self._set_result_text(f"提取失败:\n{msg}")
        messagebox.showerror("错误", msg)

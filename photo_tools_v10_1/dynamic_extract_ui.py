"""dynamic_extract_ui.py - 动态照片提取界面 (V6.2)"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .dynamic_extract import (
    VIDEO_FOLDER_NAME,
    collect_dynamic_targets,
    extract_dynamic_batch,
    list_media,
)


class DynamicExtractTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.folder_items = []
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
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(list_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ctk.CTkLabel(hdr, text="已导入动态图文件夹（可多选）", font=F(12, True)).pack(side="left")
        self.sel_lb = ctk.CTkLabel(hdr, text="", font=F(11), text_color="#7f8c8d")
        self.sel_lb.pack(side="right", padx=4)

        body = ctk.CTkFrame(list_frame, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.listbox = tk.Listbox(body, selectmode=tk.EXTENDED, height=12,
                                  bg="#2b2b2b", fg="#e0e0e0",
                                  selectbackground="#1f538d",
                                  font=("Microsoft YaHei", 10),
                                  highlightthickness=0, borderwidth=0)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scroll = tk.Scrollbar(body, orient="vertical", command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._update_count())

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
        ctk.CTkCheckBox(opt, text="剪切文件（从原始文件夹移出）", variable=self.move_var,
                        font=F(12)).grid(row=1, column=0, columnspan=2, padx=6, pady=4, sticky="w")
        self.delete_originals_var = tk.BooleanVar(value=True)
        self.delete_originals_cb = ctk.CTkCheckBox(
            opt, text="删除已清空的原始动态图文件夹（删除前自动确认文件夹为空）",
            variable=self.delete_originals_var, font=F(12))
        self.delete_originals_cb.grid(row=2, column=0, columnspan=2, padx=6, pady=4, sticky="w")
        ctk.CTkLabel(opt, text="照片导出到上一级，视频统一放入“动态视频存储”",
                     font=F(11), text_color="#7f8c8d").grid(row=1, column=2, columnspan=2,
                                                            padx=6, pady=4, sticky="w")

        action = ctk.CTkFrame(self)
        action.pack(fill="x", padx=10, pady=5)
        self.start_btn = ctk.CTkButton(action, text="开始导出", width=140, height=34,
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
        self.result_text.insert("0.0", "导出结果将在这里显示")
        self.result_text.configure(state="disabled")

        self._refresh_listbox()

    def _selected_count(self):
        return len(self.listbox.curselection())

    def _update_count(self):
        total = len(self.folder_items)
        selected = self._selected_count()
        self.count_lb.configure(text=f"共 {total} 个文件夹，已选择 {selected} 个")
        self.sel_lb.configure(text=f"已选择 {selected} / {total}")

    def _refresh_listbox(self):
        self.listbox.delete(0, "end")
        for item in self.folder_items:
            name = os.path.basename(item["path"]) or item["path"]
            line = f"{name}  |  {item['path']}  |  JPG {item.get('jpgs', 0)} / MP4 {item.get('mp4s', 0)}"
            self.listbox.insert("end", line)
        self._update_count()

    def _add_common(self, items):
        existing = {os.path.normcase(os.path.abspath(f["path"])) for f in self.folder_items}
        added = 0
        for item in items:
            key = os.path.normcase(os.path.abspath(item["path"]))
            if key not in existing:
                self.folder_items.append(item)
                existing.add(key)
                added += 1
        self._refresh_listbox()
        if not self.video_dir_entry.get().strip() and self.folder_items:
            first = self.folder_items[0]["path"]
            parent = os.path.dirname(os.path.abspath(first))
            self._set_video_dir(os.path.join(parent, VIDEO_FOLDER_NAME))
        return added

    def _batch_add(self):
        parent = filedialog.askdirectory(title="选择包含动态照片文件夹的目录")
        if not parent:
            return
        items = collect_dynamic_targets(parent)
        if not items:
            messagebox.showinfo("提示", "所选目录及其子目录下没有找到同时包含 JPG 和 MP4 的动态照片文件夹")
            return
        added = self._add_common(items)
        messagebox.showinfo("添加完成", f"找到 {len(items)} 个动态照片文件夹，本次新增 {added} 个")

    def _add_single(self):
        folder = filedialog.askdirectory(title="选择动态照片文件夹（包含 JPG 和 MP4）")
        if not folder:
            return
        items = collect_dynamic_targets(folder)
        if not items:
            messagebox.showwarning("提示", "所选文件夹及其子目录下未找到同时包含 JPG 和 MP4 的动态照片文件夹")
            return
        added = self._add_common(items)
        messagebox.showinfo("添加完成", f"找到 {len(items)} 个动态照片文件夹，本次新增 {added} 个")

    def _selected_paths(self):
        return [self.folder_items[i]["path"] for i in self.listbox.curselection()]

    def _select_all(self):
        if self.folder_items:
            self.listbox.selection_set(0, "end")
        self._update_count()

    def _select_none(self):
        self.listbox.selection_clear(0, "end")
        self._update_count()

    def _remove_selected(self):
        indexes = set(self.listbox.curselection())
        if indexes:
            self.folder_items = [item for i, item in enumerate(self.folder_items) if i not in indexes]
            self._refresh_listbox()

    def _clear(self):
        self.folder_items = []
        self._refresh_listbox()

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
            messagebox.showwarning("提示", "目录不存在，请先执行导出")

    def _set_result_text(self, text):
        self.result_text.configure(state="normal")
        self.result_text.delete("0.0", "end")
        self.result_text.insert("0.0", text)
        self.result_text.configure(state="disabled")

    def _set_buttons_state(self, state):
        for btn in (self.batch_btn, self.add_btn, self.sel_all_btn, self.sel_none_btn,
                    self.remove_btn, self.clear_btn, self.browse_btn, self.open_dir_btn):
            btn.configure(state=state)
        self.delete_originals_cb.configure(state=state)
        self.start_btn.configure(state=state)

    def _on_progress(self, done, total, folder):
        self.pb.set(done / max(total, 1))
        self.status_lb.configure(text=f"正在导出 {done}/{total}: {os.path.basename(folder)}")

    def _start_extract(self):
        if self.busy:
            return
        selected = self._selected_paths()
        if not selected:
            messagebox.showwarning("提示", "请先在列表中选择要导出的动态照片文件夹")
            return
        video_dir = self.video_dir_entry.get().strip().strip('"')
        if not video_dir:
            video_dir = os.path.join(os.path.dirname(os.path.abspath(selected[0])), VIDEO_FOLDER_NAME)
            self._set_video_dir(video_dir)
        move = self.move_var.get()
        delete_originals = self.delete_originals_var.get()
        try:
            os.makedirs(video_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法创建动态视频存储目录:\n{e}")
            return
        self.busy = True
        self._set_buttons_state("disabled")
        self.pb.set(0)
        self.status_lb.configure(text="正在导出...")
        self._set_result_text("正在导出，请稍候...")

        def worker():
            def cb(done, total, folder):
                self.after(0, lambda: self._on_progress(done, total, folder))
            try:
                result = extract_dynamic_batch(
                    selected, video_dir, move=move,
                    delete_originals=delete_originals, progress_callback=cb)
                self.after(0, lambda: self._on_done(result))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, result):
        self.busy = False
        self._set_buttons_state("normal")
        self.pb.set(1)
        self.status_lb.configure(text="导出完成")
        ok, skip, error = result["ok"], result["skip"], result["error"]
        text = (f"完成：成功 {ok}，跳过 {skip}，失败 {error}"
                f"（共 {result['folders']} 个文件夹）\n"
                f"视频存储目录: {result['video_dir']}\n\n")
        deleted_count = 0
        for r in result["results"]:
            text += f"== {os.path.basename(r['folder'])} ==\n"
            for item in r["items"]:
                text += f"[{item['status']}] {item['kind']}: {os.path.basename(item['source'])} -> {item['dest']}"
                if item["message"]:
                    text += f"（{item['message']}）"
                text += "\n"
            deletion = r.get("deletion", {})
            if deletion.get("attempted") and deletion.get("deleted"):
                deleted_count += 1
                text += "[已删除] 原始动态图文件夹已确认清空并删除\n"
            elif deletion.get("message"):
                text += f"[未删除] {deletion['message']}\n"
        self._set_result_text(text)

        deleted_paths = {
            os.path.normcase(os.path.abspath(r["folder"]))
            for r in result["results"]
            if r.get("deletion", {}).get("deleted")
        }
        if deleted_paths:
            self.folder_items = [
                item for item in self.folder_items
                if os.path.normcase(os.path.abspath(item["path"])) not in deleted_paths
            ]
        for item in self.folder_items:
            jpgs, mp4s = list_media(item["path"])
            item["jpgs"] = len(jpgs)
            item["mp4s"] = len(mp4s)
        self._refresh_listbox()

        messagebox.showinfo("导出完成", f"成功 {ok} 个文件，跳过 {skip} 个，失败 {error} 个\n已删除空文件夹 {deleted_count} 个")
        if result.get("aborted"):
            messagebox.showwarning("已停止", f"{result['abort_message']}\n\n请手动处理该文件夹后再继续。")

    def _on_error(self, msg):
        self.busy = False
        self._set_buttons_state("normal")
        self.pb.set(0)
        self.status_lb.configure(text="导出失败")
        self._set_result_text(f"导出失败:\n{msg}")
        messagebox.showerror("错误", msg)

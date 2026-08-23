"""gallery_ui.py - 作品展示界面 (V9)"""

import math
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .gallery import (
    SUPPORTED_EXTENSIONS,
    UNSUPPORTED_IMAGE_EXTENSIONS,
    clean_cache,
    collect_image_files,
    get_cache_dir,
    make_preview,
    make_thumbnail,
    read_image_info,
)
from .utils import format_size

CELL_W = 180
CELL_H = 160
CELL_PAD = 8


class GalleryTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.items = []
        self.busy = False
        self.scanning = False
        self.cancel_event = threading.Event()
        self.selected_index = None
        self.zoom = 1.0
        self._preview_pil = None
        self._cell_widgets = {}
        self._render_job = None
        self.cache_dir = get_cache_dir()
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

        self.add_file_btn = ctk.CTkButton(top, text="添加图片", width=100, height=32,
                                          font=F(13), command=self._add_files)
        self.add_file_btn.pack(side="left", padx=5)
        self.add_folder_btn = ctk.CTkButton(top, text="添加文件夹", width=110, height=32,
                                            font=F(13), command=self._add_folder)
        self.add_folder_btn.pack(side="left", padx=5)
        self.remove_btn = ctk.CTkButton(top, text="移除选中", width=100, height=32,
                                        font=F(13), command=self._remove_selected)
        self.remove_btn.pack(side="left", padx=5)
        self.clear_btn = ctk.CTkButton(top, text="清空列表", width=100, height=32,
                                       font=F(13), command=self._clear)
        self.clear_btn.pack(side="left", padx=5)
        self.count_lb = ctk.CTkLabel(top, text="共 0 张图片", font=F(12))
        self.count_lb.pack(side="left", padx=15)
        self.cancel_btn = ctk.CTkButton(top, text="取消导入", width=100, height=32,
                                        font=F(13), command=self._cancel,
                                        state="disabled", fg_color="#c0392b",
                                        hover_color="#96281b")
        self.cancel_btn.pack(side="right", padx=5)

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=8, pady=4)
        main.grid_columnconfigure(0, weight=3, uniform="gallery")
        main.grid_columnconfigure(1, weight=2, uniform="gallery")
        main.grid_columnconfigure(2, weight=1, uniform="gallery")
        main.grid_rowconfigure(0, weight=1)

        # 左侧：懒加载缩略图网格
        left = ctk.CTkFrame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        self.grid_canvas = tk.Canvas(left, bg="#1a1a1a", highlightthickness=0)
        self.grid_canvas.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        grid_scroll = tk.Scrollbar(left, orient="vertical", command=self.grid_canvas.yview)
        grid_scroll.grid(row=0, column=1, sticky="ns", pady=4)
        self.grid_canvas.configure(yscrollcommand=grid_scroll.set)
        self.grid_inner = tk.Frame(self.grid_canvas, bg="#1a1a1a")
        self.grid_canvas.create_window((0, 0), window=self.grid_inner, anchor="nw")
        self.grid_canvas.bind("<Configure>", lambda e: self._on_grid_configure())
        self.grid_canvas.bind("<MouseWheel>", self._on_wheel)

        # 中间：放大预览
        center = ctk.CTkFrame(main)
        center.grid(row=0, column=1, sticky="nsew", padx=4)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(center, text="点击左侧缩略图查看大图",
                                          font=F(13), text_color="#7f8c8d")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.preview_label.bind("<MouseWheel>", self._on_preview_wheel)
        zoom_bar = ctk.CTkFrame(center, fg_color="transparent")
        zoom_bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        ctk.CTkButton(zoom_bar, text="缩小", width=60, height=28, font=F(12),
                      command=lambda: self._zoom_by(0.8)).pack(side="left", padx=3)
        ctk.CTkButton(zoom_bar, text="放大", width=60, height=28, font=F(12),
                      command=lambda: self._zoom_by(1.25)).pack(side="left", padx=3)
        ctk.CTkButton(zoom_bar, text="适应", width=60, height=28, font=F(12),
                      command=self._zoom_fit).pack(side="left", padx=3)
        self.zoom_lb = ctk.CTkLabel(zoom_bar, text="100%", font=F(12))
        self.zoom_lb.pack(side="left", padx=8)

        # 右侧：照片信息
        right = ctk.CTkFrame(main)
        right.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(right, text="照片信息", font=F(14, True)).pack(anchor="w", padx=10, pady=(10, 6))
        info_body = ctk.CTkFrame(right, fg_color="transparent")
        info_body.pack(fill="both", expand=True, padx=6, pady=4)
        fields = [
            ("分辨率", "resolution"),
            ("文件大小", "size"),
            ("文件格式", "format"),
            ("光圈", "aperture"),
            ("快门速度", "shutter"),
            ("ISO", "iso"),
            ("焦距", "focal"),
            ("拍摄设备", "device"),
            ("拍摄时间", "datetime"),
        ]
        self.info_labels = {}
        for i, (label, key) in enumerate(fields):
            ctk.CTkLabel(info_body, text=label, font=F(12, True),
                         anchor="w").grid(row=i, column=0, sticky="w", padx=8, pady=4)
            val = ctk.CTkLabel(info_body, text="未知", font=F(12),
                               anchor="w", wraplength=180)
            val.grid(row=i, column=1, sticky="w", padx=8, pady=4)
            self.info_labels[key] = val

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=8, pady=(0, 8))
        bottom.grid_columnconfigure(0, weight=1)
        self.pb = ctk.CTkProgressBar(bottom, height=12)
        self.pb.grid(row=0, column=0, columnspan=3, sticky="ew", padx=6, pady=(4, 2))
        self.pb.set(0)
        self.current_lb = ctk.CTkLabel(bottom, text="当前: -", anchor="w", font=F(12))
        self.current_lb.grid(row=1, column=0, columnspan=3, sticky="ew", padx=8)
        self.status_lb = ctk.CTkLabel(bottom, text="就绪", anchor="w", font=F(12))
        self.status_lb.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8)

    # ---------- 网格懒加载 ----------
    def _on_grid_configure(self):
        try:
            self.grid_inner.configure(width=max(self.grid_canvas.winfo_width(), 200))
        except Exception:
            pass
        self._schedule_render()

    def _schedule_render(self):
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
        self._render_job = self.after(30, self._render_visible)

    def _on_wheel(self, event):
        try:
            self.grid_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            self._schedule_render()
        except Exception:
            pass

    def _render_visible(self):
        self._render_job = None
        for widget in self._cell_widgets.values():
            widget.destroy()
        self._cell_widgets.clear()
        if not self.items:
            self.grid_canvas.configure(scrollregion=(0, 0, 0, 0))
            return
        try:
            canvas_w = max(self.grid_canvas.winfo_width(), 200)
            canvas_h = max(self.grid_canvas.winfo_height(), 300)
        except Exception:
            canvas_w, canvas_h = 600, 600
        cols = max(1, (canvas_w - 10) // (CELL_W + CELL_PAD))
        rows = math.ceil(len(self.items) / cols)
        total_h = rows * (CELL_H + CELL_PAD) + CELL_PAD
        self.grid_inner.configure(height=total_h)
        self.grid_canvas.configure(scrollregion=(0, 0, canvas_w, total_h))
        top = self.grid_canvas.canvasy(0)
        bottom = self.grid_canvas.canvasy(canvas_h)
        start_row = max(0, int(top // (CELL_H + CELL_PAD)) - 1)
        end_row = min(rows, int(bottom // (CELL_H + CELL_PAD)) + 1)
        for row in range(start_row, end_row):
            for col in range(cols):
                idx = row * cols + col
                if idx >= len(self.items):
                    break
                self._create_cell(idx, row, col)

    def _create_cell(self, idx, row, col):
        item = self.items[idx]
        x = CELL_PAD + col * (CELL_W + CELL_PAD)
        y = CELL_PAD + row * (CELL_H + CELL_PAD)
        selected = item.get("selected", False)
        frame = ctk.CTkFrame(
            self.grid_inner, width=CELL_W, height=CELL_H, corner_radius=8,
            fg_color="#2b2b2b",
            border_width=2 if selected else 0,
            border_color="#e0b341")
        frame.place(x=x, y=y)
        frame.pack_propagate(False)
        label = ctk.CTkLabel(frame, text="加载中...", font=self.F(11),
                             text_color="#7f8c8d")
        label.pack(fill="both", expand=True, padx=4, pady=4)
        label.bind("<Button-1>", lambda e, i=idx: self._select_item(i))
        label.bind("<MouseWheel>", self._on_wheel)

        status = item.get("status", "待生成")
        if status == "不支持":
            label.configure(text="不支持")
        elif item.get("thumb_path") and os.path.exists(item["thumb_path"]):
            try:
                from PIL import Image
                img = Image.open(item["thumb_path"])
                img.thumbnail((CELL_W - 16, CELL_H - 16), Image.LANCZOS)
                ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                label.configure(image=ctk_image, text="")
                label._ctk_image = ctk_image
            except Exception:
                label.configure(text="预览失败")
        else:
            label.configure(text=status)
        self._cell_widgets[idx] = frame

    # ---------- 导入 ----------
    def _add_files(self):
        if self.busy:
            return
        exts = " ".join(
            f"*.{e.lstrip('.')}"
            for e in sorted(SUPPORTED_EXTENSIONS | UNSUPPORTED_IMAGE_EXTENSIONS)
        )
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", exts), ("所有文件", "*.*")],
        )
        if paths:
            self._add_paths(paths)
            self._start_thumbnails()

    def _add_folder(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title="选择图片文件夹")
        if not folder:
            return
        self.busy = True
        self.scanning = True
        self.cancel_event.clear()
        self._set_busy_ui(True, "正在扫描文件夹...")

        def worker():
            found = []
            err = ""
            try:
                found = collect_image_files(folder)
            except Exception as e:
                err = str(e)
            self.after(0, lambda: self._folder_scan_done(found, err))

        threading.Thread(target=worker, daemon=True).start()

    def _folder_scan_done(self, found, err):
        self.scanning = False
        self.busy = False
        if self.cancel_event.is_set():
            self._set_busy_ui(False, "已取消")
            return
        if err:
            self._set_busy_ui(False, "扫描失败")
            messagebox.showerror("扫描失败", err)
            return
        if not found:
            self._set_busy_ui(False, "未找到图片")
            messagebox.showinfo("提示", "该文件夹中没有找到图片")
            return
        self._add_paths(found)
        self._start_thumbnails()

    def _add_paths(self, paths):
        existing = {self._item_key(i["path"]) for i in self.items}
        added = 0
        for p in paths:
            path = str(p)
            key = self._item_key(path)
            if key in existing or not os.path.exists(path):
                continue
            existing.add(key)
            self.items.append({
                "path": path,
                "status": "待生成",
                "thumb_path": "",
                "info": None,
                "selected": False,
            })
            added += 1
        self._update_count()
        self._schedule_render()

    @staticmethod
    def _item_key(path):
        return os.path.normcase(os.path.abspath(path))

    def _start_thumbnails(self):
        if self.busy:
            return
        if not self.items:
            return
        self.busy = True
        self.cancel_event.clear()
        self._set_busy_ui(True, "正在生成缩略图...")
        total = len(self.items)
        done = 0

        def worker():
            nonlocal done
            for idx, item in enumerate(self.items):
                if self.cancel_event.is_set():
                    break
                if item.get("info") is not None or item.get("thumb_path"):
                    done += 1
                    self.after(0, lambda d=done, t=total, i=idx: self._thumb_progress(d, t, i))
                    continue
                info = read_image_info(item["path"])
                item["info"] = info
                if info.get("supported"):
                    thumb = make_thumbnail(item["path"], self.cache_dir)
                    item["thumb_path"] = thumb
                    item["status"] = "已导入" if thumb else "失败"
                else:
                    item["status"] = "不支持"
                done += 1
                self.after(0, lambda d=done, t=total, i=idx: self._thumb_progress(d, t, i))
            self.after(0, lambda: self._thumb_done())

        threading.Thread(target=worker, daemon=True).start()

    def _thumb_progress(self, done, total, idx):
        self.pb.set(done / max(total, 1))
        try:
            name = os.path.basename(self.items[idx]["path"])
        except Exception:
            name = "-"
        self.current_lb.configure(text=f"当前: {name}")
        self.status_lb.configure(text=f"进度 {done}/{total}")
        self._schedule_render()

    def _thumb_done(self):
        cancelled = self.cancel_event.is_set()
        self.busy = False
        self._set_busy_ui(False, "已取消" if cancelled else "导入完成")
        self._schedule_render()

    def _cancel(self):
        if self.busy or self.scanning:
            self.cancel_event.set()
            self.cancel_btn.configure(state="disabled")
            self.status_lb.configure(text="正在取消...")

    def _clear(self):
        if self.busy or self.scanning:
            messagebox.showinfo("提示", "请先停止当前导入")
            return
        self.items.clear()
        self.selected_index = None
        self._preview_pil = None
        self.preview_label.configure(image=None, text="点击左侧缩略图查看大图")
        self.preview_label._ctk_image = None
        self._reset_info()
        self.pb.set(0)
        self.current_lb.configure(text="当前: -")
        self.status_lb.configure(text="就绪")
        self._update_count()
        self._schedule_render()

    def _remove_selected(self):
        if self.busy or self.scanning:
            return
        if self.selected_index is None:
            messagebox.showinfo("提示", "请先点击选择要移除的图片")
            return
        self.items.pop(self.selected_index)
        self.selected_index = None
        self._preview_pil = None
        self.preview_label.configure(image=None, text="点击左侧缩略图查看大图")
        self.preview_label._ctk_image = None
        self._reset_info()
        self._update_count()
        self._schedule_render()

    # ---------- 预览与信息 ----------
    def _select_item(self, idx):
        if self.selected_index is not None and self.selected_index < len(self.items):
            self.items[self.selected_index]["selected"] = False
        self.selected_index = idx
        self.items[idx]["selected"] = True
        self._schedule_render()
        item = self.items[idx]
        self._reset_info()
        self._preview_pil = None
        self.preview_label.configure(image=None, text="正在加载...")
        self.preview_label._ctk_image = None
        if item.get("info"):
            self._update_info(item["info"])

        def worker():
            info = item.get("info") or read_image_info(item["path"])
            preview_path = make_preview(item["path"], self.cache_dir) if info.get("supported") else ""
            self.after(0, lambda: self._preview_ready(idx, info, preview_path))

        threading.Thread(target=worker, daemon=True).start()

    def _preview_ready(self, idx, info, preview_path):
        if self.selected_index != idx:
            return
        self._update_info(info)
        if not preview_path or not os.path.exists(preview_path):
            self.preview_label.configure(image=None, text="无法预览")
            self.preview_label._ctk_image = None
            return
        try:
            from PIL import Image
            self._preview_pil = Image.open(preview_path)
            self.zoom = 1.0
            self._display_preview()
        except Exception:
            self.preview_label.configure(image=None, text="无法预览")
            self.preview_label._ctk_image = None

    def _display_preview(self):
        if self._preview_pil is None:
            return
        try:
            from PIL import Image
            w = max(1, int(self._preview_pil.width * self.zoom))
            h = max(1, int(self._preview_pil.height * self.zoom))
            img = self._preview_pil.resize((w, h), Image.LANCZOS)
            ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            self.preview_label.configure(image=ctk_image, text="")
            self.preview_label._ctk_image = ctk_image
            self.zoom_lb.configure(text=f"{int(self.zoom * 100)}%")
        except Exception:
            pass

    def _zoom_by(self, factor):
        self.zoom = max(0.2, min(4.0, self.zoom * factor))
        self._display_preview()

    def _zoom_fit(self):
        if self._preview_pil is None:
            return
        try:
            pw = max(self.preview_label.winfo_width(), 200)
            ph = max(self.preview_label.winfo_height(), 200)
            scale = min(pw / self._preview_pil.width, ph / self._preview_pil.height, 2.0)
            self.zoom = max(0.2, scale)
        except Exception:
            self.zoom = 1.0
        self._display_preview()

    def _on_preview_wheel(self, event):
        if self._preview_pil is not None:
            self._zoom_by(1.1 if event.delta > 0 else 0.9)

    def _reset_info(self):
        for key in self.info_labels:
            self.info_labels[key].configure(text="未知")

    def _update_info(self, info):
        if not info:
            self._reset_info()
            return
        text_map = {
            "resolution": f"{info.get('width', 0)} × {info.get('height', 0)}",
            "size": format_size(info.get("size_bytes", 0)),
            "format": info.get("format", "") or "未知",
            "aperture": info.get("aperture", "未知"),
            "shutter": info.get("shutter", "未知"),
            "iso": info.get("iso", "未知"),
            "focal": info.get("focal", "未知"),
            "device": info.get("device", "未知"),
            "datetime": info.get("datetime", "未知"),
        }
        for key, value in text_map.items():
            self.info_labels[key].configure(text=value or "未知")

    def _set_busy_ui(self, busy, text):
        state = "disabled" if busy else "normal"
        for btn in (self.add_file_btn, self.add_folder_btn, self.remove_btn, self.clear_btn):
            btn.configure(state=state)
        self.cancel_btn.configure(state="normal" if busy else "disabled")
        self.status_lb.configure(text=text)
        self.current_lb.configure(text="当前: -" if not busy else self.current_lb.cget("text"))

    def _update_count(self):
        self.count_lb.configure(text=f"共 {len(self.items)} 张图片")

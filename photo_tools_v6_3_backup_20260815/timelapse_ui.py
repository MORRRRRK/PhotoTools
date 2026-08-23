"""timelapse_ui.py - 一键生成延时视频界面 (V5.1)"""

import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .timelapse import (
    FPS_OPTIONS,
    IMAGE_EXTENSIONS,
    QUALITY_CRF,
    default_output_name,
    generate_timelapse,
)
from .utils import format_size


class TimelapseTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.files = []
        self.busy = False
        self.cancel_event = threading.Event()
        self.result_info = None
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

        self.add_file_btn = ctk.CTkButton(top, text="添加JPG文件", width=120,
                                          font=F(13), command=self._add_files)
        self.add_file_btn.pack(side="left", padx=5)
        self.add_folder_btn = ctk.CTkButton(top, text="添加JPG文件夹", width=130,
                                            font=F(13), command=self._add_folder)
        self.add_folder_btn.pack(side="left", padx=5)
        self.clear_btn = ctk.CTkButton(top, text="清空列表", width=90,
                                       font=F(13), command=self._clear)
        self.clear_btn.pack(side="left", padx=5)
        self.file_lb = ctk.CTkLabel(top, text="未添加 JPG 文件", font=F(13))
        self.file_lb.pack(side="left", padx=15)

        settings = ctk.CTkFrame(self)
        settings.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(settings, text="目标分辨率:", font=F(13)).grid(row=0, column=0, padx=6, pady=4, sticky="w")
        self.res_opt = ctk.CTkOptionMenu(settings, values=["1080P", "2K", "4K"], width=90)
        self.res_opt.set("1080P")
        self.res_opt.configure(command=lambda _: self._refresh_name())
        self.res_opt.grid(row=0, column=1, padx=6, pady=4)

        ctk.CTkLabel(settings, text="画质:", font=F(13)).grid(row=0, column=2, padx=6, pady=4, sticky="w")
        self.quality_opt = ctk.CTkOptionMenu(
            settings, values=["标准 CRF14", "高 CRF12", "最高 CRF10"], width=110)
        self.quality_opt.set("高 CRF12")
        self.quality_opt.grid(row=0, column=3, padx=6, pady=4)

        ctk.CTkLabel(settings, text="帧率:", font=F(13)).grid(row=0, column=4, padx=6, pady=4, sticky="w")
        self.fps_opt = ctk.CTkOptionMenu(settings, values=FPS_OPTIONS, width=70)
        self.fps_opt.set("30")
        self.fps_opt.configure(command=lambda _: self._refresh_name())
        self.fps_opt.grid(row=0, column=5, padx=6, pady=4)

        self.stab_var = ctk.BooleanVar(value=False)
        self.stab_switch = ctk.CTkSwitch(settings, text="增稳", variable=self.stab_var,
                                          font=F(13), command=self._on_stab_toggle)
        self.stab_switch.grid(row=1, column=0, columnspan=2, padx=6, pady=4, sticky="w")

        ctk.CTkLabel(settings, text="增稳强度:", font=F(13)).grid(row=1, column=2, padx=6, pady=4, sticky="w")
        self.strength_opt = ctk.CTkOptionMenu(settings, values=["低", "中", "高"], width=70)
        self.strength_opt.set("中")
        self.strength_opt.grid(row=1, column=3, padx=6, pady=4)

        self.stab_note = ctk.CTkLabel(
            settings, text="增稳会产生轻微裁切/缩放，属正常现象", font=F(11),
            text_color="#f39c12")
        self.stab_note.grid(row=1, column=4, columnspan=2, padx=6, pady=4, sticky="w")
        self.stab_note.grid_remove()

        output = ctk.CTkFrame(self)
        output.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(output, text="输出文件夹:", font=F(13)).pack(side="left", padx=6)
        self.output_entry = ctk.CTkEntry(output, width=400)
        self.output_entry.pack(side="left", padx=5)
        self.browse_btn = ctk.CTkButton(output, text="选择", width=70,
                                        font=F(13), command=self._browse_output)
        self.browse_btn.pack(side="left", padx=5)
        self.name_lb = ctk.CTkLabel(output, text="", font=F(12))
        self.name_lb.pack(side="left", padx=10)

        action = ctk.CTkFrame(self)
        action.pack(fill="x", padx=10, pady=5)
        self.start_btn = ctk.CTkButton(action, text="生成延时视频", width=150,
                                       font=F(14, True), command=self._start,
                                       fg_color="#1f6feb", hover_color="#1750a9")
        self.start_btn.pack(side="left", padx=8)
        self.cancel_btn = ctk.CTkButton(action, text="停止生成", width=100,
                                        font=F(13), command=self._cancel,
                                        state="disabled", fg_color="#c0392b",
                                        hover_color="#96281b")
        self.cancel_btn.pack(side="left", padx=8)

        progress = ctk.CTkFrame(self)
        progress.pack(fill="x", padx=10, pady=5)
        self.pb = ctk.CTkProgressBar(progress, height=14)
        self.pb.pack(fill="x", padx=8, pady=(6, 2))
        self.pb.set(0)
        self.phase_lb = ctk.CTkLabel(progress, text="就绪", font=F(12), anchor="w")
        self.phase_lb.pack(fill="x", padx=8)
        self.frame_lb = ctk.CTkLabel(progress, text="", font=F(12), anchor="w")
        self.frame_lb.pack(fill="x", padx=8)
        self.eta_lb = ctk.CTkLabel(progress, text="", font=F(12), anchor="w")
        self.eta_lb.pack(fill="x", padx=8)

        result = ctk.CTkFrame(self)
        result.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        result.grid_columnconfigure(0, weight=1)
        self.result_text = ctk.CTkTextbox(result, font=F(13), wrap="word")
        self.result_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.result_text.insert("0.0", "生成结果将在这里显示")
        self.result_text.configure(state="disabled")

        self._refresh_name()

    def _refresh_name(self):
        name = default_output_name(
            self.res_opt.get(), int(self.fps_opt.get()), self.stab_var.get())
        self.name_lb.configure(text=name)

    def _on_stab_toggle(self):
        if self.stab_var.get():
            self.stab_note.grid()
        else:
            self.stab_note.grid_remove()
        self._refresh_name()

    def _add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(
            title="选择 JPG 序列",
            filetypes=[("JPG 图片", "*.jpg *.jpeg"), ("所有文件", "*.*")])
        if paths:
            self._add_paths(paths)

    def _add_folder(self):
        if self.busy:
            return
        folder = filedialog.askdirectory(title="选择 JPG 文件夹")
        if folder:
            self._add_paths([folder])

    def _add_paths(self, paths):
        added = 0
        seen = {os.path.normcase(os.path.abspath(p)) for p in self.files}
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for root, _dirs, names in os.walk(path):
                    for name in names:
                        if Path(name).suffix.lower() in IMAGE_EXTENSIONS:
                            fp = os.path.join(root, name)
                            key = os.path.normcase(os.path.abspath(fp))
                            if key not in seen:
                                seen.add(key)
                                self.files.append(fp)
                                added += 1
            elif path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                key = os.path.normcase(os.path.abspath(str(path)))
                if key not in seen:
                    seen.add(key)
                    self.files.append(str(path))
                    added += 1
        if added:
            self.file_lb.configure(text=f"已添加 {len(self.files)} 张 JPG")
        else:
            messagebox.showinfo("提示", "没有新增 JPG 文件")

    def _clear(self):
        if self.busy:
            return
        self.files.clear()
        self.file_lb.configure(text="未添加 JPG 文件")
        self.pb.set(0)
        self.phase_lb.configure(text="就绪")
        self.frame_lb.configure(text="")
        self.eta_lb.configure(text="")

    def _browse_output(self):
        folder = filedialog.askdirectory(title="选择延时视频输出文件夹")
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)

    def _start(self):
        if self.busy:
            return
        if not self.files:
            messagebox.showwarning("提示", "请先添加 JPG 照片")
            return
        out_dir = self.output_entry.get().strip()
        if not out_dir:
            messagebox.showwarning("提示", "请选择输出文件夹")
            return
        if not Path(out_dir).exists():
            try:
                Path(out_dir).mkdir(parents=True, exist_ok=True)
            except Exception:
                messagebox.showerror("错误", "输出文件夹不可用")
                return

        resolution = self.res_opt.get()
        quality = self.quality_opt.get()
        crf = QUALITY_CRF.get(quality, 19)
        fps = int(self.fps_opt.get())
        stabilize = bool(self.stab_var.get())
        strength = self.strength_opt.get()
        filename = default_output_name(resolution, fps, stabilize)
        output_path = str(Path(out_dir) / filename)

        self.busy = True
        self.total_frames = len(self.files)
        self.cancel_event.clear()
        self.pb.set(0)
        self.phase_lb.configure(text="准备中...")
        self.frame_lb.configure(text="")
        self.eta_lb.configure(text="")
        self.start_btn.configure(state="disabled", text="生成中...")
        self.cancel_btn.configure(state="normal")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.res_opt, self.quality_opt, self.fps_opt,
                  self.stab_switch, self.strength_opt, self.browse_btn):
            w.configure(state="disabled")

        def worker():
            def cb(info):
                self.after(0, lambda: self._on_progress(info))
            result = generate_timelapse(
                list(self.files), output_path, resolution, fps, crf,
                stabilize, strength, self.cancel_event, cb)
            self.after(0, lambda: self._done(result))

        threading.Thread(target=worker, daemon=True).start()

    def _cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.cancel_btn.configure(state="disabled")
            self.phase_lb.configure(text="正在停止，请稍候...")

    def _on_progress(self, info):
        phase = info.get("phase", "")
        current = info.get("current", 0)
        total = info.get("total", 0)
        percent = info.get("percent", 0)
        self.pb.set(percent)
        if phase == "处理帧":
            self.phase_lb.configure(text="处理帧")
            self.frame_lb.configure(text=f"第 {current}/{total} 帧")
            eta = info.get("eta", 0)
            self.eta_lb.configure(text=f"预计剩余: {int(eta)} 秒" if eta else "")
        elif phase in ("分析中", "编码中"):
            self.phase_lb.configure(text=phase)
            self.frame_lb.configure(text=f"总帧数 {self.total_frames}，当前进度 {int(percent * 100)}%")

    def _done(self, result):
        self.busy = False
        self.start_btn.configure(state="normal", text="生成延时视频")
        self.cancel_btn.configure(state="disabled")
        for w in (self.add_file_btn, self.add_folder_btn, self.clear_btn,
                  self.res_opt, self.quality_opt, self.fps_opt,
                  self.stab_switch, self.strength_opt, self.browse_btn):
            w.configure(state="normal")
        status = result.get("status")
        if status == "cancelled":
            self.phase_lb.configure(text="已停止")
            messagebox.showinfo("已停止", "延时视频生成已停止")
            return
        if status != "done":
            self.phase_lb.configure(text="生成失败")
            self.result_text.configure(state="normal")
            self.result_text.delete("0.0", "end")
            self.result_text.insert("0.0", f"生成失败: {result.get('error', '未知错误')}")
            self.result_text.configure(state="disabled")
            messagebox.showerror("失败", result.get("error", "未知错误"))
            return

        output = result.get("output", "")
        self.pb.set(1)
        self.phase_lb.configure(text="生成完成")
        self.frame_lb.configure(text=f"帧数: {result.get('frames', '-')}  |  "
                                      f"分辨率: {result.get('width', '-')}x{result.get('height', '-')}  |  "
                                      f"帧率: {result.get('fps', '-')} fps")
        self.eta_lb.configure(text=f"时长: {result.get('duration', '-'):.2f}s  |  "
                                    f"大小: {format_size(result.get('size', 0))}")
        self.result_text.configure(state="normal")
        self.result_text.delete("0.0", "end")
        self.result_text.insert(
            "0.0",
            f"输出文件: {output}\n"
            f"帧数: {result.get('frames', '-')}\n"
            f"分辨率: {result.get('width', '-')}x{result.get('height', '-')}\n"
            f"帧率: {result.get('fps', '-')} fps\n"
            f"时长: {result.get('duration', '-'):.2f} 秒\n"
            f"文件大小: {format_size(result.get('size', 0))}\n"
            f"增稳: {'是' if result.get('stabilized') else '否'}")
        self.result_text.configure(state="disabled")
        messagebox.showinfo("完成", f"延时视频已生成\n{output}")

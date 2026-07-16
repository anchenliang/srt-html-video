#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gui.py – CustomTkinter 图形界面 for SRT → Video 流水线
独立于现有代码，通过调用 main.py 并捕获输出来实现进度监控。
"""

import os
import sys
import json
import re
import subprocess
import threading
import queue
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

# ---------- 路径设定 ----------
# 当前脚本所在目录（scripts/）
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
# 项目根目录（scripts/ 的父级）
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)

# config.json 路径
CONFIG_PATH = os.path.join(SCRIPTS_DIR, "config.json")

# main.py 路径
MAIN_PY = os.path.join(SCRIPTS_DIR, "main.py")

# 默认模板路径（相对 ROOT_DIR）
DEFAULT_TEMPLATE_REL = "scripts/templates/podcast-enhanced-template.html"
DEFAULT_TEMPLATE_ABS = os.path.join(ROOT_DIR, DEFAULT_TEMPLATE_REL)

# ---------- 加载配置 ----------
def load_config():
    """从 config.json 加载参数，若文件不存在则返回默认值。"""
    defaults = {
        "split_parts": 30,
        "quality": "standard",
        "workers": 1,
        "template": DEFAULT_TEMPLATE_ABS
    }
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            # 转换 template 为绝对路径（若存在且为相对路径）
            if "template" in cfg:
                tpl = cfg["template"]
                if not os.path.isabs(tpl):
                    tpl = os.path.join(ROOT_DIR, tpl)
                cfg["template"] = tpl
            defaults.update(cfg)
        except Exception as e:
            print(f"读取 config.json 失败: {e}")
    return defaults

# ---------- 主界面类 ----------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SRT → Video 生成器")
        self.geometry("900x700")
        self.minsize(800, 600)

        # 加载配置
        self.config = load_config()

        # 运行状态
        self.is_running = False
        self.process = None
        self.output_queue = queue.Queue()
        self.total_parts = 0          # 总视频段数
        self.current_part = 0         # 当前正在处理的段（从1开始）
        self.parts_completed = 0      # 已完成段数

        # ---------- 布局 ----------
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)   # 日志区域占用剩余空间

        # 标题
        title_label = ctk.CTkLabel(self, text="SRT → Video 自动生成工具", font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # ---- 文件选择 ----
        file_frame = ctk.CTkFrame(self)
        file_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        file_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(file_frame, text="SRT 文件:", width=80).grid(row=0, column=0, padx=(5, 10), sticky="w")
        self.srt_entry = ctk.CTkEntry(file_frame)
        self.srt_entry.grid(row=0, column=1, padx=5, sticky="ew")
        btn_browse = ctk.CTkButton(file_frame, text="浏览...", width=80, command=self.browse_srt)
        btn_browse.grid(row=0, column=2, padx=5)

        # ---- 参数设置 ----
        param_frame = ctk.CTkFrame(self)
        param_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        param_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 分割行数
        ctk.CTkLabel(param_frame, text="每段行数:", width=90).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.split_parts_var = ctk.StringVar(value=str(self.config.get("split_parts", 30)))
        spin_split = ctk.CTkEntry(param_frame, textvariable=self.split_parts_var, width=70)
        spin_split.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 质量
        ctk.CTkLabel(param_frame, text="质量:", width=60).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.quality_var = ctk.StringVar(value=self.config.get("quality", "standard"))
        opt_quality = ctk.CTkOptionMenu(param_frame, values=["draft", "standard", "high"], variable=self.quality_var, width=100)
        opt_quality.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # 工作线程数
        ctk.CTkLabel(param_frame, text="工作线程:", width=90).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.workers_var = ctk.StringVar(value=str(self.config.get("workers", 1)))
        spin_workers = ctk.CTkEntry(param_frame, textvariable=self.workers_var, width=70)
        spin_workers.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # 模板文件
        ctk.CTkLabel(param_frame, text="模板文件:", width=90).grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.template_entry = ctk.CTkEntry(param_frame)
        self.template_entry.grid(row=1, column=3, padx=5, pady=5, sticky="ew")
        # 填充默认模板路径
        self.template_entry.insert(0, self.config.get("template", DEFAULT_TEMPLATE_ABS))
        # 浏览模板按钮放在第4列？ 另起一行更好，但这里简单加一个按钮在旁边
        # 为了不占用太多列，我们重新调整：将模板浏览按钮放在第4列（额外）
        # 因 grid_columnconfigure 只有4列，我们增加一列
        param_frame.grid_columnconfigure(4, weight=0)
        btn_template = ctk.CTkButton(param_frame, text="...", width=40, command=self.browse_template)
        btn_template.grid(row=1, column=4, padx=5, pady=5, sticky="w")

        # ---- 操作按钮 ----
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(btn_frame, text="开始生成", command=self.start_process, width=150, height=40)
        self.start_btn.grid(row=0, column=0, padx=10, pady=5)

        self.open_folder_btn = ctk.CTkButton(btn_frame, text="打开输出文件夹", command=self.open_output_folder, state="disabled", width=150, height=40)
        self.open_folder_btn.grid(row=0, column=1, padx=10, pady=5)

        # ---- 进度显示 ----
        progress_frame = ctk.CTkFrame(self)
        progress_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=0)
        progress_frame.grid_columnconfigure(1, weight=1)
        progress_frame.grid_columnconfigure(2, weight=0)

        self.progress_label = ctk.CTkLabel(progress_frame, text="进度: 0 / 0", width=100)
        self.progress_label.grid(row=0, column=0, padx=5, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(progress_frame, mode="indeterminate")
        self.progress_bar.grid(row=0, column=1, padx=5, sticky="ew")
        self.progress_bar.set(0)
        # 初始为不确定模式
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        self.status_label = ctk.CTkLabel(progress_frame, text="就绪", width=150)
        self.status_label.grid(row=0, column=2, padx=5, sticky="e")

        # ---- 日志输出 ----
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=5, column=0, padx=20, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(log_frame, wrap="word", font=ctk.CTkFont(size=12))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        # 添加滚动条（CTkTextbox自带）

        # 初始化完成后，检查config是否加载成功
        self.append_log("界面已启动，从 config.json 加载参数。")

    # ---------- 辅助方法 ----------
    def browse_srt(self):
        """选择 SRT 文件"""
        file_path = filedialog.askopenfilename(
            title="选择 SRT 字幕文件",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )
        if file_path:
            self.srt_entry.delete(0, "end")
            self.srt_entry.insert(0, file_path)

    def browse_template(self):
        """选择模板 HTML 文件"""
        file_path = filedialog.askopenfilename(
            title="选择模板 HTML 文件",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if file_path:
            self.template_entry.delete(0, "end")
            self.template_entry.insert(0, file_path)

    def append_log(self, text, level="info"):
        """向日志文本框追加文本，并自动滚动到底部"""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def update_progress(self, current, total):
        """更新进度条和标签"""
        self.current_part = current
        self.total_parts = total
        if total > 0:
            # 转为确定模式
            if self.progress_bar.cget("mode") == "indeterminate":
                self.progress_bar.configure(mode="determinate")
                self.progress_bar.stop()
            progress = (current - 1) / total if current > 0 else 0
            if progress < 0:
                progress = 0
            self.progress_bar.set(progress)
            self.progress_label.configure(text=f"进度: {current} / {total}")
            self.status_label.configure(text=f"正在处理第 {current} 段")
        else:
            self.progress_label.configure(text="进度: ? / ?")
            self.status_label.configure(text="等待解析总段数...")

    def set_progress_complete(self):
        """设置进度为完成状态"""
        if self.progress_bar.cget("mode") == "indeterminate":
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.progress_label.configure(text=f"进度: 完成")
        self.status_label.configure(text="全部完成")

    def reset_ui(self):
        """重置界面状态（完成或取消）"""
        self.is_running = False
        self.start_btn.configure(text="开始生成", state="normal")
        self.open_folder_btn.configure(state="normal" if self.output_folder_exists() else "disabled")
        if self.progress_bar.cget("mode") == "indeterminate":
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
        else:
            self.progress_bar.set(0)
        self.progress_label.configure(text="进度: 0 / 0")
        self.status_label.configure(text="就绪")

    def output_folder_exists(self):
        """检查输出文件夹是否存在（用于启用打开按钮）"""
        # 根据当前SRT文件名确定项目名
        srt_path = self.srt_entry.get().strip()
        if not srt_path:
            return False
        base = os.path.splitext(os.path.basename(srt_path))[0]
        # 由 main.py 生成的输出目录：output/video/<clean_name>
        # 但 clean_name 可能经过清理，此处简化，直接检查目录是否存在
        # 更可靠的方式是从日志中提取，但我们可以尝试拼接
        # 不过为了简单，我们可以在进程完成后，将输出路径保存在实例变量中
        # 这里我们保存最后生成的 all.mp4 或 part1.mp4 所在目录
        if hasattr(self, 'output_dir') and os.path.isdir(self.output_dir):
            return True
        return False

    def open_output_folder(self):
        """打开输出文件夹（在文件管理器中）"""
        if hasattr(self, 'output_dir') and os.path.isdir(self.output_dir):
            webbrowser.open(self.output_dir)  # 在Windows上会打开资源管理器
        else:
            # 尝试根据SRT名称构造
            srt_path = self.srt_entry.get().strip()
            if srt_path:
                base = os.path.splitext(os.path.basename(srt_path))[0]
                # 清理名称（与main.py保持一致）
                from process_srt import clean_filename   # 直接导入其函数
                clean = clean_filename(base)
                out_dir = os.path.join(ROOT_DIR, "output", "video", clean)
                if os.path.isdir(out_dir):
                    webbrowser.open(out_dir)
                else:
                    messagebox.showinfo("提示", f"输出目录不存在：{out_dir}")

    # ---------- 核心流程 ----------
    def start_process(self):
        """启动生成流程（在子线程中运行 main.py）"""
        if self.is_running:
            return

        # 验证SRT文件
        srt_path = self.srt_entry.get().strip()
        if not srt_path:
            messagebox.showerror("错误", "请先选择 SRT 文件")
            return
        if not os.path.isfile(srt_path):
            messagebox.showerror("错误", f"文件不存在：{srt_path}")
            return

        # 收集参数
        try:
            split_parts = int(self.split_parts_var.get())
            workers = int(self.workers_var.get())
        except ValueError:
            messagebox.showerror("错误", "split_parts 和 workers 必须为整数")
            return

        quality = self.quality_var.get()
        if quality not in ["draft", "standard", "high"]:
            quality = "standard"

        template = self.template_entry.get().strip()
        if not template:
            template = DEFAULT_TEMPLATE_ABS
        if not os.path.isfile(template):
            # 尝试转为绝对路径
            if not os.path.isabs(template):
                template = os.path.join(ROOT_DIR, template)
            if not os.path.isfile(template):
                messagebox.showerror("错误", f"模板文件不存在：{template}")
                return

        # 禁用启动按钮，清空日志和进度
        self.is_running = True
        self.start_btn.configure(text="运行中...", state="disabled")
        self.open_folder_btn.configure(state="disabled")
        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", "end")
        self.log_text.configure(state="disabled")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.progress_label.configure(text="启动中...")
        self.status_label.configure(text="正在初始化...")
        self.total_parts = 0
        self.current_part = 0
        self.output_dir = None   # 将在解析时尝试保存

        # 清空队列
        while not self.output_queue.empty():
            self.output_queue.get()

        # 启动子进程
        cmd = [
            sys.executable,
            MAIN_PY,
            srt_path,
            "--split-parts", str(split_parts),
            "--quality", quality,
            "--workers", str(workers),
            "--template", template
        ]
        self.append_log(f"> 启动命令: {' '.join(cmd)}")
        self.append_log("=" * 60)

        # 在后台线程中运行
        thread = threading.Thread(target=self.run_subprocess, args=(cmd,), daemon=True)
        thread.start()

        # 启动UI轮询
        self.after(100, self.poll_queue)

    def run_subprocess(self, cmd):
        """在子线程中执行 main.py，并将输出放入队列"""
        try:
            # 设置工作目录为项目根目录，以便相对路径（如 projects/）正确
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=ROOT_DIR,
                encoding='utf-8',
                errors='replace'
            )
            # 逐行读取并放入队列
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.output_queue.put(('stdout', line))
            self.process.stdout.close()
            return_code = self.process.wait()
            self.output_queue.put(('returncode', return_code))
        except Exception as e:
            self.output_queue.put(('error', str(e)))

    def poll_queue(self):
        """定期检查队列，更新UI（在主线程中执行）"""
        try:
            while True:
                item = self.output_queue.get_nowait()
                if item[0] == 'stdout':
                    line = item[1].rstrip('\n')
                    self.parse_output(line)
                    self.append_log(line, level="stdout")
                elif item[0] == 'returncode':
                    code = item[1]
                    self.process_finished(code)
                    return
                elif item[0] == 'error':
                    err = item[1]
                    self.append_log(f"错误: {err}")
                    self.process_finished(-1)
                    return
        except queue.Empty:
            pass
        finally:
            if self.is_running:
                self.after(100, self.poll_queue)

    def parse_output(self, line):
        """解析输出行，更新进度"""
        # 匹配总段数: "Total parts: X"
        match = re.search(r'Total parts:\s*(\d+)', line)
        if match:
            total = int(match.group(1))
            if total > 0:
                self.total_parts = total
                self.progress_label.configure(text=f"进度: 0 / {total}")
                self.status_label.configure(text="准备开始...")
                # 切换进度条为确定模式
                if self.progress_bar.cget("mode") == "indeterminate":
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate")
                self.progress_bar.set(0)
            return

        # 匹配 "Processing Part X/Y"
        match = re.search(r'Processing Part\s*(\d+)/(\d+)', line)
        if match:
            current = int(match.group(1))
            total = int(match.group(2))
            if total != self.total_parts:
                self.total_parts = total
            self.update_progress(current, total)
            return

        # 匹配 "Part X completed"
        match = re.search(r'Part\s*(\d+)\s*completed', line, re.IGNORECASE)
        if match:
            part_num = int(match.group(1))
            if self.total_parts > 0:
                progress = part_num / self.total_parts
                if progress > 1:
                    progress = 1
                self.progress_bar.set(progress)
                self.progress_label.configure(text=f"进度: {part_num} / {self.total_parts}")
                self.status_label.configure(text=f"已完成第 {part_num} 段")
            return

        # 匹配 "All parts processed successfully."
        if "All parts processed successfully." in line:
            self.set_progress_complete()
            return

        # 匹配 "Concatenating parts into all.mp4..."
        if "Concatenating parts into all.mp4" in line:
            self.status_label.configure(text="正在拼接视频...")
            return

        # 匹配 "Success: ..." (拼接成功)
        if "Success:" in line and "all.mp4" in line:
            # 可能已拼接完成
            pass

        # 尝试从输出中提取输出目录（用于打开文件夹）
        if "All parts processed successfully." in line:
            # 此时已经完成，输出目录可能在之前的日志中打印，但我们可以在最后根据srt名称构造
            pass

        # 捕获 "[FATAL]" 错误
        if "[FATAL]" in line:
            self.status_label.configure(text="处理失败，请查看日志")
            # 进度条可能停在某个位置

    def process_finished(self, returncode):
        """子进程结束处理"""
        self.is_running = False
        self.start_btn.configure(text="开始生成", state="normal")
        if returncode == 0:
            self.status_label.configure(text="全部完成！")
            self.set_progress_complete()
            # 尝试确定输出文件夹
            srt_path = self.srt_entry.get().strip()
            if srt_path:
                from process_srt import clean_filename
                clean = clean_filename(os.path.splitext(os.path.basename(srt_path))[0])
                self.output_dir = os.path.join(ROOT_DIR, "output", "video", clean)
                if os.path.isdir(self.output_dir):
                    self.open_folder_btn.configure(state="normal")
                else:
                    # 可能是在 projects 下，但输出视频在 output/video/ 下
                    self.open_folder_btn.configure(state="normal" if os.path.isdir(self.output_dir) else "disabled")
            self.append_log("=" * 60)
            self.append_log("✅ 所有视频片段生成并拼接完成！")
        else:
            self.status_label.configure(text=f"进程异常退出 (code {returncode})")
            self.append_log("=" * 60)
            self.append_log(f"❌ 进程退出，返回码：{returncode}")
            # 进度条停止
            if self.progress_bar.cget("mode") == "indeterminate":
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)
            self.start_btn.configure(state="normal")
            self.open_folder_btn.configure(state="disabled")

        # 启用开始按钮（已启用），重置运行标志
        self.is_running = False

# ---------- 启动 ----------
if __name__ == "__main__":
    # 检查 customtkinter 是否安装
    try:
        import customtkinter
    except ImportError:
        print("错误: 未安装 customtkinter。请执行: pip install customtkinter")
        sys.exit(1)

    # 设置外观模式
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()
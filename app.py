#!/usr/bin/env python3
"""PDF水印去除 v2 - Self-contained macOS app with in-window drag-and-drop."""

import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path

import fitz  # PyMuPDF

# Try to import tkinterdnd2 for in-window drag-and-drop
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# --- Watermark detection ---

ROTATION_PATTERN = "0.70711 0.70711 -0.70711 0.70711"

INLINE_WM_RE = re.compile(
    r'q\s+'
    r'[\d.]+\s+0\s+0\s+[\d.]+\s+[\d.]+\s+[\d.]+\s*'
    r'cm\s+BT\s+'
    r'([\d.]+)\s+\1\s+-\1\s+\1'
    r'.*?'
    r'TJ\s+ET\s*Q',
    re.DOTALL
)


def _check_stream(text: str) -> str:
    if ROTATION_PATTERN in text:
        return "separate"
    if INLINE_WM_RE.search(text):
        return "inline"
    return "none"


def has_watermark(pdf_path: str) -> bool:
    doc = fitz.open(pdf_path)
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for c_xref in page.get_contents():
            stream = doc.xref_stream(c_xref)
            if stream is None:
                continue
            if _check_stream(stream.decode("latin-1", errors="replace")) != "none":
                doc.close()
                return True
    doc.close()
    return False


def remove_watermark_from_pdf(input_path: str, output_path: str) -> int:
    doc = fitz.open(input_path)
    removed = 0
    for page_num in range(doc.page_count):
        page = doc[page_num]
        for c_xref in page.get_contents():
            stream = doc.xref_stream(c_xref)
            if stream is None:
                continue
            text = stream.decode("latin-1", errors="replace")
            wm_type = _check_stream(text)
            if wm_type == "separate":
                doc.update_stream(c_xref, b" Q\n")
                removed += 1
            elif wm_type == "inline":
                cleaned = INLINE_WM_RE.sub('', text)
                doc.update_stream(c_xref, cleaned.encode("latin-1"))
                removed += 1
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return removed


# --- App UI ---

class WatermarkRemoverApp:
    def __init__(self):
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("PDF水印去除")
        self.root.geometry("580x440")
        self.root.resizable(False, False)
        self.root.configure(bg="#f5f5f7")

        # Center on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 580) // 2
        y = (self.root.winfo_screenheight() - 440) // 2
        self.root.geometry(f"580x440+{x}+{y}")

        # Style
        style = ttk.Style()
        style.configure("Big.TButton", font=("", 13), padding=(16, 8))
        style.configure("Title.TLabel", font=("", 22, "bold"), background="#f5f5f7")
        style.configure("Sub.TLabel", font=("", 12), foreground="#888", background="#f5f5f7")
        style.configure("Main.TFrame", background="#f5f5f7")

        self.output_paths: list[str] = []
        self._build_main_ui()

        # Handle file arguments (drag to app icon / Open With)
        args = sys.argv[1:]
        if args:
            self.root.after(100, lambda: self._start_processing(args))

    def _build_main_ui(self):
        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, style="Main.TFrame", padding=24)
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(frame, text="PDF 水印去除工具", style="Title.TLabel").pack(pady=(0, 4))
        ttk.Label(frame, text="v2.0", style="Sub.TLabel").pack(pady=(0, 16))

        # Drop zone
        self.drop_frame = tk.Canvas(
            frame, width=520, height=180,
            bg="#ffffff", highlightthickness=2,
            highlightbackground="#d0d0d0", highlightcolor="#007aff",
            relief=tk.FLAT, cursor="hand2",
        )
        self.drop_frame.pack(pady=(0, 16))

        # Draw dashed border inside
        self._draw_drop_zone_content()

        # Bind click to open file dialog
        self.drop_frame.bind("<Button-1>", lambda e: self._pick_files())

        # Enable drag-and-drop if available
        if HAS_DND:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<DropEnter>>', self._on_drag_enter)
            self.drop_frame.dnd_bind('<<DropLeave>>', self._on_drag_leave)
            self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)

        # Buttons row
        btn_frame = ttk.Frame(frame, style="Main.TFrame")
        btn_frame.pack(pady=(0, 8))

        ttk.Button(btn_frame, text="选择 PDF 文件", style="Big.TButton",
                   command=self._pick_files).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="选择文件夹", style="Big.TButton",
                   command=self._pick_folder).pack(side=tk.LEFT, padx=8)

        # Hint
        ttk.Label(frame, text="支持批量处理 · 文件夹内所有 PDF 自动检测并去除水印",
                  style="Sub.TLabel").pack(pady=(8, 0))

    def _draw_drop_zone_content(self, active=False):
        c = self.drop_frame
        c.delete("all")
        w, h = 520, 180

        # Dashed border
        color = "#007aff" if active else "#c0c0c0"
        dash = (6, 4)
        pad = 12
        c.create_rectangle(pad, pad, w - pad, h - pad,
                           outline=color, width=2, dash=dash)

        if active:
            c.create_text(w // 2, h // 2 - 16, text="松开以添加文件",
                          font=("", 18, "bold"), fill="#007aff")
            c.create_text(w // 2, h // 2 + 20, text="释放鼠标即可开始处理",
                          font=("", 12), fill="#007aff")
        else:
            # Icon: down arrow
            cx, cy = w // 2, h // 2 - 24
            c.create_text(cx, cy - 8, text="↓", font=("", 36), fill="#999")
            c.create_text(cx, cy + 36, text="将 PDF 文件或文件夹拖拽到这里",
                          font=("", 14), fill="#666")
            c.create_text(cx, cy + 62, text="或点击此区域选择文件",
                          font=("", 11), fill="#999")

    def _on_drag_enter(self, event):
        self.drop_frame.config(highlightbackground="#007aff")
        self._draw_drop_zone_content(active=True)
        return event.action

    def _on_drag_leave(self, event):
        self.drop_frame.config(highlightbackground="#d0d0d0")
        self._draw_drop_zone_content(active=False)
        return event.action

    def _on_drop(self, event):
        self.drop_frame.config(highlightbackground="#d0d0d0")
        self._draw_drop_zone_content(active=False)

        # Parse dropped paths (may be space-separated, with {} for paths containing spaces)
        raw = event.data
        paths = []
        i = 0
        while i < len(raw):
            if raw[i] == '{':
                end = raw.index('}', i)
                paths.append(raw[i + 1:end])
                i = end + 2  # skip } and space
            elif raw[i] == ' ':
                i += 1
            else:
                end = raw.find(' ', i)
                if end == -1:
                    end = len(raw)
                paths.append(raw[i:end])
                i = end + 1

        if paths:
            self._start_processing(paths)
        return event.action

    def _pick_files(self):
        files = filedialog.askopenfilenames(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if files:
            self._start_processing(list(files))

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            self._start_processing([folder])

    def _start_processing(self, items: list[str]):
        self.output_paths = []

        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, style="Main.TFrame", padding=24)
        frame.pack(fill=tk.BOTH, expand=True)

        self.p_title = ttk.Label(frame, text="正在处理...", font=("", 18, "bold"),
                                 background="#f5f5f7")
        self.p_title.pack(anchor=tk.W)

        self.p_status = ttk.Label(frame, text="扫描文件中...", font=("", 12),
                                  background="#f5f5f7")
        self.p_status.pack(anchor=tk.W, pady=(12, 4))

        self.p_bar = ttk.Progressbar(frame, length=530, mode='determinate')
        self.p_bar.pack(pady=(4, 8))

        self.p_detail = ttk.Label(frame, text="", font=("", 10), foreground="gray",
                                  background="#f5f5f7")
        self.p_detail.pack(anchor=tk.W)

        self.p_log = tk.Text(frame, height=10, font=("Menlo", 10), state=tk.DISABLED,
                             bg="#ffffff", relief=tk.FLAT, highlightthickness=1,
                             highlightcolor="#ddd", highlightbackground="#ddd")
        self.p_log.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        thread = threading.Thread(target=self._process, args=(items,), daemon=True)
        thread.start()

    def _log(self, msg: str):
        def _do():
            self.p_log.config(state=tk.NORMAL)
            self.p_log.insert(tk.END, msg + "\n")
            self.p_log.see(tk.END)
            self.p_log.config(state=tk.DISABLED)
        self.root.after(0, _do)

    def _update(self, status=None, detail=None, progress=None):
        def _do():
            if status:
                self.p_status.config(text=status)
            if detail is not None:
                self.p_detail.config(text=detail)
            if progress is not None:
                self.p_bar['value'] = progress
        self.root.after(0, _do)

    def _process(self, items: list[str]):
        try:
            self._do_process(items)
        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: self._show_error(err_msg))

    def _do_process(self, items: list[str]):
        all_tasks: list[dict] = []

        for item_path in items:
            p = Path(item_path)
            if p.is_dir():
                dst = p.parent / (p.name + "_无水印")
                dst.mkdir(exist_ok=True)
                self.output_paths.append(str(dst))
                for f in sorted(p.rglob("*")):
                    if f.is_dir():
                        continue
                    rel = f.relative_to(p)
                    out = dst / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    all_tasks.append({
                        "src": str(f), "dst": str(out),
                        "name": str(rel), "is_pdf": f.suffix.lower() == ".pdf",
                    })
            elif p.suffix.lower() == ".pdf":
                out = str(p.with_stem(p.stem + "_无水印"))
                self.output_paths.append(out)
                all_tasks.append({
                    "src": str(p), "dst": out,
                    "name": p.name, "is_pdf": True,
                })

        total = len(all_tasks)
        if total == 0:
            self.root.after(0, lambda: self._show_done(0, 0, 0))
            return

        wm_removed = 0
        copied = 0

        for i, task in enumerate(all_tasks):
            name = task["name"]
            pct = int((i / total) * 100)
            self._update(
                status=f"({i+1}/{total}) {name}",
                detail="检测水印..." if task["is_pdf"] else "复制文件...",
                progress=pct,
            )

            if task["is_pdf"]:
                if has_watermark(task["src"]):
                    self._update(detail="去除水印中...")
                    pages = remove_watermark_from_pdf(task["src"], task["dst"])
                    wm_removed += 1
                    self._log(f"  ✓ 去除水印 ({pages}页): {name}")
                else:
                    shutil.copy2(task["src"], task["dst"])
                    copied += 1
                    self._log(f"  - 无水印，已复制: {name}")
            else:
                shutil.copy2(task["src"], task["dst"])
                copied += 1
                self._log(f"  - 已复制: {name}")

        self._update(progress=100, status="处理完成！", detail="")
        self.root.after(300, lambda: self._show_done(total, wm_removed, copied))

    def _show_done(self, total: int, removed: int, copied: int):
        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, style="Main.TFrame", padding=24)
        frame.pack(fill=tk.BOTH, expand=True)

        # Success header
        ttk.Label(frame, text="处理完成！", font=("", 22, "bold"),
                  foreground="#28a745", background="#f5f5f7").pack(pady=(10, 12))

        # Stats
        stats_frame = tk.Frame(frame, bg="#f5f5f7")
        stats_frame.pack(pady=(0, 16))

        for label, value, color in [
            ("总文件", str(total), "#333"),
            ("去除水印", f"{removed} 个", "#007aff"),
            ("直接复制", f"{copied} 个", "#888"),
        ]:
            box = tk.Frame(stats_frame, bg="#ffffff", padx=16, pady=8,
                           highlightthickness=1, highlightbackground="#e0e0e0")
            box.pack(side=tk.LEFT, padx=6)
            tk.Label(box, text=value, font=("", 18, "bold"), fg=color, bg="#ffffff").pack()
            tk.Label(box, text=label, font=("", 10), fg="#888", bg="#ffffff").pack()

        # Output paths
        ttk.Label(frame, text="输出位置：", font=("", 13, "bold"),
                  background="#f5f5f7").pack(anchor=tk.W, pady=(8, 4))

        for p in self.output_paths:
            path_frame = tk.Frame(frame, bg="#f0f4ff", padx=10, pady=6,
                                  highlightthickness=1, highlightbackground="#c0d0f0")
            path_frame.pack(fill=tk.X, pady=2)
            lbl = tk.Label(path_frame, text=p, font=("Menlo", 11),
                           fg="#0066cc", bg="#f0f4ff", cursor="hand2")
            lbl.pack(anchor=tk.W)
            lbl.bind("<Button-1>", lambda e, path=p: self._open_path(path))

        # Buttons
        btn_frame = ttk.Frame(frame, style="Main.TFrame")
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text="在 Finder 中打开", style="Big.TButton",
                   command=self._open_in_finder).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="继续处理", style="Big.TButton",
                   command=self._build_main_ui).pack(side=tk.LEFT, padx=8)

    def _open_path(self, path: str):
        target = Path(path)
        if target.is_dir():
            subprocess.run(["open", str(target)])
        else:
            subprocess.run(["open", "-R", str(target)])

    def _open_in_finder(self):
        for p in self.output_paths:
            self._open_path(p)

    def _show_error(self, error: str):
        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, style="Main.TFrame", padding=24)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="处理出错", font=("", 20, "bold"),
                  foreground="red", background="#f5f5f7").pack(pady=(20, 12))
        ttk.Label(frame, text=error, font=("", 12), wraplength=500,
                  background="#f5f5f7").pack(pady=(0, 20))
        ttk.Button(frame, text="返回", style="Big.TButton",
                   command=self._build_main_ui).pack()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    WatermarkRemoverApp().run()

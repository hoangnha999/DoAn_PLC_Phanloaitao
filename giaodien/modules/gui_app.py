import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import os
import sys
import threading
import cv2
import sqlite3
from datetime import datetime

# Đảm bảo Python tìm thấy thư mục Processing
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Processing.analyzer import FruitAnalyzer
from modules.database import AppDatabase
from modules.plc import PLCManager
from modules.camera import CameraManager



class FruitClassificationApp:
    """Giao diện chính của ứng dụng nhận dạng và phân loại táo."""

    # ─── Cấu hình giao diện ──────────────────────────────────────────
    WINDOW_WIDTH = 950
    WINDOW_HEIGHT = 700
    BG_COLOR = "#F5F5F5"         # Xám nhạt tĩnh lặng (SCADA Light Mode)
    TITLE_COLOR = "#1A237E"       # Xanh đậm đen
    SUBTITLE_COLOR = "#455A64"    # Xám xanh đậm
    TOPIC_COLOR = "#D32F2F"       # Đỏ công nghiệp
    TEXT_COLOR = "#212121"
    BTN_RUN_COLOR = "#2E7D32"     # Xanh lá cây (Bắt đầu)
    BTN_STOP_COLOR = "#B71C1C"    # Đỏ đậm (Dừng)
    BTN_TEXT_COLOR = "#FFFFFF"

    def __init__(self, root):
        self.root = root
        
        # ── PLC (Dùng chung cho trang chính) ──
        self.plc_manager = PLCManager()
        # ── Cơ sở dữ liệu ──
        self.db = AppDatabase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self._setup_window()
        self._load_images()
        self._build_ui()

    # ─── Thiết lập cửa sổ ────────────────────────────────────────────
    def _setup_window(self):
        """Cấu hình cửa sổ chính."""
        self.root.title("Nhận dạng và phân loại táo")
        self.root.configure(bg=self.BG_COLOR)
        self.root.resizable(True, True)

        # Lắng nghe phím Q từ mọi nơi để tắt app
        self.root.bind_all("<q>", lambda e: self.root.destroy())
        self.root.bind_all("<Q>", lambda e: self.root.destroy())

        # Căn giữa cửa sổ trên màn hình
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - self.WINDOW_WIDTH) // 2
        y = (screen_h - self.WINDOW_HEIGHT) // 2
        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}+{x}+{y}")


    # ─── Tải hình ảnh ─────────────────────────────────────────────────
    def _get_image_path(self, filename):
        """Trả về đường dẫn tuyệt đối tới file ảnh."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, "images", filename)

    def _load_images(self):
        """Tải và resize các hình ảnh."""
        try:
            # Logo khoa (bên trái)
            faculty_img = Image.open(self._get_image_path("faculty_logo.png"))
            faculty_img = faculty_img.resize((80, 80), Image.LANCZOS)
            self.faculty_logo = ImageTk.PhotoImage(faculty_img)

            # Logo trường UTE (bên phải)
            ute_img = Image.open(self._get_image_path("ute_logo.png"))
            ute_img = ute_img.resize((80, 80), Image.LANCZOS)
            self.ute_logo = ImageTk.PhotoImage(ute_img)

            # Hình hệ thống băng chuyền
            conveyor_img = Image.open(self._get_image_path("conveyor_system.png"))
            conveyor_img = conveyor_img.resize((380, 260), Image.LANCZOS)
            self.conveyor_image = ImageTk.PhotoImage(conveyor_img)


        except FileNotFoundError as e:
            messagebox.showerror("Lỗi", f"Không tìm thấy file ảnh:\n{e}")
            sys.exit(1)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi tải ảnh:\n{e}")
            sys.exit(1)

    # ─── Xây dựng giao diện ──────────────────────────────────────────
    def _build_ui(self):
        """Xây dựng toàn bộ giao diện."""
        # Gói toàn bộ giao diện vào một Frame trung tâm để tự căn giữa khi cửa sổ to ra
        self.wrapper = tk.Frame(self.root, bg=self.BG_COLOR)
        self.wrapper.pack(fill="both", expand=True, padx=30, pady=30)
        
        self._build_header()
        self._build_content()
        self._build_buttons()

    def _build_header(self):
        """Phần header: logo + thông tin khoa/trường."""
        header_frame = tk.Frame(self.wrapper, bg=self.BG_COLOR)
        header_frame.pack(fill="x", padx=20, pady=(15, 5))

        # Logo khoa (trái)
        logo_left = tk.Label(header_frame, image=self.faculty_logo, bg=self.BG_COLOR)
        logo_left.pack(side="left", padx=(0, 10))

        # Thông tin trường/khoa (giữa)
        info_frame = tk.Frame(header_frame, bg=self.BG_COLOR)
        info_frame.pack(side="left", expand=True, fill="x")

        tk.Label(
            info_frame,
            text="TRƯỜNG ĐẠI HỌC CÔNG NGHỆ KỸ THUẬT TP.HCM",
            font=("Arial", 13, "bold"),
            fg=self.SUBTITLE_COLOR,
            bg=self.BG_COLOR,
        ).pack()

        tk.Label(
            info_frame,
            text="KHOA ĐIỆN-ĐIỆN TỬ",
            font=("Arial", 18, "bold"),
            fg=self.TITLE_COLOR,
            bg=self.BG_COLOR,
        ).pack()

        tk.Label(
            info_frame,
            text="NGÀNH CNKT ĐIỀU KHIỂN VÀ TỰ ĐỘNG HÓA",
            font=("Arial", 14, "bold"),
            fg=self.SUBTITLE_COLOR,
            bg=self.BG_COLOR,
        ).pack()

        # Logo UTE (phải)
        logo_right = tk.Label(header_frame, image=self.ute_logo, bg=self.BG_COLOR)
        logo_right.pack(side="right", padx=(10, 0))

    def _build_content(self):
        """Phần nội dung: đề tài, GVHD, nhóm, hình ảnh."""
        content_frame = tk.Frame(self.wrapper, bg=self.BG_COLOR)
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # ── Đề tài ──
        topic_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        topic_frame.pack(fill="x", pady=(5, 10))

        tk.Label(
            topic_frame,
            text="ĐỒ ÁN ĐIỀU KHIỂN LẬP TRÌNH",
            font=("Arial", 14, "bold"),
            fg=self.TOPIC_COLOR,
            bg=self.BG_COLOR,
        ).pack(pady=(0, 5))

        tk.Label(
            topic_frame,
            text="ĐỀ TÀI: HỆ THỐNG PHÂN LOẠI HẠNG CHẤT LƯỢNG TÁO",
            font=("Arial", 13, "bold"),
            fg=self.TOPIC_COLOR,
            bg=self.BG_COLOR,
            wraplength=800,
        ).pack()

        # ── Khu vực chính: Hình ảnh (trái) + Thông tin (phải) ──
        main_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        main_frame.pack(fill="both", expand=True, pady=5)

        # --- Hình băng chuyền (bên trái) ---
        img_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        img_frame.pack(side="left", expand=True, fill="both", padx=(0, 15))

        tk.Label(img_frame, image=self.conveyor_image, bg=self.BG_COLOR).pack(
            expand=True
        )

        # --- Thông tin bên phải ---
        info_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        info_frame.pack(side="right", expand=True)

        # GVHD
        tk.Label(
            info_frame,
            text="GVHD: TS. Lê Chí Kiên",
            font=("Arial", 15, "bold"),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR,
            anchor="w",
        ).pack(fill="x", pady=(15, 15))

        # Danh sách thành viên
        members = [
            ("Mai Hoàng Nhã", "23151284"),
            ("Mai Nguyễn Minh Nhật", "23151287"),
            
        ]

        for name, student_id in members:
            member_frame = tk.Frame(info_frame, bg=self.BG_COLOR)
            member_frame.pack(fill="x", pady=5)

            tk.Label(
                member_frame,
                text=name,
                font=("Arial", 14),
                fg=self.TEXT_COLOR,
                bg=self.BG_COLOR,
                width=22,
                anchor="w",
            ).pack(side="left")

            tk.Label(
                member_frame,
                text=student_id,
                font=("Arial", 14),
                fg=self.TEXT_COLOR,
                bg=self.BG_COLOR,
                anchor="w",
            ).pack(side="left")



    def _build_buttons(self):
        """Phần nút bấm ở cuối giao diện."""
        # Đường kẻ phân cách
        separator = tk.Frame(self.wrapper, height=2, bg="#E0E0E0")
        separator.pack(fill="x", padx=20, pady=(5, 0))

        btn_frame = tk.Frame(self.wrapper, bg="#F5F5F5")
        btn_frame.pack(fill="x", padx=0, pady=0, side="bottom")

        btn_container = tk.Frame(btn_frame, bg="#F5F5F5")
        btn_container.pack(expand=True)

        # Nút "Chạy chương trình"
        btn_run = tk.Button(
            btn_container,
            text="Chạy chương trình",
            font=("Arial", 14, "bold"),
            fg=self.BTN_TEXT_COLOR,
            bg=self.BTN_RUN_COLOR,
            activebackground="#388E3C",
            activeforeground=self.BTN_TEXT_COLOR,
            relief="flat",
            cursor="hand2",
            padx=35,
            pady=12,
            command=self._on_run,
        )
        btn_run.pack(side="left", padx=15, pady=20)

        # Nút "Kết thúc chương trình"
        btn_stop = tk.Button(
            btn_container,
            text="Kết thúc chương trình",
            font=("Arial", 14, "bold"),
            fg=self.BTN_TEXT_COLOR,
            bg=self.BTN_STOP_COLOR,
            activebackground="#D32F2F",
            activeforeground=self.BTN_TEXT_COLOR,
            relief="flat",
            cursor="hand2",
            padx=35,
            pady=12,
            command=self._on_stop,
        )
        btn_stop.pack(side="left", padx=15, pady=20)


    # ─── Xử lý sự kiện ───────────────────────────────────────────────
    def _on_run(self):
        """Mở cửa sổ chương trình chính và ẩn màn hình chào mừng."""
        self.root.withdraw() # Ẩn màn hình chào mừng
        CameraWindow(self.root)

    def _on_stop(self):
        """Xử lý khi nhấn nút 'Kết thúc chương trình'."""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn kết thúc chương trình?"):
            self.root.destroy()


# ─── Cửa sổ Camera + Phân loại + PLC ─────────────────────────────────
class CameraWindow:
    """Cửa sổ chính: stream camera, thống kê phân loại, giao tiếp PLC S7-1200."""

    CAM_SOURCES = [
        "Astra Pro SDK (Depth + RGB)",
        "Camera máy tính (Tích hợp)",
        "Webcam rời 1 (Cổng USB)",
        "Webcam rời 2 (Cổng USB)",
        "Luồng RTSP / IP Camera",
        "📂 Mở File Ảnh (.jpg, .png)",
        "🎞️ Mở File Video (.mp4, .avi)"
    ]

    GRADE_CFG = {
        "Grade-1":   {"label": "Grade-1",   "color": "#00E676", "bg": "#0A2E14", "icon": "✅", "desc": "TC1 (≥80%) & TC2 (≥80mm)"},
        "Grade-2": {"label": "Grade-2", "color": "#FFD600", "bg": "#2E2800", "icon": "🟡", "desc": "TC1 (70-79%) hoặc TC2 (60-79mm)"},
        "Grade-3":    {"label": "Grade-3",    "color": "#FF1744", "bg": "#2E0A0A", "icon": "❌", "desc": "TC1 (<70%) hoặc TC2 (<60mm)"},
    }

    # Địa chỉ Merker PLC S7-1200 (1214C)
    # MW10=Grade-1, MW12=Grade-2, MW14=Grade-3  |  M0.0=Start, M0.1=Stop
    PLC_MW_GRADE1   = 10
    PLC_MW_GRADE2 = 12
    PLC_MW_GRADE3    = 14
    PLC_START_BYTE, PLC_START_BIT = 0, 0
    PLC_STOP_BYTE,  PLC_STOP_BIT  = 0, 1

    def __init__(self, parent):
        self.parent = parent
        self.db = AppDatabase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # ── Camera (hoàn toàn độc lập với PLC) ──
        self.camera = CameraManager(
            on_frame_callback=self._on_frame_received,
            on_error_callback=lambda msg: (messagebox.showerror("Lỗi Camera", msg), self._log_event(msg, "ERROR")),
            on_log_callback=self._log_event
        )
        self.last_buffer_time = 0

        # ── PLC (chỉ khởi tạo khi bấm Kết nối) ──
        self.plc = PLCManager()
        self._plc_poll_id   = None
        self._count_vars    = {}
        self._percent_vars  = {}

        # ── Quản lý Trang & Menu ──
        self.sidebar_visible = False
        self.current_page = "PHANLOAI" 
        self._grade_desc_labels = {} 
        
        # ── Biến cấu hình hệ thống (Có thể chỉnh sửa từ UI) ──
        self.cfg_smooth_frames = tk.StringVar(value="10")
        self.cfg_analysis_ms = tk.StringVar(value="100")
        self._last_analysis_time = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Hệ thống phân loại hạng chất lượng táo")
        self.win.configure(bg="#F1F5F9")
        self.win.resizable(True, True)
        # Loại bỏ thanh tiêu đề mặc định của Windows để dùng custom header
        self.win.overrideredirect(True)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        W, H = 1160, 760 # Tăng chiều cao để hiển thị đủ thẻ Yield và nút Camera
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        self.win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self.analyzer = FruitAnalyzer()
        self.current_grade = "UNKNOWN"
        self._refresh_stats_ui() # Tải thống kê từ CSDL cũ (nếu có)
        self._build_ui()
        self._log_event("Hệ thống Vision đã khởi động.", "INFO")
        
        # Thẻ để Windows nhận diện là một ứng dụng riêng biệt trên Taskbar (quan trọng cho cửa sổ borderless)
        self.win.after(200, self._set_appwindow)

    def _set_appwindow(self):
        """Hệ quả của overrideredirect(True) là mất icon Taskbar. Hàm này dùng ctypes để lấy lại icon đó."""
        try:
            import ctypes
            # GWL_EXSTYLE = -20, WS_EX_APPWINDOW = 0x00040000, WS_EX_TOOLWINDOW = 0x00000080
            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style = style & ~0x00000080 # Xóa ToolWindow (ẩn khỏi taskbar)
            style = style | 0x00040000  # Thêm AppWindow (hiện ở taskbar)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
            
            # Cần ẩn và hiện lại để Windows cập nhật taskbar
            # self.win.withdraw()
            # self.win.deiconify()
        except Exception as e:
            print(f"Failed to set Taskbar Icon: {e}")

    def _refresh_stats_ui(self):
        """Cập nhật các ô số Grade-1/Grade-2/Grade-3 và Yield Rate từ CSDL."""
        if not hasattr(self, 'win') or not self.win.winfo_exists(): return
        try:
            stats = self.db.get_stats()
            total = stats["TOTAL"]
            
            for grade in ["Grade-1", "Grade-2", "Grade-3"]:
                if grade in getattr(self, "_count_vars", {}):
                    count = stats[grade]
                    self._count_vars[grade].set(str(count))
                    
                    # Cập nhật % từng loại
                    if grade in getattr(self, "_percent_vars", {}):
                        p = (count / total * 100) if total > 0 else 0
                        self._percent_vars[grade].set(f"({p:.1f}%)")
                    
            if hasattr(self, '_total_var'):
                self._total_var.set(str(total))
                
            if total > 0:
                y_rate = (stats["Grade-1"] / total) * 100
                if hasattr(self, '_yield_var'):
                    self._yield_var.set(f"{y_rate:.1f}%")
        except Exception as e:
            print(f"Error refreshing stats: {e}")

    # ═══════════════════════════════════════════════════════
    #  DATABASE (SQLITE) & LƯU ẢNH
    # ═══════════════════════════════════════════════════════
    def _init_db(self):
        # Hàm này đã được chuyển vào modules/database.py
        pass

    def _save_to_sql(self, grade=None):
        """Lưu lịch sử phân loại vào Database."""
        if not hasattr(self, 'frame_to_save') or self.frame_to_save is None:
            return

        if not grade or grade == "MANUAL":
            grade = self.current_grade if hasattr(self, 'current_grade') else "UNKNOWN"
            
        # Lấy đường kính hiện tại (nếu có)
        diameter = getattr(self, "current_diameter", 0)
            
        success, msg, filepath = self.db.save_record(grade, self.frame_to_save, diameter_mm=diameter)
        if success:
            self._log_event(msg, "INFO")
            self._refresh_stats_ui()
            
            # Cập nhật khung hình 10 ảnh
            if hasattr(self, 'win'):
                self.win.after(0, self._update_snapshot_gallery, filepath, None)
                
            # Nếu đang ở trang Lịch sử thì cập nhật bảng
            if getattr(self, "current_page", None) == "history":
                self._refresh_history_table()

    def _update_snapshot_gallery(self, filepath=None, cv2_frame=None):
        if not hasattr(self, 'win') or not self.win.winfo_exists(): return
        try:
            if filepath:
                img = Image.open(filepath)
            elif cv2_frame is not None:
                rgb_frame = cv2.cvtColor(cv2_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
            else:
                return
            
            # Khung nhỏ (dưới camera)
            img_small = img.resize((85, 60), Image.LANCZOS)
            photo_small = ImageTk.PhotoImage(img_small)
            self.snapshot_images.insert(0, photo_small)
            if len(self.snapshot_images) > 10:
                self.snapshot_images.pop()
            for i, p in enumerate(self.snapshot_images):
                self.snapshot_labels[i].config(image=p, width=85, height=60)
                self.snapshot_labels[i].image = p
        except Exception as e:
            print(f"Error updating snapshot: {e}")
            self._log_event(f"Error updating snapshot: {e}", "ERROR")

    def _manual_snapshot(self):
        """Gọi khi nhấn nút Chụp Ảnh Thủ Công."""
        if not self.camera.is_running():
            messagebox.showwarning("Cảnh báo", "Vui lòng Bật Camera trước khi chụp!")
            return
        
        if not hasattr(self, 'frame_to_save') or self.frame_to_save is None:
            messagebox.showwarning("Cảnh báo", "Chưa nhận được khung hình từ Camera!")
            return
            
        self._save_to_sql("MANUAL")

    def _on_view_mode_change(self, event=None):
        """Cập nhật tiêu đề khi đổi chế độ hiển thị."""
        mode = self.view_mode_var.get()
        if mode == "Color & Gray":
            self.lbl_view1.config(text="📷  CAMERA (COLOR)")
            self.lbl_view2.config(text="🔲  MACHINE VISION (GRAYSCALE)")
        elif mode == "Color & Binary":
            self.lbl_view1.config(text="📷  CAMERA (COLOR)")
            self.lbl_view2.config(text="🔳  MACHINE VISION (BINARY/THRESHOLD)")
        elif mode == "Gray & Binary":
            self.lbl_view1.config(text="🔲  MACHINE VISION (GRAYSCALE)")
            self.lbl_view2.config(text="🔳  MACHINE VISION (BINARY/THRESHOLD)")
        elif mode == "Color & BG Removal":
            self.lbl_view1.config(text="📷  CAMERA (COLOR)")
            self.lbl_view2.config(text="👤  FOREGROUND MASK (BG REMOVAL)")

    def _clear_buffer(self):
        """Xóa sạch bộ nhớ đệm hình ảnh (Buffer)."""
        self.snapshot_images = []
            
        # Reset các label ở màn hình chính
        for lbl in self.snapshot_labels:
            lbl.config(image='')
            lbl.image = None
                
        self._log_event("🧹 Đã xóa sạch bộ nhớ đệm (Buffer Cleared).", "WARNING")


    # ═══════════════════════════════════════════════════════
    #  GIAO DIỆN & NAVIGATION
    # ═══════════════════════════════════════════════════════
    # ── Hằng số cấu hình Log ──
    LOG_MAX_LINES = 500  # Giới hạn số dòng tối đa để tránh tràn bộ nhớ

    def _log_event(self, msg, level=None):
        """Ghi log vào ô Text với phân loại màu sắc (INFO, WARNING, ERROR, SUCCESS).
        Khi level=ERROR/WARNING, tự động ghi thêm vị trí gọi (hàm, file, dòng) để dễ debug."""
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
            return
        try:
            import time
            import inspect
            t = time.strftime("%H:%M:%S")
            self.log_text.config(state="normal")

            # Tự động nhận diện level
            tag = "info"
            if level:
                lu = level.upper()
                if lu == "WARNING":  tag = "warning"
                elif lu == "ERROR":  tag = "error"
                elif lu == "SUCCESS": tag = "success"
            else:
                msg_lower = msg.lower()
                if any(x in msg for x in ["⚠️", "cảnh báo", "warning"]):
                    tag = "warning"
                elif any(x in msg_lower for x in ["lỗi", "error", "❌", "🔴", "critical"]):
                    tag = "error"
                elif any(x in msg for x in ["✅", "🟢", "thành công", "success"]):
                    tag = "success"

            # Tự động lấy vị trí nguồn gốc lỗi khi ERROR hoặc WARNING
            source_info = ""
            if tag in ("error", "warning"):
                # Lấy caller frame (bỏ qua chính _log_event)
                frame = inspect.currentframe()
                caller = frame.f_back if frame else None
                if caller:
                    func_name = caller.f_code.co_name
                    file_name = os.path.basename(caller.f_code.co_filename)
                    line_no = caller.f_lineno
                    source_info = f"  📍 [{file_name} → {func_name}() dòng {line_no}]"

            # Prefix icon theo level
            prefix_map = {"info": "ℹ", "warning": "⚠", "error": "✖", "success": "✔"}
            prefix = prefix_map.get(tag, "")

            # Chèn dòng log
            self.log_text.insert("end", f"[{t}] ", "time")
            self.log_text.insert("end", f"{prefix} {msg}{source_info}\n", tag)

            # Giới hạn số dòng
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > self.LOG_MAX_LINES:
                self.log_text.delete("1.0", f"{line_count - self.LOG_MAX_LINES}.0")

            self.log_text.see("end")
            self.log_text.config(state="disabled")

            # Cập nhật bộ đếm
            if not hasattr(self, '_log_counters'):
                self._log_counters = {"info": 0, "warning": 0, "error": 0, "success": 0}
            self._log_counters[tag] = self._log_counters.get(tag, 0) + 1
            self._update_log_counter_badges()

            # Lưu vào bộ nhớ nội bộ để lọc
            if not hasattr(self, '_log_entries'):
                self._log_entries = []
            self._log_entries.append({"time": t, "msg": msg, "tag": tag, "prefix": prefix, "source": source_info})
            if len(self._log_entries) > self.LOG_MAX_LINES:
                self._log_entries = self._log_entries[-self.LOG_MAX_LINES:]

            # Hiệu ứng nhấp nháy viền khi có ERROR
            if tag == "error" and hasattr(self, '_log_frame_widget'):
                self._flash_log_border()
        except:
            pass

    def _build_ui(self):
        # 1. Thanh tiêu đề (Header) với nút Menu
        self.hdr = tk.Frame(self.win, bg="#0F172A", height=50) # Slate 900
        self.hdr.pack(fill="x", side="top")
        self.hdr.pack_propagate(False)

        # Nút 3 gạch (☰)
        self.btn_menu = tk.Button(self.hdr, text="☰", font=("Arial", 18, "bold"),
                                  fg="#38BDF8", bg="#0F172A", activebackground="#1E293B",
                                  activeforeground="#FFFFFF", bd=0, cursor="hand2",
                                  padx=15, command=self._toggle_sidebar)
        self.btn_menu.pack(side="left")

        self.title_lbl = tk.Label(self.hdr, text="🍎 HỆ THỐNG PHÂN LOẠI TÁO (MODERN PROFESSIONAL MODE)",
                                  font=("Arial", 12, "bold"), fg="#F8FAFC", bg="#0F172A")
        self.title_lbl.pack(side="left", padx=10)

        # Nút điều khiển cửa sổ (bên phải header)
        window_controls = tk.Frame(self.hdr, bg="#0F172A")
        window_controls.pack(side="right", padx=10)

        self.btn_minimize = tk.Button(window_controls, text="—", font=("Arial", 10, "bold"),
                                      fg="#94A3B8", bg="#0F172A", activebackground="#1E293B",
                                      activeforeground="#FFFFFF", bd=0, cursor="hand2", width=4,
                                      command=self._minimize_window)
        self.btn_minimize.pack(side="left")

        self.btn_restore = tk.Button(window_controls, text="▢", font=("Arial", 12, "bold"),
                                     fg="#94A3B8", bg="#0F172A", activebackground="#1E293B",
                                     activeforeground="#FFFFFF", bd=0, cursor="hand2", width=4,
                                     command=self._restore_window)
        self.btn_restore.pack(side="left")

        self.btn_close = tk.Button(window_controls, text="✕", font=("Arial", 12, "bold"),
                                   fg="#94A3B8", bg="#0F172A", activebackground="#EF4444",
                                   activeforeground="#FFFFFF", bd=0, cursor="hand2", width=4,
                                   command=self._on_close)
        self.btn_close.pack(side="left")

        # Hỗ trợ kéo thả cửa sổ bằng header
        self.hdr.bind("<ButtonPress-1>", self._start_move)
        self.hdr.bind("<B1-Motion>", self._do_move)
        self.title_lbl.bind("<ButtonPress-1>", self._start_move)
        self.title_lbl.bind("<B1-Motion>", self._do_move)

        # 2. Container chính
        self.main_container = tk.Frame(self.win, bg="#F1F5F9")
        self.main_container.pack(fill="both", expand=True)

        # 3. Sidebar
        self.sidebar = tk.Frame(self.win, bg="#FFFFFF", width=220, bd=1, relief="ridge")
        self.sidebar.place(x=-220, y=50, relheight=1)

        self._build_sidebar_items()

        # 4. Tạo các Trang (Frames)
        self.page_phanloai = tk.Frame(self.main_container, bg="#F1F5F9")
        self.page_setting = tk.Frame(self.main_container, bg="#F1F5F9")
        self.page_history = tk.Frame(self.main_container, bg="#F1F5F9")

        self._build_phanloai_page()
        self._build_setting_page()
        self._build_history_page()

        # Hiển thị trang mặc định
        self._show_page("PHANLOAI")

    def _toggle_sidebar(self):
        """Hiệu ứng ẩn hiện Sidebar."""
        if not self.sidebar_visible:
            # Hiện sidebar
            self._animate_sidebar(0)
            self.sidebar_visible = True
        else:
            # Ẩn sidebar
            self._animate_sidebar(-220)
            self.sidebar_visible = False

    def _animate_sidebar(self, target_x):
        self.sidebar.place(x=target_x)

    # ─── ĐIỀU KHIỂN CỬA SỔ (WINDOW CONTROLS) ─────────────────────────
    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.win.winfo_x() + deltax
        y = self.win.winfo_y() + deltay
        self.win.geometry(f"+{x}+{y}")

    def _minimize_window(self):
        """Thu nhỏ cửa sổ xuống Taskbar."""
        self.win.update_idletasks()
        self.win.overrideredirect(False)
        self.win.state('iconic')
        # Khi người dùng mở lại từ taskbar, bind sự kiện Map để bật lại không viền
        self.win.bind("<Map>", self._on_deiconify)
        
    def _on_deiconify(self, event):
        """Bật lại chế độ không viền khi cửa sổ hiện lên."""
        self.win.unbind("<Map>")
        self.win.overrideredirect(True)
        self.win.after(10, self._set_appwindow)

    def _restore_window(self):
        if self.win.state() == 'zoomed':
            self.win.state('normal')
            self.btn_restore.config(text="🗗") # Icon Restore Down
        else:
            self.win.state('zoomed')
            self.btn_restore.config(text="🗖") # Icon Maximize

    def _build_sidebar_items(self):
        """Các mục trong menu bên."""
        tk.Label(self.sidebar, text="MENU CHÍNH", font=("Arial", 10, "bold"),
                 fg="#0284C7", bg="#FFFFFF", pady=20).pack()

        menu_items = [
            ("📊  PHÂN LOẠI", "PHANLOAI"),
            ("⚙️  CÀI ĐẶT", "SETTING"),
            ("📂  LỊCH SỬ SQL", "HISTORY")
        ]

        for text, page_id in menu_items:
            btn = tk.Button(self.sidebar, text=text, font=("Arial", 11, "bold"),
                            fg="#334155", bg="#FFFFFF", activebackground="#F1F5F9",
                            activeforeground="#0284C7", bd=0, cursor="hand2",
                            anchor="w", padx=25, pady=12,
                            command=lambda p=page_id: self._show_page(p))
            btn.pack(fill="x")

    def _show_page(self, page_id):
        """Chuyển đổi giữa các trang."""

        
        self.current_page = page_id
        
        # Ẩn tất cả trang
        self.page_phanloai.pack_forget()
        self.page_setting.pack_forget()
        if hasattr(self, 'page_history'): self.page_history.pack_forget()

        if page_id == "PHANLOAI":
            self.page_phanloai.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🍎 HỆ THỐNG PHÂN LOẠI TÁO - GIÁM SÁT")
        elif page_id == "HISTORY":
            if hasattr(self, 'page_history'):
                self.page_history.pack(fill="both", expand=True, padx=10, pady=10)
                self._refresh_history_table() # Tải lại dữ liệu mỗi khi mở trang
            self.title_lbl.config(text="📂 LỊCH SỬ PHÂN LOẠI SQL")
        else:
            self.page_setting.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="⚙️ HỆ THỐNG PHÂN LOẠI TÁO - CÀI ĐẶT")

        # Đóng menu sau khi chọn
        if self.sidebar_visible:
            self._toggle_sidebar()



    def _build_history_page(self):
        """Trang Lịch sử phân loại (SQL Database)."""
        container = tk.Frame(self.page_history, bg="#FFFFFF", bd=1, relief="ridge")
        container.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Label(container, text="📂 DANH SÁCH LỊCH SỬ PHÂN LOẠI (SQL DATABASE)", 
                 font=("Arial", 12, "bold"), fg="#0F172A", bg="#FFFFFF", pady=15).pack()

        # Bảng dữ liệu
        cols = ("ID", "Thời gian", "Kết quả", "Tỷ lệ", "Đường dẫn ảnh")
        self.history_tree = ttk.Treeview(container, columns=cols, show="headings", height=15)
        
        # Cấu hình cột
        self.history_tree.heading("ID", text="ID")
        self.history_tree.column("ID", width=50, anchor="center")
        self.history_tree.heading("Thời gian", text="Thời gian")
        self.history_tree.column("Thời gian", width=150, anchor="center")
        self.history_tree.heading("Kết quả", text="Kết quả")
        self.history_tree.column("Kết quả", width=100, anchor="center")
        self.history_tree.heading("Tỷ lệ", text="Tỷ lệ Yield")
        self.history_tree.column("Tỷ lệ", width=100, anchor="center")
        self.history_tree.heading("Đường dẫn ảnh", text="Đường dẫn file ảnh")
        self.history_tree.column("Đường dẫn ảnh", width=400, anchor="w")
        
        self.history_tree.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Nút điều khiển
        btn_frame = tk.Frame(container, bg="#FFFFFF")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="🔄 LÀM MỚI", font=("Arial", 10, "bold"),
                  bg="#0284C7", fg="white", width=15, pady=8, cursor="hand2",
                  command=self._refresh_history_table).pack(side="left", padx=10)
                  
        tk.Button(btn_frame, text="🗑️ XÓA SẠCH DỮ LIỆU", font=("Arial", 10, "bold"),
                  bg="#EF4444", fg="white", width=20, pady=8, cursor="hand2",
                  command=self._clear_sql_history).pack(side="left", padx=10)

    def _refresh_history_table(self):
        """Tải lại dữ liệu từ CSDL vào bảng."""
        if not hasattr(self, 'history_tree'): return
        
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        try:
            conn = sqlite3.connect(self.db.db_path)
            c = conn.cursor()
            # Lấy các cột tương ứng với bảng Treeview (ID, thoi_gian, ket_qua, ty_le_yield, duong_dan_anh)
            # Lưu ý: ty_le_yield hiện tại có thể đang để trống hoặc chứa thông tin khác
            c.execute("SELECT id, thoi_gian, ket_qua, ty_le_yield, duong_dan_anh FROM phan_loai_history ORDER BY id DESC LIMIT 100")
            rows = c.fetchall()
            for row in rows:
                self.history_tree.insert("", "end", values=row)
            conn.close()
        except Exception as e:
            self._log_event(f"Lỗi đọc DB: {e}", "ERROR")

    def _clear_sql_history(self):
        """Xóa toàn bộ dữ liệu trong bảng và xóa sạch file ảnh trong thư mục."""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa TOÀN BỘ lịch sử và hình ảnh?\n(Hành động này không thể hoàn tác!)"):
            try:
                conn = sqlite3.connect(self.db.db_path)
                c = conn.cursor()
                c.execute("DELETE FROM phan_loai_history")
                conn.commit()
                conn.close()
                
                if os.path.exists(self.db.img_dir):
                    for f in os.listdir(self.db.img_dir):
                        file_path = os.path.join(self.db.img_dir, f)
                        try:
                            if os.path.isfile(file_path): os.unlink(file_path)
                        except: pass
                
                self._refresh_history_table()
                self._refresh_stats_ui() # Reset các con số về 0
                messagebox.showinfo("Thành công", "Đã dọn dẹp sạch sẽ CSDL và thư mục ảnh!")
                self._log_event("🗑️ Đã xóa sạch toàn bộ lịch sử SQL.", "WARNING")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa dữ liệu: {e}")

    def _build_phanloai_page(self):
        """Trang Phân loại: Thống kê + Camera + Start/Stop + Log."""
        # 1. Log và PLC ở dưới cùng
        self._build_plc_status_area(self.page_phanloai)
        self._build_log_area(self.page_phanloai)

        # 2. Sau đó mới chia layout Trái (Stats) / Phải (Camera) ở phần còn lại
        self._build_left(self.page_phanloai)
        self._build_right(self.page_phanloai)

    def _build_setting_page(self):
        """Trang Cài đặt: PLC IP, Nguồn Camera, Reset."""
        container = tk.Frame(self.page_setting, bg="#F1F5F9")
        container.place(relx=0.5, rely=0.4, anchor="center")

        # 1. Cấu hình PLC
        plc_box = tk.LabelFrame(container, text=" KẾT NỐI PLC S7-1200 ", font=("Arial", 10, "bold"),
                                fg="#0284C7", bg="#FFFFFF", padx=20, pady=20)
        plc_box.pack(fill="x", pady=10)

        # IP Entry
        tk.Label(plc_box, text="Địa chỉ IP:", fg="#475569", bg="#FFFFFF").grid(row=0, column=0, sticky="w")
        self.plc_ip_var = tk.StringVar(value="192.168.0.1")
        tk.Entry(plc_box, textvariable=self.plc_ip_var, width=20, bg="#F8FAFC", fg="#0F172A", bd=1).grid(row=0, column=1, padx=10, pady=5)

        # Rack/Slot
        tk.Label(plc_box, text="Rack/Slot:", fg="#475569", bg="#FFFFFF").grid(row=1, column=0, sticky="w")
        rs_frame = tk.Frame(plc_box, bg="#FFFFFF")
        rs_frame.grid(row=1, column=1, sticky="w", pady=5, padx=10)
        self.plc_rack_var = tk.StringVar(value="0")
        self.plc_slot_var = tk.StringVar(value="1")
        tk.Entry(rs_frame, textvariable=self.plc_rack_var, width=3, bg="#F8FAFC", fg="#0F172A", bd=1).pack(side="left")
        tk.Label(rs_frame, text=" / ", fg="#475569", bg="#FFFFFF").pack(side="left")
        tk.Entry(rs_frame, textvariable=self.plc_slot_var, width=3, bg="#F8FAFC", fg="#0F172A", bd=1).pack(side="left")

        self.btn_connect = tk.Button(plc_box, text="🔌 KẾT NỐI PLC", font=("Arial", 10, "bold"),
                                     bg="#1976D2", fg="white", padx=20, command=self._toggle_plc)
        self.btn_connect.grid(row=2, column=0, columnspan=2, pady=15)

        # 2. Cấu hình Camera
        cam_box = tk.LabelFrame(container, text=" CẤU HÌNH CAMERA ", font=("Arial", 10, "bold"),
                                fg="#0284C7", bg="#FFFFFF", padx=20, pady=20)
        cam_box.pack(fill="x", pady=10)
        
        tk.Label(cam_box, text="Chế độ Hoạt động (Mode):", fg="#475569", bg="#FFFFFF").pack(anchor="w")
        self.cam_var = tk.StringVar(value=self.CAM_SOURCES[0]) # Mặc định chọn Astra Pro SDK
        self.combo = ttk.Combobox(cam_box, textvariable=self.cam_var, values=self.CAM_SOURCES, state="readonly", width=35)
        self.combo.pack(pady=(0, 15), anchor="w")

        # Nút Tìm Camera Tự Động
        tk.Button(cam_box, text="🔍 TÌM TẤT CẢ CAMERA", font=("Arial", 9, "bold"),
                  bg="#8B5CF6", fg="white", padx=15, pady=5, cursor="hand2",
                  command=self._detect_cameras).pack(pady=(0, 15), anchor="w")

        tk.Label(cam_box, text="Nguồn Camera Màu (Khi dùng Astra 3D):", fg="#475569", bg="#FFFFFF").pack(anchor="w")
        self.astra_color_list = ["Cổng 0 (Laptop)", "Cổng 1 (USB Ngoài 1)", "Cổng 2 (USB Ngoài 2)"]
        self.astra_color_var = tk.StringVar(value=self.astra_color_list[1]) # Ưu tiên cổng 1 cho Astra
        self.combo_astra_color = ttk.Combobox(cam_box, textvariable=self.astra_color_var, values=self.astra_color_list, state="readonly", width=35)
        self.combo_astra_color.pack(pady=(0, 5), anchor="w")

        # 3. Cấu hình xử lý ảnh (MỚI CHUYỂN VÀO ĐÂY)
        proc_box = tk.LabelFrame(container, text=" CẤU HÌNH XỬ LÝ HÌNH ẢNH ", font=("Arial", 10, "bold"),
                                 fg="#0284C7", bg="#FFFFFF", padx=20, pady=15)
        proc_box.pack(fill="x", pady=10)

        # Số khung hình mượt
        tk.Label(proc_box, text="Số khung hình mượt (Smoothing):", bg="#FFFFFF").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(proc_box, textvariable=self.cfg_smooth_frames, width=10, justify="center", font=("Arial", 10, "bold")).grid(row=0, column=1, padx=10)

        # Tốc độ quét
        tk.Label(proc_box, text="Tốc độ chụp/quét (ms):", bg="#FFFFFF").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(proc_box, textvariable=self.cfg_analysis_ms, width=10, justify="center", font=("Arial", 10, "bold")).grid(row=1, column=1, padx=10)

        # Nút Lưu Cấu Hình
        tk.Button(proc_box, text="💾 LƯU VÀ CẬP NHẬT CẤU HÌNH", font=("Arial", 9, "bold"), bg="#0EA5E9", fg="white", 
                  padx=15, command=self._save_system_config).grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="we")

        tk.Button(container, text="🔄 RESET BỘ ĐẾM DỮ LIỆU", bg="#3949AB", fg="white", 
                  font=("Arial", 10, "bold"), pady=8, command=self._reset_counts).pack(fill="x", pady=10)

    def _build_log_area(self, parent):
        """Khung hiển thị Log nâng cao: lọc, đếm, sao chép, xuất file."""
        self._log_frame_widget = tk.LabelFrame(
            parent, text=" 📝 EVENT LOG ",
            font=("Arial", 9, "bold"), fg="#475569", bg="#FFFFFF", padx=6, pady=4)
        self._log_frame_widget.pack(side="bottom", fill="x", padx=5, pady=(0, 5))

        # ── Thanh công cụ Log (toolbar) ──
        toolbar = tk.Frame(self._log_frame_widget, bg="#FFFFFF")
        toolbar.pack(fill="x", pady=(0, 3))

        # Nút lọc theo level
        self._log_filter_var = tk.StringVar(value="ALL")
        filter_cfg = [
            ("ALL",     "#334155", "#F1F5F9"),
            ("INFO",    "#0F172A", "#E0F2FE"),
            ("SUCCESS", "#065F46", "#D1FAE5"),
            ("WARNING", "#92400E", "#FEF3C7"),
            ("ERROR",   "#991B1B", "#FEE2E2"),
        ]
        for label, fg_c, bg_c in filter_cfg:
            btn = tk.Button(
                toolbar, text=label, font=("Consolas", 7, "bold"),
                fg=fg_c, bg=bg_c, bd=0, padx=6, pady=1, cursor="hand2",
                command=lambda l=label: self._filter_log(l))
            btn.pack(side="left", padx=1)

        # Badge đếm lỗi / cảnh báo
        self._badge_error = tk.Label(toolbar, text="ERR: 0", font=("Consolas", 7, "bold"),
                                      fg="#FFFFFF", bg="#EF4444", padx=4, pady=0)
        self._badge_error.pack(side="right", padx=(2, 0))
        self._badge_warn = tk.Label(toolbar, text="WARN: 0", font=("Consolas", 7, "bold"),
                                     fg="#FFFFFF", bg="#F59E0B", padx=4, pady=0)
        self._badge_warn.pack(side="right", padx=(2, 0))

        # Nút tiện ích
        tk.Button(toolbar, text="📋 Copy", font=("Arial", 7, "bold"),
                  fg="#334155", bg="#E2E8F0", bd=0, padx=5, cursor="hand2",
                  command=self._copy_log_to_clipboard).pack(side="right", padx=2)
        tk.Button(toolbar, text="💾 Xuất", font=("Arial", 7, "bold"),
                  fg="#334155", bg="#E2E8F0", bd=0, padx=5, cursor="hand2",
                  command=self._export_log_to_file).pack(side="right", padx=2)

        # ── Vùng hiển thị log + scrollbar ──
        text_frame = tk.Frame(self._log_frame_widget, bg="#F8FAFC")
        text_frame.pack(fill="x")

        scrollbar = tk.Scrollbar(text_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            text_frame, height=4, bg="#F8FAFC", fg="#0F172A",
            font=("Consolas", 9), bd=0, state="disabled",
            yscrollcommand=scrollbar.set, wrap="word")
        self.log_text.pack(side="left", fill="x", expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Cấu hình màu sắc cho các loại log
        self.log_text.tag_configure("info",    foreground="#0F172A")
        self.log_text.tag_configure("success", foreground="#059669", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("warning", foreground="#D97706", background="#FFFBEB")
        self.log_text.tag_configure("error",   foreground="#DC2626", background="#FEF2F2", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("time",    foreground="#64748B")

        # Khởi tạo bộ đếm và bộ nhớ log
        self._log_counters = {"info": 0, "warning": 0, "error": 0, "success": 0}
        self._log_entries = []

    def _build_plc_status_area(self, parent):
        """Thanh điều khiển nhanh PLC + Camera."""
        bar = tk.LabelFrame(parent, text=" ⚡ ĐIỀU KHIỂN NHANH ",
                              font=("Arial", 10, "bold"), fg="#0284C7", bg="#FFFFFF",
                              padx=10, pady=4, height=105)
        bar.pack(side="bottom", fill="x", pady=(5, 0), padx=5)
        bar.pack_propagate(False) # Ngăn khung co lại

        # ── Hàng 1: PLC START / STOP + CHỤP + XÓA BUFFER ──
        row1 = tk.Frame(bar, bg="#FFFFFF")
        row1.pack(fill="x", pady=(0, 3))

        ctrl1 = tk.Frame(row1, bg="#FFFFFF")
        ctrl1.pack()

        self.btn_start = tk.Button(ctrl1, text="▶  START", font=("Arial", 10, "bold"),
                                    fg="#FFFFFF", bg="#10B981", width=10, pady=4, 
                                    relief="flat", cursor="hand2", command=self._plc_start)
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_stop_plc = tk.Button(ctrl1, text="⏹  STOP", font=("Arial", 10, "bold"),
                                       fg="#FFFFFF", bg="#EF4444", width=10, pady=4,
                                       relief="flat", cursor="hand2", command=self._plc_stop)
        self.btn_stop_plc.pack(side="left", padx=(0, 6))

        self.btn_snapshot = tk.Button(ctrl1, text="📸 CHỤP LƯU SQL", font=("Arial", 10, "bold"),
                                       fg="#FFFFFF", bg="#F59E0B", width=14, pady=4,
                                       relief="flat", cursor="hand2", command=self._manual_snapshot)
        self.btn_snapshot.pack(side="left", padx=(0, 6))

        self.btn_clear_buffer = tk.Button(ctrl1, text="🧹 XÓA BUFFER", font=("Arial", 10, "bold"),
                                        fg="#FFFFFF", bg="#64748B", width=12, pady=4,
                                        relief="flat", cursor="hand2", command=self._clear_buffer)
        self.btn_clear_buffer.pack(side="left", padx=(0, 6))

        self.btn_plc_quick = tk.Button(ctrl1, text="🔌 KẾT NỐI PLC", font=("Arial", 10, "bold"),
                                        fg="#FFFFFF", bg="#1565C0", width=14, pady=4,
                                        relief="flat", cursor="hand2", command=self._toggle_plc)
        self.btn_plc_quick.pack(side="left", padx=(0, 6))

        self.lbl_plc_status = tk.Label(ctrl1, text="⚫ PLC chưa kết nối", font=("Arial", 9),
                                        fg="#64748B", bg="#FFFFFF")
        self.lbl_plc_status.pack(side="left", padx=(6, 0))

        # ── Hàng 2: Camera ON/OFF + MỞ FILE + Trạng thái Camera ──
        row2 = tk.Frame(bar, bg="#FFFFFF")
        row2.pack(fill="x")

        ctrl2 = tk.Frame(row2, bg="#FFFFFF")
        ctrl2.pack()

        self.btn_cam = tk.Button(ctrl2, text="▶ BẬT CAMERA", font=("Arial", 10, "bold"),
                                  fg="#FFFFFF", bg="#2E7D32", width=14, pady=4,
                                  relief="flat", cursor="hand2", command=self._toggle_camera)
        self.btn_cam.pack(side="left", padx=(0, 6))

        self.btn_open_file = tk.Button(ctrl2, text="📂 MỞ FILE (ẢNH/VIDEO)", font=("Arial", 10, "bold"),
                                       fg="#FFFFFF", bg="#6366F1", width=20, pady=4,
                                       relief="flat", cursor="hand2", command=self._quick_open_file)
        self.btn_open_file.pack(side="left", padx=(0, 6))

        self.lbl_cam_status = tk.Label(ctrl2, text="⚫ Camera chưa bật", font=("Arial", 9),
                                        fg="#475569", bg="#FFFFFF")
        self.lbl_cam_status.pack(side="left", padx=(10, 0))

        # ── Hàng 3: Các nút chức năng (Làm mới hệ thống) ──
        row3 = tk.Frame(bar, bg="#FFFFFF")
        row3.pack(fill="x", pady=(2, 0))
        
        ctrl3 = tk.Frame(row3, bg="#FFFFFF")
        ctrl3.pack()
        
        self.btn_refresh = tk.Button(ctrl3, text="🔄 LÀM MỚI HỆ THỐNG", font=("Arial", 9, "bold"),
                                     fg="#FFFFFF", bg="#0EA5E9", activebackground="#0284C7",
                                     relief="flat", cursor="hand2", padx=10, pady=2,
                                     command=self._refresh_system)
        self.btn_refresh.pack(side="left", padx=5)
        
        self.btn_clear_log = tk.Button(ctrl3, text="🗑️ XÓA LOG", font=("Arial", 9, "bold"),
                                       fg="#FFFFFF", bg="#64748B", activebackground="#475569",
                                       relief="flat", cursor="hand2", padx=10, pady=2,
                                       command=self._clear_log)
        self.btn_clear_log.pack(side="left", padx=5)

    # ─── Panel trái ─────────────────────────────────────
    def _build_left(self, parent):
        lf = tk.Frame(parent, bg="#FFFFFF", width=310, bd=1, relief="ridge")
        lf.pack(side="left", fill="y", padx=(0, 8))
        lf.pack_propagate(False)

        tk.Label(lf, text="📊  KẾT QUẢ PHÂN LOẠI",
                 font=("Arial", 11, "bold"), fg="#0284C7", bg="#FFFFFF",
                 ).pack(pady=(4, 4))

        self.lbl_grading_status = tk.Label(lf, text="Đang phân loại:  🍎 Táo",
                 font=("Arial", 10, "bold"), fg="#DC2626", bg="#FFFFFF",
                 )
        self.lbl_grading_status.pack(pady=(0, 6))

        # ═══════════════════════════════════════════════════
        #  PANEL ĐÁNH GIÁ 2 TIÊU CHÍ
        # ═══════════════════════════════════════════════════
        criteria_frame = tk.LabelFrame(lf, text=" 📋 ĐÁNH GIÁ 2 TIÊU CHÍ ",
                                        font=("Arial", 9, "bold"), fg="#1565C0",
                                        bg="#F0F4F8", padx=8, pady=6)
        criteria_frame.pack(fill="x", padx=8, pady=(0, 6))

        # ── TC1: Độ chín vỏ quả ──
        tc1_frame = tk.Frame(criteria_frame, bg="#F0F4F8")
        tc1_frame.pack(fill="x", pady=(0, 4))

        lbl_tc1 = tk.Label(tc1_frame, text="TC1  ĐỘ CHÍN VỎ QUẢ",
                 font=("Arial", 9, "bold"), fg="#1B5E20", bg="#F0F4F8", cursor="hand2")
        lbl_tc1.pack(anchor="w")
        lbl_tc1.bind("<Double-1>", self._open_tc1_settings)

        # Thanh tiến trình TC1 (tỉ lệ đỏ)
        self._tc1_progress = ttk.Progressbar(tc1_frame, length=260, mode='determinate', maximum=100)
        self._tc1_progress.pack(fill="x", pady=(2, 0))

        tc1_detail = tk.Frame(tc1_frame, bg="#F0F4F8")
        tc1_detail.pack(fill="x")

        self._tc1_red_var = tk.StringVar(value="Đỏ: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_red_var,
                 font=("Consolas", 8), fg="#C62828", bg="#F0F4F8").pack(side="left")

        self._tc1_yellow_var = tk.StringVar(value="Vàng: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_yellow_var,
                 font=("Consolas", 8), fg="#F9A825", bg="#F0F4F8").pack(side="left", padx=(5, 0))
                 
        self._tc1_green_var = tk.StringVar(value="Xanh: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_green_var,
                 font=("Consolas", 8), fg="#2E7D32", bg="#F0F4F8").pack(side="left", padx=(5, 0))

        self._tc1_grade_var = tk.StringVar(value="---")
        self._tc1_grade_lbl = tk.Label(tc1_detail, textvariable=self._tc1_grade_var,
                 font=("Arial", 9, "bold"), fg="#616161", bg="#F0F4F8")
        self._tc1_grade_lbl.pack(side="right")

        # Đường phân cách
        tk.Frame(criteria_frame, bg="#CFD8DC", height=1).pack(fill="x", pady=4)

        # ── TC2: Kích thước quả ──
        tc2_frame = tk.Frame(criteria_frame, bg="#F0F4F8")
        tc2_frame.pack(fill="x", pady=(0, 0))

        lbl_tc2 = tk.Label(tc2_frame, text="TC2  KÍCH THƯỚC QUẢ",
                 font=("Arial", 8, "bold"), fg="#E65100", bg="#F0F4F8", cursor="hand2")
        lbl_tc2.pack(anchor="w")
        lbl_tc2.bind("<Double-1>", self._open_tc2_settings)

        # Thanh tiến trình TC2 (kích thước)
        self._tc2_progress = ttk.Progressbar(tc2_frame, length=260, mode='determinate', maximum=120)
        self._tc2_progress.pack(fill="x", pady=(1, 0))

        tc2_detail = tk.Frame(tc2_frame, bg="#F0F4F8")
        tc2_detail.pack(fill="x")

        self._tc2_diameter_var = tk.StringVar(value="Ø: 0 mm")
        tk.Label(tc2_detail, textvariable=self._tc2_diameter_var,
                 font=("Consolas", 8), fg="#4E342E", bg="#F0F4F8").pack(side="left")

        self._tc2_grade_var = tk.StringVar(value="---")
        self._tc2_grade_lbl = tk.Label(tc2_detail, textvariable=self._tc2_grade_var,
                 font=("Arial", 8, "bold"), fg="#616161", bg="#F0F4F8")
        self._tc2_grade_lbl.pack(side="right")

        # ═══════════════════════════════════════════════════
        #  THỐNG KÊ 3 HẠNG
        # ═══════════════════════════════════════════════════

        # Thẻ 3 hạng (Tối ưu hóa không gian)
        for grade, cfg in self.GRADE_CFG.items():
            card = tk.Frame(lf, bg=cfg["bg"])
            card.pack(fill="x", padx=8, pady=1)
            
            # Hàng tiêu đề + Số lượng
            header_row = tk.Frame(card, bg=cfg["bg"])
            header_row.pack(fill="x", padx=10, pady=(2, 0))
            
            tk.Label(header_row, text=f"{cfg['icon']}  {cfg['label']}",
                     font=("Arial", 10, "bold"), fg=cfg["color"], bg=cfg["bg"]
                     ).pack(side="left")
            
            var = tk.StringVar(value="0")
            p_var = tk.StringVar(value="(0.0%)")
            self._count_vars[grade] = var
            self._percent_vars[grade] = p_var
            
            tk.Label(header_row, textvariable=p_var,
                     font=("Arial", 8, "bold"), fg="#94A3B8", bg=cfg["bg"]
                     ).pack(side="right", padx=(0, 5))
            
            tk.Label(header_row, textvariable=var,
                     font=("Consolas", 16, "bold"), fg="#FFFFFF", bg=cfg["bg"]
                     ).pack(side="right")
            
            # Dòng chú thích tiêu chí
            desc_lbl = tk.Label(card, text=cfg.get("desc", ""),
                     font=("Arial", 7, "italic"), fg="#94A3B8", bg=cfg["bg"])
            desc_lbl.pack(anchor="w", padx=30, pady=(0, 2))
            self._grade_desc_labels[grade] = desc_lbl

        # ═══════════════════════════════════════════════════
        #  TỔNG CỘNG (Ở dưới 3 loại)
        # ═══════════════════════════════════════════════════
        tk.Frame(lf, bg="#E2E8F0", height=1).pack(fill="x", padx=8, pady=4)
        
        summary_frame = tk.Frame(lf, bg="#FFFFFF")
        summary_frame.pack(fill="x", padx=8, pady=2)
        
        total_card = tk.Frame(summary_frame, bg="#F8FAFC", bd=1, relief="groove")
        total_card.pack(fill="both", expand=True)
        tk.Label(total_card, text="TỔNG CỘNG", font=("Arial", 9, "bold"), fg="#475569", bg="#F8FAFC").pack(pady=(2, 0))
        self._total_var = tk.StringVar(value="0")
        tk.Label(total_card, textvariable=self._total_var, font=("Consolas", 18, "bold"), fg="#0F172A", bg="#F8FAFC").pack(pady=(0, 2))



# ─── Panel phải: camera màu + ảnh xám ─────────────────
    def _build_right(self, parent):
        rf = tk.Frame(parent, bg="#FFFFFF", bd=1, relief="ridge")
        rf.pack(side="left", fill="both", expand=True)

        # ── Thanh điều khiển chế độ xem ──
        view_ctrl = tk.Frame(rf, bg="#F1F5F9", pady=3)
        view_ctrl.pack(fill="x")
        tk.Label(view_ctrl, text="📺 CHẾ ĐỘ HIỂN THỊ:", font=("Arial", 9, "bold"), fg="#475569", bg="#F1F5F9").pack(side="left", padx=10)
        
        self.view_mode_var = tk.StringVar(value="Color & Binary")
        view_modes = ["Color & Gray", "Color & Binary", "Gray & Binary", "Color & BG Removal"]
        self.view_combo = ttk.Combobox(view_ctrl, textvariable=self.view_mode_var, values=view_modes, state="readonly", width=18)
        self.view_combo.pack(side="left", padx=5)
        self.view_combo.bind("<<ComboboxSelected>>", self._on_view_mode_change)




        # ── Vùng hiển thị Camera (Cân bằng kích thước) ──
        display_area = tk.Frame(rf, bg="#FFFFFF")
        display_area.pack(fill="both", expand=True, padx=6, pady=2)
        display_area.rowconfigure(0, weight=1)
        display_area.rowconfigure(1, weight=1)
        display_area.columnconfigure(0, weight=1)

        # --- Khung hiển thị 1 ---
        f1 = tk.Frame(display_area, bg="#FFFFFF")
        f1.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        
        self.lbl_view1 = tk.Label(f1, text="📷  CAMERA (COLOR)",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF")
        self.lbl_view1.pack(anchor="w")
        
        self.canvas = tk.Canvas(f1, bg="#000000", highlightthickness=1, 
                                highlightbackground="#CBD5E1", cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        # --- Khung hiển thị 2 ---
        f2 = tk.Frame(display_area, bg="#FFFFFF")
        f2.grid(row=1, column=0, sticky="nsew", pady=(0, 2))
        
        self.lbl_view2 = tk.Label(f2, text="🔲  MACHINE VISION (DEPTH MAP / GRAYSCALE)",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF")
        self.lbl_view2.pack(anchor="w")
        
        self.canvas_gray = tk.Canvas(f2, bg="#000000", highlightthickness=1, 
                                     highlightbackground="#CBD5E1", cursor="cross")
        self.canvas_gray.pack(fill="both", expand=True)
        
        # Nút bật 3D Point Cloud (Thu nhỏ lại một chút để tiết kiệm diện tích)
        self.btn_3d = tk.Button(rf, text="🌌 MỞ POINT CLOUD 3D", font=("Arial", 8, "bold"),
                                bg="#4F46E5", fg="white", cursor="hand2", pady=2, command=self._show_point_cloud)
        self.btn_3d.pack(pady=2)

        # ── Frame Snapshot 10 hình (dưới cùng) ──
        tk.Label(rf, text="📸 10 ẢNH GẦN NHẤT (LIVE BUFFER)", font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF").pack(anchor="w", padx=6, pady=(5, 0))
        self.snapshot_frame = tk.Frame(rf, bg="#0F172A", height=60)
        self.snapshot_frame.pack(fill="x", padx=4, pady=2)
        
        self.snapshot_labels = []
        self.snapshot_images = [] # Tránh garbage collection
        
        for i in range(10):
            lbl = tk.Label(self.snapshot_frame, bg="#0F172A", bd=0, highlightthickness=0)
            lbl.pack(side="left")
            self.snapshot_labels.append(lbl)

        self._draw_placeholder()
        
        # Cập nhật tiêu đề hiển thị sau khi các thành phần UI đã được tạo xong
        self._on_view_mode_change()

    def _quick_open_file(self):
        """Hàm mở file nhanh từ nút bấm ở sidebar."""
        file_path = filedialog.askopenfilename(
            parent=self.win,
            title="Chọn file ảnh hoặc video để phân tích",
            filetypes=[("Tất cả tệp media", "*.jpg *.jpeg *.png *.bmp *.mp4 *.avi *.mkv *.mov"),
                       ("Ảnh", "*.jpg *.jpeg *.png *.bmp"),
                       ("Video", "*.mp4 *.avi *.mkv *.mov")]
        )
        if not file_path:
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        is_video = ext in [".mp4", ".avi", ".mkv", ".mov"]
        
        if self.camera.is_running():
            self._stop_camera()
            
        success = self.camera.start_file_mode(file_path, is_video=is_video)
        if success:
            self._last_static_processed = False # Reset để ảnh mới được xử lý
            self.btn_cam.config(text="⏹  Dừng File", bg="#B71C1C", activebackground="#7F0000")
            self.lbl_cam_status.config(text="🟢  Đang phát File", fg="#69F0AE")
            self.combo.config(state="disabled")

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, 1000, 1000, fill="#0A0A0A")
        self.canvas.create_text(320, 100, text="📷", font=("Arial", 36), fill="#424242")
        self.canvas.create_text(320, 150,
                                text="[SYSTEM READY - WAITING FOR CAMERA]",
                                font=("Consolas", 10), fill="#00E676")
        self.canvas_gray.delete("all")
        self.canvas_gray.create_rectangle(0, 0, 1000, 1000, fill="#0A0A0A")
        self.canvas_gray.create_text(320, 100, text="🔲", font=("Arial", 36), fill="#333333")
        self.canvas_gray.create_text(320, 150,
                                     text="Ảnh xử lý sẽ hiển thị tại đây",
                                     font=("Arial", 10), fill="#333344")
        
        # Đặt lại ID để vẽ frame mới khi bật camera
        self.img_id_color = None
        self.img_id_gray = None

    # ═══════════════════════════════════════════════════════
    #  LOGIC CAMERA
    # ═══════════════════════════════════════════════════════
    def _detect_cameras(self):
        """Quét tất cả camera có sẵn trên hệ thống."""
        from tkinter import messagebox
        
        self._log_event("🔍 Đang quét camera...", "INFO")
        
        # Chạy trong thread riêng để không block UI
        def scan():
            cameras = self.camera.detect_available_cameras(max_test=5)
            
            if not cameras:
                self.win.after(0, lambda: messagebox.showwarning(
                    "Không tìm thấy camera",
                    "Không phát hiện camera nào!\n\nKiểm tra:\n"
                    "• Camera đã cắm đúng cổng USB\n"
                    "• Driver camera đã cài đặt\n"
                    "• Không có ứng dụng nào đang dùng camera"
                ))
            else:
                # Hiển thị kết quả
                msg = "📹 DANH SÁCH CAMERA TÌM THẤY:\n\n"
                for idx, name in cameras:
                    msg += f"✅ Cổng {idx}: {name}\n"
                msg += "\n💡 Gợi ý:\n"
                msg += "• Chọn 'Camera máy tính' cho cổng 0\n"
                msg += "• Chọn 'Webcam rời 1' cho cổng 1\n"
                msg += "• Chọn 'Webcam rời 2' cho cổng 2"
                
                self.win.after(0, lambda: messagebox.showinfo("Kết quả quét", msg))
                self._log_event(f"✅ Tìm thấy {len(cameras)} camera", "INFO")
        
        threading.Thread(target=scan, daemon=True).start()
    
    def _toggle_camera(self):
        if self.camera.is_running():
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        val = self.cam_var.get()
        success = False
        
        if "Astra Pro" in val:
            sel_idx = self.combo_astra_color.current()
            if sel_idx < 0: sel_idx = 1
            success = self.camera.start_astra_camera(sel_idx)
        elif "Mở File Ảnh" in val:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
            if path:
                success = self.camera.start_file_mode(path, is_video=False)
        elif "Mở File Video" in val:
            path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")])
            if path:
                success = self.camera.start_file_mode(path, is_video=True)
        else:
            idx = self.combo.current() - 1
            if idx < 0: idx = 0
            success = self.camera.start_cv2_camera(idx)
            
        if success:
            if "Astra Pro" in val:
                self.btn_cam.config(text="⏹  Tắt Astra Pro", bg="#B71C1C", activebackground="#7F0000")
                self.lbl_cam_status.config(text="🟢  Đang phát (Astra Pro 3D)", fg="#69F0AE")
            elif "File" in val:
                self.btn_cam.config(text="⏹  Dừng File", bg="#B71C1C", activebackground="#7F0000")
                self.lbl_cam_status.config(text="🟢  Đang phát File", fg="#69F0AE")
            else:
                self.btn_cam.config(text="⏹  Tắt Camera", bg="#B71C1C", activebackground="#7F0000")
                self.lbl_cam_status.config(text="🟢  Đang phát", fg="#69F0AE")
            self.combo.config(state="disabled")

    def _stop_camera(self):
        self.camera.stop()
        self.btn_cam.config(text="▶  Bật Camera", bg="#2E7D32", activebackground="#1B5E20")
        self.lbl_cam_status.config(text="⚫  Camera chưa bật", fg="#666680")
        self.combo.config(state="readonly")
        self._draw_placeholder()

    def _on_frame_received(self, frame, is_astra=False, depth_colormap=None, raw_depth=None):
        import time
        # Kiểm tra tốc độ chụp theo cấu hình (Analysis Interval)
        curr_time = time.time() * 1000 # Convert to ms
        interval = float(self.cfg_analysis_ms.get() or 100)
        if curr_time - self._last_analysis_time < interval:
            return # Bỏ qua frame này để giữ đúng tốc độ chụp yêu cầu
        
        self._last_analysis_time = curr_time
        self.frame_to_save = frame.copy()
        
        # Kiểm tra xem đang chạy ảnh tĩnh hay video
        is_static = getattr(self.camera, "is_single_image", False)
        
        # Nếu là ảnh tĩnh và đã xử lý xong rồi thì bỏ qua để tránh chớp màn hình
        if is_static and hasattr(self, "_last_static_processed") and self._last_static_processed:
            return
        
        try:
            # Sử dụng raw_depth được truyền trực tiếp từ CameraManager
            processed_frame, defect_area, ripeness, grade, detail_info = self.analyzer.analyze_apple(frame, depth_frame=raw_depth)
            frame = processed_frame
            self.current_grade = grade
            self.current_diameter = detail_info.get('diameter_mm', 0)
            
            # Khởi tạo bộ đệm tích lũy cho video nếu chưa có
            if not hasattr(self, "_video_session_buffer"): self._video_session_buffer = []
            
            color_map_hex = {"Grade-1": "#10B981", "Grade-2": "#F59E0B", "Grade-3": "#EF4444", "UNKNOWN": "#64748B"}
            status_text = f"Đang phân loại: 🍎 {grade}"
            
            # Quản lý Event Log cho người giám sát
            if not hasattr(self, "_last_detected_grade"): self._last_detected_grade = "NO_APPLE"
            
            if grade != "NO_APPLE" and grade != "UNKNOWN":
                status_text += f" ({ripeness:.0f}% Đỏ)"
                self._no_apple_counter = 0 # Reset bộ đếm khi thấy táo
                
                if is_static:
                    # TRƯỜNG HỢP ẢNH TĨNH: Chốt luôn
                    if self._last_detected_grade == "NO_APPLE":
                        self._log_event(f"🖼️ ẢNH TĨNH: Hạng {grade}", "INFO")
                        self._save_to_sql(grade)
                        self._last_static_processed = True # Đánh dấu đã xong
                else:
                    # TRƯỜNG HỢP VIDEO: Chụp đủ 10 tấm rồi chốt
                    if not getattr(self, "_session_finalized", False):
                        if self._last_detected_grade == "NO_APPLE":
                            self._log_event("🔄 Bắt đầu lấy 10 mẫu phân tích...", "INFO")
                            self._video_session_buffer = []
                        
                        self._video_session_buffer.append(grade)
                        
                        # Hiển thị tiến trình chụp 1/10, 2/10...
                        count = len(self._video_session_buffer)
                        status_text = f"📸 Đang chụp: {count}/10 | Hạng: {grade}"
                        
                        if count >= 10:
                            self._finalize_video_session()
                            self._session_finalized = True
                
                self._last_detected_grade = grade

                # Gửi tín hiệu PLC (có cooldown để tránh spam)
                current_time = time.time()
                if not hasattr(self, "_last_plc_send_time"): self._last_plc_send_time = 0
                if current_time - self._last_plc_send_time > 2.0:
                    self.send_grade_to_plc(grade)
                    self._last_plc_send_time = current_time
            else:
                # KHI TÁO RỜI KHỎI KHUNG HÌNH (NO_APPLE)
                if not hasattr(self, "_no_apple_counter"): self._no_apple_counter = 0
                self._no_apple_counter += 1
                
                # Đợi 5 khung hình (~0.5s) mất dấu liên tục mới cho phép bắt quả tiếp theo
                if self._no_apple_counter >= 5:
                    if not is_static and not getattr(self, "_session_finalized", False):
                        # Nếu táo đi qua quá nhanh mà chưa đủ 10 tấm thì vẫn chốt với những gì đã có
                        if len(self._video_session_buffer) > 0:
                            self._finalize_video_session()
                    
                    self._session_finalized = False # Reset trạng thái để bắt quả mới
                    self._video_session_buffer = []
                    self._last_detected_grade = "NO_APPLE"


                    
            self.lbl_grading_status.config(text=status_text, fg=color_map_hex.get(grade, "#64748B"))
            self._update_criteria_panels(detail_info)



            h_f = frame.shape[0]
            color_map_bgr = {"Grade-1": (0, 255, 0), "Grade-2": (0, 255, 255), "Grade-3": (0, 0, 255)}
            cv2.putText(frame, f"STATUS: {grade}", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_map_bgr.get(grade, (255,255,255)), 2)
        except Exception:
            pass

        # ─── PHẦN HIỂN THỊ CAMERA (Đưa trở lại vòng lặp chính) ───
        current_time = time.time()
        if current_time - self.last_buffer_time >= 0.1:
            self.last_buffer_time = current_time
            self.canvas.after(0, self._update_snapshot_gallery, None, self.frame_to_save.copy())
            
        # Lấy kích thước thực tế của canvas để resize ảnh
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10: cw, ch = 640, 240
        
        color_res = cv2.resize(frame, (cw, ch))
        color_rgb = cv2.cvtColor(color_res, cv2.COLOR_BGR2RGB)
        
        if is_astra and depth_colormap is not None:
            f2_raw = cv2.resize(depth_colormap, (cw, ch))
            f2_rgb = cv2.cvtColor(f2_raw, cv2.COLOR_BGR2RGB)
        else:
            gray_res = cv2.cvtColor(color_res, cv2.COLOR_BGR2GRAY)
            if self.view_mode_var.get() == "Color & Binary":
                _, binary = cv2.threshold(gray_res, 127, 255, cv2.THRESH_BINARY)
                f2_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            elif self.view_mode_var.get() == "Color & BG Removal":
                fg_mask = self.analyzer.get_foreground_mask(color_res)
                f2_rgb = cv2.cvtColor(fg_mask, cv2.COLOR_GRAY2RGB)
            else:
                f2_rgb = cv2.cvtColor(gray_res, cv2.COLOR_GRAY2RGB)
            
        mode = self.view_mode_var.get()
        if mode == "Gray & Binary":
            gray_res = cv2.cvtColor(color_res, cv2.COLOR_BGR2GRAY)
            f1_rgb = cv2.cvtColor(gray_res, cv2.COLOR_GRAY2RGB)
            _, binary = cv2.threshold(gray_res, 127, 255, cv2.THRESH_BINARY)
            f2_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        else:
            f1_rgb = color_rgb
            
        imgtk1 = ImageTk.PhotoImage(image=Image.fromarray(f1_rgb))
        imgtk2 = ImageTk.PhotoImage(image=Image.fromarray(f2_rgb))
        
        try:
            self.canvas.imgtk = imgtk1
            self.canvas_gray.imgtk = imgtk2
            self.canvas.after(0, self._update_canvas, imgtk1, imgtk2)
        except: pass


    def _finalize_video_session(self):
        """Chốt kết quả phân loại sau khi đã thu thập đủ mẫu (10 tấm)."""
        if not hasattr(self, "_video_session_buffer") or len(self._video_session_buffer) == 0:
            return

        # CHỐT KẾT QUẢ VIDEO (Multi-frame Consensus)
        # Ưu tiên lấy kết quả tệ nhất trong các mặt đã thấy
        final_grade = "Grade-1"
        if "Grade-3" in self._video_session_buffer:
            final_grade = "Grade-3"
        elif "Grade-2" in self._video_session_buffer:
            final_grade = "Grade-2"
        
        self._log_event(f"📸 ĐÃ CHỤP ĐỦ 10 MẪU. Kết quả chốt: {final_grade}", "INFO")
        self._save_to_sql(final_grade)

    def _show_point_cloud(self):
        if self.camera:
            self.camera.show_point_cloud(self.frame_to_save)

    def _update_criteria_panels(self, detail_info):
        """Cập nhật panel hiển thị 2 tiêu chí TC1 (Độ chín) và TC2 (Kích thước)."""
        if detail_info is None:
            return
        try:
            # ── TC1: Độ chín ──
            red_r = detail_info.get("red_ratio", 0)
            yellow_r = detail_info.get("yellow_ratio", 0)
            green_r = detail_info.get("green_ratio", 0)
            r_label = detail_info.get("ripeness_label", "---")
            r_grade = detail_info.get("ripeness_grade", "---")

            self._tc1_progress['value'] = min(red_r, 100)
            self._tc1_red_var.set(f"Đỏ: {red_r:.1f}%")
            self._tc1_yellow_var.set(f"Vàng: {yellow_r:.1f}%")
            self._tc1_green_var.set(f"Xanh: {green_r:.1f}%")
            self._tc1_grade_var.set(f"⇒ {r_label}")

            tc1_colors = {"Grade-1": "#2E7D32", "Grade-2": "#F9A825", "Grade-3": "#C62828"}
            self._tc1_grade_lbl.config(fg=tc1_colors.get(r_grade, "#616161"))

            # ── TC2: Kích thước ──
            d_mm = detail_info.get("diameter_mm", 0)
            s_label = detail_info.get("size_label", "---")
            s_grade = detail_info.get("size_grade", "---")

            self._tc2_progress['value'] = min(d_mm, 120)
            self._tc2_diameter_var.set(f"Ø: {d_mm:.0f} mm")
            self._tc2_grade_var.set(f"⇒ {s_label}")

            tc2_colors = {"A": "#1B5E20", "B": "#F57F17", "C": "#B71C1C"}
            self._tc2_grade_lbl.config(fg=tc2_colors.get(s_grade, "#616161"))
            
            # ── Performance Metrics (Machine Vision Industrial) ──
            fps = detail_info.get("fps", 0.0)
            proc_time = detail_info.get("processing_time_ms", 0.0)
            
            self._fps_var.set(f"{fps:.1f}")
            self._proc_time_var.set(f"{proc_time:.1f} ms")
            
            # ── Motion Blur Detection ──
            blur_status = detail_info.get("blur_status", "N/A")
            blur_score = detail_info.get("blur_score", 0.0)
            is_blurry = detail_info.get("is_blurry", False)
            
            # Cập nhật text và màu theo trạng thái
            if blur_status == "SHARP":
                self._blur_status_var.set(f"✓ SHARP ({blur_score:.0f})")
                self._blur_status_label.config(fg="#10B981")  # Xanh lá - Good
            elif blur_status == "BLURRY→SHARPENED":
                self._blur_status_var.set(f"⚠ AUTO-SHARP ({blur_score:.0f})")
                self._blur_status_label.config(fg="#F59E0B")  # Cam - Warning
            elif blur_status == "BLURRY":
                self._blur_status_var.set(f"✗ BLURRY ({blur_score:.0f})")
                self._blur_status_label.config(fg="#EF4444")  # Đỏ - Bad
            else:
                self._blur_status_var.set("N/A")
                self._blur_status_label.config(fg="#6B7280")  # Xám
            
            # ── 3D Shape Analysis - REMOVED ──
            # Section removed by user request
        except Exception:
            pass

    def _update_canvas(self, imgtk_color, imgtk_gray):
        if self.camera.is_running():
            if getattr(self, 'img_id_color', None) is None:
                self.canvas.delete("all")
                self.canvas_gray.delete("all")
                self.img_id_color = self.canvas.create_image(0, 0, anchor="nw", image=imgtk_color)
                self.img_id_gray = self.canvas_gray.create_image(0, 0, anchor="nw", image=imgtk_gray)
            else:
                self.canvas.itemconfig(self.img_id_color, image=imgtk_color)
                self.canvas_gray.itemconfig(self.img_id_gray, image=imgtk_gray)

    # ═══════════════════════════════════════════════════════
    #  3D VISUALIZATION - REMOVED
    # ═══════════════════════════════════════════════════════
    # Function removed by user request

    # ═══════════════════════════════════════════════════════
    #  LOGIC PLC S7-1200 (snap7)
    # ═══════════════════════════════════════════════════════
    def _toggle_plc(self):
        if self.plc.connected:
            self._disconnect_plc()
        else:
            self._connect_plc()

    def _connect_plc(self):
        ip   = self.plc_ip_var.get().strip()
        rack = int(self.plc_rack_var.get() or 0)
        slot = int(self.plc_slot_var.get() or 1)
        
        self._log_event(f"🔄 Đang kết nối PLC tại {ip} (Rack={rack}, Slot={slot})...", "INFO")
        success, msg = self.plc.connect(ip, rack, slot)
        
        if success:
            self.btn_connect.config(text="🔌  Ngắt kết nối",
                                    bg="#6A1B9A", activebackground="#4A148C")
            if hasattr(self, 'btn_plc_quick'):
                self.btn_plc_quick.config(text="🔌 NGẮT PLC", bg="#6A1B9A")
            self.lbl_plc_status.config(text=f"🟢  PLC: {ip}", fg="#2E7D32")
            self._plc_poll_id = self.win.after(1000, self._poll_plc)
            self._log_event(f"🟢 Kết nối PLC thành công! IP={ip}, Rack={rack}, Slot={slot}", "SUCCESS")
        else:
            # Thông báo lỗi từ msg giờ đã cực kỳ chi tiết nhờ bộ chẩn đoán trong PLCManager
            self._log_event(f"Kết nối PLC thất bại ({ip})", "ERROR")
            self._log_event(msg, "ERROR")
            messagebox.showerror("Lỗi PLC", f"Không kết nối được PLC!\n\n{msg}")

    def _disconnect_plc(self):
        if self._plc_poll_id:
            self.win.after_cancel(self._plc_poll_id)
            self._plc_poll_id = None
        self.plc.disconnect()
        self.btn_connect.config(text="🔌  Kết nối PLC",
                                bg="#1565C0", activebackground="#0D47A1")
        if hasattr(self, 'btn_plc_quick'):
            self.btn_plc_quick.config(text="🔌 KẾT NỐI PLC", bg="#1565C0")
        self.lbl_plc_status.config(text="⚫  PLC chưa kết nối", fg="#64748B")
        self._log_event("⚫ Đã ngắt kết nối PLC.", "WARNING")

    def _poll_plc(self):
        """Đọc bộ đếm từ PLC mỗi 1 giây."""
        if not self.plc.connected:
            return
        
        counters = self.plc.read_counters()
        if counters:
            grade1, grade2, grade3 = counters
            self._update_counts(grade1, grade2, grade3)
            
        self._plc_poll_id = self.win.after(1000, self._poll_plc)

    def _plc_start(self):
        """Ghi DB1.DBX0.0 = True → Tạo xung Start."""
        success, msg = self.plc.start_machine()
        if success:
            self.lbl_plc_status.config(text="🟢 PLC: Đang chạy (Pulse DB1.0.0)", fg="#2E7D32")
            self._log_event("▶️ Đã gửi lệnh START (DB1.DBX0.0)", "INFO")
            # Tự động tắt bit sau 500ms (tạo xung)
            self.win.after(500, lambda: self.plc.write_db_bit(self.plc.PLC_DB_NUMBER, self.plc.PLC_START_BYTE, self.plc.PLC_START_BIT, False))
        else:
            self.lbl_plc_status.config(text="🔴 Lỗi ghi START", fg="#D32F2F")
            self._log_event(f"❌ Lỗi khi gửi lệnh START xuống PLC: {msg}", "ERROR")

    def _plc_stop(self):
        """Ghi DB1.DBX0.1 = True → Tạo xung Stop."""
        success, msg = self.plc.stop_machine()
        if success:
            self.lbl_plc_status.config(text="🟡 PLC: Đã dừng (Pulse DB1.0.1)", fg="#C62828")
            self._log_event("⏹️ Đã gửi lệnh STOP (DB1.DBX0.1)", "WARNING")
            # Tự động tắt bit sau 500ms (tạo xung)
            self.win.after(500, lambda: self.plc.write_db_bit(self.plc.PLC_DB_NUMBER, self.plc.PLC_STOP_BYTE, self.plc.PLC_STOP_BIT, False))
        else:
            self.lbl_plc_status.config(text="🔴 Lỗi ghi STOP", fg="#D32F2F")
            self._log_event(f"❌ Lỗi khi gửi lệnh STOP xuống PLC: {msg}", "ERROR")

    def send_grade_to_plc(self, grade):
        """Gửi tín hiệu phân loại xuống PLC (Tạo xung 500ms)."""
        if not self.plc.connected:
            return
            
        success, msg = self.plc.set_grade(grade)
        if success:
            print(f"[PLC] Sent grade signal: {grade}")
            self.win.after(500, self._reset_grade_bits_plc)
        else:
            self._log_event(f"❌ Lỗi gửi tín hiệu {grade} xuống PLC: {msg}", "ERROR")

    def _reset_grade_bits_plc(self):
        """Reset các bit phân loại về False."""
        if self.plc.connected:
            self.plc.reset_grades()

    # ═══════════════════════════════════════════════════════
    #  BỘ ĐẾM PHÂN LOẠI
    # ═══════════════════════════════════════════════════════
    def _update_counts(self, grade1, grade2, grade3):
        old_grade1 = int(self._count_vars["Grade-1"].get())
        old_grade2 = int(self._count_vars["Grade-2"].get())
        old_grade3 = int(self._count_vars["Grade-3"].get())

        self._count_vars["Grade-1"].set(str(grade1))
        self._count_vars["Grade-2"].set(str(grade2))
        self._count_vars["Grade-3"].set(str(grade3))
        
        total = grade1 + grade2 + grade3
        self._total_var.set(str(total))
        
        # Cập nhật % từng loại
        if total > 0:
            for g_name, val in [("Grade-1", grade1), ("Grade-2", grade2), ("Grade-3", grade3)]:
                if g_name in self._percent_vars:
                    p = (val / total) * 100
                    self._percent_vars[g_name].set(f"({p:.1f}%)")
            
            y_rate = (grade1 / total) * 100
            if hasattr(self, '_yield_var'):
                self._yield_var.set(f"{y_rate:.1f}%")
        else:
            for g_name in ["Grade-1", "Grade-2", "Grade-3"]:
                if g_name in self._percent_vars: self._percent_vars[g_name].set("(0.0%)")
            if hasattr(self, '_yield_var'): self._yield_var.set("0.0%")
        


        # LƯU LỊCH SỬ (Tự động kích hoạt khi có táo mới được phân loại)
        if grade1 > old_grade1:
            self._save_to_sql("Grade-1")
        if grade2 > old_grade2:
            self._save_to_sql("Grade-2")
        if grade3 > old_grade3:
            self._save_to_sql("Grade-3")

    def _reset_counts(self):
        self._update_counts(0, 0, 0)

    def _refresh_system(self):
        """Làm mới toàn bộ trạng thái UI và đồng bộ DB."""
        self._refresh_stats_ui()
        self._refresh_history_table()
        self._video_session_buffer = []
        self._last_detected_grade = "NO_APPLE"
        self._log_event("🔄 Hệ thống đã được làm mới và đồng bộ dữ liệu.", "INFO")
        
    def _clear_log(self):
        """Xóa trắng khung log và reset bộ đếm."""
        if messagebox.askyesno("Xác nhận", "Bạn có muốn xóa toàn bộ log hiện tại?"):
            self.log_text.config(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.config(state="disabled")
            self._log_counters = {"info": 0, "warning": 0, "error": 0, "success": 0}
            self._log_entries = []
            self._update_log_counter_badges()
            self._log_event("🗑️ Đã dọn dẹp khung Log.", "WARNING")

    # ═══════════════════════════════════════════════════════
    #  LOG UTILITIES (Lọc, Sao chép, Xuất file, Flash)
    # ═══════════════════════════════════════════════════════
    def _update_log_counter_badges(self):
        """Cập nhật badge đếm WARNING / ERROR trên toolbar."""
        if hasattr(self, '_badge_warn'):
            w = self._log_counters.get("warning", 0)
            self._badge_warn.config(text=f"WARN: {w}")
        if hasattr(self, '_badge_error'):
            e = self._log_counters.get("error", 0)
            self._badge_error.config(text=f"ERR: {e}")

    def _filter_log(self, level):
        """Lọc hiển thị log theo level (ALL/INFO/SUCCESS/WARNING/ERROR)."""
        if not hasattr(self, '_log_entries'):
            return
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        target = level.lower()
        for entry in self._log_entries:
            if target == "all" or entry["tag"] == target:
                self.log_text.insert("end", f"[{entry['time']}] ", "time")
                src = entry.get("source", "")
                self.log_text.insert("end", f"{entry['prefix']} {entry['msg']}{src}\n", entry["tag"])
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self._log_filter_var.set(level)

    def _copy_log_to_clipboard(self):
        """Sao chép toàn bộ log ra clipboard."""
        try:
            content = self.log_text.get("1.0", "end-1c")
            self.win.clipboard_clear()
            self.win.clipboard_append(content)
            self._log_event("📋 Đã sao chép log vào clipboard.", "SUCCESS")
        except Exception as e:
            self._log_event(f"Lỗi sao chép: {e}", "ERROR")

    def _export_log_to_file(self):
        """Xuất log ra file .txt để debug."""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                title="Lưu Event Log")
            if filepath:
                content = self.log_text.get("1.0", "end-1c")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"=== EVENT LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    f.write(f"Total: INFO={self._log_counters.get('info',0)} | "
                            f"SUCCESS={self._log_counters.get('success',0)} | "
                            f"WARNING={self._log_counters.get('warning',0)} | "
                            f"ERROR={self._log_counters.get('error',0)}\n")
                    f.write("=" * 60 + "\n")
                    f.write(content)
                self._log_event(f"💾 Đã xuất log ra: {filepath}", "SUCCESS")
        except Exception as e:
            self._log_event(f"Lỗi xuất file: {e}", "ERROR")

    def _flash_log_border(self, count=0):
        """Nhấp nháy viền đỏ khi có ERROR để thu hút sự chú ý."""
        if count >= 6:
            self._log_frame_widget.config(fg="#475569")
            return
        color = "#EF4444" if count % 2 == 0 else "#475569"
        self._log_frame_widget.config(fg=color)
        self.win.after(300, self._flash_log_border, count + 1)

    def _save_system_config(self):
        """Cập nhật các thông số từ UI vào bộ xử lý."""
        try:
            smooth_val = int(self.cfg_smooth_frames.get())
            # Cập nhật vào analyzer
            self.analyzer.MAX_HISTORY = smooth_val
            
            # Xóa buffer cũ để áp dụng smoothing mới ngay lập tức
            self.analyzer.history_cx = []
            self.analyzer.history_cy = []
            self.analyzer.history_r = []
            
            interval = int(self.cfg_analysis_ms.get())
            self._log_event(f"⚙️ Đã lưu cấu hình: Smoothing={smooth_val} frames, Interval={interval}ms", "SUCCESS")
            messagebox.showinfo("Thành công", "Đã cập nhật cấu hình hệ thống!")
        except ValueError:
            messagebox.showerror("Lỗi", "Vui lòng nhập số nguyên hợp lệ cho các thông số cấu hình!")

    def _open_tc1_settings(self, event=None):
        """Mở cửa sổ cấu hình ngưỡng TC1 (Độ chín)."""
        top = tk.Toplevel(self.win)
        top.title("Cấu hình TC1 - Độ chín vỏ quả")
        top.geometry("350x240")
        top.transient(self.win)
        top.grab_set()
        top.config(bg="#F8FAFC")

        var_good = tk.IntVar(value=self.analyzer.__class__.RIPENESS_GOOD_THRESH)
        var_medium = tk.IntVar(value=self.analyzer.__class__.RIPENESS_MEDIUM_THRESH)

        tk.Label(top, text="Ngưỡng 1 (Đỏ ≥ %):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#1B5E20").pack(pady=(15, 0))
        f1 = tk.Frame(top, bg="#F8FAFC")
        f1.pack()
        tk.Scale(f1, from_=0, to=100, orient="horizontal", length=200, bg="#F8FAFC", highlightthickness=0, variable=var_good, showvalue=False).pack(side="left")
        ttk.Spinbox(f1, from_=0, to=100, textvariable=var_good, width=5, font=("Consolas", 10)).pack(side="left", padx=(5,0))

        tk.Label(top, text="Ngưỡng 2 (Đỏ ≥ %):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#F9A825").pack(pady=(10, 0))
        f2 = tk.Frame(top, bg="#F8FAFC")
        f2.pack()
        tk.Scale(f2, from_=0, to=100, orient="horizontal", length=200, bg="#F8FAFC", highlightthickness=0, variable=var_medium, showvalue=False).pack(side="left")
        ttk.Spinbox(f2, from_=0, to=100, textvariable=var_medium, width=5, font=("Consolas", 10)).pack(side="left", padx=(5,0))

        def save(event=None):
            try:
                val_good = var_good.get()
                val_medium = var_medium.get()
            except tk.TclError:
                messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ!", parent=top)
                return
                
            if val_medium >= val_good:
                messagebox.showerror("Lỗi", "Ngưỡng 1 phải lớn hơn Ngưỡng 2!", parent=top)
                return
            
            # Cập nhật trực tiếp vào class
            self.analyzer.__class__.RIPENESS_GOOD_THRESH = val_good
            self.analyzer.__class__.RIPENESS_MEDIUM_THRESH = val_medium
            self._update_grade_descriptions()
            self._log_event(f"⚙️ Cập nhật TC1: Loại 1 (≥{val_good}%), Loại 2 (≥{val_medium}%)", "INFO")
            top.destroy()

        top.bind('<Return>', save)
        tk.Button(top, text="LƯU CẤU HÌNH (Enter)", bg="#1565C0", fg="white", font=("Arial", 9, "bold"), cursor="hand2", command=save, padx=20, pady=5, relief="flat").pack(pady=15)

    def _open_tc2_settings(self, event=None):
        """Mở cửa sổ cấu hình ngưỡng TC2 (Kích thước)."""
        top = tk.Toplevel(self.win)
        top.title("Cấu hình TC2 - Kích thước quả")
        top.geometry("350x240")
        top.transient(self.win)
        top.grab_set()
        top.config(bg="#F8FAFC")

        var_large = tk.IntVar(value=self.analyzer.SIZE_THRESHOLDS["large"])
        var_medium = tk.IntVar(value=self.analyzer.SIZE_THRESHOLDS["medium"])

        tk.Label(top, text="Ngưỡng 1 (Kích thước ≥ mm):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#E65100").pack(pady=(15, 0))
        f1 = tk.Frame(top, bg="#F8FAFC")
        f1.pack()
        tk.Scale(f1, from_=0, to=150, orient="horizontal", length=200, bg="#F8FAFC", highlightthickness=0, variable=var_large, showvalue=False).pack(side="left")
        ttk.Spinbox(f1, from_=0, to=150, textvariable=var_large, width=5, font=("Consolas", 10)).pack(side="left", padx=(5,0))

        tk.Label(top, text="Ngưỡng 2 (Kích thước ≥ mm):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#E65100").pack(pady=(10, 0))
        f2 = tk.Frame(top, bg="#F8FAFC")
        f2.pack()
        tk.Scale(f2, from_=0, to=150, orient="horizontal", length=200, bg="#F8FAFC", highlightthickness=0, variable=var_medium, showvalue=False).pack(side="left")
        ttk.Spinbox(f2, from_=0, to=150, textvariable=var_medium, width=5, font=("Consolas", 10)).pack(side="left", padx=(5,0))

        def save(event=None):
            try:
                val_large = var_large.get()
                val_medium = var_medium.get()
            except tk.TclError:
                messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ!", parent=top)
                return
                
            if val_medium >= val_large:
                messagebox.showerror("Lỗi", "Ngưỡng 1 phải lớn hơn Ngưỡng 2!", parent=top)
                return
            
            # Cập nhật trực tiếp vào dictionary
            self.analyzer.SIZE_THRESHOLDS["large"] = val_large
            self.analyzer.SIZE_THRESHOLDS["medium"] = val_medium
            self._update_grade_descriptions()
            self._log_event(f"⚙️ Cập nhật TC2: Loại 1 (≥{val_large}mm), Loại 2 (≥{val_medium}mm)", "INFO")
            top.destroy()

        top.bind('<Return>', save)
        tk.Button(top, text="LƯU CẤU HÌNH (Enter)", bg="#1565C0", fg="white", font=("Arial", 9, "bold"), cursor="hand2", command=save, padx=20, pady=5, relief="flat").pack(pady=15)

    def _update_grade_descriptions(self):
        """Cập nhật giao diện text cho 3 loại khi cấu hình thay đổi."""
        t1_good = self.analyzer.__class__.RIPENESS_GOOD_THRESH
        t1_med = self.analyzer.__class__.RIPENESS_MEDIUM_THRESH
        t2_large = self.analyzer.SIZE_THRESHOLDS["large"]
        t2_med = self.analyzer.SIZE_THRESHOLDS["medium"]

        if "Grade-1" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-1"].config(text=f"TC1 (≥{t1_good}%) & TC2 (≥{t2_large}mm)")
        if "Grade-2" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-2"].config(text=f"TC1 ({t1_med}-{t1_good-1}%) hoặc TC2 ({t2_med}-{t2_large-1}mm)")
        if "Grade-3" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-3"].config(text=f"TC1 (<{t1_med}%) hoặc TC2 (<{t2_med}mm)")

    # ═══════════════════════════════════════════════════════
    #  ĐÓNG
    # ═══════════════════════════════════════════════════════
    def _on_close(self):
        """Xử lý khi đóng cửa sổ."""
        if messagebox.askyesno("Xác nhận thoát", "Bạn có chắc muốn đóng chương trình?\n- 'Yes' để thoát hoàn toàn\n- 'No' để quay lại"):
            self._stop_camera()
            if self.plc.connected:
                self.plc.disconnect()
            
            # Thoát toàn bộ ứng dụng
            self.parent.destroy()




# ─── Điểm khởi chạy ──────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = FruitClassificationApp(root)
    root.mainloop()

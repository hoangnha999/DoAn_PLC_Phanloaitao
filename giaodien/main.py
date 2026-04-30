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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Processing.analyzer import FruitAnalyzer


class FruitClassificationApp:
    """Giao diện chính của ứng dụng nhận dạng và phân loại trái cây."""

    # ─── Cấu hình giao diện ──────────────────────────────────────────
    WINDOW_WIDTH = 750
    WINDOW_HEIGHT = 580
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
        try:
            import snap7
            self._plc = snap7.client.Client()
        except:
            self._plc = None
        self._plc_connected = False

        self._setup_window()
        self._load_images()
        self._build_ui()

    # ─── Thiết lập cửa sổ ────────────────────────────────────────────
    def _setup_window(self):
        """Cấu hình cửa sổ chính."""
        self.root.title("Nhận dạng và phân loại hàng trái cây")
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
        base_dir = os.path.dirname(os.path.abspath(__file__))
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
            conveyor_img = conveyor_img.resize((280, 200), Image.LANCZOS)
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
        self.wrapper.place(relx=0.5, rely=0.5, anchor="center")
        
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
            font=("Arial", 11, "bold"),
            fg=self.SUBTITLE_COLOR,
            bg=self.BG_COLOR,
        ).pack()

        tk.Label(
            info_frame,
            text="KHOA ĐIỆN-ĐIỆN TỬ",
            font=("Arial", 16, "bold"),
            fg=self.TITLE_COLOR,
            bg=self.BG_COLOR,
        ).pack()

        tk.Label(
            info_frame,
            text="NGÀNH CNKT ĐIỀU KHIỂN VÀ TỰ ĐỘNG HÓA",
            font=("Arial", 12, "bold"),
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
            font=("Arial", 12, "bold"),
            fg=self.TOPIC_COLOR,
            bg=self.BG_COLOR,
        ).pack(pady=(0, 5))

        tk.Label(
            topic_frame,
            text="ĐỀ TÀI: HỆ THỐNG PHÂN LOẠI HẠNG CHẤT LƯỢNG TRÁI CÂY",
            font=("Arial", 11, "bold"),
            fg=self.TOPIC_COLOR,
            bg=self.BG_COLOR,
            wraplength=650,
        ).pack()

        # ── Khu vực chính: Hình ảnh (trái) + Thông tin (phải) ──
        main_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        main_frame.pack(fill="both", expand=True, pady=5)

        # --- Hình băng chuyền (bên trái) ---
        img_frame = tk.Frame(main_frame, bg=self.BG_COLOR, bd=2, relief="groove")
        img_frame.pack(side="left", padx=(0, 15))

        tk.Label(img_frame, image=self.conveyor_image, bg=self.BG_COLOR).pack(
            padx=5, pady=5
        )

        # --- Thông tin bên phải ---
        info_frame = tk.Frame(main_frame, bg=self.BG_COLOR)
        info_frame.pack(side="left", fill="both", expand=True)

        # GVHD
        tk.Label(
            info_frame,
            text="GVHD: TS. Lê Chí Kiên",
            font=("Arial", 13, "bold"),
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
            member_frame.pack(fill="x", pady=2)

            tk.Label(
                member_frame,
                text=name,
                font=("Arial", 12),
                fg=self.TEXT_COLOR,
                bg=self.BG_COLOR,
                width=22,
                anchor="w",
            ).pack(side="left")

            tk.Label(
                member_frame,
                text=student_id,
                font=("Arial", 12),
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
            font=("Arial", 12, "bold"),
            fg=self.BTN_TEXT_COLOR,
            bg=self.BTN_RUN_COLOR,
            activebackground="#388E3C",
            activeforeground=self.BTN_TEXT_COLOR,
            relief="flat",
            cursor="hand2",
            padx=25,
            pady=8,
            command=self._on_run,
        )
        btn_run.pack(side="left", padx=10, pady=12)

        # Nút "Kết thúc chương trình"
        btn_stop = tk.Button(
            btn_container,
            text="Kết thúc chương trình",
            font=("Arial", 12, "bold"),
            fg=self.BTN_TEXT_COLOR,
            bg=self.BTN_STOP_COLOR,
            activebackground="#D32F2F",
            activeforeground=self.BTN_TEXT_COLOR,
            relief="flat",
            cursor="hand2",
            padx=25,
            pady=8,
            command=self._on_stop,
        )
        btn_stop.pack(side="left", padx=10, pady=12)


    # ─── Xử lý sự kiện ───────────────────────────────────────────────
    def _on_run(self):
        """Mở cửa sổ chương trình chính với màn hình camera."""
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
        "GOOD":   {"label": "GOOD",   "color": "#00E676", "bg": "#0A2E14", "icon": "✅"},
        "MEDIUM": {"label": "MEDIUM", "color": "#FFD600", "bg": "#2E2800", "icon": "🟡"},
        "BAD":    {"label": "BAD",    "color": "#FF1744", "bg": "#2E0A0A", "icon": "❌"},
    }

    # Địa chỉ Merker PLC S7-1200 (1214C)
    # MW10=Good, MW12=Medium, MW14=Bad  |  M0.0=Start, M0.1=Stop
    PLC_MW_GOOD   = 10
    PLC_MW_MEDIUM = 12
    PLC_MW_BAD    = 14
    PLC_START_BYTE, PLC_START_BIT = 0, 0
    PLC_STOP_BYTE,  PLC_STOP_BIT  = 0, 1

    def __init__(self, parent):
        self.parent = parent

        # ── Camera (hoàn toàn độc lập với PLC) ──
        self.cap          = None
        self._cam_running = False
        self._cam_thread  = None

        # ── PLC (chỉ khởi tạo khi bấm Kết nối) ──
        self._snap7       = None
        self._plc         = None
        self._plc_connected = False
        self._plc_poll_id   = None
        self._count_vars    = {}

        # ── Quản lý Trang & Menu ──
        self.sidebar_visible = False
        self.current_page = "PHANLOAI" # Mặc định trang phân loại

        self.win = tk.Toplevel(parent)
        self.win.title("Hệ thống phân loại hạng chất lượng trái cây")
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
        self._init_db()
        self._refresh_stats_ui() # Tải thống kê từ CSDL cũ (nếu có)
        self._build_ui()

        # KHÔNG tự động bật camera – chờ người dùng chọn loại đầu báo camera rồi bấm "BẬT CAMERA"
        self._log_event("Hệ thống Vision đã khởi động.")
        self._log_event("Đã tải xong CSDL Lịch sử (SQLite).")
        self._log_event("⚠️ Vui lòng chọn nguồn Camera ở tab CÀI ĐẶT rồi bấm ▶ BẬT CAMERA.")

    # ═══════════════════════════════════════════════════════
    #  DATABASE (SQLITE) & LƯU ẢNH
    # ═══════════════════════════════════════════════════════
    def _init_db(self):
        """Khởi tạo SQLite Database và thư mục chứa ảnh."""
        self.img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_images")
        if not os.path.exists(self.img_dir):
            os.makedirs(self.img_dir)
            
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS phan_loai_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      thoi_gian TEXT,
                      ket_qua TEXT,
                      duong_dan_anh TEXT,
                      ty_le_yield TEXT)''')
        conn.commit()
        conn.close()

    def _save_to_sql(self, grade=None):
        """Lưu thông tin phân loại và hình ảnh vào CSDL SQL."""
        if not hasattr(self, 'frame_to_save') or self.frame_to_save is None:
            return

        # Nếu không truyền grade, lấy grade từ bộ phân tích hiện tại
        if grade is None or grade == "MANUAL":
            grade = self.current_grade if self.current_grade != "UNKNOWN" else "GOOD"
            
        # Tạo tên file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] # YYYYMMDD_HHMMSS_mmm
        filename = f"{grade}_{timestamp}.jpg"
        filepath = os.path.join(self.img_dir, filename)
        
        # Lưu ảnh gốc
        cv2.imwrite(filepath, self.frame_to_save)
        
        # Lưu DB
        try:
            yield_str = self._yield_var.get()
            t_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO phan_loai_history (thoi_gian, ket_qua, duong_dan_anh, ty_le_yield) VALUES (?, ?, ?, ?)",
                      (t_str, grade, filepath, yield_str))
            conn.commit()
            conn.close()
            self._log_event(f"SQL Saved: [{grade}] -> {filename}")
            
            # Cập nhật các con số thống kê trên giao diện
            self._refresh_stats_ui()
        except Exception as e:
            self._log_event(f"SQL Error: {e}")

        # Cập nhật khung hình 10 ảnh
        if hasattr(self, 'win'):
            self.win.after(0, self._update_snapshot_gallery, filepath, None)

    def _refresh_stats_ui(self):
        """Cập nhật các ô số GOOD/MEDIUM/BAD và Yield Rate từ CSDL."""
        if not hasattr(self, 'win') or not self.win.winfo_exists(): return
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            total_count = 0
            good_count = 0
            
            for grade in ["GOOD", "MEDIUM", "BAD"]:
                c.execute("SELECT COUNT(*) FROM phan_loai_history WHERE ket_qua=?", (grade,))
                count = c.fetchone()[0]
                total_count += count
                if grade == "GOOD": good_count = count
                
                if grade in self._count_vars:
                    self._count_vars[grade].set(str(count))
            
            if hasattr(self, '_total_var'): self._total_var.set(str(total_count))
            
            if total_count > 0:
                y_rate = (good_count / total_count) * 100
                if hasattr(self, '_yield_var'): self._yield_var.set(f"{y_rate:.1f} %")
            else:
                if hasattr(self, '_yield_var'): self._yield_var.set("0.0 %")
                
            conn.close()
        except Exception as e:
            print(f"Error refreshing stats: {e}")

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
                
            # Khung lớn (Trang Gallery)
            if hasattr(self, 'gallery_images') and hasattr(self, 'gallery_labels'):
                img_large = img.resize((200, 150), Image.LANCZOS)
                photo_large = ImageTk.PhotoImage(img_large)
                self.gallery_images.insert(0, photo_large)
                if len(self.gallery_images) > 10:
                    self.gallery_images.pop()
                for i, p in enumerate(self.gallery_images):
                    self.gallery_labels[i].config(image=p, width=200, height=150)
                    self.gallery_labels[i].image = p
        except Exception as e:
            print(f"Lỗi cập nhật ảnh Gallery: {e}")
            self._log_event(f"Lỗi cập nhật Gallery: {e}")

    def _manual_snapshot(self):
        """Gọi khi nhấn nút Chụp Ảnh Thủ Công."""
        if not self._cam_running:
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

    def _clear_buffer(self):
        """Xóa sạch bộ nhớ đệm hình ảnh (Buffer)."""
        self.snapshot_images = []
        if hasattr(self, 'gallery_images'):
            self.gallery_images = []
            
        # Reset các label ở màn hình chính
        for lbl in self.snapshot_labels:
            lbl.config(image='')
            lbl.image = None
            
        # Reset các label ở trang Gallery
        if hasattr(self, 'gallery_labels'):
            for lbl in self.gallery_labels:
                lbl.config(image='')
                lbl.image = None
                
        self._log_event("🧹 Đã xóa sạch bộ nhớ đệm (Buffer Cleared).")


    # ═══════════════════════════════════════════════════════
    #  GIAO DIỆN & NAVIGATION
    # ═══════════════════════════════════════════════════════
    def _log_event(self, msg):
        """Ghi log vào ô Text ở cuối trang."""
        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
            return
        try:
            import time
            t = time.strftime("%H:%M:%S")
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{t}] {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
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

        self.title_lbl = tk.Label(self.hdr, text="🍎 HỆ THỐNG PHÂN LOẠI TRÁI CÂY (MODERN PROFESSIONAL MODE)",
                                  font=("Arial", 12, "bold"), fg="#F8FAFC", bg="#0F172A")
        self.title_lbl.pack(side="left", padx=10)

        # Nút điều khiển cửa sổ (bên phải header)
        window_controls = tk.Frame(self.hdr, bg="#0F172A")
        window_controls.pack(side="right", padx=10)

        self.btn_minimize = tk.Button(window_controls, text="🗕", font=("Arial", 12),
                                      fg="#94A3B8", bg="#0F172A", activebackground="#1E293B",
                                      activeforeground="#FFFFFF", bd=0, cursor="hand2",
                                      command=self._minimize_window)
        self.btn_minimize.pack(side="left", padx=5)

        self.btn_restore = tk.Button(window_controls, text="🗗", font=("Arial", 12),
                                     fg="#94A3B8", bg="#0F172A", activebackground="#1E293B",
                                     activeforeground="#FFFFFF", bd=0, cursor="hand2",
                                     command=self._restore_window)
        self.btn_restore.pack(side="left", padx=5)

        self.btn_close = tk.Button(window_controls, text="🗙", font=("Arial", 12),
                                   fg="#94A3B8", bg="#0F172A", activebackground="#EF4444",
                                   activeforeground="#FFFFFF", bd=0, cursor="hand2",
                                   command=self._on_close)
        self.btn_close.pack(side="left", padx=5)

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
        self.page_gallery = tk.Frame(self.main_container, bg="#F1F5F9")
        self.page_history = tk.Frame(self.main_container, bg="#F1F5F9")

        self._build_phanloai_page()
        self._build_setting_page()
        self._build_gallery_page()
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
        # Khi dùng overrideredirect, iconify() có thể lỗi trên một số bản Windows.
        # Ta tạm thời tắt overrideredirect trước khi thu nhỏ.
        self.win.overrideredirect(False)
        self.win.iconify()
        # Bind sự kiện khi cửa sổ mở lên lại thì bật overrideredirect
        self.win.bind("<Map>", self._on_deiconify)
        
    def _on_deiconify(self, event):
        self.win.overrideredirect(True)
        self.win.unbind("<Map>")

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
            ("🖼️  10 ẢNH GẦN NHẤT", "GALLERY"),
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
        if hasattr(self, 'page_gallery'): self.page_gallery.pack_forget()
        if hasattr(self, 'page_history'): self.page_history.pack_forget()

        if page_id == "PHANLOAI":
            self.page_phanloai.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🍎 HỆ THỐNG PHÂN LOẠI TRÁI CÂY - GIÁM SÁT")
        elif page_id == "GALLERY":
            if hasattr(self, 'page_gallery'):
                self.page_gallery.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🖼️ BỘ SƯU TẬP 10 ẢNH GẦN NHẤT")
        elif page_id == "HISTORY":
            if hasattr(self, 'page_history'):
                self.page_history.pack(fill="both", expand=True, padx=10, pady=10)
                self._refresh_history_table() # Tải lại dữ liệu mỗi khi mở trang
            self.title_lbl.config(text="📂 LỊCH SỬ PHÂN LOẠI SQL")
        else:
            self.page_setting.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="⚙️ HỆ THỐNG PHÂN LOẠI TRÁI CÂY - CÀI ĐẶT")

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
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT * FROM phan_loai_history ORDER BY id DESC LIMIT 100")
            rows = c.fetchall()
            for row in rows:
                self.history_tree.insert("", "end", values=row)
            conn.close()
        except Exception as e:
            self._log_event(f"Lỗi đọc DB: {e}")

    def _clear_sql_history(self):
        """Xóa toàn bộ dữ liệu trong bảng và xóa sạch file ảnh trong thư mục."""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa TOÀN BỘ lịch sử và hình ảnh?\n(Hành động này không thể hoàn tác!)"):
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("DELETE FROM phan_loai_history")
                conn.commit()
                conn.close()
                
                if os.path.exists(self.img_dir):
                    for f in os.listdir(self.img_dir):
                        file_path = os.path.join(self.img_dir, f)
                        try:
                            if os.path.isfile(file_path): os.unlink(file_path)
                        except: pass
                
                self._refresh_history_table()
                self._refresh_stats_ui() # Reset các con số về 0
                messagebox.showinfo("Thành công", "Đã dọn dẹp sạch sẽ CSDL và thư mục ảnh!")
                self._log_event("🗑️ Đã xóa sạch toàn bộ lịch sử SQL.")
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

    def _build_gallery_page(self):
        """Trang Bộ Sưu Tập 10 Ảnh Gần Nhất."""
        self.gallery_labels = []
        self.gallery_images = []
        
        title_frame = tk.Frame(self.page_gallery, bg="#F1F5F9")
        title_frame.pack(fill="x", pady=(20, 30))
        tk.Label(title_frame, text="📸 BỘ SƯU TẬP 10 ẢNH GẦN NHẤT", font=("Arial", 16, "bold"), fg="#0F172A", bg="#F1F5F9").pack()
        
        grid_frame = tk.Frame(self.page_gallery, bg="#F1F5F9")
        grid_frame.pack(expand=True)
        
        for row in range(2):
            row_frame = tk.Frame(grid_frame, bg="#F1F5F9")
            row_frame.pack(pady=0)
            for col in range(5):
                lbl = tk.Label(row_frame, bg="#E2E8F0", bd=0, highlightthickness=0)
                lbl.pack(side="left", padx=1, pady=1) # Giữ 1px để phân biệt nhẹ hoặc 0 để dính liền
                self.gallery_labels.append(lbl)

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
        self.cam_var = tk.StringVar(value=self.CAM_SOURCES[1]) # Mặc định chọn Camera máy tính
        self.combo = ttk.Combobox(cam_box, textvariable=self.cam_var, values=self.CAM_SOURCES, state="readonly", width=35)
        self.combo.pack(pady=(0, 15), anchor="w")

        tk.Label(cam_box, text="Nguồn Camera Màu (Khi dùng Astra 3D):", fg="#475569", bg="#FFFFFF").pack(anchor="w")
        self.astra_color_list = ["Cổng 0 (Laptop)", "Cổng 1 (USB Ngoài 1)", "Cổng 2 (USB Ngoài 2)"]
        self.astra_color_var = tk.StringVar(value=self.astra_color_list[1]) # Ưu tiên cổng 1 cho Astra
        self.combo_astra_color = ttk.Combobox(cam_box, textvariable=self.astra_color_var, values=self.astra_color_list, state="readonly", width=35)
        self.combo_astra_color.pack(pady=(0, 5), anchor="w")

        # 3. Khác

        tk.Button(container, text="🔄 RESET BỘ ĐẾM DỮ LIỆU", bg="#3949AB", fg="white", 
                  font=("Arial", 10, "bold"), pady=8, command=self._reset_counts).pack(fill="x", pady=20)

    def _build_log_area(self, parent):
        """Khung hiển thị Log."""
        log_frame = tk.LabelFrame(parent, text=" 📝 EVENT LOG ", font=("Arial", 9, "bold"), fg="#475569", bg="#FFFFFF", padx=10, pady=5)
        log_frame.pack(side="bottom", fill="x", padx=5, pady=(0, 5))
        self.log_text = tk.Text(log_frame, height=3, bg="#F8FAFC", fg="#0F172A", font=("Consolas", 9), bd=0, state="disabled")
        self.log_text.pack(fill="x")

    def _build_plc_status_area(self, parent):
        """Thanh điều khiển nhanh PLC."""
        bar = tk.LabelFrame(parent, text=" ⚡ ĐIỀU KHIỂN NHANH PLC (S7-1200 1214C) ",
                              font=("Arial", 10, "bold"), fg="#0284C7", bg="#FFFFFF",
                              padx=15, pady=8, height=65)
        bar.pack(side="bottom", fill="x", pady=(5, 0), padx=5)
        bar.pack_propagate(False) # Ngăn khung co lại

        # Nút START / STOP (Căn giữa)
        ctrl = tk.Frame(bar, bg="#FFFFFF")
        ctrl.place(relx=0.5, rely=0.5, anchor="center")

        self.btn_start = tk.Button(ctrl, text="▶  START", font=("Arial", 11, "bold"),
                                    fg="#FFFFFF", bg="#10B981", width=12, pady=5, 
                                    relief="flat", cursor="hand2", command=self._plc_start)
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop_plc = tk.Button(ctrl, text="⏹  STOP", font=("Arial", 11, "bold"),
                                       fg="#FFFFFF", bg="#EF4444", width=12, pady=5,
                                       relief="flat", cursor="hand2", command=self._plc_stop)
        self.btn_stop_plc.pack(side="left", padx=(0, 10))

        # Nút CHỤP ẢNH THỦ CÔNG
        self.btn_snapshot = tk.Button(ctrl, text="📸  CHỤP LƯU SQL", font=("Arial", 11, "bold"),
                                       fg="#FFFFFF", bg="#F59E0B", width=16, pady=5,
                                       relief="flat", cursor="hand2", command=self._manual_snapshot)
        self.btn_snapshot.pack(side="left")

        # Nút XÓA BUFFER
        self.btn_clear_buffer = tk.Button(ctrl, text="🧹 XÓA BUFFER", font=("Arial", 11, "bold"),
                                        fg="#FFFFFF", bg="#64748B", width=14, pady=5,
                                        relief="flat", cursor="hand2", command=self._clear_buffer)
        self.btn_clear_buffer.pack(side="left", padx=(10, 0))

        self.lbl_plc_status = tk.Label(bar, text="⚫ PLC chưa kết nối", font=("Arial", 10),
                                        fg="#64748B", bg="#FFFFFF")
        self.lbl_plc_status.pack(side="right", padx=10)

    # ─── Panel trái ─────────────────────────────────────
    def _build_left(self, parent):
        lf = tk.Frame(parent, bg="#FFFFFF", width=275, bd=1, relief="ridge")
        lf.pack(side="left", fill="y", padx=(0, 8))
        lf.pack_propagate(False)

        tk.Label(lf, text="📊  KẾT QUẢ PHÂN LOẠI",
                 font=("Arial", 11, "bold"), fg="#0284C7", bg="#FFFFFF",
                 ).pack(pady=(4, 6))

        self.lbl_grading_status = tk.Label(lf, text="Đang phân loại:  🍎 Táo",
                 font=("Arial", 10, "bold"), fg="#DC2626", bg="#FFFFFF",
                 )
        self.lbl_grading_status.pack(pady=(0, 10))

        # Thẻ 3 hạng
        for grade, cfg in self.GRADE_CFG.items():
            card = tk.Frame(lf, bg=cfg["bg"])
            card.pack(fill="x", padx=8, pady=2)
            tk.Label(card, text=f"{cfg['icon']}  {cfg['label']}",
                     font=("Arial", 11, "bold"), fg=cfg["color"], bg=cfg["bg"],
                     ).pack(anchor="w", padx=10, pady=(2, 0))
            var = tk.StringVar(value="0")
            self._count_vars[grade] = var
            tk.Label(card, textvariable=var,
                     font=("Consolas", 24, "bold"), fg="#FFFFFF", bg=cfg["bg"],
                     ).pack(anchor="e", padx=14, pady=(0, 2))

        # Tổng
        tk.Frame(lf, bg="#E2E8F0", height=1).pack(fill="x", padx=8, pady=4)
        total_card = tk.Frame(lf, bg="#F8FAFC")
        total_card.pack(fill="x", padx=8)
        tk.Label(total_card, text="TỔNG SỐ",
                 font=("Arial", 10, "bold"), fg="#475569", bg="#F8FAFC",
                 ).pack(pady=(2, 0))
        self._total_var = tk.StringVar(value="0")
        tk.Label(total_card, textvariable=self._total_var,
                 font=("Consolas", 20, "bold"), fg="#0F172A", bg="#F8FAFC",
                 ).pack(pady=(0, 2))

        # Thẻ Yield Rate (Tỷ lệ đạt)
        tk.Frame(lf, bg="#E2E8F0", height=1).pack(fill="x", padx=8, pady=4)
        yield_card = tk.Frame(lf, bg="#F8FAFC")
        yield_card.pack(fill="x", padx=8)
        tk.Label(yield_card, text="🎯 YIELD RATE", font=("Arial", 10, "bold"), fg="#475569", bg="#F8FAFC").pack(pady=(2,0))
        self._yield_var = tk.StringVar(value="0.0 %")
        tk.Label(yield_card, textvariable=self._yield_var, font=("Consolas", 16, "bold"), fg="#059669", bg="#F8FAFC").pack(pady=(0,2))

        # Nút Bật/Tắt Camera
        self.btn_cam = tk.Button(lf, text="▶ BẬT CAMERA", font=("Arial", 10, "bold"),
                                  bg="#2E7D32", fg="white", pady=6, cursor="hand2", command=self._toggle_camera)
        self.btn_cam.pack(fill="x", padx=15, pady=(10, 2))

        # Nút Mở File (Ảnh/Video) nhanh
        self.btn_open_file = tk.Button(lf, text="📂 MỞ FILE (ẢNH/VIDEO)", font=("Arial", 10, "bold"),
                                       bg="#6366F1", fg="white", pady=6, cursor="hand2", command=self._quick_open_file)
        self.btn_open_file.pack(fill="x", padx=15, pady=5)

        self.lbl_cam_status = tk.Label(lf, text="⚫ Camera chưa bật", font=("Arial", 9),
                                        fg="#475569", bg="#FFFFFF")
        self.lbl_cam_status.pack(pady=0)


    # ─── Panel phải: camera màu + ảnh xám ─────────────────
    def _build_right(self, parent):
        rf = tk.Frame(parent, bg="#FFFFFF", bd=1, relief="ridge")
        rf.pack(side="left", fill="both", expand=True)

        # ── Thanh điều khiển chế độ xem ──
        view_ctrl = tk.Frame(rf, bg="#F1F5F9", pady=3)
        view_ctrl.pack(fill="x")
        tk.Label(view_ctrl, text="📺 CHẾ ĐỘ HIỂN THỊ:", font=("Arial", 9, "bold"), fg="#475569", bg="#F1F5F9").pack(side="left", padx=10)
        
        self.view_mode_var = tk.StringVar(value="Color & Gray")
        view_modes = ["Color & Gray", "Color & Binary", "Gray & Binary"]
        self.view_combo = ttk.Combobox(view_ctrl, textvariable=self.view_mode_var, values=view_modes, state="readonly", width=18)
        self.view_combo.pack(side="left", padx=5)
        self.view_combo.bind("<<ComboboxSelected>>", self._on_view_mode_change)

        # ── Canvas 1 (trên) ──
        self.lbl_view1 = tk.Label(rf, text="📷  CAMERA (COLOR)",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF")
        self.lbl_view1.pack(anchor="w", padx=6, pady=(4, 0))
        self.canvas = tk.Canvas(rf, width=850, height=240,
                                bg="#000000", highlightthickness=1, highlightbackground="#CBD5E1")
        self.canvas.pack(padx=4, pady=(0, 2))

        # ── Canvas 2 (dưới) ──
        self.lbl_view2 = tk.Label(rf, text="🔲  MACHINE VISION (DEPTH MAP / GRAYSCALE)",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF")
        self.lbl_view2.pack(anchor="w", padx=6, pady=(2, 0))
        self.canvas_gray = tk.Canvas(rf, width=850, height=240,
                                     bg="#000000", highlightthickness=1, highlightbackground="#CBD5E1")
        self.canvas_gray.pack(padx=4, pady=(0, 4))
        
        # Nút bật 3D Point Cloud
        self.btn_3d = tk.Button(rf, text="🌌 MỞ POINT CLOUD 3D", font=("Arial", 9, "bold"),
                                bg="#4F46E5", fg="white", cursor="hand2", pady=4, command=self._show_point_cloud)
        self.btn_3d.pack(pady=5)

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

    def _quick_open_file(self):
        """Hàm mở file nhanh từ nút bấm ở sidebar."""
        file_path = filedialog.askopenfilename(
            title="Chọn file ảnh hoặc video để phân tích",
            filetypes=[("Tất cả tệp media", "*.jpg *.jpeg *.png *.bmp *.mp4 *.avi *.mkv *.mov"),
                       ("Ảnh", "*.jpg *.jpeg *.png *.bmp"),
                       ("Video", "*.mp4 *.avi *.mkv *.mov")]
        )
        if not file_path:
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        is_video = ext in [".mp4", ".avi", ".mkv", ".mov"]
        
        # Nếu đang chạy camera thì dừng lại trước
        if self._cam_running:
            self._stop_camera()
            
        # Gọi hàm khởi tạo chế độ file đã viết trước đó
        self._start_file_mode(file_path, is_video=is_video)

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, 850, 240, fill="#0A0A0A")
        self.canvas.create_text(425, 105, text="📷", font=("Arial", 36), fill="#424242")
        self.canvas.create_text(425, 155,
                                text="[SYSTEM READY - WAITING FOR CAMERA]",
                                font=("Consolas", 12), fill="#00E676")
        self.canvas_gray.delete("all")
        self.canvas_gray.create_rectangle(0, 0, 850, 240, fill="#0A0A0A")
        self.canvas_gray.create_text(425, 105, text="🔲", font=("Arial", 36), fill="#333333")
        self.canvas_gray.create_text(425, 155,
                                     text="Ảnh xám sẽ hiển thị khi camera hoạt động",
                                     font=("Arial", 12), fill="#333344")
        
        # Đặt lại ID để vẽ frame mới khi bật camera
        self.img_id_color = None
        self.img_id_gray = None



    # ═══════════════════════════════════════════════════════
    #  LOGIC CAMERA
    # ═══════════════════════════════════════════════════════
    def _toggle_camera(self):
        if self._cam_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        val = self.cam_var.get()
        self.is_single_image = False # Reset mặc định
        
        if "Astra Pro" in val:
            self._start_astra_camera()
            return
            
        # Mở File Ảnh
        if "Mở File Ảnh" in val:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
            if not path: return
            self._start_file_mode(path, is_video=False)
            return
            
        # Mở File Video
        if "Mở File Video" in val:
            path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")])
            if not path: return
            self._start_file_mode(path, is_video=True)
            return
            
        # Code cũ cho OpenCV bình thường
        idx = self.combo.current() - 1 # Do thêm Astra lên đầu
        if idx < 0:
            idx = 0
        self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Lỗi Camera", f"Không thể mở camera {idx}.")
            return
        self._cam_running = True
        self.btn_cam.config(text="⏹  Tắt Camera", bg="#B71C1C", activebackground="#7F0000")
        self.lbl_cam_status.config(text="🟢  Đang phát", fg="#69F0AE")
        self.combo.config(state="disabled")
        self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._cam_thread.start()

    def _start_file_mode(self, path, is_video=False):
        """Khởi tạo chế độ đọc file ảnh hoặc video."""
        if is_video:
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                messagebox.showerror("Lỗi", "Không thể mở file video này!")
                return
        else:
            img = cv2.imread(path)
            if img is None:
                messagebox.showerror("Lỗi", "Không thể mở file ảnh này!")
                return
            self.single_image_frame = img
            self.is_single_image = True
            
        self._cam_running = True
        self.btn_cam.config(text="⏹  Dừng File", bg="#B71C1C")
        self.lbl_cam_status.config(text="🟢  Đang phát File", fg="#69F0AE")
        self.combo.config(state="disabled")
        self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._cam_thread.start()

    def _stop_camera(self):
        self._cam_running = False
        
        # Tắt Astra
        if hasattr(self, 'astra_dev') and self.astra_dev:
            try:
                if hasattr(self, 'astra_color_stream'): self.astra_color_stream.stop()
                if hasattr(self, 'astra_depth_stream'): self.astra_depth_stream.stop()
                from openni import openni2
                openni2.unload()
                self.astra_dev = None
            except: pass
            
        # Tắt OpenCV
        if self.cap:
            self.cap.release()
            self.cap = None
            
        self.btn_cam.config(text="▶  Bật Camera", bg="#2E7D32", activebackground="#1B5E20")
        self.lbl_cam_status.config(text="⚫  Camera chưa bật", fg="#666680")
        self.combo.config(state="readonly")
        self._draw_placeholder()


    def _stream_loop(self):
        import time
        last_buffer_time = time.time()
        is_single = getattr(self, 'is_single_image', False)
        
        while self._cam_running:
            if is_single:
                frame = self.single_image_frame.copy()
                ret = True
                time.sleep(0.05) # Giảm tải CPU cho ảnh tĩnh
            else:
                ret, frame = self.cap.read()
                if not ret:
                    # Nếu là video thì lặp lại (Loop video)
                    if self.cap.get(cv2.CAP_PROP_FRAME_COUNT) > 1:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
                
            self.frame_to_save = frame.copy() # Lưu lại frame hiện hành để chụp ảnh
            
            # --- VẼ KHUNG PHÂN TÍCH & XỬ LÝ ---
            h_f, w_f = frame.shape[:2]
            x1, y1, x2, y2 = w_f//2 - 100, 20, w_f//2 + 100, h_f - 20
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(frame, "ANALYSIS ZONE", (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # --- GỌI LOGIC PHÂN LOẠI THÂM ĐEN ---
            try:
                roi = frame[y1:y2, x1:x2]
                processed_roi, defect_area, ripeness, grade = self.analyzer.analyze_apple(roi)
                frame[y1:y2, x1:x2] = processed_roi
                self.current_grade = grade # Cập nhật grade vào biến toàn cục
                
                # Hiển thị kết quả lên GUI (Panel trái)
                color_map_hex = {"GOOD": "#10B981", "MEDIUM": "#F59E0B", "BAD": "#EF4444", "UNKNOWN": "#64748B"}
                status_text = f"Đang phân loại: 🍎 {grade}"
                if grade != "NO_APPLE" and grade != "UNKNOWN":
                    status_text += f" ({ripeness:.0f}% Đỏ)"
                self.lbl_grading_status.config(text=status_text, fg=color_map_hex.get(grade, "#64748B"))

                # Hiển thị kết quả lên khung hình Camera
                color_map_bgr = {"GOOD": (0, 255, 0), "MEDIUM": (0, 255, 255), "BAD": (0, 0, 255)}
                cv2.putText(frame, f"STATUS: {grade}", (x1, y2 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_map_bgr.get(grade, (255,255,255)), 2)
            except:
                pass

            # Auto buffer update (tự động đẩy khung hình) theo thời gian thực (0.1s/lần)
            current_time = time.time()
            if current_time - last_buffer_time >= 0.1:
                last_buffer_time = current_time
                self.canvas.after(0, self._update_snapshot_gallery, None, self.frame_to_save.copy())
            
            # ── Tạo 3 loại khung hình ──
            # 1. Màu
            color_res = cv2.resize(frame, (850, 240))
            color_rgb = cv2.cvtColor(color_res, cv2.COLOR_BGR2RGB)
            
            # 2. Xám
            gray_res = cv2.cvtColor(color_res, cv2.COLOR_BGR2GRAY)
            gray_rgb = cv2.cvtColor(gray_res, cv2.COLOR_GRAY2RGB)
            
            # 3. Nhị phân (Binary)
            _, binary = cv2.threshold(gray_res, 127, 255, cv2.THRESH_BINARY)
            binary_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            
            # Chọn khung hình hiển thị dựa trên View Mode
            mode = self.view_mode_var.get()
            if mode == "Color & Gray":
                f1_rgb, f2_rgb = color_rgb, gray_rgb
            elif mode == "Color & Binary":
                f1_rgb, f2_rgb = color_rgb, binary_rgb
            else: # Gray & Binary
                f1_rgb, f2_rgb = gray_rgb, binary_rgb
                
            imgtk1 = ImageTk.PhotoImage(image=Image.fromarray(f1_rgb))
            imgtk2 = ImageTk.PhotoImage(image=Image.fromarray(f2_rgb))
            
            try:
                self.canvas.imgtk = imgtk1
                self.canvas_gray.imgtk = imgtk2
                self.canvas.after(0, self._update_canvas, imgtk1, imgtk2)
            except Exception:
                break

    # ─── ASTRA PRO SDK LOGIC ──────────────────────────────────────────────
    def _start_astra_camera(self):
        try:
            from openni import openni2
            # Khởi tạo OpenNI2
            openni2.initialize() 
            self.astra_dev = openni2.Device.open_any()
            
            # CHỈ MỞ DEPTH STREAM (Astra Pro dùng UVC cho Color, không hỗ trợ qua OpenNI)
            self.astra_depth_stream = self.astra_dev.create_depth_stream()
            self.astra_depth_stream.start()
            
            # Mở Color Stream bằng OpenCV (Webcam tiêu chuẩn)
            self.cap = None
            
            # Lấy cổng camera màu người dùng chọn ở tab Cài Đặt
            sel_idx = self.combo_astra_color.current()
            if sel_idx < 0: sel_idx = 1
            
            # Ưu tiên quét cổng được chọn trước, dự phòng các cổng khác nếu cổng đó lỗi
            scan_order = [sel_idx] + [i for i in (1, 2, 0) if i != sel_idx]
            
            for i in scan_order:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    # Ép tỷ lệ 4:3 (640x480) giống hệt với Depth Map để tránh lệch góc nhìn
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    ret, _ = cap.read()
                    if ret:
                        self.cap = cap
                        break
                    else:
                        cap.release()
            
            if self.cap is None:
                self.win.after(0, self._log_event, "⚠️ Cảnh báo: Không thể tìm thấy RGB Camera. Chỉ chạy Depth.")
                
            self._cam_running = True
            self.btn_cam.config(text="⏹  Tắt Astra Pro", bg="#B71C1C", activebackground="#7F0000")
            self.lbl_cam_status.config(text="🟢  Đang phát (Astra Pro 3D)", fg="#69F0AE")
            self.combo.config(state="disabled")
            self._cam_thread = threading.Thread(target=self._stream_astra_loop, daemon=True)
            self._cam_thread.start()
        except ImportError:
            messagebox.showerror("Thiếu thư viện", "Chưa cài đặt SDK. Chạy lệnh trong Terminal:\n pip install openni")
        except Exception as e:
            messagebox.showerror("Lỗi Astra Pro SDK", f"Không thể kết nối Camera Astra. Hãy chắc chắn bạn đã cắm cáp và cài Driver của hãng.\nChi tiết: {e}")

    def _stream_astra_loop(self):
        import numpy as np
        from openni import openni2
        import time
        self.win.after(0, self._log_event, "Đã vào luồng Astra. Đang đồng bộ hóa RGB và Depth...")
        
        last_buffer_time = time.time()
        while self._cam_running:
            try:
                # Đọc Color Frame từ OpenCV (UVC)
                color_img = None
                if self.cap and self.cap.isOpened():
                    ret, cframe = self.cap.read()
                    if ret:
                        self.frame_to_save = cframe.copy()
                        color_img = cv2.cvtColor(cframe, cv2.COLOR_BGR2RGB)
                
                # Chờ có Depth Frame mới (timeout 1 giây để không bị treo vĩnh viễn)
                openni2.wait_for_any_stream([self.astra_depth_stream], timeout=1000)
                
                # Đọc Depth Frame từ OpenNI
                dframe = self.astra_depth_stream.read_frame()
                ddata = np.frombuffer(dframe.get_buffer_as_uint16(), dtype=np.uint16)
                depth_img = ddata.reshape((dframe.height, dframe.width))
                self.last_depth_map = depth_img.copy() # Lưu lại cho 3D
                
                # Tạo Depth Map Color (Ảnh màu nhiệt)
                depth_norm = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)
                
                # --- VẼ THƯỚC ĐO THANG MÀU (COLORBAR LEGEND) ---
                h, w = depth_colormap.shape[:2]
                bar_h, bar_w, margin = 150, 15, 10
                if h > bar_h + 20 and w > bar_w + 60:
                    # Tạo gradient dọc: 255 (Nóng/Đỏ/Xa) ở trên, 0 (Lạnh/Xanh/Gần) ở dưới
                    gradient = np.linspace(255, 0, bar_h, dtype=np.uint8).reshape(-1, 1)
                    gradient = np.repeat(gradient, bar_w, axis=1)
                    colorbar_color = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
                    
                    x1, y1 = w - margin - bar_w, margin
                    depth_colormap[y1:y1+bar_h, x1:x1+bar_w] = colorbar_color
                    
                    # Viền trắng cho thước đo
                    cv2.rectangle(depth_colormap, (x1, y1), (x1+bar_w, y1+bar_h), (255, 255, 255), 1)
                    # Ghi chú FAR / NEAR
                    cv2.putText(depth_colormap, "FAR", (x1 - 35, y1 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(depth_colormap, "NEAR", (x1 - 42, y1 + bar_h), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                # -----------------------------------------------
                
                # Nếu không có Color Frame, dùng Depth thay thế
                if color_img is None:
                    color_img = cv2.cvtColor(depth_colormap, cv2.COLOR_BGR2RGB)
                    self.frame_to_save = depth_colormap.copy()
                
                # --- VẼ KHUNG PHÂN TÍCH LÊN COLOR IMG ---
                h_c, w_c = color_img.shape[:2]
                cv2.rectangle(color_img, (w_c//2 - 100, 20), (w_c//2 + 100, h_c - 20), (255, 255, 255), 2)
                cv2.putText(color_img, "ANALYSIS ZONE", (w_c//2 - 95, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

                
                # Resize và hiển thị
                color_resized = cv2.resize(color_img, (850, 240))
                color_rgb = cv2.cvtColor(color_resized, cv2.COLOR_BGR2RGB)
                
                # Gray từ Astra
                gray_astra = cv2.cvtColor(color_resized, cv2.COLOR_BGR2GRAY)
                gray_rgb = cv2.cvtColor(gray_astra, cv2.COLOR_GRAY2RGB)
                
                # Binary từ Astra
                _, binary_astra = cv2.threshold(gray_astra, 127, 255, cv2.THRESH_BINARY)
                binary_rgb = cv2.cvtColor(binary_astra, cv2.COLOR_GRAY2RGB)
                
                # Chọn View Mode cho Astra
                mode = self.view_mode_var.get()
                if mode == "Color & Gray":
                    f1_rgb, f2_rgb = color_rgb, gray_rgb
                elif mode == "Color & Binary":
                    f1_rgb, f2_rgb = color_rgb, binary_rgb
                else:
                    f1_rgb, f2_rgb = gray_rgb, binary_rgb
                
                imgtk1 = ImageTk.PhotoImage(image=Image.fromarray(f1_rgb))
                imgtk2 = ImageTk.PhotoImage(image=Image.fromarray(f2_rgb))
                
                # Auto buffer update
                current_time = time.time()
                if current_time - last_buffer_time >= 0.1:
                    last_buffer_time = current_time
                    self.canvas.after(0, self._update_snapshot_gallery, None, self.frame_to_save.copy())
                
                self.canvas.imgtk = imgtk1
                self.canvas_gray.imgtk = imgtk2
                self.canvas.after(0, self._update_canvas, imgtk1, imgtk2)
            except Exception as e:
                # Tránh in lỗi timeout liên tục khi chờ stream
                if "OniStatus.ONI_STATUS_TIME_OUT" not in str(e):
                    self.win.after(0, self._log_event, f"Astra Error: {e}")
                import time
                time.sleep(0.5)

    def _show_point_cloud(self):
        if not hasattr(self, 'last_depth_map') or self.last_depth_map is None:
            messagebox.showwarning("Chưa có dữ liệu", "Hãy bật Camera Astra Pro và để camera quét Depth Map trước khi mở 3D!")
            return
            
        try:
            import open3d as o3d
            import numpy as np
            
            # Chuyển đổi định dạng cho Open3D
            color_rgb = cv2.cvtColor(self.frame_to_save, cv2.COLOR_BGR2RGB)
            depth_img = self.last_depth_map
            
            o3d_color = o3d.geometry.Image(color_rgb)
            o3d_depth = o3d.geometry.Image(depth_img)
            
            rgbd_image = o3d.geometry.RGBDImage.create_from_color_and_depth(
                o3d_color, o3d_depth, depth_scale=1000.0, depth_trunc=3.0, convert_rgb_to_intensity=False)
            
            intrinsics = o3d.camera.PinholeCameraIntrinsic(
                o3d.camera.PinholeCameraIntrinsicParameters.PrimeSenseDefault)
                
            pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd_image, intrinsics)
            pcd.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]) # Lật trục
            
            # Hiện cửa sổ Open3D
            o3d.visualization.draw_geometries([pcd], window_name="Astra Pro 3D Point Cloud", width=800, height=600)
            
        except ImportError:
            messagebox.showerror("Thiếu thư viện", "Chưa cài đặt Open3D. Chạy lệnh:\n pip install open3d")
        except Exception as e:
            messagebox.showerror("Lỗi Open3D", f"Không thể tạo Point Cloud:\n{e}")
            
    # ─── END ASTRA PRO SDK LOGIC ────────────────────────────────────────

    def _update_canvas(self, imgtk_color, imgtk_gray):
        if self._cam_running:
            if getattr(self, 'img_id_color', None) is None:
                self.canvas.delete("all")
                self.canvas_gray.delete("all")
                self.img_id_color = self.canvas.create_image(0, 0, anchor="nw", image=imgtk_color)
                self.img_id_gray = self.canvas_gray.create_image(0, 0, anchor="nw", image=imgtk_gray)
            else:
                self.canvas.itemconfig(self.img_id_color, image=imgtk_color)
                self.canvas_gray.itemconfig(self.img_id_gray, image=imgtk_gray)

    # ═══════════════════════════════════════════════════════
    #  LOGIC PLC S7-1200 (snap7)
    # ═══════════════════════════════════════════════════════
    def _toggle_plc(self):
        if self._plc_connected:
            self._disconnect_plc()
        else:
            self._connect_plc()

    def _connect_plc(self):
        # Khởi tạo snap7 lần đầu khi bấm kết nối
        try:
            import snap7
            self._snap7 = snap7
            self._plc   = snap7.client.Client()
        except ImportError:
            messagebox.showerror("Thiếu thư viện",
                                 "Chưa cài python-snap7!\nChạy lệnh:\n  pip install python-snap7")
            return
        except Exception as e:
            messagebox.showerror("Lỗi snap7",
                                 f"Không thể khởi tạo snap7 (thiếu snap7.dll?):\n{e}")
            return

        ip   = self.plc_ip_var.get().strip()
        rack = int(self.plc_rack_var.get() or 0)
        slot = int(self.plc_slot_var.get() or 1)
        try:
            self._plc.connect(ip, rack, slot)
            self._plc_connected = True
            self.btn_connect.config(text="🔌  Ngắt kết nối",
                                    bg="#6A1B9A", activebackground="#4A148C")
            self.lbl_plc_status.config(text=f"🟢  PLC: {ip}", fg="#69F0AE")
            self._plc_poll_id = self.win.after(1000, self._poll_plc)
        except Exception as e:
            messagebox.showerror("Lỗi PLC", f"Không kết nối được PLC!\n{e}")

    def _disconnect_plc(self):
        if self._plc_poll_id:
            self.win.after_cancel(self._plc_poll_id)
            self._plc_poll_id = None
        try:
            self._plc.disconnect()
        except Exception:
            pass
        self._plc_connected = False
        self.btn_connect.config(text="🔌  Kết nối PLC",
                                bg="#1565C0", activebackground="#0D47A1")
        self.lbl_plc_status.config(text="⚫  PLC chưa kết nối", fg="#666680")

    def _poll_plc(self):
        """Đọc bộ đếm từ PLC mỗi 1 giây."""
        if not self._plc_connected:
            return
        try:
            import snap7.types as s7t
            data   = self._plc.read_area(s7t.Areas.MK, 0, self.PLC_MW_GOOD, 6)
            good   = self._snap7.util.get_int(data, 0)
            medium = self._snap7.util.get_int(data, 2)
            bad    = self._snap7.util.get_int(data, 4)
            self._update_counts(good, medium, bad)
        except Exception:
            pass
        self._plc_poll_id = self.win.after(1000, self._poll_plc)

    def _plc_write_bit(self, byte_addr, bit_addr, value: bool):
        if not self._plc_connected:
            messagebox.showwarning("Chưa kết nối", "Vui lòng kết nối PLC trước!")
            return
        try:
            import snap7.types as s7t
            data = self._plc.read_area(s7t.Areas.MK, 0, byte_addr, 1)
            self._snap7.util.set_bool(data, 0, bit_addr, value)
            self._plc.write_area(s7t.Areas.MK, 0, byte_addr, data)
        except Exception as e:
            messagebox.showerror("Lỗi PLC", f"Ghi dữ liệu thất bại!\n{e}")

    # ─── PLC 1214C Control Bits ───
    PLC_START_BYTE = 0 # M0
    PLC_START_BIT  = 0 # .0 -> M0.0
    PLC_STOP_BYTE  = 0 # M0
    PLC_STOP_BIT   = 1 # .1 -> M0.1

    def _plc_start(self):
        """Ghi M0.0 = True → PLC bắt đầu chạy."""
        success = self._plc_write_bit(self.PLC_START_BYTE, self.PLC_START_BIT, True)
        if success:
            self.lbl_plc_status.config(text="🟢 PLC: Đang chạy (M0.0)", fg="#2E7D32")
        else:
            self.lbl_plc_status.config(text="🔴 Lỗi ghi START", fg="#D32F2F")

    def _plc_stop(self):
        """Ghi M0.1 = True → PLC dừng."""
        success = self._plc_write_bit(self.PLC_STOP_BYTE, self.PLC_STOP_BIT, True)
        if success:
            self.lbl_plc_status.config(text="🟡 PLC: Đã dừng (M0.1)", fg="#C62828")
        else:
            self.lbl_plc_status.config(text="🔴 Lỗi ghi STOP", fg="#D32F2F")

    # ═══════════════════════════════════════════════════════
    #  BỘ ĐẾM PHÂN LOẠI
    # ═══════════════════════════════════════════════════════
    def _update_counts(self, good, medium, bad):
        old_good = int(self._count_vars["GOOD"].get())
        old_medium = int(self._count_vars["MEDIUM"].get())
        old_bad = int(self._count_vars["BAD"].get())

        self._count_vars["GOOD"].set(str(good))
        self._count_vars["MEDIUM"].set(str(medium))
        self._count_vars["BAD"].set(str(bad))
        total = good + medium + bad
        self._total_var.set(str(total))
        
        # Cập nhật Yield
        if total > 0:
            yield_rate = (good / total) * 100
            self._yield_var.set(f"{yield_rate:.1f} %")
        else:
            self._yield_var.set("0.0 %")

        # LƯU LỊCH SỬ (Tự động kích hoạt khi có táo mới được phân loại)
        if good > old_good:
            self._save_to_sql("GOOD")
        if medium > old_medium:
            self._save_to_sql("MEDIUM")
        if bad > old_bad:
            self._save_to_sql("BAD")

    def _reset_counts(self):
        self._update_counts(0, 0, 0)

    # ═══════════════════════════════════════════════════════
    #  ĐÓNG
    # ═══════════════════════════════════════════════════════
    def _on_close(self):
        self._stop_camera()
        self._disconnect_plc()
        self.win.destroy()


# ─── Điểm khởi chạy ──────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = FruitClassificationApp(root)
    root.mainloop()

"""
Giao diện báo điện - Đồ án Nhận dạng và Phân loại Trái cây
Khoa Điện - Điện Tử, Trường ĐH Sư phạm Kỹ thuật TP.HCM (UTE)
"""

import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import os
import sys
import threading
import cv2
import sqlite3
from datetime import datetime


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
        self.root.resizable(False, False)

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
        self._build_header()
        self._build_content()
        self._build_buttons()

    def _build_header(self):
        """Phần header: logo + thông tin khoa/trường."""
        header_frame = tk.Frame(self.root, bg=self.BG_COLOR)
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
        content_frame = tk.Frame(self.root, bg=self.BG_COLOR)
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # ── Đề tài ──
        topic_frame = tk.Frame(content_frame, bg=self.BG_COLOR)
        topic_frame.pack(fill="x", pady=(5, 10))

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
        separator = tk.Frame(self.root, height=2, bg="#E0E0E0")
        separator.pack(fill="x", padx=20, pady=(5, 0))

        btn_frame = tk.Frame(self.root, bg="#F5F5F5")
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
        "Camera máy tính (Tích hợp)",
        "Webcam rời 1 (Cổng USB)",
        "Webcam rời 2 (Cổng USB)",
        "Webcam rời 3",
        "Luồng RTSP / IP Camera",
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
        self.win.configure(bg="#F1F5F9") # Slate 100 - Trắng xám sáng sủa
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        W, H = 1160, 760 # Tăng chiều cao để hiển thị đủ thẻ Yield và nút Camera
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        self.win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._init_db()
        self._build_ui()

        # Tự động bật camera ngay sau khi mở cửa sổ
        self.win.after(500, self._start_camera)
        self._log_event("Hệ thống Vision đã khởi động.")
        self._log_event("Đã tải xong CSDL Lịch sử (SQLite).")

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

    def _save_to_sql(self, grade):
        """Lưu ảnh và thông tin vào CSDL."""
        if not hasattr(self, 'frame_to_save') or self.frame_to_save is None:
            return
            
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
        except Exception as e:
            self._log_event(f"SQL Error: {e}")

    # ═══════════════════════════════════════════════════════
    #  GIAO DIỆN & NAVIGATION
    # ═══════════════════════════════════════════════════════
    def _log_event(self, msg):
        """Ghi log hệ thống."""
        if hasattr(self, 'log_text'):
            import time
            t = time.strftime("%H:%M:%S")
            self.log_text.config(state="normal")
            self.log_text.insert("end", f"[{t}] {msg}\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

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

        self._build_phanloai_page()
        self._build_setting_page()

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
        if page_id == "HISTORY":
            self._show_history_window()
            return

        self.current_page = page_id
        
        # Ẩn tất cả trang
        self.page_phanloai.pack_forget()
        self.page_setting.pack_forget()

        if page_id == "PHANLOAI":
            self.page_phanloai.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🍎 HỆ THỐNG PHÂN LOẠI TRÁI CÂY - GIÁM SÁT")
        else:
            self.page_setting.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="⚙️ HỆ THỐNG PHÂN LOẠI TRÁI CÂY - CÀI ĐẶT")

        # Đóng menu sau khi chọn
        if self.sidebar_visible:
            self._toggle_sidebar()

    def _show_history_window(self):
        """Mở cửa sổ xem lịch sử lưu trong CSDL SQLite."""
        hw = tk.Toplevel(self.win)
        hw.title("Lịch sử Phân loại (SQLite)")
        hw.geometry("900x500")
        hw.configure(bg="#F1F5F9")
        
        # Header
        tk.Label(hw, text="📂 LỊCH SỬ PHÂN LOẠI & HÌNH ẢNH", font=("Arial", 14, "bold"), fg="#0F172A", bg="#F1F5F9").pack(pady=10)
        
        # Bảng (Treeview)
        columns = ("ID", "Thời gian", "Kết quả", "Tỷ lệ", "Đường dẫn ảnh")
        tree = ttk.Treeview(hw, columns=columns, show="headings", height=15)
        
        tree.heading("ID", text="ID")
        tree.column("ID", width=50, anchor="center")
        tree.heading("Thời gian", text="Thời gian")
        tree.column("Thời gian", width=150, anchor="center")
        tree.heading("Kết quả", text="Kết quả")
        tree.column("Kết quả", width=100, anchor="center")
        tree.heading("Tỷ lệ", text="Tỷ lệ Yield")
        tree.column("Tỷ lệ", width=100, anchor="center")
        tree.heading("Đường dẫn ảnh", text="Đường dẫn file ảnh lưu trữ")
        tree.column("Đường dẫn ảnh", width=450, anchor="w")
        
        tree.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Load dữ liệu
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT * FROM phan_loai_history ORDER BY id DESC LIMIT 100")
            rows = c.fetchall()
            for row in rows:
                tree.insert("", "end", values=row)
            conn.close()
        except Exception as e:
            messagebox.showerror("Lỗi CSDL", f"Không thể đọc dữ liệu:\n{e}")

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
        
        self.cam_var = tk.StringVar(value=self.CAM_SOURCES[0])
        self.combo = ttk.Combobox(cam_box, textvariable=self.cam_var, values=self.CAM_SOURCES, state="readonly", width=30)
        self.combo.pack(pady=10)

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
        self.btn_stop_plc.pack(side="left")

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

        tk.Label(lf, text="Đang phân loại:  🍎 Táo",
                 font=("Arial", 10, "bold"), fg="#DC2626", bg="#FFFFFF",
                 ).pack(pady=(0, 10))

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

        self.lbl_cam_status = tk.Label(lf, text="⚫ Camera chưa bật", font=("Arial", 9),
                                        fg="#475569", bg="#FFFFFF")
        self.lbl_cam_status.pack(pady=0)


    # ─── Panel phải: camera màu + ảnh xám ─────────────────
    def _build_right(self, parent):
        rf = tk.Frame(parent, bg="#FFFFFF", bd=1, relief="ridge")
        rf.pack(side="left", fill="both", expand=True)

        # ── Canvas màu (trên) ──
        tk.Label(rf, text="📷  CAMERA (COLOR)",
                 font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF",
                 ).pack(anchor="w", padx=6, pady=(4, 0))
        self.canvas = tk.Canvas(rf, width=850, height=240,
                                bg="#000000", highlightthickness=1, highlightbackground="#CBD5E1")
        self.canvas.pack(padx=4, pady=(0, 2))

        # ── Canvas xám (dưới) ──
        tk.Label(rf, text="🔲  MACHINE VISION (GRAYSCALE)",
                 font=("Arial", 9, "bold"), fg="#0284C7", bg="#FFFFFF",
                 ).pack(anchor="w", padx=6, pady=(2, 0))
        self.canvas_gray = tk.Canvas(rf, width=850, height=240,
                                     bg="#000000", highlightthickness=1, highlightbackground="#CBD5E1")
        self.canvas_gray.pack(padx=4, pady=(0, 4))

        self._draw_placeholder()

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



    # ═══════════════════════════════════════════════════════
    #  LOGIC CAMERA
    # ═══════════════════════════════════════════════════════
    def _toggle_camera(self):
        if self._cam_running:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        idx = self.combo.current()
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

    def _stop_camera(self):
        self._cam_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        self.btn_cam.config(text="▶  Bật Camera", bg="#2E7D32", activebackground="#1B5E20")
        self.lbl_cam_status.config(text="⚫  Camera chưa bật", fg="#666680")
        self.combo.config(state="readonly")
        self._draw_placeholder()


    def _stream_loop(self):
        while self._cam_running:
            ret, frame = self.cap.read()
            if not ret:
                break
                
            self.frame_to_save = frame.copy() # Lưu lại frame hiện hành để chụp ảnh
            
            # ── Frame màu ──
            color = cv2.resize(frame, (850, 240))
            color_rgb = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
            imgtk_color = ImageTk.PhotoImage(image=Image.fromarray(color_rgb))
            # ── Frame xám ──
            gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
            gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)  # convert để PhotoImage dùng được
            imgtk_gray = ImageTk.PhotoImage(image=Image.fromarray(gray_rgb))
            try:
                self.canvas.imgtk = imgtk_color
                self.canvas_gray.imgtk = imgtk_gray
                self.canvas.after(0, self._update_canvas, imgtk_color, imgtk_gray)
            except Exception:
                break

    def _update_canvas(self, imgtk_color, imgtk_gray):
        if self._cam_running:
            self.canvas.create_image(0, 0, anchor="nw", image=imgtk_color)
            self.canvas_gray.create_image(0, 0, anchor="nw", image=imgtk_gray)

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

import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageTk
import os
import sys
import threading
import time
import cv2
from datetime import datetime

# Đảm bảo Python tìm thấy cả 2 gốc import:
# - project_root chứa Processing (mới)
# - giaodien chứa config, modules, images
_GIAODIEN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_GIAODIEN_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _GIAODIEN_DIR not in sys.path:
    sys.path.insert(0, _GIAODIEN_DIR)

from Processing.analyzer import FruitAnalyzer
from Processing.analyzer_modules.session_decision import (
    grade_rank as decision_grade_rank,
    compute_frame_quality_weight as decision_compute_frame_quality_weight,
    fuse_session_decision as decision_fuse_session_decision,
    compute_temporal_stability as decision_compute_temporal_stability,
    aggregate_track_decisions as decision_aggregate_track_decisions,
)
from config.runtime_config import load_runtime_config, save_runtime_config
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
        self.camera_window = None
        
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
        if self.camera_window is None or not getattr(self.camera_window, "win", None) or not self.camera_window.win.winfo_exists():
            self.camera_window = CameraWindow(self.root)

    def _on_stop(self):
        """Xử lý khi nhấn nút 'Kết thúc chương trình'."""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn kết thúc chương trình?"):
            self.root.destroy()


# ─── Cửa sổ Camera + Phân loại + PLC ─────────────────────────────────
class CameraWindow:
    """Cửa sổ chính: stream camera, thống kê phân loại, giao tiếp PLC S7-1200."""

    STATE_SAFE_STOP = "SAFE_STOP"
    STATE_DEGRADED = "DEGRADED"
    STATE_RUNNING = "RUNNING"
    STATE_FAULT = "FAULT"

    CAM_SPECIAL_SOURCES = [
        "Astra Pro SDK (RGB)",
        "Luồng RTSP / IP Camera",
        "📂 Mở File Ảnh (.jpg, .png)",
        "🎞️ Mở File Video (.mp4, .avi)",
    ]

    GRADE_CFG = {
        "Grade-1":   {"label": "PREMIUM SELECT (Grade-1)",   "color": "#16A34A", "count_fg": "#14532D", "bg": "#F0FDF4", "icon": "🍏", "desc": "TC1 (≥80%) & TC2 (≥80mm)"},
        "Grade-2": {"label": "STANDARD GRADE (Grade-2)", "color": "#0284C7", "count_fg": "#0C4A6E", "bg": "#F0F9FF", "icon": "🔹", "desc": "TC1 (70-79%) hoặc TC2 (60-79mm)"},
        "Grade-3":    {"label": "PROCESSING (Grade-3)",    "color": "#4B5563", "count_fg": "#1F2937", "bg": "#F3F4F6", "icon": "🗑️", "desc": "TC1 (<70%) hoặc TC2 (<60mm)"},
    }

    # Địa chỉ Merker PLC S7-1200 (1214C)
    # MW10=Grade-1, MW12=Grade-2, MW14=Grade-3  |  M0.0=Start, M0.1=Stop
    PLC_MW_GRADE1   = 10
    PLC_MW_GRADE2 = 12
    PLC_MW_GRADE3    = 14
    PLC_START_BYTE, PLC_START_BIT = 0, 0
    PLC_STOP_BYTE,  PLC_STOP_BIT  = 0, 1

    # Bảng màu tối giản cho header + nút điều khiển nhanh
    HEADER_BG = "#E2E8F0"
    HEADER_BG_HOVER = "#CBD5E1"
    HEADER_TEXT = "#1F2937"
    HEADER_SUBTEXT = "#334155"

    BTN_PRIMARY = "#3B82F6"
    BTN_PRIMARY_ACTIVE = "#2563EB"
    BTN_SUCCESS = "#10B981"
    BTN_SUCCESS_ACTIVE = "#059669"
    BTN_DANGER = "#EF4444"
    BTN_DANGER_ACTIVE = "#DC2626"
    BTN_WARNING = "#F59E0B"
    BTN_WARNING_ACTIVE = "#D97706"
    BTN_NEUTRAL = "#64748B"
    BTN_NEUTRAL_ACTIVE = "#475569"

    def __init__(self, parent):
        self.parent = parent
        self.db = AppDatabase(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.runtime_cfg = load_runtime_config().get("runtime", {})

        # ── Camera (hoàn toàn độc lập với PLC) ──
        self.camera = CameraManager(
            on_frame_callback=self._on_frame_received,
            on_error_callback=self._camera_error_callback,
            on_log_callback=self._camera_log_callback
        )
        self.cam_source_values = list(self.CAM_SPECIAL_SOURCES)
        self._cam_mode_to_index = {}
        self.camera.require_depth_for_astra = bool(self.runtime_cfg.get("require_depth_for_astra", False))
        self.last_buffer_time = 0

        # ── PLC (chỉ khởi tạo khi bấm Kết nối) ──
        self.plc = PLCManager()
        self._plc_poll_id   = None
        self._plc_connecting = False
        self._count_vars    = {}
        self._percent_vars  = {}
        self._throughput_vars = {}
        self.capture_frames_required = int(self.runtime_cfg.get("capture_frames_required", 10))
        self.capture_wait_timeout_s = float(self.runtime_cfg.get("capture_wait_timeout_s", 10.0))
        self.decision_min_quality_score = float(self.runtime_cfg.get("decision_min_quality_score", 0.50))
        self.decision_margin_delta = float(self.runtime_cfg.get("decision_margin_delta", 0.10))
        self.decision_min_valid_frames = int(self.runtime_cfg.get("decision_min_valid_frames", 6))
        self.single_fruit_station_mode = bool(self.runtime_cfg.get("single_fruit_station_mode", True))
        self.track_min_frames = int(self.runtime_cfg.get("track_min_frames", 3))
        self.track_stability_min = float(self.runtime_cfg.get("track_stability_min", 0.60))
        self._plc_poll_ms = int(self.runtime_cfg.get("plc_poll_ms", 200))
        self._plc_fault_threshold = int(self.runtime_cfg.get("plc_fault_threshold", 3))
        self._vision_fault_threshold = int(self.runtime_cfg.get("vision_fault_threshold", 3))
        self._capture_session_active = False
        self._capture_session_source = ""
        self._capture_session_start_ts = 0.0
        self._capture_sample_records = []
        self._video_decision_buffer = []
        self._session_track_results = {}
        self._last_10_capture_records = []
        self._plc_sensor_prev = False
        self._last_counter_poll_ts = 0.0
        self._plc_fault_count = 0
        self._vision_fault_count = 0
        self.system_state = self.STATE_SAFE_STOP
        self.system_state_reason = "init"

        # ── Bộ lọc ổn định detection (debounce chống nhiễu nhất thời) ────────────────
        # Chỉ công nhận là táo thật khi detect xuất hiện liên tiếp >= DETECT_DEBOUNCE_MIN_FRAMES frame.
        # Nếu chỉ bắt vài frame rồi mất (ngón tay, vật nhất thời) → bỏ qua, không ghi phiên.
        self.DETECT_DEBOUNCE_MIN_FRAMES = int(self.runtime_cfg.get("detect_debounce_min_frames", 4))
        # Số frame không có táo liên tiếp trước khi reset trạng thái xác nhận
        self.DETECT_DEBOUNCE_RESET_FRAMES = int(self.runtime_cfg.get("detect_debounce_reset_frames", 3))
        self._detect_consecutive_count = 0    # Số frame detect liên tiếp hiện tại
        self._no_detect_consecutive_count = 0 # Số frame không detect liên tiếp hiện tại
        self._detection_confirmed = False     # True khi đã qua ngưỡng debounce


        # ── Anti-freeze (chống treo UI Not Responding) ──
        self._ui_frame_update_pending = False
        self._ui_latest_payload = None
        self._ui_min_update_interval_ms = 33  # ~30 FPS cho UI để tránh nghẽn main thread
        self._last_ui_apply_ms = 0.0
        self._last_heartbeat_ts = 0.0
        self._watchdog_warned = False
        self._last_camera_popup_ts = 0.0
        self._camera_popup_cooldown_s = 3.0
        self._last_vision_error_log_ts = 0.0

        # ── Quản lý Trang & Menu ──
        self.sidebar_visible = False
        self.current_page = "PHANLOAI" 
        self._grade_desc_labels = {} 
        
        # ── Biến cấu hình hệ thống (Có thể chỉnh sửa từ UI) ──
        self.cfg_smooth_frames = tk.StringVar(value=str(self.runtime_cfg.get("smooth_frames", 10)))
        self.cfg_analysis_ms = tk.StringVar(value=str(self.runtime_cfg.get("analysis_interval_ms", 100)))
        saved_lot = self.runtime_cfg.get("lot", "")
        self.current_orchard_var = tk.StringVar(value=self.runtime_cfg.get("orchard", "NHA_VUON_A"))
        self.current_lot_var = tk.StringVar(value=saved_lot if saved_lot else datetime.now().strftime("LO_%Y%m%d_%H%M"))
        self._last_analysis_time = 0

        self.win = tk.Toplevel(parent)
        self.win.title("Hệ thống phân loại hạng chất lượng táo")
        self.win.configure(bg="#F1F5F9")
        self.win.resizable(True, True)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        W, H = 1160, 760
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        self.win.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.win.minsize(900, 600)

        self.analyzer = FruitAnalyzer()
        # Nạp tham số ngưỡng bảng luật (nếu đã lưu trước đó)
        analyzer_cfg = self.runtime_cfg.get("analyzer", {})
        if "ripeness" in analyzer_cfg:
            self.analyzer.RIPENESS_GOOD_THRESH = analyzer_cfg["ripeness"].get("good_thresh", self.analyzer.RIPENESS_GOOD_THRESH)
            self.analyzer.RIPENESS_MEDIUM_THRESH = analyzer_cfg["ripeness"].get("medium_thresh", self.analyzer.RIPENESS_MEDIUM_THRESH)
        if "size" in analyzer_cfg:
            self.analyzer.SIZE_THRESHOLDS["large"] = analyzer_cfg["size"].get("large_mm", self.analyzer.SIZE_THRESHOLDS["large"])
            self.analyzer.SIZE_THRESHOLDS["medium"] = analyzer_cfg["size"].get("medium_mm", self.analyzer.SIZE_THRESHOLDS["medium"])
        if "shape" in analyzer_cfg:
            self.analyzer.SHAPE_GOOD_THRESH = analyzer_cfg["shape"].get("good_thresh", self.analyzer.SHAPE_GOOD_THRESH)
            self.analyzer.SHAPE_MEDIUM_THRESH = analyzer_cfg["shape"].get("medium_thresh", self.analyzer.SHAPE_MEDIUM_THRESH)

        self.current_grade = "UNKNOWN"
        self._refresh_stats_ui()
        self._build_ui()
        self._reset_tracking_monitor()
        self._log_event("Hệ thống Vision đã khởi động.", "INFO")
        if self.camera.require_depth_for_astra:
            self._log_event("⚙️ Astra mode: STRICT (yêu cầu depth, thiếu depth sẽ không chạy camera)", "INFO")
        else:
            self._log_event("⚙️ Astra mode: FLEX (cho phép chạy RGB khi depth chưa sẵn sàng)", "INFO")
        self._auto_start_astra_priority()
        self._set_system_state(self.STATE_SAFE_STOP, "Chờ bật camera", level="INFO")
        self._start_ui_watchdog()

        # Ẩn thanh tiêu đề gốc của Windows nhưng giữ viền resize (qua Windows API)
        self.win.after(100, self._apply_borderless_style)

    def _camera_log_callback(self, msg):
        """Callback log từ luồng camera, chuyển về UI thread an toàn."""
        try:
            if hasattr(self, "win") and self.win.winfo_exists():
                self.win.after(0, lambda m=str(msg): self._log_event(m, "INFO"))
            else:
                self.parent.after(0, lambda m=str(msg): self._log_event(m, "INFO"))
        except Exception:
            pass

    def _start_ui_watchdog(self):
        """Khởi động watchdog theo dõi vòng đời UI để cảnh báo nguy cơ treo app."""
        import time as _time

        self._last_heartbeat_ts = _time.time()

        def _heartbeat():
            try:
                if hasattr(self, "win") and self.win.winfo_exists():
                    self._last_heartbeat_ts = _time.time()
                    self.win.after(250, _heartbeat)
            except Exception:
                pass

        def _watcher_thread():
            while True:
                try:
                    if not hasattr(self, "win") or not self.win.winfo_exists():
                        break
                    delta = _time.time() - float(self._last_heartbeat_ts or 0.0)
                    if delta > 2.0 and not self._watchdog_warned:
                        self._watchdog_warned = True
                        self._log_event(
                            f"⚠️ UI phản hồi chậm ({delta:.1f}s). Đang tự giảm tải cập nhật giao diện.",
                            "WARNING",
                        )
                    elif delta <= 1.0 and self._watchdog_warned:
                        self._watchdog_warned = False
                        self._log_event("🟢 UI đã phục hồi phản hồi bình thường.", "SUCCESS")
                except Exception:
                    pass
                _time.sleep(0.5)

        self.win.after(250, _heartbeat)
        threading.Thread(target=_watcher_thread, daemon=True).start()

    def _schedule_ui_frame_apply(self, payload):
        """Gộp (coalesce) frame update để tránh backlog làm treo Tk main thread."""
        self._ui_latest_payload = payload
        if self._ui_frame_update_pending:
            return
        self._ui_frame_update_pending = True
        try:
            if hasattr(self, "win") and self.win.winfo_exists():
                self.win.after(0, self._drain_ui_frame_apply)
        except Exception:
            self._ui_frame_update_pending = False

    def _drain_ui_frame_apply(self):
        """Xử lý frame mới nhất theo nhịp giới hạn để không nghẽn giao diện."""
        import time as _time

        if not hasattr(self, "win") or not self.win.winfo_exists():
            self._ui_frame_update_pending = False
            self._ui_latest_payload = None
            return

        now_ms = _time.time() * 1000.0
        elapsed = now_ms - float(self._last_ui_apply_ms or 0.0)
        wait_ms = max(0, int(self._ui_min_update_interval_ms - elapsed))
        if wait_ms > 0:
            self.win.after(wait_ms, self._drain_ui_frame_apply)
            return

        payload = self._ui_latest_payload
        self._ui_latest_payload = None
        if payload is not None:
            try:
                self._apply_frame_result(*payload)
            finally:
                self._last_ui_apply_ms = _time.time() * 1000.0

        self._ui_frame_update_pending = False
        if self._ui_latest_payload is not None:
            # Nếu trong lúc xử lý có frame mới tới, lên lịch chạy tiếp ngay.
            self._ui_frame_update_pending = True
            self.win.after(0, self._drain_ui_frame_apply)

    def _camera_error_callback(self, msg):
        """Callback lỗi từ luồng camera, hiển thị popup trên UI thread để tránh crash Tkinter."""
        def _show():
            now_ts = time.time()
            show_popup = (now_ts - float(self._last_camera_popup_ts or 0.0)) >= float(self._camera_popup_cooldown_s)
            if show_popup:
                self._last_camera_popup_ts = now_ts
            try:
                if show_popup:
                    messagebox.showerror("Lỗi Camera", str(msg), parent=self.win if hasattr(self, "win") and self.win.winfo_exists() else None)
            except Exception:
                pass
            self._log_event(str(msg), "ERROR")

        try:
            if hasattr(self, "win") and self.win.winfo_exists():
                self.win.after(0, _show)
            else:
                self.parent.after(0, _show)
        except Exception:
            pass

    def _apply_borderless_style(self):
        """Ẩn thanh tiêu đề gốc của Windows nhưng GIỮ NGUYÊN viền resize.
        Sử dụng Windows API (ctypes) thay vì overrideredirect(True).
        Kết quả: cửa sổ có thể kéo thay đổi kích thước từ mọi cạnh như phần mềm thương mại."""
        try:
            import ctypes
            GWL_STYLE = -16
            # Các style flag của Windows
            WS_CAPTION = 0x00C00000    # Thanh tiêu đề
            WS_THICKFRAME = 0x00040000 # Viền resize
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            WS_SYSMENU = 0x00080000

            hwnd = ctypes.windll.user32.GetParent(self.win.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)

            # Xóa thanh tiêu đề gốc, giữ viền resize + nút taskbar
            style = (style & ~WS_CAPTION) | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Buộc Windows vẽ lại khung cửa sổ với style mới
            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
            )
        except Exception as e:
            print(f"[WARN] Windows API borderless failed: {e}")
            # Fallback: dùng overrideredirect nếu API thất bại
            self.win.overrideredirect(True)

    def _refresh_stats_ui(self):
        """Cập nhật các ô số Grade-1/Grade-2/Grade-3 và Yield Rate từ CSDL."""
        if threading.current_thread() is not threading.main_thread():
            try:
                if hasattr(self, 'win') and self.win.winfo_exists():
                    self.win.after(0, self._refresh_stats_ui)
                elif hasattr(self, 'parent') and self.parent.winfo_exists():
                    self.parent.after(0, self._refresh_stats_ui)
            except Exception:
                pass
            return

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
            return None

        if not grade or grade == "MANUAL":
            grade = self.current_grade if hasattr(self, 'current_grade') else "UNKNOWN"
            
        # Lấy đường kính hiện tại (nếu có)
        diameter = getattr(self, "current_diameter", 0)
            
        orchard_name = (self.current_orchard_var.get() if hasattr(self, "current_orchard_var") else "").strip()
        lot_code = (self.current_lot_var.get() if hasattr(self, "current_lot_var") else "").strip()
        success, msg, filepath, history_id = self.db.save_record(
            grade,
            self.frame_to_save,
            diameter_mm=diameter,
            orchard_name=orchard_name,
            lot_code=lot_code,
        )
        if success:
            self._log_event(msg, "SUCCESS")
            self._refresh_stats_ui()
            
            # Cập nhật khung hình 10 ảnh
            if hasattr(self, 'win'):
                self.win.after(0, self._update_snapshot_gallery, filepath, None)
                
            current_page = str(getattr(self, "current_page", "")).upper()
            # Nếu đang ở trang Lịch sử thì cập nhật bảng
            if current_page == "HISTORY":
                self._refresh_history_table()

            return history_id
        return None

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
        """Cố định chế độ hiển thị: khung 1 Color, khung 2 Binary."""
        self.lbl_view1.config(text="📷  CAMERA (COLOR)")
        self.lbl_view2.config(text="🔳  BINARY/THRESHOLD")

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
        if threading.current_thread() is not threading.main_thread():
            try:
                if hasattr(self, 'win') and self.win.winfo_exists():
                    self.win.after(0, lambda m=str(msg), l=level: self._log_event(m, l))
                else:
                    self.parent.after(0, lambda m=str(msg), l=level: self._log_event(m, l))
            except Exception:
                pass
            return

        if not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
            return
        if getattr(self, "_log_paused", False):
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
        except Exception as e:
            try:
                print(f"[LOG] _log_event failed: {e}")
            except Exception:
                pass

    def _build_ui(self):
        # 1. Thanh tiêu đề (Header) với nút Menu
        self.hdr = tk.Frame(self.win, bg=self.HEADER_BG, height=50)
        self.hdr.pack(fill="x", side="top")
        self.hdr.pack_propagate(False)

        # Nút 3 gạch (☰)
        self.btn_menu = tk.Button(self.hdr, text="☰", font=("Arial", 18, "bold"),
                      fg=self.HEADER_TEXT, bg=self.HEADER_BG, activebackground=self.HEADER_BG_HOVER,
                      activeforeground=self.HEADER_TEXT, bd=0, cursor="hand2",
                                  padx=15, command=self._toggle_sidebar)
        self.btn_menu.pack(side="left")

        self.title_lbl = tk.Label(self.hdr, text="🍊 OSPREYX - INDUSTRIAL APPLE SORTING SYSTEM",
                      font=("Arial", 12, "bold"), fg=self.HEADER_TEXT, bg=self.HEADER_BG)
        self.title_lbl.pack(side="left", padx=10)

        # OspreyX-style Global Status Badges
        status_frame = tk.Frame(self.hdr, bg=self.HEADER_BG)
        status_frame.pack(side="left", padx=20)

        self.led_lbl = tk.Label(status_frame, text="🟢 System Online", font=("Arial", 9, "bold"), fg="#059669", bg=self.HEADER_BG)
        # Ẩn badge trạng thái tổng theo yêu cầu giao diện mới.
        # Vẫn giữ widget để không ảnh hưởng logic cũ nếu có tham chiếu.

        # Nút điều khiển cửa sổ (bên phải header)
        window_controls = tk.Frame(self.hdr, bg=self.HEADER_BG)
        window_controls.pack(side="right", padx=10)

        self.btn_minimize = tk.Button(window_controls, text="—", font=("Arial", 10, "bold"),
                          fg=self.HEADER_SUBTEXT, bg=self.HEADER_BG, activebackground=self.HEADER_BG_HOVER,
                          activeforeground=self.HEADER_TEXT, bd=0, cursor="hand2", width=4,
                                      command=self._minimize_window)
        self.btn_minimize.pack(side="left")

        self.btn_restore = tk.Button(window_controls, text="▢", font=("Arial", 12, "bold"),
                         fg=self.HEADER_SUBTEXT, bg=self.HEADER_BG, activebackground=self.HEADER_BG_HOVER,
                         activeforeground=self.HEADER_TEXT, bd=0, cursor="hand2", width=4,
                                     command=self._restore_window)
        self.btn_restore.pack(side="left")

        self.btn_close = tk.Button(window_controls, text="✕", font=("Arial", 12, "bold"),
                       fg=self.HEADER_SUBTEXT, bg=self.HEADER_BG, activebackground=self.BTN_DANGER,
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
        self.page_db10_test = tk.Frame(self.main_container, bg="#F1F5F9")

        self._build_phanloai_page()
        self._build_setting_page()
        self._build_history_page()
        self._build_db10_test_page()

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
        self.win.state('iconic')

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
            ("📂  LỊCH SỬ SQL", "HISTORY"),
            ("🧪  TEST PLC", "DB10TEST"),
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
        if hasattr(self, 'page_db10_test'): self.page_db10_test.pack_forget()

        if page_id == "PHANLOAI":
            self.page_phanloai.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🍎 HỆ THỐNG PHÂN LOẠI TÁO - GIÁM SÁT")
        elif page_id == "HISTORY":
            if hasattr(self, 'page_history'):
                self.page_history.pack(fill="both", expand=True, padx=10, pady=10)
                self._refresh_history_table() # Tải lại dữ liệu mỗi khi mở trang
            self.title_lbl.config(text="📂 LỊCH SỬ PHÂN LOẠI SQL")
        elif page_id == "DB10TEST":
            if hasattr(self, 'page_db10_test'):
                self.page_db10_test.pack(fill="both", expand=True, padx=10, pady=10)
            self.title_lbl.config(text="🧪 TEST PLC - GỬI LỆNH UI QUA PLC")
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

        # Bộ lọc theo loại và theo thùng (10 quả/thùng)
        filter_bar = tk.Frame(container, bg="#FFFFFF")
        filter_bar.pack(fill="x", padx=15, pady=(0, 6))

        tk.Label(filter_bar, text="Xem theo loại:", font=("Arial", 9, "bold"), fg="#334155", bg="#FFFFFF").pack(side="left")
        self.history_grade_filter_var = tk.StringVar(value="TẤT CẢ")
        self.history_grade_filter_cb = ttk.Combobox(
            filter_bar,
            textvariable=self.history_grade_filter_var,
            values=["TẤT CẢ", "Grade-1", "Grade-2", "Grade-3"],
            state="readonly",
            width=12,
        )
        self.history_grade_filter_cb.pack(side="left", padx=(8, 16))
        self.history_grade_filter_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_history_table())

        tk.Label(filter_bar, text="Xem theo thùng:", font=("Arial", 9, "bold"), fg="#334155", bg="#FFFFFF").pack(side="left")
        self.history_bin_filter_var = tk.StringVar(value="Tất cả thùng")
        self.history_bin_filter_cb = ttk.Combobox(
            filter_bar,
            textvariable=self.history_bin_filter_var,
            values=["Tất cả thùng"],
            state="readonly",
            width=18,
        )
        self.history_bin_filter_cb.pack(side="left", padx=(8, 16))
        self.history_bin_filter_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_history_table())

        self.history_filter_summary_var = tk.StringVar(value="")
        tk.Label(
            filter_bar,
            textvariable=self.history_filter_summary_var,
            font=("Consolas", 9, "bold"),
            fg="#0F766E",
            bg="#FFFFFF",
        ).pack(side="right")

        # Bảng dữ liệu có thanh cuộn
        tree_frame = tk.Frame(container, bg="#FFFFFF")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)

        cols = ("ID", "Thùng", "Vị trí", "Thời gian", "Nhà vườn", "Mã lô", "Kết quả", "Tỷ lệ", "Đường dẫn ảnh")
        self.history_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=15)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.history_tree.pack(side="left", fill="both", expand=True)
        
        # Cấu hình cột
        self.history_tree.heading("ID", text="ID")
        self.history_tree.column("ID", width=50, anchor="center")
        self.history_tree.heading("Thùng", text="Thùng")
        self.history_tree.column("Thùng", width=80, anchor="center")
        self.history_tree.heading("Vị trí", text="Vị trí")
        self.history_tree.column("Vị trí", width=60, anchor="center")
        self.history_tree.heading("Thời gian", text="Thời gian")
        self.history_tree.column("Thời gian", width=145, anchor="center")
        self.history_tree.heading("Nhà vườn", text="Nhà vườn")
        self.history_tree.column("Nhà vườn", width=120, anchor="center")
        self.history_tree.heading("Mã lô", text="Mã lô")
        self.history_tree.column("Mã lô", width=120, anchor="center")
        self.history_tree.heading("Kết quả", text="Kết quả")
        self.history_tree.column("Kết quả", width=90, anchor="center")
        self.history_tree.heading("Tỷ lệ", text="Tỷ lệ Yield")
        self.history_tree.column("Tỷ lệ", width=90, anchor="center")
        self.history_tree.heading("Đường dẫn ảnh", text="Đường dẫn file ảnh")
        self.history_tree.column("Đường dẫn ảnh", width=300, anchor="w")
        self.history_tree.tag_configure("latest", background="#FFF7CC", foreground="#1E3A8A")
        self.history_tree.bind("<Double-1>", self._on_history_row_double_click)
        
        # Nút điều khiển
        btn_frame = tk.Frame(container, bg="#FFFFFF")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="🔄 LÀM MỚI", font=("Arial", 10, "bold"),
                  bg="#0284C7", fg="white", width=15, pady=8, cursor="hand2",
                  command=self._refresh_history_table).pack(side="left", padx=10)

        tk.Button(btn_frame, text="📤 XUẤT DỮ LIỆU", font=("Arial", 10, "bold"),
              bg="#16A34A", fg="white", width=18, pady=8, cursor="hand2",
              command=self._export_sql_history).pack(side="left", padx=10)
                  
        tk.Button(btn_frame, text="🗑️ XÓA SẠCH DỮ LIỆU", font=("Arial", 10, "bold"),
                  bg="#EF4444", fg="white", width=20, pady=8, cursor="hand2",
                  command=self._clear_sql_history).pack(side="left", padx=10)

    def _refresh_history_table(self):
        """Tải lại dữ liệu từ CSDL vào bảng."""
        if not hasattr(self, 'history_tree'): return

        grade_code_map = {"Grade-1": "G1", "Grade-2": "G2", "Grade-3": "G3"}

        def _bin_code(grade, bin_no):
            gcode = grade_code_map.get(str(grade or "").strip(), "GX")
            if int(bin_no or 0) <= 0:
                return "-"
            return f"{gcode}-T{int(bin_no):03d}"
        
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
            
        try:
            with self.db._get_conn() as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT id, thoi_gian, nha_vuon, ma_lo, ket_qua, ty_le_yield, duong_dan_anh "
                    "FROM phan_loai_history ORDER BY id ASC"
                )
                raw_rows = c.fetchall()

            # Đánh số thùng riêng cho từng loại (10 quả/thùng)
            grade_counter = {"Grade-1": 0, "Grade-2": 0, "Grade-3": 0}
            enriched = []
            for row in raw_rows:
                rec_id, thoi_gian, nha_vuon, ma_lo, ket_qua, ty_le_yield, duong_dan_anh = row
                grade = str(ket_qua or "").strip()
                if grade in grade_counter:
                    grade_counter[grade] += 1
                    idx_g = grade_counter[grade]
                    bin_no = ((idx_g - 1) // 10) + 1
                    pos_no = ((idx_g - 1) % 10) + 1
                else:
                    bin_no = 0
                    pos_no = 0

                enriched.append({
                    "id": rec_id,
                    "thoi_gian": thoi_gian,
                    "nha_vuon": nha_vuon,
                    "ma_lo": ma_lo,
                    "ket_qua": ket_qua,
                    "ty_le_yield": ty_le_yield,
                    "duong_dan_anh": duong_dan_anh,
                    "bin_no": bin_no,
                    "pos_no": pos_no,
                })

            # Lọc theo loại
            grade_sel = self.history_grade_filter_var.get() if hasattr(self, "history_grade_filter_var") else "TẤT CẢ"
            if grade_sel and grade_sel != "TẤT CẢ":
                filtered = [r for r in enriched if str(r.get("ket_qua", "")) == grade_sel]
            else:
                filtered = list(enriched)

            # Cập nhật danh sách thùng theo loại đang chọn
            if hasattr(self, "history_bin_filter_cb") and hasattr(self, "history_bin_filter_var"):
                bin_values = ["Tất cả thùng"]
                if grade_sel and grade_sel != "TẤT CẢ":
                    max_bin = max([int(r.get("bin_no", 0)) for r in filtered] + [0])
                    for b in range(1, max_bin + 1):
                        bin_values.append(_bin_code(grade_sel, b))

                self.history_bin_filter_cb["values"] = bin_values
                if self.history_bin_filter_var.get() not in bin_values:
                    self.history_bin_filter_var.set("Tất cả thùng")

            # Lọc theo thùng
            bin_sel = self.history_bin_filter_var.get() if hasattr(self, "history_bin_filter_var") else "Tất cả thùng"
            if bin_sel and bin_sel != "Tất cả thùng" and grade_sel != "TẤT CẢ":
                try:
                    if "-T" in str(bin_sel):
                        sel_bin_no = int(str(bin_sel).split("-T")[-1])
                    else:
                        sel_bin_no = int(str(bin_sel).split()[-1])
                    filtered = [r for r in filtered if int(r.get("bin_no", 0)) == sel_bin_no]
                except Exception:
                    pass

            # Hiển thị mới nhất trước
            rows = sorted(filtered, key=lambda r: int(r.get("id", 0)), reverse=True)

            for idx, rec in enumerate(rows):
                tags = ("latest",) if idx == 0 else ()
                self.history_tree.insert(
                    "",
                    "end",
                    values=(
                        rec.get("id"),
                        _bin_code(rec.get("ket_qua"), rec.get("bin_no", 0)),
                        (int(rec.get("pos_no", 0)) if int(rec.get("pos_no", 0)) > 0 else "-"),
                        rec.get("thoi_gian"),
                        rec.get("nha_vuon"),
                        rec.get("ma_lo"),
                        rec.get("ket_qua"),
                        rec.get("ty_le_yield"),
                        rec.get("duong_dan_anh"),
                    ),
                    tags=tags,
                )

            # Tính tổng số thùng của loại đang chọn
            g1_bins = ((grade_counter.get("Grade-1", 0) - 1) // 10) + 1 if grade_counter.get("Grade-1", 0) > 0 else 0
            g2_bins = ((grade_counter.get("Grade-2", 0) - 1) // 10) + 1 if grade_counter.get("Grade-2", 0) > 0 else 0
            g3_bins = ((grade_counter.get("Grade-3", 0) - 1) // 10) + 1 if grade_counter.get("Grade-3", 0) > 0 else 0

            if grade_sel == "TẤT CẢ":
                total_bins = g1_bins + g2_bins + g3_bins
            elif grade_sel == "Grade-1":
                total_bins = g1_bins
            elif grade_sel == "Grade-2":
                total_bins = g2_bins
            elif grade_sel == "Grade-3":
                total_bins = g3_bins
            else:
                total_bins = 0

            if hasattr(self, "history_filter_summary_var"):
                self.history_filter_summary_var.set(
                    f"Tổng: {total_bins} thùng | Hiển thị: {len(rows)} bản ghi"
                )
        except Exception as e:
            self._log_event(f"Lỗi đọc DB: {e}", "ERROR")

    def _on_history_row_double_click(self, event=None):
        """Double-click một dòng lịch sử để xem chi tiết 10 ảnh của lần phân loại đó."""
        if not hasattr(self, "history_tree"):
            return
        sel = self.history_tree.selection()
        if not sel:
            return

        values = self.history_tree.item(sel[0], "values")
        if not values:
            return

        try:
            history_id = int(values[0])
        except Exception:
            return

        self._open_history_detail_window(history_id)

    def _open_history_detail_window(self, history_id):
        """Popup hiển thị chi tiết batch 10 ảnh của một bản ghi lịch sử."""
        records = self.db.get_session_10_by_history_id(history_id)

        top = tk.Toplevel(self.win)
        top.title(f"Chi tiết 10 ảnh - Record ID {history_id}")
        top.geometry("1180x700")
        top.minsize(1100, 650)
        top.configure(bg="#FFFFFF")

        tk.Label(
            top,
            text=f"CHI TIẾT 10 ẢNH THEO LẦN PHÂN LOẠI (ID={history_id})",
            font=("Arial", 12, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            pady=10,
        ).pack()

        toggle = tk.Frame(top, bg="#FFFFFF")
        toggle.pack(fill="x", padx=12)

        content = tk.Frame(top, bg="#FFFFFF")
        content.pack(fill="both", expand=True, padx=10, pady=8)

        table_view = tk.Frame(content, bg="#FFFFFF")
        grid_view = tk.Frame(content, bg="#FFFFFF")

        btn_table = tk.Button(toggle, text="📋 BẢNG CHI TIẾT", font=("Arial", 10, "bold"),
                              bg="#0284C7", fg="white", padx=12, pady=6, cursor="hand2")
        btn_table.pack(side="left", padx=(0, 8))
        btn_grid = tk.Button(toggle, text="🖼️ 10 ẢNH", font=("Arial", 10, "bold"),
                             bg="#E2E8F0", fg="#334155", padx=12, pady=6, cursor="hand2")
        btn_grid.pack(side="left")

        # Chế độ hiển thị ảnh (Overlay, Raw, Binary, Gray) cho 10 ảnh
        view_mode_var = tk.StringVar(value="OVERLAY")
        mode_frame = tk.Frame(toggle, bg="#FFFFFF")
        
        tk.Label(mode_frame, text="Hiển thị ảnh:", font=("Arial", 9, "bold"), fg="#475569", bg="#FFFFFF").pack(side="left", padx=(15, 6))
        
        def on_mode_change(*args):
            _render_detail_gallery()
            
        view_mode_var.trace_add("write", on_mode_change)
        
        r1 = tk.Radiobutton(mode_frame, text="Ảnh vẽ khung (Overlay)", font=("Arial", 9), variable=view_mode_var, value="OVERLAY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r1.pack(side="left", padx=4)
        r2 = tk.Radiobutton(mode_frame, text="Ảnh gốc (Không khung)", font=("Arial", 9), variable=view_mode_var, value="RAW", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r2.pack(side="left", padx=4)
        r3 = tk.Radiobutton(mode_frame, text="Ảnh nhị phân (Binary)", font=("Arial", 9), variable=view_mode_var, value="BINARY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r3.pack(side="left", padx=4)
        r4 = tk.Radiobutton(mode_frame, text="Ảnh xám (Gray)", font=("Arial", 9), variable=view_mode_var, value="GRAY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r4.pack(side="left", padx=4)

        sort_hint_var = tk.StringVar(value="Nhấn tiêu đề % Đỏ / Đường kính / Độ tròn / YOLO để sắp xếp")

        cols = ("Frame", "Thời gian", "Trigger", "Hạng", "% Đỏ", "Đường kính", "Độ tròn", "YOLO", "Z (mm)")
        sort_bar = tk.Frame(table_view, bg="#FFFFFF")
        sort_bar.pack(fill="x", padx=8, pady=(8, 0))

        tk.Label(
            sort_bar,
            textvariable=sort_hint_var,
            font=("Arial", 9, "bold"),
            fg="#334155",
            bg="#FFFFFF",
        ).pack(side="left")

        tree_frame = tk.Frame(table_view, bg="#FFFFFF")
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=18)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        record_by_frame = {}

        def _to_float(val, default=0.0):
            try:
                return float(val)
            except Exception:
                return default

        def _roundness_score_value(rec, default=None):
            circ = rec.get("circularity", None)
            if circ is None:
                return default
            try:
                circ_f = float(circ)
            except Exception:
                return default

            # Chuẩn hóa về thang 0..1 (dữ liệu cũ có thể lưu 0..100)
            score = circ_f / 100.0 if circ_f > 1.0 else circ_f
            score = max(0.0, min(1.0, score))
            return score

        def _roundness_score_text(rec):
            score = _roundness_score_value(rec, default=None)
            if score is None:
                return rec.get("shape", "")
            return f"{score:.3f}"

        def _refresh_table(rows):
            tree.delete(*tree.get_children())
            record_by_frame.clear()

            for rec in rows:
                frame_idx = int(rec.get("frame_idx", 0) or 0)
                if frame_idx > 0:
                    record_by_frame[frame_idx] = rec

                tree.insert(
                    "", "end",
                    values=(
                        rec.get("frame_idx", ""),
                        rec.get("timestamp", ""),
                        rec.get("trigger_source", ""),
                        rec.get("grade", ""),
                        f"{_to_float(rec.get('ripeness_pct', 0.0)):.1f}",
                        f"{_to_float(rec.get('diameter_mm', 0.0)):.1f}",
                        _roundness_score_text(rec),
                        f"{_to_float(rec.get('yolo_conf', 0.0)):.3f}",
                        f"{_to_float(rec.get('z_distance_mm', 0.0)):.1f}" if rec.get("z_distance_mm") is not None else "N/A"
                    )
                )

        sort_state = {"% Đỏ": None, "Đường kính": None, "Độ tròn": None, "YOLO": None}

        def _set_heading_labels(active_col=None, ascending=True):
            for col in cols:
                text = col
                if col == active_col:
                    text = f"{col} {'↑' if ascending else '↓'}"

                if col in sort_state:
                    tree.heading(col, text=text, command=lambda c=col: _on_sort_heading_click(c))
                else:
                    tree.heading(col, text=text)

        def _sort_table(metric, ascending, col_name):
            if metric == "tc1":
                key_fn = lambda r: _to_float(r.get("ripeness_pct", 0.0))
                metric_name = "TC1 (% Đỏ)"
            elif metric == "tc2":
                key_fn = lambda r: _to_float(r.get("diameter_mm", 0.0))
                metric_name = "TC2 (Đường kính)"
            elif metric == "tc3":
                key_fn = lambda r: _roundness_score_value(r, default=-1.0)
                metric_name = "TC3 (Độ tròn)"
            else:
                key_fn = lambda r: _to_float(r.get("yolo_conf", 0.0))
                metric_name = "YOLO"

            sorted_rows = sorted(records, key=key_fn, reverse=(not ascending))
            _refresh_table(sorted_rows)
            _set_heading_labels(active_col=col_name, ascending=ascending)
            sort_hint_var.set(
                f"Sắp xếp: {metric_name} {'Tăng dần' if ascending else 'Giảm dần'}"
            )

        def _on_sort_heading_click(col_name):
            metric_map = {"% Đỏ": "tc1", "Đường kính": "tc2", "Độ tròn": "tc3", "YOLO": "yolo"}
            metric = metric_map.get(col_name)
            if metric is None:
                return

            prev = sort_state.get(col_name)
            ascending = True if prev is None else (not prev)

            for k in sort_state.keys():
                sort_state[k] = None
            sort_state[col_name] = ascending

            _sort_table(metric, ascending, col_name)

        _set_heading_labels()
        tree.column("Frame", width=70, anchor="center")
        tree.column("Thời gian", width=150, anchor="center")
        tree.column("Trigger", width=90, anchor="center")
        tree.column("Hạng", width=90, anchor="center")
        tree.column("% Đỏ", width=90, anchor="center")
        tree.column("Đường kính", width=90, anchor="center")
        tree.column("Độ tròn", width=100, anchor="center")
        tree.column("YOLO", width=90, anchor="center")
        tree.column("Z (mm)", width=90, anchor="center")
        tree.pack(side="left", fill="both", expand=True)

        _refresh_table(records)

        grid_wrap = tk.Frame(grid_view, bg="#FFFFFF")
        grid_wrap.pack(fill="both", expand=True, padx=8, pady=8)
        top._detail_resize_job = None
        top._detail_gallery_items = []
        top._detail_imgs = []

        for i in range(10):
            r = i // 5
            c = i % 5
            cell = tk.LabelFrame(grid_wrap, text=f"Frame {i+1}", font=("Arial", 8, "bold"),
                                 fg="#334155", bg="#FFFFFF", bd=1, relief="ridge", padx=4, pady=4)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            cell.grid_columnconfigure(0, weight=1)
            cell.grid_rowconfigure(0, weight=1)

            # Ảnh sẽ tự fit tối đa theo kích thước ô.
            img_box = tk.Frame(cell, bg="#0F172A")
            img_box.pack(fill="both", expand=True, pady=(2, 2))
            img_box.pack_propagate(False)

            img_lbl = tk.Label(img_box, text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
            img_lbl.pack(fill="both", expand=True)
            meta_lbl = tk.Label(cell, text="-", font=("Consolas", 8), fg="#475569", bg="#FFFFFF")
            meta_lbl.pack(pady=(4, 0))

            pil_img = None

            if i < len(records):
                rec = records[i]
                img_path = rec.get("image_path", "")
                if img_path and os.path.isfile(img_path):
                    try:
                        pil_img = Image.open(img_path).convert("RGB")
                    except Exception:
                        img_lbl.config(image="", text="NO IMAGE")

                circ_txt = "-"
                circ_val = rec.get("circularity", None)
                if circ_val is not None:
                    try:
                        circ_f = float(circ_val)
                        circ_f = circ_f / 100.0 if circ_f > 1.0 else circ_f
                        circ_f = max(0.0, min(1.0, circ_f))
                        circ_txt = f"{circ_f:.3f}"
                    except Exception:
                        circ_txt = "-"

                meta_lbl.config(
                    text=(
                        f"{rec.get('grade', '-') } | "
                        f"{float(rec.get('ripeness_pct', 0.0)):.1f}% | "
                        f"{float(rec.get('diameter_mm', 0.0)):.1f} mm | "
                        f"{circ_txt}"
                    )
                )

                # Double-click từng frame để mở popup thông số chi tiết
                cell.configure(cursor="hand2")
                img_lbl.configure(cursor="hand2")
                meta_lbl.configure(cursor="hand2")
                cell.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=view_mode_var.get()))
                img_lbl.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=view_mode_var.get()))
                meta_lbl.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=view_mode_var.get()))

            top._detail_gallery_items.append({
                "cell": cell,
                "meta_lbl": meta_lbl,
                "frame_idx": (int(rec.get("frame_idx", 0) or 0) if i < len(records) else i + 1),
                "img_box": img_box,
                "img_lbl": img_lbl,
                "pil": pil_img,
                "rec": rec if i < len(records) else None,
            })

        for c in range(5):
            grid_wrap.grid_columnconfigure(c, weight=1)
        for r in range(2):
            grid_wrap.grid_rowconfigure(r, weight=1)

        grid_wrap.bind("<Configure>", lambda _e: self._refresh_sheet10_gallery(getattr(self, "_last_10_capture_records", [])))

        def _render_detail_gallery():
            top._detail_imgs = []
            mode = view_mode_var.get()
            for item in top._detail_gallery_items:
                img_box = item["img_box"]
                img_lbl = item["img_lbl"]
                rec = item.get("rec")
                
                pil = None
                if rec is not None:
                    img_path = rec.get("image_path", "")
                    if img_path and os.path.isfile(img_path):
                        base_no_ext, ext = os.path.splitext(img_path)
                        target_path = img_path
                        
                        if mode == "RAW":
                            raw_path = f"{base_no_ext}_raw.jpg"
                            if os.path.isfile(raw_path):
                                target_path = raw_path
                        elif mode == "BINARY":
                            mask_path = f"{base_no_ext}_mask.png"
                            if os.path.isfile(mask_path):
                                target_path = mask_path
                        elif mode == "GRAY":
                            raw_path = f"{base_no_ext}_raw.jpg"
                            if os.path.isfile(raw_path):
                                target_path = raw_path
                                
                        try:
                            img_loaded = Image.open(target_path).convert("RGB")
                            if mode == "GRAY":
                                pil = img_loaded.convert("L").convert("RGB")
                            elif mode == "BINARY" and not os.path.isfile(f"{base_no_ext}_mask.png"):
                                gray_temp = img_loaded.convert("L")
                                pil = gray_temp.point(lambda p: 255 if p > 75 else 0).convert("RGB")
                            else:
                                pil = img_loaded
                        except Exception:
                            pil = item["pil"]
                    else:
                        pil = item["pil"]
                else:
                    pil = item["pil"]

                if pil is None:
                    img_lbl.config(image="", text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
                    img_lbl.image = None
                    continue

                box_w = max(int(img_box.winfo_width()) - 4, 80)
                box_h = max(int(img_box.winfo_height()) - 4, 60)

                resized = self._fit_frame_full_color(pil, box_w, box_h)
                photo = ImageTk.PhotoImage(resized)
                img_lbl.config(image=photo, text="")
                img_lbl.image = photo
                top._detail_imgs.append(photo)

        def _queue_render(_evt=None):
            if top._detail_resize_job is not None:
                top.after_cancel(top._detail_resize_job)
            top._detail_resize_job = top.after(90, _render_detail_gallery)

        def _highlight_detail_frame(frame_idx):
            for item in top._detail_gallery_items:
                cell = item.get("cell")
                if cell is None:
                    continue
                is_target = int(item.get("frame_idx", -1)) == int(frame_idx)
                if is_target:
                    cell.config(bd=2, relief="solid", fg="#0284C7")
                else:
                    cell.config(bd=1, relief="ridge", fg="#334155")

        def _on_table_row_double_click(_event=None):
            sel = tree.selection()
            if not sel:
                return

            values = tree.item(sel[0], "values")
            if not values:
                return

            try:
                frame_idx = int(values[0])
            except Exception:
                return

            rec = record_by_frame.get(frame_idx)
            if rec is None:
                return

            show("GRID")
            _highlight_detail_frame(frame_idx)
            self._open_single_frame_detail_window(rec, view_mode=view_mode_var.get())

        grid_wrap.bind("<Configure>", _queue_render)
        top.after(120, _render_detail_gallery)
        tree.bind("<Double-1>", _on_table_row_double_click)

        def show(mode):
            table_view.pack_forget()
            grid_view.pack_forget()
            if mode == "GRID":
                grid_view.pack(fill="both", expand=True)
                btn_grid.config(bg="#0284C7", fg="white")
                btn_table.config(bg="#E2E8F0", fg="#334155")
                mode_frame.pack(side="right", padx=(8, 0))
            else:
                table_view.pack(fill="both", expand=True)
                btn_table.config(bg="#0284C7", fg="white")
                btn_grid.config(bg="#E2E8F0", fg="#334155")
                mode_frame.pack_forget()

        btn_table.config(command=lambda: show("TABLE"))
        btn_grid.config(command=lambda: show("GRID"))

        show("TABLE")
        if not records:
            messagebox.showinfo("Thông báo", f"Record ID {history_id} chưa có dữ liệu 10 ảnh.")

    def _fit_frame_full_color(self, pil_img, target_w, target_h):
        """Cắt viền đen trên/dưới (nếu có) rồi resize đầy khung như canvas color chính."""
        if pil_img is None:
            return None

        try:
            img = pil_img.convert("RGB")
            gray = img.convert("L")
            w, h = gray.size
            px = gray.load()

            dark_threshold = 20
            dark_ratio_required = 0.88
            scan_limit = max(1, int(h * 0.28))
            sample_step = max(1, int(w / 320))

            def _row_dark_ratio(y):
                dark = 0
                total = 0
                for x in range(0, w, sample_step):
                    total += 1
                    if px[x, y] <= dark_threshold:
                        dark += 1
                return float(dark) / float(total or 1)

            top = 0
            for y in range(scan_limit):
                if _row_dark_ratio(y) >= dark_ratio_required:
                    top = y + 1
                else:
                    break

            bottom = h
            for y in range(h - 1, max(h - scan_limit - 1, -1), -1):
                if _row_dark_ratio(y) >= dark_ratio_required:
                    bottom = y
                else:
                    break

            # Chỉ cắt khi vùng còn lại vẫn đủ lớn để tránh cắt nhầm nội dung thật.
            if (top > 0 or bottom < h) and (bottom - top) >= int(h * 0.45):
                img = img.crop((0, top, w, bottom))

            # Giữ toàn bộ overlay (bbox, nhãn, contour) bằng cách KHÔNG crop ngang.
            # Cách này giống luồng chính: ép ảnh full khung chữ nhật.
            return img.resize((max(int(target_w), 1), max(int(target_h), 1)), Image.LANCZOS)
        except Exception:
            try:
                return pil_img.resize((max(int(target_w), 1), max(int(target_h), 1)), Image.LANCZOS)
            except Exception:
                return pil_img

    def _open_single_frame_detail_window(self, rec, view_mode="OVERLAY"):
        """Mở cửa sổ chi tiết thông số của một frame trong bộ 10 ảnh."""
        top = tk.Toplevel(self.win)
        frame_idx = rec.get("frame_idx", "-")
        top.title(f"Chi tiết Frame {frame_idx}")
        top.geometry("900x620")
        top.configure(bg="#FFFFFF")

        tk.Label(
            top,
            text=f"CHI TIẾT FRAME {frame_idx}",
            font=("Arial", 12, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            pady=10,
        ).pack()

        body = tk.Frame(top, bg="#FFFFFF")
        body.pack(fill="both", expand=True, padx=12, pady=8)

        img_panel = tk.LabelFrame(body, text="Ảnh frame", font=("Arial", 9, "bold"),
                                  fg="#334155", bg="#FFFFFF", bd=1, relief="ridge")
        img_panel.pack(side="left", fill="both", expand=True, padx=(0, 8))

        info_panel = tk.LabelFrame(body, text="Thông số", font=("Arial", 9, "bold"),
                                   fg="#334155", bg="#FFFFFF", bd=1, relief="ridge")
        info_panel.pack(side="left", fill="both", padx=(8, 0))

        # --- Thanh cuộn dọc cho info_panel ---
        info_canvas = tk.Canvas(info_panel, bg="#FFFFFF", highlightthickness=0, width=320)
        info_scrollbar = ttk.Scrollbar(info_panel, orient="vertical", command=info_canvas.yview)
        info_inner = tk.Frame(info_canvas, bg="#FFFFFF")

        info_inner.bind(
            "<Configure>",
            lambda e: info_canvas.configure(scrollregion=info_canvas.bbox("all"))
        )
        info_canvas.create_window((0, 0), window=info_inner, anchor="nw")
        info_canvas.configure(yscrollcommand=info_scrollbar.set)

        info_scrollbar.pack(side="right", fill="y")
        info_canvas.pack(side="left", fill="both", expand=True)

        # Hỗ trợ cuộn bằng con lăn chuột
        def _on_mousewheel(event):
            info_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(event):
            info_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _unbind_mousewheel(event):
            info_canvas.unbind_all("<MouseWheel>")

        info_canvas.bind("<Enter>", _bind_mousewheel)
        info_canvas.bind("<Leave>", _unbind_mousewheel)
        # --- Kết thúc thanh cuộn ---

        img_lbl = tk.Label(img_panel, text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
        img_lbl.pack(fill="both", expand=True, padx=8, pady=8)

        img_path = rec.get("image_path", "")
        _displayed = False
        img_loaded = None

        # 1. Thử lấy từ in-memory preview (cho live session)
        preview = None
        if view_mode == "OVERLAY":
            preview = rec.get("preview_frame_annotated") or rec.get("preview_frame")
        elif view_mode == "RAW":
            preview = rec.get("preview_frame_raw")
        elif view_mode == "BINARY":
            preview = rec.get("preview_frame_mask")
            if preview is None:
                preview_raw = rec.get("preview_frame_raw")
                if preview_raw is not None:
                    gray_temp = cv2.cvtColor(preview_raw, cv2.COLOR_BGR2GRAY)
                    _, preview = cv2.threshold(gray_temp, 75, 255, cv2.THRESH_BINARY)
        elif view_mode == "GRAY":
            preview_raw = rec.get("preview_frame_raw")
            if preview_raw is not None:
                preview = cv2.cvtColor(preview_raw, cv2.COLOR_BGR2GRAY)
            else:
                preview_annotated = rec.get("preview_frame_annotated") or rec.get("preview_frame")
                if preview_annotated is not None:
                    preview = cv2.cvtColor(preview_annotated, cv2.COLOR_BGR2GRAY)

        if preview is not None:
            try:
                if len(preview.shape) == 2:
                    rgb = cv2.cvtColor(preview, cv2.COLOR_GRAY2RGB)
                else:
                    rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                if rgb is not None:
                    img_loaded = Image.fromarray(rgb)
                    _displayed = True
            except Exception:
                pass

        # 2. Nếu không có preview hoặc lỗi, thử đọc từ file trên đĩa (cho history)
        if not _displayed and img_path and os.path.isfile(img_path):
            try:
                base_no_ext, ext = os.path.splitext(img_path)
                target_path = img_path
                
                if view_mode == "RAW":
                    raw_path = f"{base_no_ext}_raw.jpg"
                    if os.path.isfile(raw_path):
                        target_path = raw_path
                elif view_mode == "BINARY":
                    mask_path = f"{base_no_ext}_mask.png"
                    if os.path.isfile(mask_path):
                        target_path = mask_path
                elif view_mode == "GRAY":
                    raw_path = f"{base_no_ext}_raw.jpg"
                    if os.path.isfile(raw_path):
                        target_path = raw_path

                img_loaded = Image.open(target_path).convert("RGB")
                if view_mode == "GRAY":
                    img_loaded = img_loaded.convert("L").convert("RGB")
                elif view_mode == "BINARY" and not os.path.isfile(f"{base_no_ext}_mask.png"):
                    gray_temp = img_loaded.convert("L")
                    img_loaded = gray_temp.point(lambda p: 255 if p > 75 else 0).convert("RGB")
                
                _displayed = True
            except Exception:
                pass

        # Hiển thị ảnh nếu load thành công
        if _displayed and img_loaded is not None:
            try:
                img = self._fit_frame_full_color(img_loaded, 620, 380)
                photo = ImageTk.PhotoImage(img)
                img_lbl.config(image=photo, text="")
                img_lbl.image = photo
                top._single_detail_photo = photo
            except Exception:
                img_lbl.config(image="", text="NO IMAGE")
        else:
            img_lbl.config(image="", text="NO IMAGE")

        # Ưu tiên lấy độ phân giải từ frame preview (đúng thời điểm chụp),
        # fallback sang file ảnh đã lưu nếu không có preview.
        captured_resolution = "N/A"
        try:
            preview_frame = rec.get("preview_frame_annotated") or rec.get("preview_frame") or rec.get("preview_frame_raw")
            if preview_frame is not None and hasattr(preview_frame, "shape") and len(preview_frame.shape) >= 2:
                ph, pw = int(preview_frame.shape[0]), int(preview_frame.shape[1])
                if pw > 0 and ph > 0:
                    captured_resolution = f"{pw}x{ph} px"
            elif img_path and os.path.isfile(img_path):
                with Image.open(img_path) as src_img:
                    pw, ph = src_img.size
                if int(pw) > 0 and int(ph) > 0:
                    captured_resolution = f"{int(pw)}x{int(ph)} px"
        except Exception:
            captured_resolution = "N/A"

        def _fmt(value, digits=1, suffix=""):
            if value is None:
                return "N/A"
            try:
                return f"{float(value):.{digits}f}{suffix}"
            except Exception:
                return "N/A"

        def _num(key, fallback=None):
            if key in rec:
                return rec.get(key)
            return fallback

        def _raw_txt(key):
            if key in rec and str(rec.get(key, "")).strip() != "":
                return rec.get(key)
            return None

        def _txt(key, fallback="N/A"):
            val = _raw_txt(key)
            if val is not None:
                return val
            return fallback

        red_ratio_v = _num("red_ratio", rec.get("ripeness_pct"))
        diameter_mm_v = _num("diameter_mm")
        circularity_v = _num("circularity")
        ripeness_label_v = _raw_txt("ripeness_label")
        ripeness_grade_v = _raw_txt("ripeness_grade")
        size_label_v = _raw_txt("size_label")
        size_grade_v = _raw_txt("size_grade")
        shape_label_v = rec.get("shape", _raw_txt("shape_label"))
        shape_grade_v = _raw_txt("shape_grade")

        analyzer = getattr(self, "analyzer", None)
        if analyzer is not None:
            try:
                if (ripeness_label_v is None or ripeness_grade_v is None) and red_ratio_v is not None:
                    lbl, grd = analyzer._classify_ripeness(float(red_ratio_v))
                    if ripeness_label_v is None:
                        ripeness_label_v = lbl
                    if ripeness_grade_v is None:
                        ripeness_grade_v = grd
                if (size_label_v is None or size_grade_v is None) and diameter_mm_v is not None:
                    lbl, grd = analyzer._classify_size(float(diameter_mm_v))
                    if size_label_v is None:
                        size_label_v = lbl
                    if size_grade_v is None:
                        size_grade_v = grd
                if (shape_grade_v is None) and circularity_v is not None:
                    _, grd = analyzer._classify_shape(float(circularity_v))
                    shape_grade_v = grd
            except Exception:
                pass

        # Fallback cho record cũ chỉ có nhãn hình dạng mà chưa có shape_grade.
        if shape_grade_v is None and isinstance(shape_label_v, str):
            s = shape_label_v.upper()
            if "TRÒN" in s:
                shape_grade_v = "Grade-1"
            elif "MÉO" in s:
                shape_grade_v = "Grade-3"

        def _add_section(parent, title, rows):
            sec = tk.LabelFrame(parent, text=title, font=("Arial", 9, "bold"),
                                fg="#0F172A", bg="#FFFFFF", bd=1, relief="groove", padx=6, pady=4)
            sec.pack(fill="x", padx=6, pady=4)
            for i, (k, v) in enumerate(rows):
                tk.Label(sec, text=f"{k}:", font=("Arial", 9, "bold"),
                         fg="#1F2937", bg="#FFFFFF", anchor="w").grid(row=i, column=0, sticky="w", padx=4, pady=2)
                tk.Label(sec, text=str(v), font=("Consolas", 9),
                         fg="#334155", bg="#FFFFFF", anchor="w", justify="left", wraplength=260).grid(row=i, column=1, sticky="w", padx=6, pady=2)

        _add_section(info_inner, "Thông tin chung", [
            ("Frame", rec.get("frame_idx", "N/A")),
            ("Thời gian", rec.get("timestamp", "N/A")),
            ("Trigger", rec.get("trigger_source", "N/A")),
            ("Z (mm)", f"{float(rec.get('z_distance_mm')):.1f}" if rec.get('z_distance_mm') is not None else "N/A"),
            ("Kết quả cuối frame", rec.get("grade", "N/A")),
            ("Độ phân giải ảnh", captured_resolution),
            ("Đường dẫn ảnh", img_path if img_path else "N/A"),
        ])

        _add_section(info_inner, "TC1 - Màu sắc / Độ chín", [
            ("% Đỏ", _fmt(red_ratio_v, 1, "%")),
            ("% Vàng", _fmt(_num("yellow_ratio"), 1, "%")),
            ("% Xanh", _fmt(_num("green_ratio"), 1, "%")),
            ("Nhãn TC1", ripeness_label_v if ripeness_label_v is not None else "N/A"),
            ("Grade TC1", ripeness_grade_v if ripeness_grade_v is not None else "N/A"),
        ])

        _add_section(info_inner, "TC2 - Kích thước", [
            ("Đường kính", _fmt(diameter_mm_v, 1, " mm")),
            ("Nhãn TC2", size_label_v if size_label_v is not None else "N/A"),
            ("Grade TC2", size_grade_v if size_grade_v is not None else "N/A"),
        ])

        _add_section(info_inner, "TC3 - Hình dạng", [
            ("Nhãn TC3", shape_label_v if shape_label_v else "N/A"),
            ("Grade TC3", shape_grade_v if shape_grade_v is not None else "N/A"),
            ("Circularity", _fmt(circularity_v, 3, "")),
        ])

        _add_section(info_inner, "YOLO", [
            ("Class", rec.get("yolo_class", "apple")),
            ("Confidence", _fmt(_num("yolo_conf"), 3, "")),
            ("Track ID", _txt("track_id", "-")),
            ("Active tracks", _fmt(_num("active_tracks"), 0, "")),
            ("Tracker mode", _txt("yolo_tracker_mode", "predict")),
        ])

        _add_section(info_inner, "Tracking / Video-level", [
            ("Track final grade", _txt("track_final_grade", "-")),
            ("Track frames", _fmt(_num("track_frames"), 0, "")),
            ("Track temporal", _fmt(_num("track_temporal_stability"), 2, "")),
            ("Track confidence", _fmt(_num("track_confidence"), 2, "")),
            ("Session total tracks", _fmt(_num("session_total_tracks"), 0, "")),
            ("Session temporal", _fmt(_num("session_temporal_stability"), 2, "")),
            ("Decision method", _txt("decision_method", "weighted_voting")),
        ])

        _add_section(info_inner, "Hiệu năng / Chất lượng ảnh", [
            ("Thời gian xử lý", _fmt(_num("processing_time_ms"), 1, " ms")),
            ("FPS", _fmt(_num("fps"), 1, "")),
            ("Blur status", _txt("blur_status")),
            ("Blur score", _fmt(_num("blur_score"), 1, "")),
        ])

    def _on_sheet10_row_double_click(self, event=None):
        """Double-click một dòng trong bảng Sheet 10 để xem chi tiết frame đó."""
        if not hasattr(self, "sheet10_tree"):
            return
        sel = self.sheet10_tree.selection()
        if not sel:
            return
        values = self.sheet10_tree.item(sel[0], "values")
        if not values:
            return
        try:
            frame_idx = int(values[0])
        except Exception:
            return

        records = getattr(self, "_last_10_capture_records", [])
        rec = None
        for r in records:
            if int(r.get("frame_idx", 0) or 0) == frame_idx:
                rec = r
                break
        if rec is None:
            return

        self._show_sheet10_view("GRID")
        view_mode = self.sheet10_view_mode_var.get() if hasattr(self, "sheet10_view_mode_var") else "OVERLAY"
        self._open_single_frame_detail_window(rec, view_mode=view_mode)

    def _build_sheet_page(self):
        """Trang Sheet 10 ảnh táo: hỗ trợ 2 kiểu xem (Bảng / Lưới ảnh)."""
        container = tk.Frame(self.page_sheet10, bg="#FFFFFF", bd=1, relief="ridge")
        container.pack(fill="both", expand=True, padx=5, pady=5)

        tk.Label(
            container,
            text="📄 SHEET 10 ẢNH TÁO (PHIÊN GẦN NHẤT)",
            font=("Arial", 12, "bold"), fg="#0F172A", bg="#FFFFFF", pady=15
        ).pack()

        # Thanh chuyển đổi 2 kiểu xem
        toggle_bar = tk.Frame(container, bg="#FFFFFF")
        toggle_bar.pack(fill="x", padx=15, pady=(0, 6))

        self._sheet10_view_mode = "TABLE"
        self.btn_sheet10_table = tk.Button(
            toggle_bar, text="📋 XEM DẠNG BẢNG", font=("Arial", 10, "bold"),
            bg="#0284C7", fg="white", padx=12, pady=6, cursor="hand2",
            command=lambda: self._show_sheet10_view("TABLE")
        )
        self.btn_sheet10_table.pack(side="left", padx=(0, 8))

        self.btn_sheet10_grid = tk.Button(
            toggle_bar, text="🖼️ XEM DẠNG 10 ẢNH", font=("Arial", 10, "bold"),
            bg="#E2E8F0", fg="#334155", padx=12, pady=6, cursor="hand2",
            command=lambda: self._show_sheet10_view("GRID")
        )
        self.btn_sheet10_grid.pack(side="left")

        # Chế độ hiển thị ảnh (Overlay, Raw, Binary, Gray) cho Sheet 10
        self.sheet10_view_mode_var = tk.StringVar(value="OVERLAY")
        self.sheet10_mode_frame = tk.Frame(toggle_bar, bg="#FFFFFF")
        
        tk.Label(self.sheet10_mode_frame, text="Hiển thị ảnh:", font=("Arial", 9, "bold"), fg="#475569", bg="#FFFFFF").pack(side="left", padx=(15, 6))
        
        def on_sheet10_mode_change(*args):
            self._refresh_sheet10_gallery(getattr(self, "_last_10_capture_records", []))
            
        self.sheet10_view_mode_var.trace_add("write", on_sheet10_mode_change)
        
        r1 = tk.Radiobutton(self.sheet10_mode_frame, text="Ảnh vẽ khung (Overlay)", font=("Arial", 9), variable=self.sheet10_view_mode_var, value="OVERLAY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r1.pack(side="left", padx=4)
        r2 = tk.Radiobutton(self.sheet10_mode_frame, text="Ảnh gốc (Không khung)", font=("Arial", 9), variable=self.sheet10_view_mode_var, value="RAW", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r2.pack(side="left", padx=4)
        r3 = tk.Radiobutton(self.sheet10_mode_frame, text="Ảnh nhị phân (Binary)", font=("Arial", 9), variable=self.sheet10_view_mode_var, value="BINARY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r3.pack(side="left", padx=4)
        r4 = tk.Radiobutton(self.sheet10_mode_frame, text="Ảnh xám (Gray)", font=("Arial", 9), variable=self.sheet10_view_mode_var, value="GRAY", bg="#FFFFFF", activebackground="#FFFFFF", cursor="hand2")
        r4.pack(side="left", padx=4)

        self.sheet10_content = tk.Frame(container, bg="#FFFFFF")
        self.sheet10_content.pack(fill="both", expand=True)

        self.sheet10_table_view = tk.Frame(self.sheet10_content, bg="#FFFFFF")
        self.sheet10_grid_view = tk.Frame(self.sheet10_content, bg="#FFFFFF")

        cols = (
            "Frame", "Thời gian", "Nguồn Trigger", "Hạng",
            "% Đỏ", "Đường kính (mm)", "Hình dạng", "YOLO Conf", "Z (mm)"
        )
        tree_frame = tk.Frame(self.sheet10_table_view, bg="#FFFFFF")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        self.sheet10_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=14)

        self.sheet10_tree.heading("Frame", text="Frame")
        self.sheet10_tree.column("Frame", width=70, anchor="center")
        self.sheet10_tree.heading("Thời gian", text="Thời gian")
        self.sheet10_tree.column("Thời gian", width=150, anchor="center")
        self.sheet10_tree.heading("Nguồn Trigger", text="Nguồn Trigger")
        self.sheet10_tree.column("Nguồn Trigger", width=120, anchor="center")
        self.sheet10_tree.heading("Hạng", text="Hạng")
        self.sheet10_tree.column("Hạng", width=90, anchor="center")
        self.sheet10_tree.heading("% Đỏ", text="% Đỏ")
        self.sheet10_tree.column("% Đỏ", width=90, anchor="center")
        self.sheet10_tree.heading("Đường kính (mm)", text="Đường kính (mm)")
        self.sheet10_tree.column("Đường kính (mm)", width=90, anchor="center")
        self.sheet10_tree.heading("Hình dạng", text="Hình dạng")
        self.sheet10_tree.column("Hình dạng", width=140, anchor="center")
        self.sheet10_tree.heading("YOLO Conf", text="YOLO Conf")
        self.sheet10_tree.column("YOLO Conf", width=100, anchor="center")
        self.sheet10_tree.heading("Z (mm)", text="Z (mm)")
        self.sheet10_tree.column("Z (mm)", width=90, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sheet10_tree.yview)
        self.sheet10_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.sheet10_tree.pack(side="left", fill="both", expand=True)
        self.sheet10_tree.bind("<Double-1>", self._on_sheet10_row_double_click)

        # Khung lưới 10 ảnh (2 hàng x 5 cột)
        self.sheet10_gallery_cells = []
        self.sheet10_gallery_images = []
        grid_wrap = tk.Frame(self.sheet10_grid_view, bg="#FFFFFF")
        grid_wrap.pack(fill="both", expand=True, padx=12, pady=10)

        for i in range(10):
            r = i // 5
            c = i % 5
            cell = tk.LabelFrame(
                grid_wrap,
                text=f"Frame {i+1}",
                font=("Arial", 8, "bold"),
                fg="#334155",
                bg="#FFFFFF",
                bd=1,
                relief="ridge",
                padx=4,
                pady=4,
            )
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")
            cell.grid_columnconfigure(0, weight=1)
            cell.grid_rowconfigure(0, weight=1)

            img_box = tk.Frame(cell, bg="#0F172A")
            img_box.pack(fill="both", expand=True, pady=(2, 2))
            img_box.pack_propagate(False)

            img_lbl = tk.Label(img_box, text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
            img_lbl.pack(fill="both", expand=True)

            meta_lbl = tk.Label(cell, text="-", font=("Consolas", 8), fg="#475569", bg="#FFFFFF")
            meta_lbl.pack(pady=(4, 0))

            self.sheet10_gallery_cells.append({
                "cell": cell,
                "img_box": img_box,
                "img_lbl": img_lbl,
                "meta_lbl": meta_lbl,
            })

        for c in range(5):
            grid_wrap.grid_columnconfigure(c, weight=1)
        for r in range(2):
            grid_wrap.grid_rowconfigure(r, weight=1)

        self._show_sheet10_view("TABLE")

        btn_frame = tk.Frame(container, bg="#FFFFFF")
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="🔄 LÀM MỚI", font=("Arial", 10, "bold"),
            bg="#0284C7", fg="white", width=14, pady=8, cursor="hand2",
            command=self._refresh_sheet10_table
        ).pack(side="left", padx=10)

        tk.Button(
            btn_frame, text="💾 XUẤT EXCEL", font=("Arial", 10, "bold"),
            bg="#16A34A", fg="white", width=14, pady=8, cursor="hand2",
            command=self._export_log_to_file
        ).pack(side="left", padx=10)

    def _show_sheet10_view(self, mode):
        """Chuyển đổi giữa 2 kiểu xem của trang Sheet 10 ảnh."""
        self._sheet10_view_mode = mode

        self.sheet10_table_view.pack_forget()
        self.sheet10_grid_view.pack_forget()

        if mode == "GRID":
            self.sheet10_grid_view.pack(fill="both", expand=True)
            self.btn_sheet10_grid.config(bg="#0284C7", fg="white")
            self.btn_sheet10_table.config(bg="#E2E8F0", fg="#334155")
            self.sheet10_mode_frame.pack(side="right", padx=(8, 0))
        else:
            self.sheet10_table_view.pack(fill="both", expand=True)
            self.btn_sheet10_table.config(bg="#0284C7", fg="white")
            self.btn_sheet10_grid.config(bg="#E2E8F0", fg="#334155")
            self.sheet10_mode_frame.pack_forget()

    def _refresh_sheet10_table(self):
        """Nạp dữ liệu 10 frame gần nhất cho cả 2 kiểu xem."""
        if not hasattr(self, 'sheet10_tree'):
            return

        for item in self.sheet10_tree.get_children():
            self.sheet10_tree.delete(item)

        records = getattr(self, "_last_10_capture_records", [])
        if not records:
            self.sheet10_tree.insert("", "end", values=("-", "-", "-", "-", "-", "-", "-", "-", "-"))
            self._refresh_sheet10_gallery([])
            return

        for rec in records:
            self.sheet10_tree.insert(
                "", "end",
                values=(
                    rec.get("frame_idx", ""),
                    rec.get("timestamp", ""),
                    rec.get("trigger_source", ""),
                    rec.get("grade", ""),
                    f"{float(rec.get('ripeness_pct', 0.0)):.1f}",
                    f"{float(rec.get('diameter_mm', 0.0)):.1f}",
                    rec.get("shape", ""),
                    f"{float(rec.get('yolo_conf', 0.0)):.3f}",
                    f"{float(rec.get('z_distance_mm')):.1f}" if rec.get("z_distance_mm") is not None else "N/A"
                )
            )

        self._refresh_sheet10_gallery(records)

    def _refresh_sheet10_gallery(self, records):
        """Nạp dữ liệu 10 frame vào chế độ lưới ảnh."""
        if not hasattr(self, "sheet10_gallery_cells"):
            return

        self.sheet10_gallery_images = []
        for idx, item in enumerate(self.sheet10_gallery_cells):
            img_box = item.get("img_box")
            img_lbl = item.get("img_lbl")
            meta_lbl = item.get("meta_lbl")
            cell = item.get("cell")
            if idx < len(records):
                rec = records[idx]
                mode_val = self.sheet10_view_mode_var.get() if hasattr(self, "sheet10_view_mode_var") else "OVERLAY"

                # Double-click từng frame để mở popup thông số chi tiết
                if cell:
                    cell.configure(cursor="hand2")
                    cell.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=self.sheet10_view_mode_var.get()))
                img_lbl.configure(cursor="hand2")
                img_lbl.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=self.sheet10_view_mode_var.get()))
                meta_lbl.configure(cursor="hand2")
                meta_lbl.bind("<Double-1>", lambda e, r=rec: self._open_single_frame_detail_window(r, view_mode=self.sheet10_view_mode_var.get()))

                preview = None
                if mode_val == "OVERLAY":
                    preview = rec.get("preview_frame_annotated")
                    if preview is None:
                        preview = rec.get("preview_frame")
                elif mode_val == "RAW":
                    preview = rec.get("preview_frame_raw")
                elif mode_val == "BINARY":
                    preview = rec.get("preview_frame_mask")
                    if preview is None:
                        preview_raw = rec.get("preview_frame_raw")
                        if preview_raw is not None:
                            gray_temp = cv2.cvtColor(preview_raw, cv2.COLOR_BGR2GRAY)
                            _, preview = cv2.threshold(gray_temp, 75, 255, cv2.THRESH_BINARY)
                elif mode_val == "GRAY":
                    preview_raw = rec.get("preview_frame_raw")
                    if preview_raw is not None:
                        preview = cv2.cvtColor(preview_raw, cv2.COLOR_BGR2GRAY)
                    else:
                        preview_annotated = rec.get("preview_frame_annotated") or rec.get("preview_frame")
                        if preview_annotated is not None:
                            preview = cv2.cvtColor(preview_annotated, cv2.COLOR_BGR2GRAY)

                _img_set = False
                if preview is not None:
                    try:
                        if len(preview.shape) == 2:
                            rgb = cv2.cvtColor(preview, cv2.COLOR_GRAY2RGB)
                        else:
                            rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
                        if rgb is not None:
                            box_w = max(int(img_box.winfo_width()) - 4, 80)
                            box_h = max(int(img_box.winfo_height()) - 4, 60)
                            img = self._fit_frame_full_color(Image.fromarray(rgb), box_w, box_h)
                            photo = ImageTk.PhotoImage(img)
                            img_lbl.config(image=photo, text="")
                            img_lbl.image = photo
                            self.sheet10_gallery_images.append(photo)
                            _img_set = True
                    except Exception:
                        pass
                if not _img_set:
                    img_path = rec.get("image_path", "")
                    if img_path and os.path.isfile(img_path):
                        try:
                            box_w = max(int(img_box.winfo_width()) - 4, 80)
                            box_h = max(int(img_box.winfo_height()) - 4, 60)
                            
                            # Xử lý các chế độ khi đọc từ file
                            base_no_ext, ext = os.path.splitext(img_path)
                            target_path = img_path
                            if mode_val == "RAW":
                                raw_path = f"{base_no_ext}_raw.jpg"
                                if os.path.isfile(raw_path):
                                    target_path = raw_path
                            elif mode_val == "BINARY":
                                mask_path = f"{base_no_ext}_mask.png"
                                if os.path.isfile(mask_path):
                                    target_path = mask_path
                            elif mode_val == "GRAY":
                                raw_path = f"{base_no_ext}_raw.jpg"
                                if os.path.isfile(raw_path):
                                    target_path = raw_path
                            
                            img_loaded = Image.open(target_path).convert("RGB")
                            if mode_val == "GRAY":
                                img_loaded = img_loaded.convert("L").convert("RGB")
                            elif mode_val == "BINARY" and not os.path.isfile(f"{base_no_ext}_mask.png"):
                                gray_temp = img_loaded.convert("L")
                                img_loaded = gray_temp.point(lambda p: 255 if p > 75 else 0).convert("RGB")
                                
                            img = self._fit_frame_full_color(img_loaded, box_w, box_h)
                            photo = ImageTk.PhotoImage(img)
                            img_lbl.config(image=photo, text="")
                            img_lbl.image = photo
                            self.sheet10_gallery_images.append(photo)
                            _img_set = True
                        except Exception:
                            pass
                if not _img_set:
                    img_lbl.config(image="", text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
                    img_lbl.image = None

                circ_txt = "-"
                circ_val = rec.get("circularity", None)
                if circ_val is not None:
                    try:
                        circ_f = float(circ_val)
                        circ_f = circ_f / 100.0 if circ_f > 1.0 else circ_f
                        circ_f = max(0.0, min(1.0, circ_f))
                        circ_txt = f"{circ_f:.3f}"
                    except Exception:
                        circ_txt = "-"

                meta_lbl.config(
                    text=(
                        f"{rec.get('grade', '-') } | "
                        f"{float(rec.get('ripeness_pct', 0.0)):.1f}% | "
                        f"{float(rec.get('diameter_mm', 0.0)):.1f} mm | "
                        f"{circ_txt}"
                    )
                )
            else:
                img_lbl.config(image="", text="NO IMAGE", bg="#0F172A", fg="#94A3B8")
                img_lbl.image = None
                meta_lbl.config(text="-")
                if cell:
                    cell.configure(cursor="")
                    cell.unbind("<Double-1>")
                img_lbl.configure(cursor="")
                img_lbl.unbind("<Double-1>")
                meta_lbl.configure(cursor="")
                meta_lbl.unbind("<Double-1>")

    def _clear_sql_history(self):
        """Xóa toàn bộ dữ liệu trong bảng và xóa sạch file ảnh trong thư mục."""
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa TOÀN BỘ lịch sử và hình ảnh?\n(Hành động này không thể hoàn tác!)"):
            try:
                with self.db._get_conn() as conn:
                    c = conn.cursor()
                    c.execute("DELETE FROM phan_loai_session_10")
                    c.execute("DELETE FROM phan_loai_history")
                
                if os.path.exists(self.db.img_dir):
                    for f in os.listdir(self.db.img_dir):
                        file_path = os.path.join(self.db.img_dir, f)
                        try:
                            if os.path.isfile(file_path): os.unlink(file_path)
                        except Exception as cleanup_err:
                            self._log_event(f"⚠️ Không xóa được file ảnh lịch sử: {cleanup_err}", "WARNING")
                
                self._refresh_history_table()
                self._refresh_stats_ui() # Reset các con số về 0
                messagebox.showinfo("Thành công", "Đã dọn dẹp sạch sẽ CSDL và thư mục ảnh!")
                self._log_event("🗑️ Đã xóa sạch toàn bộ lịch sử SQL.", "WARNING")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể xóa dữ liệu: {e}")

    def _export_sql_history(self):
        """Xuất dữ liệu lịch sử SQL ra thư mục theo thời gian và loại."""
        try:
            export_base = filedialog.askdirectory(
                title="Chọn thư mục để xuất dữ liệu lịch sử"
            )
            if not export_base:
                return

            ok, result = self.db.export_history_dataset(export_base)
            if not ok:
                messagebox.showerror("Lỗi Export", str(result))
                self._log_event(f"❌ Export thất bại: {result}", "ERROR")
                return

            msg = (
                "Xuất dữ liệu thành công!\n\n"
                f"Thư mục: {result.get('export_root', '')}\n"
                f"Số bản ghi: {result.get('row_count', 0)}\n"
                f"Ảnh đã xuất: {result.get('image_exported', 0)}\n"
                f"Ảnh thiếu: {result.get('image_missing', 0)}\n"
                f"Ảnh frame đã xuất: {result.get('frame_image_exported', 0)}\n"
                f"Ảnh frame thiếu: {result.get('frame_image_missing', 0)}\n"
                f"Số trái đủ 10 frame: {result.get('fruits_full_10', 0)}\n"
                f"Tổng số thùng (10 quả/thùng): {result.get('bin_count_total', 0)}\n\n"
                f"CSV chi tiết: {result.get('records_csv', '')}\n"
                f"CSV frame chi tiết: {result.get('frame_details_csv', '')}\n"
                f"CSV tổng hợp theo loại: {result.get('summary_csv', '')}\n"
                f"CSV tổng hợp theo thùng: {result.get('bin_summary_csv', '')}\n"
                f"CSV KPI theo thùng: {result.get('bin_kpi_csv', '')}\n\n"
                "Gợi ý kiểm tra: mở frame_details.csv để xem đầy đủ trường realtime\n"
                "(Z mm, mode đo, YOLO enable/detected, TC1 adaptive/smoothing...)."
            )
            messagebox.showinfo("Export thành công", msg)
            self._log_event(
                f"📤 Export SQL xong: {result.get('row_count', 0)} records -> {result.get('export_root', '')}",
                "SUCCESS",
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể export dữ liệu: {e}")
            self._log_event(f"❌ Lỗi export SQL: {e}", "ERROR")

    def _build_db10_test_page(self):
        """Trang test gửi lệnh DB10 (1/2/3/0) từ UI xuống PLC."""
        container = tk.Frame(self.page_db10_test, bg="#FFFFFF", bd=1, relief="ridge")
        container.pack(fill="both", expand=True, padx=5, pady=5)

        tk.Label(
            container,
            text="🧪 TEST PLC - UI GỬI QUA PLC",
            font=("Arial", 12, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
            pady=15,
        ).pack()

        tk.Label(
            container,
            text=(
                "Mapping test PLC:\n"
                "• 1 -> DB10.DBX0.0 (Grade-1)\n"
                "• 2 -> DB10.DBX0.1 (Grade-2)\n"
                "• 3 -> DB10.DBX0.2 (Grade-3)\n"
                "• 0 -> Reset DB10.DBX0.0..0.2"
            ),
            justify="left",
            anchor="w",
            font=("Arial", 10),
            fg="#334155",
            bg="#FFFFFF",
        ).pack(fill="x", padx=24, pady=(0, 16))

        btn_row = tk.Frame(container, bg="#FFFFFF")
        btn_row.pack(pady=8)

        tk.Button(
            btn_row,
            text="GỬI 1",
            font=("Arial", 11, "bold"),
            bg="#16A34A",
            fg="white",
            width=10,
            pady=8,
            cursor="hand2",
            command=lambda: self._send_db10_test_value(1),
        ).pack(side="left", padx=8)

        tk.Button(
            btn_row,
            text="GỬI 2",
            font=("Arial", 11, "bold"),
            bg="#0284C7",
            fg="white",
            width=10,
            pady=8,
            cursor="hand2",
            command=lambda: self._send_db10_test_value(2),
        ).pack(side="left", padx=8)

        tk.Button(
            btn_row,
            text="GỬI 3",
            font=("Arial", 11, "bold"),
            bg="#475569",
            fg="white",
            width=10,
            pady=8,
            cursor="hand2",
            command=lambda: self._send_db10_test_value(3),
        ).pack(side="left", padx=8)

        tk.Button(
            btn_row,
            text="GỬI 0",
            font=("Arial", 11, "bold"),
            bg="#DC2626",
            fg="white",
            width=10,
            pady=8,
            cursor="hand2",
            command=lambda: self._send_db10_test_value(0),
        ).pack(side="left", padx=8)

        self.lbl_db10_test_status = tk.Label(
            container,
            text="⚪ Chưa gửi lệnh test PLC",
            font=("Arial", 10, "bold"),
            fg="#64748B",
            bg="#FFFFFF",
        )
        self.lbl_db10_test_status.pack(pady=(18, 0))

        # ── Đèn LED tín hiệu PLC ──────────────────────────────────────
        tk.Label(
            container,
            text="── Đèn tín hiệu PLC (0.5s xung) ──",
            font=("Arial", 9),
            fg="#94A3B8",
            bg="#FFFFFF",
        ).pack(pady=(22, 6))

        led_row = tk.Frame(container, bg="#FFFFFF")
        led_row.pack(pady=4)

        # Cấu hình: (tên hiển thị, màu ON, tên attribute)
        _led_cfg = [
            ("Grade-1\nDB10.DBX0.0", "#16A34A", "_led_grade1"),
            ("Grade-2\nDB10.DBX0.1", "#0284C7", "_led_grade2"),
            ("Grade-3\nDB10.DBX0.2", "#7C3AED", "_led_grade3"),
            ("Sensor\nDB10.DBX0.3", "#EA580C", "_led_sensor"),
        ]

        for label_text, color_on, attr_name in _led_cfg:
            cell = tk.Frame(led_row, bg="#FFFFFF")
            cell.pack(side="left", padx=14)

            # Canvas vẽ đèn LED tròn
            cv = tk.Canvas(cell, width=54, height=54, bg="#FFFFFF", highlightthickness=0)
            cv.pack()
            # Đèn tắt (xám) mặc định
            led_circle = cv.create_oval(7, 7, 47, 47, fill="#CBD5E1", outline="#94A3B8", width=2)
            # Lưu canvas + id hình tròn + màu ON để cập nhật sau
            setattr(self, attr_name, (cv, led_circle, color_on))

            tk.Label(
                cell,
                text=label_text,
                font=("Arial", 8, "bold"),
                fg="#334155",
                bg="#FFFFFF",
                justify="center",
            ).pack(pady=(4, 0))

    def _build_phanloai_page(self):
        """Trang Phân loại: Thống kê + Camera + Start/Stop + Log."""
        # 1. Main split: Chiều dọc (Trên = Giao diện chính, Dưới = Log + PLC)
        self.main_pw = tk.PanedWindow(self.page_phanloai, orient=tk.VERTICAL, sashwidth=6, sashrelief="ridge", bg="#CBD5E1")
        self.main_pw.pack(fill="both", expand=True, padx=5, pady=5)

        # 2. Top area: Chiều ngang (Trái = Stats, Phải = Camera)
        self.top_pw = tk.PanedWindow(self.main_pw, orient=tk.HORIZONTAL, sashwidth=6, sashrelief="ridge", bg="#CBD5E1")
        self.main_pw.add(self.top_pw, stretch="always", minsize=400)

        self.left_frame = tk.Frame(self.top_pw, bg="#F1F5F9")
        self.right_frame = tk.Frame(self.top_pw, bg="#F1F5F9")
        self.top_pw.add(self.left_frame, minsize=250)
        self.top_pw.add(self.right_frame, stretch="always", minsize=400)

        # 3. Bottom area: Chiều dọc (Log, PLC)
        self.log_frame = tk.Frame(self.main_pw, bg="#F1F5F9")
        self.main_pw.add(self.log_frame, stretch="never", minsize=80)
        
        self.plc_frame = tk.Frame(self.main_pw, bg="#F1F5F9")
        self.main_pw.add(self.plc_frame, stretch="never", minsize=105)

        # 4. Build content vào các khung tương ứng
        self._build_left(self.left_frame)
        self._build_right(self.right_frame)
        self._build_log_area(self.log_frame)
        self._build_plc_status_area(self.plc_frame)

    def _build_setting_page(self):
        """Trang Cài đặt: PLC IP, Nguồn Camera, Reset."""
        # ── Scrollable canvas wrapper ──────────────────────────────────
        canvas = tk.Canvas(self.page_setting, bg="#F1F5F9", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.page_setting, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        container = tk.Frame(canvas, bg="#F1F5F9")
        container_id = canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(container_id, width=event.width)

        container.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Cuộn bằng chuột
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Padding bên trong container
        inner = tk.Frame(container, bg="#F1F5F9", padx=30, pady=15)
        inner.pack(fill="both", expand=True)

        # 1. Cấu hình PLC
        plc_box = tk.LabelFrame(inner, text=" KẾT NỐI PLC S7-1200 ", font=("Arial", 10, "bold"),
                                fg="#0284C7", bg="#FFFFFF", padx=20, pady=20)
        plc_box.pack(fill="x", pady=10)

        # IP Entry
        tk.Label(plc_box, text="Địa chỉ IP:", fg="#475569", bg="#FFFFFF").grid(row=0, column=0, sticky="w")
        self.plc_ip_var = tk.StringVar(value=self.runtime_cfg.get("plc_ip", "192.168.0.1"))
        tk.Entry(plc_box, textvariable=self.plc_ip_var, width=20, bg="#F8FAFC", fg="#0F172A", bd=1).grid(row=0, column=1, padx=10, pady=5)

        # Rack/Slot
        tk.Label(plc_box, text="Rack/Slot:", fg="#475569", bg="#FFFFFF").grid(row=1, column=0, sticky="w")
        rs_frame = tk.Frame(plc_box, bg="#FFFFFF")
        rs_frame.grid(row=1, column=1, sticky="w", pady=5, padx=10)
        self.plc_rack_var = tk.StringVar(value=str(self.runtime_cfg.get("plc_rack", 0)))
        self.plc_slot_var = tk.StringVar(value=str(self.runtime_cfg.get("plc_slot", 1)))
        tk.Entry(rs_frame, textvariable=self.plc_rack_var, width=3, bg="#F8FAFC", fg="#0F172A", bd=1).pack(side="left")
        tk.Label(rs_frame, text=" / ", fg="#475569", bg="#FFFFFF").pack(side="left")
        tk.Entry(rs_frame, textvariable=self.plc_slot_var, width=3, bg="#F8FAFC", fg="#0F172A", bd=1).pack(side="left")

        self.btn_connect = tk.Button(plc_box, text="🔌 KẾT NỐI PLC", font=("Arial", 10, "bold"),
                                     bg="#1976D2", fg="white", padx=20, command=self._toggle_plc)
        self.btn_connect.grid(row=2, column=0, columnspan=2, pady=15)

        # 2. Cấu hình Camera
        cam_box = tk.LabelFrame(inner, text=" CẤU HÌNH CAMERA ", font=("Arial", 10, "bold"),
                                fg="#0284C7", bg="#FFFFFF", padx=20, pady=20)
        cam_box.pack(fill="x", pady=10)
        
        tk.Label(cam_box, text="Chế độ Hoạt động (Mode):", fg="#475569", bg="#FFFFFF").pack(anchor="w")
        self._refresh_camera_mode_options()
        default_cam_mode = str(self.runtime_cfg.get("default_camera_mode", self.cam_source_values[0]))
        if default_cam_mode not in self.cam_source_values:
            default_cam_mode = self.cam_source_values[0]
        self.cam_var = tk.StringVar(value=default_cam_mode)
        self.combo = ttk.Combobox(cam_box, textvariable=self.cam_var, values=self.cam_source_values, state="readonly", width=35)
        self.combo.pack(pady=(0, 15), anchor="w")

        # Nút Tìm Camera Tự Động
        tk.Button(cam_box, text="🔍 TÌM TẤT CẢ CAMERA", font=("Arial", 9, "bold"),
                  bg="#8B5CF6", fg="white", padx=15, pady=5, cursor="hand2",
                  command=self._detect_cameras).pack(pady=(0, 15), anchor="w")

        tk.Label(cam_box, text="Nguồn Camera Màu (Khi dùng Astra):", fg="#475569", bg="#FFFFFF").pack(anchor="w")
        self.astra_color_list = [
            "Tự động (ưu tiên USB: cổng 1 -> 2 -> 0)",
            "Cổng 0 (Laptop)",
            "Cổng 1 (USB Ngoài 1)",
            "Cổng 2 (USB Ngoài 2)",
        ]
        default_astra_port = str(self.runtime_cfg.get("astra_rgb_port_mode", self.astra_color_list[0]))
        if default_astra_port not in self.astra_color_list:
            default_astra_port = self.astra_color_list[0]
        self.astra_color_var = tk.StringVar(value=default_astra_port)
        self.combo_astra_color = ttk.Combobox(cam_box, textvariable=self.astra_color_var, values=self.astra_color_list, state="readonly", width=35)
        self.combo_astra_color.pack(pady=(0, 5), anchor="w")

        # 3. Cấu hình xử lý ảnh (MỚI CHUYỂN VÀO ĐÂY)
        proc_box = tk.LabelFrame(inner, text=" CẤU HÌNH XỬ LÝ HÌNH ẢNH ", font=("Arial", 10, "bold"),
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

        # 4. Cấu hình truy vết lô hàng
        lot_box = tk.LabelFrame(inner, text=" TRUY VẾT LÔ HÀNG / NHÀ VƯỜN ", font=("Arial", 10, "bold"),
                                fg="#0284C7", bg="#FFFFFF", padx=20, pady=15)
        lot_box.pack(fill="x", pady=10)

        tk.Label(lot_box, text="Nhà vườn:", bg="#FFFFFF", fg="#475569").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(lot_box, textvariable=self.current_orchard_var, width=28, bg="#F8FAFC", fg="#0F172A", bd=1).grid(row=0, column=1, padx=10, pady=5, sticky="w")

        tk.Label(lot_box, text="Mã lô:", bg="#FFFFFF", fg="#475569").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(lot_box, textvariable=self.current_lot_var, width=28, bg="#F8FAFC", fg="#0F172A", bd=1).grid(row=1, column=1, padx=10, pady=5, sticky="w")

        tk.Label(
            lot_box,
            text="Gợi ý: đổi mã lô mỗi lần nhận lô mới để truy vết dữ liệu riêng từng lô.",
            font=("Arial", 8),
            fg="#64748B",
            bg="#FFFFFF"
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        tk.Button(inner, text="🔄 RESET BỘ ĐẾM DỮ LIỆU", bg="#3949AB", fg="white", 
                  font=("Arial", 10, "bold"), pady=8, command=self._reset_counts).pack(fill="x", pady=(10, 4))

        tk.Button(inner, text="💾  LƯU TẤT CẢ THÔNG SỐ CÀI ĐẶT", bg="#0F766E", fg="white",
                  font=("Arial", 11, "bold"), pady=10, cursor="hand2",
                  command=self._save_system_config).pack(fill="x", pady=(4, 16))

    def _build_log_area(self, parent):
        """Khung hiển thị Log nâng cao: lọc, đếm, sao chép, xuất file."""
        self._log_frame_widget = tk.LabelFrame(
            parent, text=" 📝 EVENT LOG ",
            font=("Arial", 9, "bold"), fg="#475569", bg="#FFFFFF", padx=6, pady=4)
        self._log_frame_widget.pack(fill="both", expand=True, padx=5, pady=(0, 5))

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

        # Nút xóa log ở góc phải trên cùng (trash can icon)
        self.btn_clear_log = tk.Button(
            toolbar, text="🗑️", font=("Arial", 9, "bold"),
            fg="#991B1B", bg="#FEE2E2", bd=0, padx=6, pady=1, cursor="hand2",
            command=self._clear_log
        )
        self.btn_clear_log.pack(side="right", padx=2)

        self._log_pause_btn = tk.Button(
            toolbar, text="⏸ Pause", font=("Arial", 7, "bold"),
            fg="#334155", bg="#E2E8F0", bd=0, padx=6, cursor="hand2",
            command=self._toggle_log_pause
        )
        self._log_pause_btn.pack(side="right", padx=2)

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
        text_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.log_text = tk.Text(
            text_frame, height=4, bg="#F8FAFC", fg="#0F172A",
            font=("Consolas", 9), bd=0, state="disabled",
            yscrollcommand=scrollbar.set, wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Cấu hình màu sắc cho các loại log
        self.log_text.tag_configure("info",    foreground="#0F172A")
        self.log_text.tag_configure("success", foreground="#059669", background="#ECFDF5", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("warning", foreground="#D97706", background="#FFFBEB")
        self.log_text.tag_configure("error",   foreground="#DC2626", background="#FEF2F2", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("time",    foreground="#64748B")

        # Khởi tạo bộ đếm và bộ nhớ log
        self._log_counters = {"info": 0, "warning": 0, "error": 0, "success": 0}
        self._log_entries = []
        self._log_paused = False


    def _toggle_log_pause(self):
        """Tạm dừng/tiếp tục ghi log realtime trên UI."""
        self._log_paused = not bool(getattr(self, "_log_paused", False))
        if self._log_paused:
            if hasattr(self, "_log_pause_btn"):
                self._log_pause_btn.config(text="▶ Resume", bg="#FDE68A", fg="#92400E")
            if hasattr(self, "log_text") and self.log_text.winfo_exists():
                self.log_text.config(state="normal")
                self.log_text.insert("end", "[PAUSED] ⏸ Đã tạm dừng ghi log realtime.\n", "warning")
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        else:
            if hasattr(self, "_log_pause_btn"):
                self._log_pause_btn.config(text="⏸ Pause", bg="#E2E8F0", fg="#334155")
            self._log_event("▶ Đã tiếp tục ghi log realtime.", "INFO")

    def _build_plc_status_area(self, parent):
        """Thanh điều khiển nhanh PLC + Camera."""
        bar = tk.LabelFrame(parent, text=" ⚡ ĐIỀU KHIỂN NHANH ",
                              font=("Arial", 10, "bold"), fg="#0284C7", bg="#FFFFFF",
                              padx=10, pady=4)
        bar.pack(fill="both", expand=True, pady=(5, 0), padx=5)

        # ── Hàng 1: PLC START / STOP + CHỤP + XÓA BUFFER ──
        row1 = tk.Frame(bar, bg="#FFFFFF")
        row1.pack(fill="x", pady=(0, 3))

        ctrl1 = tk.Frame(row1, bg="#FFFFFF")
        ctrl1.pack()

        self.btn_plc_quick = tk.Button(ctrl1, text="🔌 KẾT NỐI PLC", font=("Arial", 10, "bold"),
                                                     fg="#FFFFFF", bg=self.BTN_PRIMARY, width=14, pady=4,
                                                     activebackground=self.BTN_PRIMARY_ACTIVE,
                                        relief="flat", cursor="hand2", command=self._toggle_plc)
        self.btn_plc_quick.pack(side="left", padx=(0, 6))

        self.btn_sensor_test = tk.Button(ctrl1, text="🧪 TRIGGER TEST", font=("Arial", 10, "bold"),
                                 fg="#FFFFFF", bg=self.BTN_PRIMARY, width=13, pady=4,
                                 activebackground=self.BTN_PRIMARY_ACTIVE,
                         relief="flat", cursor="hand2", command=self._manual_sensor_trigger)
        self.btn_sensor_test.pack(side="left", padx=(0, 6))

        self.lbl_plc_status = tk.Label(ctrl1, text="⚫ PLC chưa kết nối", font=("Arial", 9),
                                        fg="#64748B", bg="#FFFFFF")
        self.lbl_plc_status.pack(side="left", padx=(6, 0))

        self.lbl_sensor_status = tk.Label(ctrl1, text="⚪ Sensor: OFF", font=("Arial", 9, "bold"),
                          fg="#64748B", bg="#FFFFFF")
        self.lbl_sensor_status.pack(side="left", padx=(10, 0))

        # ── Hàng 1b: Nút PLC đặc biệt (Start, Stop, Reset) ──
        row1b = tk.Frame(bar, bg="#FFFFFF")
        row1b.pack(fill="x", pady=(0, 3))
        
        ctrl1b = tk.Frame(row1b, bg="#FFFFFF")
        ctrl1b.pack()
        
        self.btn_plc_start = tk.Button(ctrl1b, text="▶ START", font=("Arial", 9, "bold"), fg="#FFFFFF", bg="#10B981", width=10, relief="flat", cursor="hand2")
        self.btn_plc_start.pack(side="left", padx=(0, 5))
        self.btn_plc_start.bind("<ButtonPress-1>", lambda e: self._set_db_bit(8, 0, 0, True))
        self.btn_plc_start.bind("<ButtonRelease-1>", lambda e: self._set_db_bit(8, 0, 0, False))

        self.btn_plc_stop = tk.Button(ctrl1b, text="⏹ STOP", font=("Arial", 9, "bold"), fg="#FFFFFF", bg="#EF4444", width=10, relief="flat", cursor="hand2")
        self.btn_plc_stop.pack(side="left", padx=(0, 5))
        self.btn_plc_stop.bind("<ButtonPress-1>", lambda e: self._set_db_bit(8, 0, 1, True))
        self.btn_plc_stop.bind("<ButtonRelease-1>", lambda e: self._set_db_bit(8, 0, 1, False))

        self.btn_plc_reset = tk.Button(ctrl1b, text="🔄 RESET", font=("Arial", 9, "bold"), fg="#FFFFFF", bg="#F59E0B", width=10, relief="flat", cursor="hand2")
        self.btn_plc_reset.pack(side="left", padx=(0, 5))
        self.btn_plc_reset.bind("<ButtonPress-1>", lambda e: self._set_db_bit(8, 0, 2, True))
        self.btn_plc_reset.bind("<ButtonRelease-1>", lambda e: self._set_db_bit(8, 0, 2, False))

        # ── Hàng 2: Camera ON/OFF + MỞ FILE + Trạng thái Camera ──
        row2 = tk.Frame(bar, bg="#FFFFFF")
        row2.pack(fill="x")

        ctrl2 = tk.Frame(row2, bg="#FFFFFF")
        ctrl2.pack()

        self.btn_cam = tk.Button(ctrl2, text="▶ BẬT CAMERA", font=("Arial", 10, "bold"),
                                                                    fg="#FFFFFF", bg=self.BTN_SUCCESS, width=14, pady=4,
                                                                    activebackground=self.BTN_SUCCESS_ACTIVE,
                                  relief="flat", cursor="hand2", command=self._toggle_camera)
        self.btn_cam.pack(side="left", padx=(0, 6))

        self.btn_open_file = tk.Button(ctrl2, text="📂 MỞ FILE (ẢNH/VIDEO)", font=("Arial", 10, "bold"),
                                                                             fg="#FFFFFF", bg=self.BTN_PRIMARY, width=20, pady=4,
                                                                             activebackground=self.BTN_PRIMARY_ACTIVE,
                                       relief="flat", cursor="hand2", command=self._quick_open_file)
        self.btn_open_file.pack(side="left", padx=(0, 6))

        self.lbl_cam_status = tk.Label(ctrl2, text="⚫ Camera chưa bật", font=("Arial", 9),
                                        fg="#475569", bg="#FFFFFF")
        self.lbl_cam_status.pack(side="left", padx=(10, 0))

    # ─── Panel trái (Tối ưu hóa Bố cục và Thẩm mỹ SCADA Cao cấp) ───
    def _build_left(self, parent):
        lf = tk.Frame(parent, bg="#F8FAFC", bd=1, relief="ridge")
        lf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        # Header dạng Control-Room cực kỳ sang trọng
        panel_header = tk.Frame(lf, bg="#0F172A", pady=6)
        panel_header.pack(fill="x")
        
        tk.Label(panel_header, text="📊  BẢNG GIÁM SÁT THỜI GIAN THỰC",
                 font=("Arial", 10, "bold"), fg="#38BDF8", bg="#0F172A",
                 ).pack()

        # Ẩn thanh trạng thái chữ (bao gồm dòng "Chờ trigger...") theo yêu cầu UI.
        # Vẫn tạo label nội bộ để các lệnh config(text=...) không phát sinh lỗi.
        self.lbl_grading_status = tk.Label(
            lf,
            text="",
            font=("Arial", 8, "bold"),
            fg="#64748B",
            bg="#F1F5F9",
        )

        # ═══════════════════════════════════════════════════
        #  PANEL ĐÁNH GIÁ 3 TIÊU CHÍ (PREMIUM SCADA STYLE)
        # ═══════════════════════════════════════════════════
        criteria_border = tk.Frame(lf, bg="#CBD5E1", bd=1)
        criteria_border.pack(fill="x", padx=8, pady=(0, 4))
        
        criteria_frame = tk.Frame(criteria_border, bg="#F8FAFC")
        criteria_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Header của nhóm tiêu chí
        criteria_header = tk.Label(criteria_frame, text="📋 CHỈ SỐ PHÂN TÍCH CHẤT LƯỢNG",
                                   font=("Arial", 8, "bold"), fg="#1E293B", bg="#E2E8F0", anchor="w", padx=8, pady=3)
        criteria_header.pack(fill="x")

        # ── TC1: Độ chín vỏ quả (chỉ giám sát, không double-click để chỉnh) ──
        tc1_frame = tk.Frame(criteria_frame, bg="#F8FAFC", padx=6, pady=2)
        tc1_frame.pack(fill="x")

        tk.Label(
            tc1_frame,
            text="TC1  ĐỘ CHÍN VỎ QUẢ",
            font=("Arial", 8, "bold"),
            fg="#166534",
            bg="#F8FAFC",
        ).pack(anchor="w")

        self._tc1_progress = ttk.Progressbar(tc1_frame, length=260, mode='determinate', maximum=100)
        self._tc1_progress.pack(fill="x", pady=(1, 0))

        tc1_detail = tk.Frame(tc1_frame, bg="#F8FAFC")
        tc1_detail.pack(fill="x")

        self._tc1_red_var = tk.StringVar(value="Đỏ: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_red_var,
                 font=("Consolas", 8), fg="#C62828", bg="#F8FAFC").pack(side="left")

        self._tc1_yellow_var = tk.StringVar(value="Vàng: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_yellow_var,
                 font=("Consolas", 8), fg="#D97706", bg="#F8FAFC").pack(side="left", padx=(5, 0))

        self._tc1_green_var = tk.StringVar(value="Xanh: 0.0%")
        tk.Label(tc1_detail, textvariable=self._tc1_green_var,
                 font=("Consolas", 8), fg="#16A34A", bg="#F8FAFC").pack(side="left", padx=(5, 0))

        self._tc1_grade_var = tk.StringVar(value="---")
        self._tc1_grade_lbl = tk.Label(tc1_detail, textvariable=self._tc1_grade_var,
                 font=("Arial", 8, "bold"), fg="#64748B", bg="#F8FAFC")
        self._tc1_grade_lbl.pack(side="right")

        tk.Frame(criteria_frame, bg="#E2E8F0", height=1).pack(fill="x", pady=2)

        # ── TC2: Kích thước quả (chỉ giám sát, không double-click để chỉnh) ──
        tc2_frame = tk.Frame(criteria_frame, bg="#F8FAFC", padx=6, pady=2)
        tc2_frame.pack(fill="x")

        tk.Label(
            tc2_frame,
            text="TC2  KÍCH THƯỚC QUẢ",
            font=("Arial", 8, "bold"),
            fg="#C2410C",
            bg="#F8FAFC",
        ).pack(anchor="w")

        self._tc2_progress = ttk.Progressbar(tc2_frame, length=260, mode='determinate', maximum=120)
        self._tc2_progress.pack(fill="x", pady=(1, 0))

        tc2_detail = tk.Frame(tc2_frame, bg="#F8FAFC")
        tc2_detail.pack(fill="x")

        self._tc2_diameter_var = tk.StringVar(value="Ø: 0 mm")
        tk.Label(tc2_detail, textvariable=self._tc2_diameter_var,
                 font=("Consolas", 8), fg="#7C2D12", bg="#F8FAFC").pack(side="left")

        self._tc2_grade_var = tk.StringVar(value="---")
        self._tc2_grade_lbl = tk.Label(tc2_detail, textvariable=self._tc2_grade_var,
                 font=("Arial", 8, "bold"), fg="#64748B", bg="#F8FAFC")
        self._tc2_grade_lbl.pack(side="right")

        tk.Frame(criteria_frame, bg="#E2E8F0", height=1).pack(fill="x", pady=2)

        # ── TC3: Độ tròn quả (chỉ giám sát, không double-click để chỉnh) ──
        tc3_frame = tk.Frame(criteria_frame, bg="#F8FAFC", padx=6, pady=2)
        tc3_frame.pack(fill="x")

        tk.Label(
            tc3_frame,
            text="TC3  ĐỘ TRÒN QUẢ",
            font=("Arial", 8, "bold"),
            fg="#0369A1",
            bg="#F8FAFC",
        ).pack(anchor="w")

        self._tc3_progress = ttk.Progressbar(tc3_frame, length=260, mode='determinate', maximum=100)
        self._tc3_progress.pack(fill="x", pady=(1, 0))

        tc3_detail = tk.Frame(tc3_frame, bg="#F8FAFC")
        tc3_detail.pack(fill="x")

        self._tc3_circularity_var = tk.StringVar(value="Độ tròn: 0.00")
        tk.Label(tc3_detail, textvariable=self._tc3_circularity_var,
                 font=("Consolas", 8), fg="#0F172A", bg="#F8FAFC").pack(side="left")

        self._tc3_grade_var = tk.StringVar(value="---")
        self._tc3_grade_lbl = tk.Label(tc3_detail, textvariable=self._tc3_grade_var,
                 font=("Arial", 8, "bold"), fg="#64748B", bg="#F8FAFC")
        self._tc3_grade_lbl.pack(side="right")

        tk.Frame(criteria_frame, bg="#E2E8F0", height=1).pack(fill="x", pady=2)

        # Nút mở bảng luật quyết định 3 tiêu chí (mỗi tiêu chí 3 mức)
        decision_btn = tk.Button(
            criteria_frame,
            text="🔎 XEM BẢNG LUẬT QUYẾT ĐỊNH 3 TIÊU CHÍ",
            font=("Arial", 8, "bold"),
            fg="#0F172A",
            bg="#E2E8F0",
            activebackground="#CBD5E1",
            activeforeground="#0F172A",
            relief="flat",
            cursor="hand2",
            command=self._open_decision_rule_table_3tc,
            padx=6,
            pady=4,
        )
        decision_btn.pack(fill="x", padx=6, pady=(0, 4))


        # Ẩn toàn bộ khối MONITOR theo yêu cầu giao diện.
        # Giữ các biến StringVar để logic cập nhật realtime không bị lỗi AttributeError.
        self._fps_var = tk.StringVar(value="0.0")
        self._proc_time_var = tk.StringVar(value="0.0 ms")
        self._blur_status_var = tk.StringVar(value="N/A")
        self._blur_status_label = tk.Label(criteria_frame, text="", bg="#F8FAFC")

        # Biến monitor track/session vẫn giữ để logic cũ hoạt động, nhưng không hiển thị panel tracking.
        self._track_live_var = tk.StringVar(value="Track: -")
        self._track_active_var = tk.StringVar(value="Active tracks: 0")
        self._session_track_var = tk.StringVar(value="Session tracks: 0")
        self._temporal_var = tk.StringVar(value="Temporal: 0.00")
        self._track_method_var = tk.StringVar(value="Decision: weighted_voting")

        # ═══════════════════════════════════════════════════
        #  THỐNG KÊ 3 HẠNG (OSPREYX PREMIUM CARDS)
        # ═══════════════════════════════════════════════════
        
        # Thẻ 3 hạng (Tối ưu hóa không gian & màu sắc SCADA)
        for grade, cfg in self.GRADE_CFG.items():
            # Tạo frame bọc ngoài giả lập viền mỏng bo góc
            card_border = tk.Frame(lf, bg="#E2E8F0", bd=1)
            card_border.pack(fill="x", padx=8, pady=2)  # Giảm pady từ 3 xuống 2 để tăng mật độ thông tin
            
            card = tk.Frame(card_border, bg=cfg["bg"])
            card.pack(fill="both", expand=True, padx=1, pady=1)
            
            # Hàng tiêu đề + Số lượng
            header_row = tk.Frame(card, bg=cfg["bg"])
            header_row.pack(fill="x", padx=10, pady=(2, 1))  # Giảm padding dọc
            
            tk.Label(header_row, text=f"{cfg['icon']}  {cfg['label']}",
                     font=("Arial", 8, "bold"), fg=cfg["color"], bg=cfg["bg"]
                     ).pack(side="left")
            
            var = tk.StringVar(value="0")
            p_var = tk.StringVar(value="(0.0%)")
            rate_var = tk.StringVar(value="0 / MIN")
            
            self._count_vars[grade] = var
            self._percent_vars[grade] = p_var
            self._throughput_vars[grade] = rate_var
            
            tk.Label(header_row, textvariable=p_var,
                     font=("Arial", 8, "bold"), fg="#64748B", bg=cfg["bg"]
                     ).pack(side="right", padx=(0, 2))
            
            tk.Label(header_row, textvariable=var,
                     font=("Consolas", 13, "bold"), fg=cfg.get("count_fg", "#1E293B"), bg=cfg["bg"]
                     ).pack(side="right", padx=(0, 5))
            
            # Hàng tốc độ gạt (Throughput Rate) - Ẩn hiển thị tốc độ trên phút theo yêu cầu
            bottom_row = tk.Frame(card, bg=cfg["bg"])
            bottom_row.pack(fill="x", padx=10, pady=(0, 2))
            
            self._grade_desc_labels[grade] = tk.Label(bottom_row, text="", bg=cfg["bg"])

        # Giữ biến để logic cũ không lỗi
        self._total_var = tk.StringVar(value="0")
        self._yield_var = tk.StringVar(value="0.0%")

# ─── Panel phải: camera màu + ảnh xám ─────────────────
    def _build_right(self, parent):
        rf = tk.Frame(parent, bg="#F8FAFC", bd=1, relief="ridge")
        rf.pack(side="left", fill="both", expand=True)

        # ── Vùng hiển thị Camera (Cân bằng kích thước bằng PanedWindow) ──
        self.display_area = tk.PanedWindow(rf, orient=tk.VERTICAL, sashwidth=6, sashrelief="ridge", bg="#CBD5E1")
        self.display_area.pack(fill="both", expand=True, padx=6, pady=2)

        # --- Khung hiển thị 1 ---
        f1 = tk.Frame(self.display_area, bg="#F8FAFC")
        self.display_area.add(f1, stretch="always", minsize=100)
        
        self.lbl_view1 = tk.Label(f1, text="📷  CAMERA (COLOR)",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#F8FAFC")
        self.lbl_view1.pack(anchor="w")
        
        self.canvas = tk.Canvas(f1, bg="#000000", highlightthickness=1, 
                                highlightbackground="#CBD5E1", cursor="cross")
        self.canvas.pack(fill="both", expand=True)

        # --- Khung hiển thị 2 ---
        f2 = tk.Frame(self.display_area, bg="#F8FAFC")
        self.display_area.add(f2, stretch="always", minsize=100)
        
        self.lbl_view2 = tk.Label(f2, text="🔳  BINARY/THRESHOLD",
                                  font=("Arial", 9, "bold"), fg="#0284C7", bg="#F8FAFC")
        self.lbl_view2.pack(anchor="w")
        
        self.canvas_gray = tk.Canvas(f2, bg="#000000", highlightthickness=1, 
                                     highlightbackground="#CBD5E1", cursor="cross")
        self.canvas_gray.pack(fill="both", expand=True)

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
            self.btn_cam.config(text="⏹  Dừng File", bg=self.BTN_DANGER, activebackground=self.BTN_DANGER_ACTIVE)
            self.lbl_cam_status.config(text="🟢  Đang phát File", fg="#059669")
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
            cameras = self.camera.detect_available_cameras(max_test=8)

            # Cập nhật trực tiếp danh sách combobox theo camera vật lý thực tế.
            self.win.after(0, lambda cams=cameras: self._refresh_camera_mode_options(cams))
            
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

    def _refresh_camera_mode_options(self, detected_cameras=None):
        """Tạo danh sách mode camera động từ camera vật lý đang cắm."""
        if detected_cameras is None:
            detected_cameras = self.camera.detect_available_cameras(max_test=8)

        values = ["Astra Pro SDK (RGB)"]
        mode_to_index = {}

        for idx, name in detected_cameras:
            mode_label = f"📷 Cổng {idx}: {name}"
            values.append(mode_label)
            mode_to_index[mode_label] = int(idx)

        # Bổ sung các nguồn không phải camera vật lý.
        values.extend([
            "Luồng RTSP / IP Camera",
            "📂 Mở File Ảnh (.jpg, .png)",
            "🎞️ Mở File Video (.mp4, .avi)",
        ])

        self.cam_source_values = values
        self._cam_mode_to_index = mode_to_index

        if hasattr(self, "combo") and self.combo.winfo_exists():
            current_mode = self.cam_var.get()
            self.combo["values"] = self.cam_source_values
            if current_mode in self.cam_source_values:
                self.cam_var.set(current_mode)
            else:
                self.cam_var.set(self.cam_source_values[0])
    
    def _toggle_camera(self):
        if self.camera.is_running():
            self._stop_camera()
        else:
            self._start_camera()

    def _auto_start_astra_priority(self):
        """Tự động dò và kết nối Astra Pro ngay khi khởi động app.
        Ưu tiên Astra Pro; nếu không có thì dùng webcam đầu tiên khả dụng.
        Toàn bộ chạy trong thread nền để không treo UI."""

        self._log_event("🔍 [AutoStart] Đang dò camera, ưu tiên Astra Pro...", "INFO")

        def _worker():
            try:
                result = self.camera.auto_detect_and_start()
                # Chuyển cập nhật UI về main thread
                self.win.after(0, lambda r=result: self._on_auto_start_result(r))
            except Exception as e:
                self.win.after(0, lambda err=str(e): self._log_event(
                    f"❌ [AutoStart] Lỗi dò camera: {err}", "ERROR"
                ))

        import threading as _th
        _th.Thread(target=_worker, daemon=True).start()

    def _on_auto_start_result(self, result):
        """Nhận kết quả auto-detect camera và cập nhật UI trên main thread."""
        if not result.get("success"):
            self._log_event(
                f"⚠️ [AutoStart] {result.get('message', 'Không tìm thấy camera')}",
                "WARNING"
            )
            self._set_system_state(self.STATE_DEGRADED, "Không tìm thấy camera", level="WARNING")
            return

        mode = result.get("mode", "none")
        port = result.get("port")
        name = result.get("name", "")
        message = result.get("message", "")

        if mode == "astra":
            # Cập nhật combo về Astra Pro
            astra_val = next(
                (v for v in self.cam_source_values if "Astra Pro" in v),
                None
            )
            if astra_val:
                try:
                    self.cam_var.set(astra_val)
                except Exception:
                    pass

            # Cập nhật combo cổng Astra nếu có
            if port is not None and hasattr(self, "astra_color_var"):
                port_label_map = {0: "Cổng 0", 1: "Cổng 1", 2: "Cổng 2"}
                port_label = port_label_map.get(port)
                if port_label:
                    try:
                        self.astra_color_var.set(
                            next((v for v in getattr(self, "_astra_port_values", [])
                                  if port_label in v), self.astra_color_var.get())
                        )
                    except Exception:
                        pass

            self.btn_cam.config(
                text="⏹  Tắt Astra Pro",
                bg=self.BTN_DANGER,
                activebackground=self.BTN_DANGER_ACTIVE
            )
            self.lbl_cam_status.config(text=f"🟢  Astra Pro RGB (cổng {port})", fg="#059669")
            self.combo.config(state="disabled")
            self._log_event(f"🟢 [AutoStart] {message}", "SUCCESS")

        else:  # webcam
            # Cập nhật combo về đúng webcam index
            webcam_val = self._cam_index_to_mode.get(port) if hasattr(self, "_cam_index_to_mode") else None
            if webcam_val is None:
                # Tìm entry đầu tiên không phải Astra/File trong combo
                webcam_val = next(
                    (v for v in self.cam_source_values
                     if "Astra" not in v and "File" not in v),
                    self.cam_source_values[0] if self.cam_source_values else ""
                )
            try:
                self.cam_var.set(webcam_val)
            except Exception:
                pass

            self.btn_cam.config(
                text="⏹  Tắt Camera",
                bg=self.BTN_DANGER,
                activebackground=self.BTN_DANGER_ACTIVE
            )
            self.lbl_cam_status.config(text=f"🟢  Webcam (cổng {port})", fg="#059669")
            self.combo.config(state="disabled")
            self._log_event(f"🟢 [AutoStart] {message}", "SUCCESS")

        # Cập nhật trạng thái hệ thống
        if self.plc.connected:
            self._set_system_state(self.STATE_RUNNING, "Camera + PLC sẵn sàng", level="SUCCESS")
        else:
            self._set_system_state(self.STATE_DEGRADED, "Camera chạy, PLC chưa kết nối", level="WARNING")


    def _start_camera(self):
        val = self.cam_var.get()
        success = False

        # Khi hệ thống yêu cầu depth, không cho khởi chạy camera thường vì sẽ luôn Z=N/A.
        require_depth = bool(getattr(self.camera, "require_depth_for_astra", False))
        if require_depth and ("Astra Pro" not in str(val)):
            self._log_event("⚠️ Đang bật chế độ bắt buộc depth: tự chuyển sang Astra Pro SDK (RGB)", "WARNING")
            val = "Astra Pro SDK (RGB)"
            try:
                self.cam_var.set(val)
            except Exception:
                pass
        
        if "Astra Pro" in val:
            sel_mode = str(self.astra_color_var.get() or "")
            sel_idx = None
            if "Cổng 0" in sel_mode:
                sel_idx = 0
            elif "Cổng 1" in sel_mode:
                sel_idx = 1
            elif "Cổng 2" in sel_mode:
                sel_idx = 2
            success = self.camera.start_astra_camera(sel_idx)
        elif "Mở File Ảnh" in val:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
            if path:
                # Reset cờ để ảnh tĩnh mới luôn được phân tích lại.
                self._last_static_processed = False
                success = self.camera.start_file_mode(path, is_video=False)
        elif "Mở File Video" in val:
            path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov")])
            if path:
                # Video không dùng cờ ảnh tĩnh, đặt lại để tránh trạng thái cũ sót lại.
                self._last_static_processed = False
                success = self.camera.start_file_mode(path, is_video=True)
        else:
            idx = int(self._cam_mode_to_index.get(val, 0))
            success = self.camera.start_cv2_camera(idx)
            
        if success:
            ok, cfg_msg = save_runtime_config({
                "runtime": {
                    "default_camera_mode": str(val),
                    "astra_rgb_port_mode": str(self.astra_color_var.get() if hasattr(self, "astra_color_var") else ""),
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được mặc định camera: {cfg_msg}", "WARNING")

            if "Astra Pro" in val:
                self.btn_cam.config(text="⏹  Tắt Astra Pro", bg=self.BTN_DANGER, activebackground=self.BTN_DANGER_ACTIVE)
                self.lbl_cam_status.config(text="🟢  Đang phát (Astra Pro RGB)", fg="#059669")
                port = getattr(self.camera, "_source_index", None)
                dstatus = str(getattr(self.camera, "depth_status", "depth status unknown"))
                self._log_event(f"🟢 Astra Pro kết nối thành công: RGB cổng {port}, {dstatus}", "SUCCESS")
            elif "File" in val:
                self.btn_cam.config(text="⏹  Dừng File", bg=self.BTN_DANGER, activebackground=self.BTN_DANGER_ACTIVE)
                self.lbl_cam_status.config(text="🟢  Đang phát File", fg="#059669")
            else:
                self.btn_cam.config(text="⏹  Tắt Camera", bg=self.BTN_DANGER, activebackground=self.BTN_DANGER_ACTIVE)
                self.lbl_cam_status.config(text="🟢  Đang phát", fg="#059669")
            self.combo.config(state="disabled")
            if self.plc.connected:
                self._set_system_state(self.STATE_RUNNING, "Camera + PLC sẵn sàng", level="SUCCESS")
            else:
                self._set_system_state(self.STATE_DEGRADED, "Camera chạy, PLC chưa kết nối", level="WARNING")
        else:
            if "Astra Pro" in val:
                dstatus = str(getattr(self.camera, "depth_status", "depth status unknown"))
                self._log_event(f"🔴 Astra Pro kết nối thất bại: {dstatus}", "ERROR")
            self._set_system_state(self.STATE_DEGRADED, "Không mở được camera", level="WARNING")

    def _stop_camera(self):
        self.camera.stop()
        self._last_static_processed = False
        self.btn_cam.config(text="▶  Bật Camera", bg=self.BTN_SUCCESS, activebackground=self.BTN_SUCCESS_ACTIVE)
        self.lbl_cam_status.config(text="⚫  Camera chưa bật", fg="#666680")
        self.combo.config(state="readonly")
        self._draw_placeholder()
        self._set_system_state(self.STATE_SAFE_STOP, "Camera dừng", level="INFO")

    def _cancel_active_capture_session(self, reason):
        if not self._capture_session_active:
            return
        self._capture_session_active = False
        self._video_session_buffer = []
        self._video_decision_buffer = []
        self._capture_sample_records = []
        self._session_track_results = {}
        self._reset_tracking_monitor()
        self._last_detected_grade = "NO_APPLE"
        self._log_event(reason, "WARNING")

    def _grade_rank(self, grade):
        return decision_grade_rank(grade)

    def _compute_frame_quality_weight(self, detail_info):
        """Ước lượng chất lượng frame để dùng làm trọng số bỏ phiếu."""
        blur_threshold = float(getattr(self.analyzer, "blur_threshold", 100.0) or 100.0)
        return decision_compute_frame_quality_weight(detail_info, blur_threshold)

    def _fuse_session_decision(self, session_entries):
        """Gộp quyết định nhiều ảnh bằng weighted voting có kiểm tra độ chắc chắn."""
        return decision_fuse_session_decision(
            session_entries,
            self.decision_min_quality_score,
            self.decision_min_valid_frames,
            self.decision_margin_delta,
        )

    def _reset_tracking_monitor(self):
        """Đặt lại các chỉ số tracking trên UI về trạng thái chờ."""
        if threading.current_thread() is not threading.main_thread():
            try:
                if hasattr(self, "win") and self.win.winfo_exists():
                    self.win.after(0, self._reset_tracking_monitor)
                elif hasattr(self, "parent") and self.parent.winfo_exists():
                    self.parent.after(0, self._reset_tracking_monitor)
            except Exception:
                pass
            return

        if hasattr(self, "_track_live_var"):
            self._track_live_var.set("Track: -")
        if hasattr(self, "_track_active_var"):
            self._track_active_var.set("Active tracks: 0")
        if hasattr(self, "_session_track_var"):
            self._session_track_var.set("Session tracks: 0")
        if hasattr(self, "_temporal_var"):
            self._temporal_var.set("Temporal: 0.00")
        if hasattr(self, "_track_method_var"):
            self._track_method_var.set("Decision: weighted_voting")

    def _compute_temporal_stability(self, grade_sequence):
        """Tính temporal stability cho một chuỗi nhãn theo track."""
        return decision_compute_temporal_stability(grade_sequence)

    def _aggregate_track_decisions(self, sample_records):
        """Gộp nhãn theo track_id để giảm dao động frame-wise và tạo metric video-level."""
        return decision_aggregate_track_decisions(
            sample_records,
            single_fruit_station_mode=self.single_fruit_station_mode,
            decision_min_quality_score=self.decision_min_quality_score,
            track_min_frames=self.track_min_frames,
        )

    def _set_system_state(self, new_state, reason="", level="INFO"):
        if new_state == self.system_state and reason == self.system_state_reason:
            return
        self.system_state = new_state
        self.system_state_reason = reason
        self._log_event(f"🏭 STATE={new_state}: {reason}", level)

    def _on_frame_received(self, frame, depth_info=None):
        import time
        # Kiểm tra tốc độ chụp theo cấu hình (Analysis Interval)
        curr_time = time.time() * 1000 # Convert to ms
        try:
            interval = max(10.0, float(self.cfg_analysis_ms.get() or 100))
        except ValueError:
            interval = 100.0
        if curr_time - self._last_analysis_time < interval:
            return # Bỏ qua frame này để giữ đúng tốc độ chụp yêu cầu
        
        self._last_analysis_time = curr_time
        raw_frame = frame.copy()
        self.frame_to_save = raw_frame.copy()
        
        # Kiểm tra xem đang chạy ảnh tĩnh hay video
        is_static = getattr(self.camera, "is_single_image", False)
        
        # Nếu là ảnh tĩnh và đã xử lý xong rồi thì bỏ qua để tránh chớp màn hình
        if is_static and hasattr(self, "_last_static_processed") and self._last_static_processed:
            return
        
        try:
            self.analyzer.update_depth_context(depth_info)
            processed_frame, defect_area, ripeness, grade, detail_info = self.analyzer.analyze_apple(frame)
            fx = detail_info.get("center_x", None)
            fy = detail_info.get("center_y", None)
            fw = detail_info.get("frame_width", frame.shape[1])
            fh = detail_info.get("frame_height", frame.shape[0])
            if fx is not None and fy is not None:
                self.camera.set_depth_focus_point(fx, fy, fw, fh)
            elif grade in ("NO_APPLE", "UNKNOWN"):
                self.camera.clear_depth_focus_point()
            if self._vision_fault_count > 0:
                self._vision_fault_count = 0
                if self.camera.is_running():
                    target_state = self.STATE_RUNNING if self.plc.connected else self.STATE_DEGRADED
                    self._set_system_state(target_state, "Vision đã phục hồi", level="SUCCESS")

            frame = processed_frame
            self.current_grade = grade
            self.current_diameter = detail_info.get('diameter_mm', 0)
            
            # Khởi tạo bộ đệm tích lũy cho video nếu chưa có
            if not hasattr(self, "_video_session_buffer"): self._video_session_buffer = []
            
            color_map_hex = {
                "Grade-1": "#10B981",
                "Grade-2": "#F59E0B",
                "Grade-3": "#EF4444",
                "UNKNOWN": "#64748B",
                "NO_APPLE": "#64748B",
            }
            status_text = f"Đang phân loại: 🍎 {grade}"
            
            # Quản lý Event Log cho người giám sát
            if not hasattr(self, "_last_detected_grade"): self._last_detected_grade = "NO_APPLE"
            
            if grade != "NO_APPLE" and grade != "UNKNOWN":
                status_text += f" ({ripeness:.0f}% Đỏ)"
                self._no_apple_counter = 0  # Reset bộ đếm khi thấy táo

                if is_static:
                    # TRƯỜNG HỢP ẢNH TĨNH: Chốt luôn
                    if self._last_detected_grade == "NO_APPLE":
                        self._log_event(f"🍎 [PHÁT HIỆN] Táo xác nhận (ảnh tĩnh) → Hạng {grade}", "SUCCESS")
                        self._log_event(f"🖼️ ẢNH TĨNH: Hạng {grade}", "INFO")
                        self._save_to_sql(grade)
                        self._last_static_processed = True # Đánh dấu đã xong
                else:
                    # TRƯỜNG HỢP VIDEO: chỉ chụp khi có trigger cảm biến (PLC/Test)
                    if self._last_detected_grade == "NO_APPLE" or self._last_detected_grade == "UNKNOWN":
                        # Chỉ in ra console debug, không hiện lên bảng log UI để tránh rối
                        print(f"[DEBUG] Táo xuất hiện — Hạng preview: {grade}")
                    if self._capture_session_active:
                        quality_score, sample_weight = self._compute_frame_quality_weight(detail_info)
                        self._video_session_buffer.append(grade)
                        self._video_decision_buffer.append({
                            "grade": grade,
                            "quality_score": quality_score,
                            "weight": sample_weight,
                        })
                        self._capture_sample_records.append({
                            "frame_idx": len(self._video_session_buffer),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                            "trigger_source": self._capture_session_source,
                            "grade": grade,
                            "quality_score": float(quality_score or 0.0),
                            "decision_weight": float(sample_weight or 0.0),
                            "ripeness_pct": float(ripeness or 0.0),
                            "red_ratio": float(detail_info.get("red_ratio") or 0.0),
                            "yellow_ratio": float(detail_info.get("yellow_ratio") or 0.0),
                            "green_ratio": float(detail_info.get("green_ratio") or 0.0),
                            "ripeness_label": str(detail_info.get("ripeness_label", "-")),
                            "ripeness_grade": str(detail_info.get("ripeness_grade", "-")),
                            "diameter_mm": float(detail_info.get("diameter_mm") or 0.0),
                            "size_label": str(detail_info.get("size_label", "-")),
                            "size_grade": str(detail_info.get("size_grade", "-")),
                            "shape": str(detail_info.get("shape_label", "---")),
                            "shape_grade": str(detail_info.get("shape_grade", "-")),
                            "circularity": float(detail_info.get("circularity") or 0.0),
                            "pixel_to_mm_effective": float(detail_info.get("pixel_to_mm_effective") or 0.0),
                            "z_distance_mm": detail_info.get("z_distance_mm", None),
                            "size_measure_mode": str(detail_info.get("size_measure_mode", "")),
                            "analysis_mode": str(detail_info.get("analysis_mode", "")),
                            "tc1_adaptive_hsv": bool(detail_info.get("tc1_adaptive_hsv", False)),
                            "tc1_temporal_smoothing": bool(detail_info.get("tc1_temporal_smoothing", False)),
                            "tc1_smoothing_window": int(detail_info.get("tc1_smoothing_window") or 0),
                            "yolo_class": str(detail_info.get("yolo_class", "apple")),
                            "yolo_enabled": bool(detail_info.get("yolo_enabled", False)),
                            "yolo_detected": bool(detail_info.get("yolo_detected", False)),
                            "yolo_conf": float(detail_info.get("yolo_confidence") or 0.0),
                            "processing_time_ms": float(detail_info.get("processing_time_ms") or 0.0),
                            "fps": float(detail_info.get("fps") or 0.0),
                            "blur_status": str(detail_info.get("blur_status", "-")),
                            "blur_score": float(detail_info.get("blur_score") or 0.0),
                            "track_id": detail_info.get("track_id", None),
                            "active_tracks": int(detail_info.get("active_tracks") or 0),
                            "yolo_tracker_mode": str(detail_info.get("yolo_tracker_mode", "predict")),
                            "preview_frame": frame.copy(),
                            "preview_frame_raw": raw_frame.copy(),
                            "preview_frame_annotated": frame.copy(),
                            "preview_frame_mask": self.analyzer.last_apple_mask.copy() if getattr(self.analyzer, "last_apple_mask", None) is not None else None,
                        })

                        count = len(self._video_session_buffer)
                        status_text = (
                            f"📸 Trigger {self._capture_session_source}: "
                            f"{count}/{self.capture_frames_required} | Hạng: {grade}"
                        )

                        if count >= self.capture_frames_required:
                            self._capture_session_active = False
                            self._session_finalized = True
                            self._last_detected_grade = "NO_APPLE"
                            status_text = "⏳ Chờ trigger cảm biến tiếp theo..."
                            if hasattr(self, "win") and self.win.winfo_exists():
                                self.win.after(0, self._finalize_video_session)
                            else:
                                self._finalize_video_session()
                        else:
                            # Kiểm tra timeout ngay cả khi CÓ táo trong khung hình nhưng thu thập quá chậm
                            elapsed = time.time() - self._capture_session_start_ts
                            if elapsed > self.capture_wait_timeout_s:
                                if len(self._video_session_buffer) >= getattr(self, "decision_min_valid_frames", 6):
                                    self._capture_session_active = False
                                    self._session_finalized = True
                                    self._last_detected_grade = "NO_APPLE"
                                    status_text = "⏳ Ép chốt kết quả do timeout (đủ frame tối thiểu)"
                                    self._log_event(f"⚠️ Ép chốt kết quả do timeout ({len(self._video_session_buffer)}/{self.capture_frames_required} frame)", "WARNING")
                                    if hasattr(self, "win") and self.win.winfo_exists():
                                        self.win.after(0, self._finalize_video_session)
                                    else:
                                        self._finalize_video_session()
                                else:
                                    self._capture_session_active = False
                                    self._video_session_buffer = []
                                    self._capture_sample_records = []
                                    self._last_detected_grade = "NO_APPLE"
                                    status_text = "⏳ Chờ trigger cảm biến tiếp theo..."
                                    self._log_event(f"⚠️ Hủy phiên chụp do timeout (chỉ có {len(self._video_session_buffer)} frame)", "ERROR")
                                    self.send_timeout_to_plc()
                    else:
                        status_text = f"⏳ Chờ trigger cảm biến | Preview: {grade}"


                    self._last_detected_grade = grade
            else:
                if not is_static:
                    if self._capture_session_active:
                        elapsed = time.time() - self._capture_session_start_ts
                        status_text = f"📸 Trigger {self._capture_session_source}: đang chờ táo ({elapsed:.1f}s)"

                        # Timeout khắt khe: có trigger nhưng sau 6s chưa đủ 10 mẫu
                        if elapsed > self.capture_wait_timeout_s:
                            if len(self._video_session_buffer) >= getattr(self, "decision_min_valid_frames", 6):
                                # Đã có đủ số mẫu tối thiểu để phân tích -> chốt kết quả
                                self._capture_session_active = False
                                self._session_finalized = True
                                self._last_detected_grade = "NO_APPLE"
                                status_text = "⏳ Ép chốt kết quả do timeout (đủ frame tối thiểu)"
                                self._log_event(f"⚠️ Ép chốt kết quả do timeout ({len(self._video_session_buffer)}/{self.capture_frames_required} frame)", "WARNING")
                                if hasattr(self, "win") and self.win.winfo_exists():
                                    self.win.after(0, self._finalize_video_session)
                                else:
                                    self._finalize_video_session()
                            else:
                                # Không đủ số mẫu tối thiểu -> Hủy và dọn phiên
                                self._capture_session_active = False
                                self._video_session_buffer = []
                                self._capture_sample_records = []
                                self._last_detected_grade = "NO_APPLE"
                                status_text = "⏳ Chờ trigger cảm biến tiếp theo..."
                                self._log_event(f"⚠️ Hủy phiên chụp do timeout (chỉ có {len(self._video_session_buffer)} frame)", "ERROR")
                                self.send_timeout_to_plc()
                    else:
                        status_text = "⏳ Chờ trigger cảm biến để bắt đầu chụp 10 mẫu"


        except Exception as e:
            self._vision_fault_count += 1
            now_ts = time.time()
            if now_ts - float(self._last_vision_error_log_ts or 0.0) >= 1.0:
                self._last_vision_error_log_ts = now_ts
                self._log_event(
                    f"❌ Vision xử lý lỗi liên tiếp ({self._vision_fault_count}/{self._vision_fault_threshold}): {e}",
                    "ERROR"
                )
            if self._vision_fault_count >= self._vision_fault_threshold:
                self._set_system_state(self.STATE_FAULT, "Lỗi Vision liên tiếp", level="ERROR")
                self._cancel_active_capture_session("⚠️ Hủy phiên chụp do lỗi Vision")
            return

        # ─── PHẦN HIỂN THỊ CAMERA ───
        # Tất cả thao tác Tk phải chạy trên main thread; worker chỉ gửi dữ liệu đã tính xong.
        if hasattr(self, "win") and self.win.winfo_exists():
            payload_frame = frame.copy()
            payload_raw = raw_frame.copy()
            payload_detail = dict(detail_info)
            self._schedule_ui_frame_apply(
                (
                    payload_frame,
                    payload_raw,
                    payload_detail,
                    depth_info,
                    status_text,
                    grade,
                    ripeness,
                    is_static,
                )
            )

    def _apply_frame_result(self, frame, raw_frame, detail_info, depth_info, status_text, grade, ripeness, is_static=False):
        """Cập nhật toàn bộ widget Tk từ kết quả đã xử lý ở luồng camera."""
        try:
            import time

            current_time = time.time()
            if current_time - self.last_buffer_time >= 0.1:
                self.last_buffer_time = current_time
                self._update_snapshot_gallery(None, raw_frame.copy())

            self.lbl_grading_status.config(text=status_text, fg={
                "Grade-1": "#10B981",
                "Grade-2": "#F59E0B",
                "Grade-3": "#EF4444",
                "UNKNOWN": "#64748B",
                "NO_APPLE": "#64748B",
            }.get(grade, "#64748B"))
            self._update_criteria_panels(detail_info)

            h_f = frame.shape[0]
            w_f = frame.shape[1]
            color_map_bgr = {"Grade-1": (0, 255, 0), "Grade-2": (0, 255, 255), "Grade-3": (0, 0, 255)}
            cv2.putText(frame, f"STATUS: {grade}", (20, h_f - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_map_bgr.get(grade, (255,255,255)), 2)

            # Hiển thị khoảng cách Z (depth) ở góc trên cùng bên phải.
            z_text = "Z: N/A"
            z_sub = ""
            z_mm = None

            if isinstance(depth_info, dict):
                z_mm = depth_info.get("z_distance_mm", None)
                if z_mm is None:
                    z_m = depth_info.get("z_distance_m", None)
                    if z_m is not None:
                        z_mm = float(z_m) * 1000.0
                z_sub = str(depth_info.get("depth_status", "depth unavailable") or "")
            else:
                z_sub = str(getattr(self.camera, "depth_status", "depth unavailable") or "")

            if z_mm is None and isinstance(detail_info, dict):
                z_mm = detail_info.get("z_distance_mm", None)

            try:
                if z_mm is not None:
                    z_text = f"Z: {float(z_mm):.1f} mm"
            except Exception:
                z_text = "Z: N/A"

            (tw, th), baseline = cv2.getTextSize(z_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            x_text = max(10, w_f - tw - 20)
            y_text = 30
            cv2.rectangle(frame, (x_text - 8, y_text - th - 8), (x_text + tw + 8, y_text + baseline + 8), (0, 0, 0), -1)
            cv2.putText(frame, z_text, (x_text, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            if z_sub:
                sub_text = z_sub[:48]
                (stw, sth), sbase = cv2.getTextSize(sub_text, cv2.FONT_HERSHEY_SIMPLEX, 0.43, 1)
                sx = max(10, w_f - stw - 20)
                sy = y_text + 20
                cv2.putText(frame, sub_text, (sx, sy), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (190, 190, 190), 1)

            # Lấy kích thước thực tế của canvas để resize ảnh
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw < 10 or ch < 10:
                cw, ch = 640, 240

            color_res = cv2.resize(frame, (cw, ch))
            color_rgb = cv2.cvtColor(color_res, cv2.COLOR_BGR2RGB)

            raw_res = cv2.resize(raw_frame, (cw, ch))
            gray_res = cv2.cvtColor(raw_res, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray_res, 127, 255, cv2.THRESH_BINARY)
            f2_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            f1_rgb = color_rgb

            imgtk1 = ImageTk.PhotoImage(image=Image.fromarray(f1_rgb))
            imgtk2 = ImageTk.PhotoImage(image=Image.fromarray(f2_rgb))

            self.canvas.imgtk = imgtk1
            self.canvas_gray.imgtk = imgtk2
            self._update_canvas(imgtk1, imgtk2)
        except Exception as e:
            self._log_event(f"❌ Lỗi cập nhật UI frame: {e}", "ERROR")


    def _finalize_video_session(self):
        """Chốt kết quả phân loại sau khi đã thu thập đủ mẫu (10 tấm)."""
        if not hasattr(self, "_video_session_buffer") or len(self._video_session_buffer) == 0:
            return

        session_entries = self._video_decision_buffer if getattr(self, "_video_decision_buffer", None) else [
            {"grade": g, "quality_score": 1.0, "weight": 1.0} for g in self._video_session_buffer
        ]
        final_grade, decision_meta = self._fuse_session_decision(session_entries)
        method = decision_meta.get("method", "weighted_voting")
        reason = decision_meta.get("reason", "ok")
        valid_count = int(decision_meta.get("valid_count", 0))
        margin = float(decision_meta.get("margin", 0.0))

        track_meta = self._aggregate_track_decisions(self._capture_sample_records)
        self._session_track_results = track_meta
        if track_meta.get("total_tracks", 0) > 0:
            track_grade, track_decision_meta = self._fuse_session_decision(track_meta.get("decision_entries", []))
            final_grade = track_grade
            decision_meta = track_decision_meta
            method = f"track_{track_decision_meta.get('method', 'weighted_voting')}"
            reason = track_decision_meta.get("reason", "ok")
            valid_count = int(track_decision_meta.get("valid_count", 0))
            margin = float(track_decision_meta.get("margin", 0.0))

        for rec in self._capture_sample_records:
            tid = rec.get("track_id", None)
            track_item = None
            if self.single_fruit_station_mode:
                track_item = track_meta.get("tracks", {}).get("station_1")
            elif tid is not None:
                track_item = track_meta.get("tracks", {}).get(str(tid))

            rec["track_final_grade"] = track_item.get("final_grade", "") if track_item else ""
            rec["track_temporal_stability"] = float(track_item.get("temporal_stability", 0.0)) if track_item else 0.0
            rec["track_confidence"] = float(track_item.get("confidence", 0.0)) if track_item else 0.0
            rec["track_frames"] = int(track_item.get("frames", 0)) if track_item else 0
            rec["session_total_tracks"] = int(track_meta.get("total_tracks", 0))
            rec["session_temporal_stability"] = float(track_meta.get("temporal_stability", 0.0))
            rec["decision_method"] = method
        
        self._log_event(
            f"📸 ĐÃ CHỤP ĐỦ {len(self._video_session_buffer)} MẪU ({self._capture_session_source}). "
            f"Kết quả chốt: {final_grade}",
            "INFO"
        )

        # Cập nhật nhanh để người vận hành thấy ngay thay đổi trên panel trái.
        self._session_track_var.set(
            f"Session tracks: {int(track_meta.get('total_tracks', 0))}"
        )
        self._temporal_var.set(f"Temporal: {float(track_meta.get('temporal_stability', 0.0)):.2f}")
        self._track_method_var.set(f"Decision: {method}")

        self._last_10_capture_records = list(self._capture_sample_records[:self.capture_frames_required])
        history_id = self._save_to_sql(final_grade)
        if history_id and self._last_10_capture_records:
            ok, db_msg = self.db.save_session_10_records(history_id, self._last_10_capture_records)
            if not ok:
                self._log_event(db_msg, "ERROR")
        self.send_grade_to_plc(final_grade)
        self._video_session_buffer = []
        self._video_decision_buffer = []
        self._capture_sample_records = []

    def _update_criteria_panels(self, detail_info):
        """Cập nhật panel giám sát 3 tiêu chí TC1/TC2/TC3 theo dữ liệu realtime."""
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

            tc2_colors = {"Grade-1": "#1B5E20", "Grade-2": "#F57F17", "Grade-3": "#B71C1C", "A": "#1B5E20", "B": "#F57F17", "C": "#B71C1C"}
            self._tc2_grade_lbl.config(fg=tc2_colors.get(s_grade, "#616161"))

            # ── TC3: Độ tròn ──
            circ = detail_info.get("circularity", 0.0)
            sh_label = detail_info.get("shape_label", "---")
            sh_grade = detail_info.get("shape_grade", "---")

            self._tc3_progress['value'] = min(circ * 100, 100)
            self._tc3_circularity_var.set(f"Độ tròn: {circ:.2f}")
            self._tc3_grade_var.set(f"⇒ {sh_label}")

            tc3_colors = {"Grade-1": "#0284C7", "Grade-2": "#F57F17", "Grade-3": "#B71C1C"}
            self._tc3_grade_lbl.config(fg=tc3_colors.get(sh_grade, "#616161"))

            # ── Performance Metrics (Machine Vision Industrial) ──
            fps = detail_info.get("fps", 0.0)
            proc_time = detail_info.get("processing_time_ms", 0.0)
            
            self._fps_var.set(f"{fps:.1f}")
            self._proc_time_var.set(f"{proc_time:.1f} ms")
            
            # ── Motion Blur Detection ──
            blur_status = detail_info.get("blur_status", "N/A")
            blur_score = detail_info.get("blur_score", 0.0)
            is_blurry = detail_info.get("is_blurry", False)

            # Giữ biến monitor để tương thích logic cũ, không hiển thị text tracking trên panel.
            track_id = detail_info.get("track_id", None)
            active_tracks = int(detail_info.get("active_tracks", 0) or 0)
            tracker_mode = str(detail_info.get("yolo_tracker_mode", "predict"))
            if self.single_fruit_station_mode:
                if track_id is None:
                    self._track_live_var.set(f"Track: Station-Apple ({tracker_mode})")
                else:
                    self._track_live_var.set(f"Track: Station-Apple / ID {int(track_id)} ({tracker_mode})")
                self._track_active_var.set(f"Active tracks: {1 if active_tracks > 0 else 0}")
            else:
                if track_id is None:
                    self._track_live_var.set(f"Track: - ({tracker_mode})")
                else:
                    self._track_live_var.set(f"Track: ID {int(track_id)} ({tracker_mode})")
                self._track_active_var.set(f"Active tracks: {active_tracks}")
            
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
    #  BỘ ĐẾM PHÂN LOẠI (OSPREYX DYNAMIC)
    # ═══════════════════════════════════════════════════════
    def _update_counts(self, grade1, grade2, grade3):
        old_grade1 = int(self._count_vars["Grade-1"].get() or 0)
        old_grade2 = int(self._count_vars["Grade-2"].get() or 0)
        old_grade3 = int(self._count_vars["Grade-3"].get() or 0)

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
        
        # ── Thuật toán tính Throughput Rate (quá trình gạt thời gian thực trong 60s) ──
        import time
        now = time.time()
        if not hasattr(self, "_apple_timestamps"):
            self._apple_timestamps = []
            
        # Thêm timestamp nếu phát hiện quả táo mới của từng hạng
        if grade1 > old_grade1:
            self._apple_timestamps.append((now, "Grade-1"))
        if grade2 > old_grade2:
            self._apple_timestamps.append((now, "Grade-2"))
        if grade3 > old_grade3:
            self._apple_timestamps.append((now, "Grade-3"))
            
        # Lọc bỏ các bản ghi cũ hơn 60 giây
        self._apple_timestamps = [t for t in self._apple_timestamps if now - t[0] <= 60]
        
        # Đếm và cập nhật tốc độ
        for g_name in ["Grade-1", "Grade-2", "Grade-3"]:
            rate = sum(1 for t in self._apple_timestamps if t[1] == g_name)
            if hasattr(self, "_throughput_vars") and g_name in self._throughput_vars:
                # Nếu không có quả nào chạy thực tế trong 60s gần nhất nhưng tổng số lớn hơn 0, 
                # ta có thể hiện một tỉ lệ tượng trưng dựa trên hoạt động trước đó hoặc giữ số thực tế.
                # Để giao diện sinh động và khớp đúng tinh thần OspreyX, ta hiển thị chính xác số rate / MIN.
                self._throughput_vars[g_name].set(f"{rate} / MIN")

        # LƯU LỊCH SỬ (Tự động kích hoạt khi có táo mới được phân loại)
        if grade1 > old_grade1:
            self._save_to_sql("Grade-1")
        if grade2 > old_grade2:
            self._save_to_sql("Grade-2")
        if grade3 > old_grade3:
            self._save_to_sql("Grade-3")

    def _toggle_plc(self):
        if self.plc.connected:
            self._disconnect_plc()
        else:
            self._connect_plc()

    def _connect_plc(self):
        ip   = self.plc_ip_var.get().strip()
        try:
            rack = int(self.plc_rack_var.get() or 0)
            slot = int(self.plc_slot_var.get() or 1)
        except ValueError:
            messagebox.showerror("Lỗi nhập liệu", "Rack/Slot phải là số nguyên hợp lệ.")
            return

        if self._plc_connecting:
            return

        self._plc_connecting = True
        self.btn_connect.config(text="⏳ Đang kết nối...", state="disabled")
        if hasattr(self, 'btn_plc_quick'):
            self.btn_plc_quick.config(text="⏳ ĐANG KẾT NỐI...", state="disabled")

        self._log_event(f"🔄 Đang kết nối PLC tại {ip} (Rack={rack}, Slot={slot})...", "INFO")

        def _worker():
            success, msg = self.plc.connect(ip, rack, slot)
            self.win.after(0, lambda: self._on_plc_connect_result(success, msg, ip, rack, slot))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_plc_connect_result(self, success, msg, ip, rack, slot):
        """Nhận kết quả kết nối PLC từ worker thread để cập nhật UI an toàn."""
        self._plc_connecting = False

        if success:
            save_runtime_config({"runtime": {"plc_ip": ip, "plc_rack": rack, "plc_slot": slot}})
            self.btn_connect.config(text="🔌  Ngắt kết nối", state="normal",
                                    bg="#6A1B9A", activebackground="#4A148C")
            if hasattr(self, 'btn_plc_quick'):
                self.btn_plc_quick.config(text="🔌 NGẮT PLC", state="normal",
                                          bg=self.BTN_DANGER, activebackground=self.BTN_DANGER_ACTIVE)
            self.lbl_plc_status.config(text=f"🟢  PLC: {ip}", fg="#2E7D32")
            self._plc_sensor_prev = False
            self._last_counter_poll_ts = 0.0
            self._plc_fault_count = 0
            self._plc_poll_id = self.win.after(self._plc_poll_ms, self._poll_plc)
            self._log_event(f"🟢 Kết nối PLC thành công! IP={ip}, Rack={rack}, Slot={slot}", "SUCCESS")
            if self.camera.is_running():
                self._set_system_state(self.STATE_RUNNING, "PLC kết nối, hệ thống sẵn sàng", level="SUCCESS")
            else:
                self._set_system_state(self.STATE_DEGRADED, "PLC kết nối, đang chờ camera", level="INFO")
            return

        self.btn_connect.config(text="🔌  Kết nối PLC", state="normal",
                                bg="#1565C0", activebackground="#0D47A1")
        if hasattr(self, 'btn_plc_quick'):
            self.btn_plc_quick.config(text="🔌 KẾT NỐI PLC", state="normal",
                                      bg=self.BTN_PRIMARY, activebackground=self.BTN_PRIMARY_ACTIVE)
        self._log_event(f"Kết nối PLC thất bại ({ip})", "ERROR")
        self._log_event(msg, "ERROR")
        messagebox.showerror("Lỗi PLC", f"Không kết nối được PLC!\n\n{msg}")
        self._set_system_state(self.STATE_DEGRADED, "PLC không kết nối được", level="WARNING")

    def _disconnect_plc(self):
        if self._plc_poll_id:
            self.win.after_cancel(self._plc_poll_id)
            self._plc_poll_id = None
        self.plc.disconnect()
        self.btn_connect.config(text="🔌  Kết nối PLC",
                                bg="#1565C0", activebackground="#0D47A1")
        if hasattr(self, 'btn_plc_quick'):
            self.btn_plc_quick.config(text="🔌 KẾT NỐI PLC", bg=self.BTN_PRIMARY, activebackground=self.BTN_PRIMARY_ACTIVE)
        self.lbl_plc_status.config(text="⚫  PLC chưa kết nối", fg="#64748B")
        if hasattr(self, "lbl_sensor_status"):
            self.lbl_sensor_status.config(text="⚪ Sensor: OFF", fg="#64748B")
        self._log_event("⚫ Đã ngắt kết nối PLC.", "WARNING")
        if self.camera.is_running():
            self._set_system_state(self.STATE_DEGRADED, "Mất PLC, chạy camera preview", level="WARNING")
        else:
            self._set_system_state(self.STATE_SAFE_STOP, "PLC ngắt kết nối", level="INFO")

    def _poll_plc(self):
        """Polling PLC: đọc trigger cảm biến nhanh và bộ đếm định kỳ."""
        import time
        if not self.plc.connected:
            return

        now = time.time()
        plc_cycle_ok = True

        sensor_on = self.plc.read_sensor_trigger()
        if sensor_on is not None:
            prev = self._plc_sensor_prev  # Lưu trạng thái trước khi cập nhật

            # Cập nhật label UI
            if hasattr(self, "lbl_sensor_status"):
                self.lbl_sensor_status.config(
                    text=("🟢 Sensor: ON" if sensor_on else "⚪ Sensor: OFF"),
                    fg=("#16A34A" if sensor_on else "#64748B")
                )

            # CẠNH LÊN: False → True — bật đèn LED sensor + trigger chụp
            if sensor_on and not prev:
                import time as _t
                _ts = _t.strftime("%H:%M:%S", _t.localtime())
                self._log_event(f"📡 [SENSOR] Cảm biến TRIGGER lúc {_ts} — bắt đầu chụp mẫu", "SUCCESS")
                # Bật đèn ngay khi bit DB10.DBX0.3 = 1
                self._set_led("_led_sensor", True)
                self._start_capture_session("PLC")

            # ĐÃ BỎ CƠ CHẾ RE-TRIGGER ĐỂ TRÁNH CHỤP ẢNH LẦN 2 KHI CHƯA QUA KHỎI CẢM BIẾN
            # (Hệ thống sẽ chỉ kích hoạt chụp duy nhất khi có Cạnh Lên: False → True)

            # CẠNH XUỐNG: True → False — tắt đèn LED sensor
            elif not sensor_on and prev:
                self._set_led("_led_sensor", False)

            # Cập nhật trạng thái prev sau khi đã xử lý cạnh
            self._plc_sensor_prev = bool(sensor_on)

        else:
            plc_cycle_ok = False

        if now - self._last_counter_poll_ts >= 1.0:
            counters = self.plc.read_counters()
            if counters:
                grade1, grade2, grade3 = counters
                self._update_counts(grade1, grade2, grade3)
            else:
                plc_cycle_ok = False
            self._last_counter_poll_ts = now

        if plc_cycle_ok:
            if self._plc_fault_count > 0:
                self._plc_fault_count = 0
                if self.camera.is_running():
                    self._set_system_state(self.STATE_RUNNING, "PLC đã phục hồi", level="SUCCESS")
        else:
            self._plc_fault_count += 1
            if self._plc_fault_count >= self._plc_fault_threshold:
                self._set_system_state(self.STATE_FAULT, "Mất giao tiếp PLC", level="ERROR")
                self._cancel_active_capture_session("⚠️ Hủy phiên chụp do mất giao tiếp PLC")

        self._plc_poll_id = self.win.after(self._plc_poll_ms, self._poll_plc)

    def _start_capture_session(self, source):
        """Bắt đầu một phiên chụp: thu đủ 10 mẫu rồi dừng, chờ trigger kế tiếp."""
        import time
        if self.system_state == self.STATE_FAULT:
            self._log_event("⛔ Bỏ qua trigger vì hệ thống đang FAULT", "WARNING")
            return
        if self._capture_session_active:
            return

        self._capture_session_active = True
        self._capture_session_source = source
        self._capture_session_start_ts = time.time()
        self._video_session_buffer = []
        self._video_decision_buffer = []
        self._capture_sample_records = []
        self._session_track_results = {}
        self._reset_tracking_monitor()
        self._track_method_var.set("Decision: collecting...")
        self._session_finalized = False
        self._last_detected_grade = "NO_APPLE"

        # Đảm bảo reset các hàng đợi lịch sử/bộ lọc của bộ phân tích để tránh lag dữ liệu giữa các quả táo
        if hasattr(self, "analyzer") and self.analyzer is not None:
            if hasattr(self.analyzer, "tc1_ratio_history") and self.analyzer.tc1_ratio_history is not None:
                self.analyzer.tc1_ratio_history.clear()
            if hasattr(self.analyzer, "diameter_history") and self.analyzer.diameter_history is not None:
                self.analyzer.diameter_history.clear()
            if hasattr(self.analyzer, "blur_scores") and self.analyzer.blur_scores is not None:
                self.analyzer.blur_scores.clear()

        self._log_event(f"🔔 Trigger {source}: bắt đầu chụp {self.capture_frames_required} mẫu", "INFO")

    def _manual_sensor_trigger(self):
        """Nút test mô phỏng cảm biến tiệm cận khi chưa có cảm biến thật."""
        # Nếu đã kết nối PLC: giả lập đúng cảm biến bằng xung DB10.DBX0.3.
        if self.plc.connected:
            ok_on, msg_on = self.plc.write_db_bit(
                self.plc.PLC_DB_NUMBER,
                self.plc.PLC_GRADE_BYTE,
                self.plc.PLC_CAMERA_BIT,
                True,
            )
            if not ok_on:
                self._log_event(f"❌ Không ghi được DB10.DBX0.3 = 1: {msg_on}", "ERROR")
                if hasattr(self, "lbl_sensor_status"):
                    self.lbl_sensor_status.config(text="🔴 Sensor Test PLC: WRITE FAIL", fg="#DC2626")
                return

            self._log_event("🧪 Trigger TEST: DB10.DBX0.3 = 1", "SUCCESS")
            if hasattr(self, "lbl_sensor_status"):
                self.lbl_sensor_status.config(text="🧪 Sensor Test PLC: DB10.DBX0.3 = 1", fg="#7C3AED")

            # Giữ xung đủ dài để vòng poll bắt được cạnh lên, sau đó reset bit về 0.
            pulse_ms = max(300, int(getattr(self, "_plc_poll_ms", 200)) + 100)

            # Bật đèn ngay khi bit DB10.DBX0.3 = 1; đèn tắt trong callback khi bit về 0
            self._set_led("_led_sensor", True)

            def _reset_test_trigger_bit():
                ok_off, msg_off = self.plc.write_db_bit(
                    self.plc.PLC_DB_NUMBER,
                    self.plc.PLC_GRADE_BYTE,
                    self.plc.PLC_CAMERA_BIT,
                    False,
                )
                if ok_off:
                    self._log_event("🧪 Trigger TEST: DB10.DBX0.3 = 0", "INFO")
                    if hasattr(self, "lbl_sensor_status"):
                        self.lbl_sensor_status.config(text="⚪ Sensor: OFF", fg="#64748B")
                    # Tắt đèn đúng lúc bit DB về 0
                    self._set_led("_led_sensor", False)
                else:
                    self._log_event(f"⚠️ Không reset được DB10.DBX0.3 về 0: {msg_off}", "WARNING")

            self.win.after(pulse_ms, _reset_test_trigger_bit)
            return

        # Nếu chưa kết nối PLC: fallback mô phỏng nội bộ để test pipeline.
        self._pulse_led("_led_sensor", 500)
        self._start_capture_session("TEST")
        if hasattr(self, "lbl_sensor_status"):
            self.lbl_sensor_status.config(text="🧪 Sensor Test: TRIGGERED (LOCAL)", fg="#7C3AED")

    def _set_db_bit(self, db_number, byte, bit, value):
        """Ghi bit liên tục theo trạng thái nhấn nhả (Mô phỏng nút nhấn vật lý)."""
        if not getattr(self, "plc", None) or not self.plc.connected:
            if value: # Chỉ báo lỗi khi nhấn xuống, không báo khi nhả ra
                self._log_event(f"⚠️ Không thể gửi tín hiệu DB{db_number}.DBX{byte}.{bit} (Chưa kết nối PLC)", "WARNING")
            return
            
        ok, msg = self.plc.write_db_bit(db_number, byte, bit, value)
        if ok:
            btn_name = {0: "START", 1: "STOP", 2: "RESET"}.get(bit, f"DBX{byte}.{bit}")
            state_str = "ON (Nhấn)" if value else "OFF (Nhả)"
            self._log_event(f"📤 Lệnh {btn_name} -> {state_str}", "INFO")
        else:
            self._log_event(f"❌ Lỗi ghi PLC: {msg}", "ERROR")


    def _send_db10_test_value(self, value):
        """Gửi lệnh test DB10 từ UI với 4 giá trị 1/2/3/0."""
        if not self.plc.connected:
            msg = "PLC chưa kết nối, không thể gửi lệnh test PLC."
            self._log_event(f"⚠️ {msg}", "WARNING")
            if hasattr(self, "lbl_db10_test_status"):
                self.lbl_db10_test_status.config(text=f"⚠️ {msg}", fg="#B45309")
            return

        grade_map = {
            1: "Grade-1",
            2: "Grade-2",
            3: "Grade-3",
        }

        if value == 0:
            success, msg = self.plc.reset_grades()
            action_txt = "PLC <- 0 (reset bit grade)"
        else:
            grade = grade_map.get(value)
            if not grade:
                self._log_event(f"❌ Giá trị test PLC không hợp lệ: {value}", "ERROR")
                return
            success, msg = self.plc.set_grade(grade)
            action_txt = f"PLC <- {value} ({grade})"

        if success:
            self._log_event(f"✅ Test PLC thành công: {action_txt}", "SUCCESS")
            if hasattr(self, "lbl_db10_test_status"):
                self.lbl_db10_test_status.config(text=f"🟢 {action_txt}", fg="#059669")
            # Bật đèn ngay khi bit DB = 1; đèn sẽ tắt trong _reset_grade_bits_plc khi bit về 0
            if value == 1:
                self._set_led("_led_grade1", True)
            elif value == 2:
                self._set_led("_led_grade2", True)
            elif value == 3:
                self._set_led("_led_grade3", True)
            if value != 0:
                # Tạo xung ngắn giống luồng gửi grade tự động.
                self.win.after(500, self._reset_grade_bits_plc)
        else:
            self._log_event(f"❌ Test PLC thất bại ({action_txt}): {msg}", "ERROR")
            if hasattr(self, "lbl_db10_test_status"):
                self.lbl_db10_test_status.config(text=f"🔴 Lỗi: {msg}", fg="#DC2626")

    def send_grade_to_plc(self, grade):
        """Gửi tín hiệu phân loại xuống PLC (Tạo xung 500ms)."""
        if not self.plc.connected:
            self._set_system_state(self.STATE_DEGRADED, "Không gửi được grade vì PLC chưa kết nối", level="WARNING")
            return

        if self.system_state == self.STATE_FAULT:
            self._log_event("⛔ Chặn gửi grade do hệ thống đang FAULT", "ERROR")
            return

        success, msg = self.plc.set_grade(grade)
        if success:
            print(f"[PLC] Sent grade signal: {grade}")
            # Bật đèn ngay khi bit DB = 1; đèn tắt trong _reset_grade_bits_plc khi bit về 0
            _grade_led_map = {
                "Grade-1": "_led_grade1",
                "Grade-2": "_led_grade2",
                "Grade-3": "_led_grade3",
            }
            led_attr = _grade_led_map.get(grade)
            if led_attr:
                self._set_led(led_attr, True)
            self.win.after(500, self._reset_grade_bits_plc)
        else:
            self._log_event(f"❌ Lỗi gửi tín hiệu {grade} xuống PLC: {msg}", "ERROR")

    def _reset_grade_bits_plc(self):
        """Reset các bit phân loại về False và tắt đèn LED grade."""
        if self.plc.connected:
            self.plc.reset_grades()
        # Tắt tất cả đèn LED grade
        for attr in ("_led_grade1", "_led_grade2", "_led_grade3"):
            self._set_led(attr, False)

    def send_timeout_to_plc(self):
        """Gửi xung 500ms báo Timeout xuống PLC qua DB10.DBX0.4"""
        if not self.plc.connected:
            return
        # Ghi True vào DB10.DBX0.4
        success, msg = self.plc.write_db_bit(self.plc.PLC_DB_NUMBER, self.plc.PLC_GRADE_BYTE, 4, True)
        if success:
            self._log_event("📡 Đã gửi xung báo TIMEOUT (DB10.DBX0.4) tới PLC", "WARNING")
            self.win.after(500, self._reset_timeout_bit_plc)

    def _reset_timeout_bit_plc(self):
        if self.plc.connected:
            self.plc.write_db_bit(self.plc.PLC_DB_NUMBER, self.plc.PLC_GRADE_BYTE, 4, False)

    # ═══════════════════════════════════════════════════════
    #  LED INDICATOR HELPERS
    # ═══════════════════════════════════════════════════════

    def _set_led(self, attr_name, state: bool):
        """Bật (state=True) hoặc tắt (state=False) đèn LED indicator theo tên attribute."""
        led_info = getattr(self, attr_name, None)
        if led_info is None:
            return
        cv, circle_id, color_on = led_info
        if state:
            cv.itemconfig(circle_id, fill=color_on, outline=color_on)
        else:
            cv.itemconfig(circle_id, fill="#CBD5E1", outline="#94A3B8")

    def _pulse_led(self, attr_name, duration_ms: int = 500):
        """Bật đèn LED rồi tự động tắt sau duration_ms milliseconds."""
        self._set_led(attr_name, True)
        self.win.after(duration_ms, lambda: self._set_led(attr_name, False))

    # ═══════════════════════════════════════════════════════
    #  BỘ ĐẾM PHÂN LOẠI - DUPLICATE REMOVED
    # ═══════════════════════════════════════════════════════

    def _reset_counts(self):
        self._update_counts(0, 0, 0)

    def _refresh_system(self):
        """Làm mới toàn bộ trạng thái UI và đồng bộ DB."""
        self._refresh_stats_ui()
        self._refresh_history_table()
        self._video_session_buffer = []
        self._capture_sample_records = []
        self._last_10_capture_records = []
        self._session_track_results = {}
        self._reset_tracking_monitor()
        self._capture_session_active = False
        self._capture_session_source = ""
        self._last_detected_grade = "NO_APPLE"
        self._plc_fault_count = 0
        self._vision_fault_count = 0
        self._log_event("🔄 Hệ thống đã được làm mới và đồng bộ dữ liệu.", "INFO")
        
    def _clear_log(self):
        """Xóa trắng khung log và reset bộ đếm."""
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
        """Xuất log ra .txt hoặc .xlsx (kèm sheet 10 ảnh táo)."""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Workbook", "*.xlsx"), ("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                title="Lưu Event Log")
            if filepath:
                ext = os.path.splitext(filepath)[1].lower()

                if ext == ".txt":
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
                    return

                try:
                    from openpyxl import Workbook
                except Exception:
                    messagebox.showerror(
                        "Thiếu thư viện",
                        "Chưa có openpyxl để xuất Excel (.xlsx).\n"
                        "Cài bằng lệnh: pip install openpyxl"
                    )
                    return

                wb = Workbook()

                # Sheet 1: Event Log
                ws_log = wb.active
                ws_log.title = "Event_Log"
                ws_log.append(["Time", "Level", "Message", "Source"])
                for entry in getattr(self, "_log_entries", []):
                    ws_log.append([
                        entry.get("time", ""),
                        str(entry.get("tag", "")).upper(),
                        entry.get("msg", ""),
                        entry.get("source", ""),
                    ])

                # Sheet 2: 10 ảnh táo theo trigger gần nhất
                ws_apple = wb.create_sheet(title="10_Anh_Tao")
                ws_apple.append([
                    "Frame_Idx", "Timestamp", "Trigger_Source", "Grade",
                    "Ripeness_%", "Diameter_mm", "Shape", "YOLO_Conf"
                ])

                records = getattr(self, "_last_10_capture_records", [])
                if records:
                    for rec in records:
                        ws_apple.append([
                            rec.get("frame_idx", ""),
                            rec.get("timestamp", ""),
                            rec.get("trigger_source", ""),
                            rec.get("grade", ""),
                            rec.get("ripeness_pct", 0.0),
                            rec.get("diameter_mm", 0.0),
                            rec.get("shape", ""),
                            rec.get("yolo_conf", 0.0),
                        ])
                else:
                    ws_apple.append(["-", "-", "-", "-", "-", "-", "-", "-"])

                wb.save(filepath)
                self._log_event(f"💾 Đã xuất Excel 2 sheet (Event_Log + 10_Anh_Tao): {filepath}", "SUCCESS")
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
            ok, cfg_msg = save_runtime_config({
                "runtime": {
                    "analysis_interval_ms": interval,
                    "smooth_frames": smooth_val,
                    "plc_ip": self.plc_ip_var.get().strip() if hasattr(self, "plc_ip_var") else "192.168.0.1",
                    "plc_rack": int(self.plc_rack_var.get() or 0) if hasattr(self, "plc_rack_var") else 0,
                    "plc_slot": int(self.plc_slot_var.get() or 1) if hasattr(self, "plc_slot_var") else 1,
                    "orchard": self.current_orchard_var.get().strip(),
                    "lot": self.current_lot_var.get().strip(),
                    "default_camera_mode": self.cam_var.get() if hasattr(self, "cam_var") else "",
                    "astra_rgb_port_mode": self.astra_color_var.get() if hasattr(self, "astra_color_var") else "",
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được config: {cfg_msg}", "WARNING")
            self._log_event(f"⚙️ Đã lưu cấu hình: Smoothing={smooth_val} frames, Interval={interval}ms", "SUCCESS")
            messagebox.showinfo("Thành công", "Đã lưu toàn bộ cấu hình hệ thống!")
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

        var_good = tk.IntVar(value=int(self.analyzer.RIPENESS_GOOD_THRESH))
        var_medium = tk.IntVar(value=int(self.analyzer.RIPENESS_MEDIUM_THRESH))

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
            
            self.analyzer.RIPENESS_GOOD_THRESH = val_good
            self.analyzer.RIPENESS_MEDIUM_THRESH = val_medium
            ok, cfg_msg = save_runtime_config({
                "analyzer": {
                    "ripeness": {
                        "good_thresh": val_good,
                        "medium_thresh": val_medium
                    }
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được TC1 vào config: {cfg_msg}", "WARNING")
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
            ok, cfg_msg = save_runtime_config({
                "analyzer": {
                    "size": {
                        "large_mm": val_large,
                        "medium_mm": val_medium
                    }
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được TC2 vào config: {cfg_msg}", "WARNING")
            self._update_grade_descriptions()
            self._log_event(f"⚙️ Cập nhật TC2: Loại 1 (≥{val_large}mm), Loại 2 (≥{val_medium}mm)", "INFO")
            top.destroy()

        top.bind('<Return>', save)
        tk.Button(top, text="LƯU CẤU HÌNH (Enter)", bg="#1565C0", fg="white", font=("Arial", 9, "bold"), cursor="hand2", command=save, padx=20, pady=5, relief="flat").pack(pady=15)

    def _open_tc3_settings(self, event=None):
        """Mở cửa sổ cấu hình ngưỡng TC3 (Độ tròn)."""
        top = tk.Toplevel(self.win)
        top.title("Cấu hình TC3 - Độ tròn quả")
        top.geometry("360x260")
        top.transient(self.win)
        top.grab_set()
        top.config(bg="#F8FAFC")

        var_good = tk.DoubleVar(value=float(self.analyzer.SHAPE_GOOD_THRESH))
        var_medium = tk.DoubleVar(value=float(self.analyzer.SHAPE_MEDIUM_THRESH))

        tk.Label(top, text="Ngưỡng 1 (Độ tròn ≥):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#0369A1").pack(pady=(15, 0))
        f1 = tk.Frame(top, bg="#F8FAFC")
        f1.pack()
        tk.Scale(
            f1,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            length=200,
            bg="#F8FAFC",
            highlightthickness=0,
            variable=var_good,
            showvalue=False,
        ).pack(side="left")
        ttk.Spinbox(
            f1,
            from_=0.0,
            to=1.0,
            increment=0.01,
            textvariable=var_good,
            width=6,
            font=("Consolas", 10),
            format="%.2f",
        ).pack(side="left", padx=(5, 0))

        tk.Label(top, text="Ngưỡng 2 (Độ tròn ≥):", bg="#F8FAFC", font=("Arial", 9, "bold"), fg="#0284C7").pack(pady=(10, 0))
        f2 = tk.Frame(top, bg="#F8FAFC")
        f2.pack()
        tk.Scale(
            f2,
            from_=0.0,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            length=200,
            bg="#F8FAFC",
            highlightthickness=0,
            variable=var_medium,
            showvalue=False,
        ).pack(side="left")
        ttk.Spinbox(
            f2,
            from_=0.0,
            to=1.0,
            increment=0.01,
            textvariable=var_medium,
            width=6,
            font=("Consolas", 10),
            format="%.2f",
        ).pack(side="left", padx=(5, 0))

        tk.Label(
            top,
            text="Gợi ý: Ngưỡng 1 > Ngưỡng 2. Ví dụ 0.88 và 0.78",
            bg="#F8FAFC",
            fg="#64748B",
            font=("Arial", 8),
        ).pack(pady=(10, 0))

        def save(event=None):
            try:
                val_good = float(var_good.get())
                val_medium = float(var_medium.get())
            except (tk.TclError, ValueError):
                messagebox.showerror("Lỗi", "Vui lòng nhập số hợp lệ!", parent=top)
                return

            if not (0.0 <= val_medium <= 1.0 and 0.0 <= val_good <= 1.0):
                messagebox.showerror("Lỗi", "Ngưỡng độ tròn phải nằm trong khoảng 0.00 đến 1.00!", parent=top)
                return

            if val_medium >= val_good:
                messagebox.showerror("Lỗi", "Ngưỡng 1 phải lớn hơn Ngưỡng 2!", parent=top)
                return

            val_good = round(val_good, 2)
            val_medium = round(val_medium, 2)

            self.analyzer.SHAPE_GOOD_THRESH = val_good
            self.analyzer.SHAPE_MEDIUM_THRESH = val_medium
            ok, cfg_msg = save_runtime_config({
                "analyzer": {
                    "shape": {
                        "good_thresh": val_good,
                        "medium_thresh": val_medium
                    }
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được TC3 vào config: {cfg_msg}", "WARNING")
            self._log_event(f"⚙️ Cập nhật TC3: Loại 1 (≥{val_good:.2f}), Loại 2 (≥{val_medium:.2f})", "INFO")
            top.destroy()

        top.bind('<Return>', save)
        tk.Button(top, text="LƯU CẤU HÌNH (Enter)", bg="#1565C0", fg="white", font=("Arial", 9, "bold"), cursor="hand2", command=save, padx=20, pady=5, relief="flat").pack(pady=15)

    def _update_grade_descriptions(self):
        """Cập nhật giao diện text cho 3 loại khi cấu hình thay đổi."""
        t1_good = self.analyzer.RIPENESS_GOOD_THRESH
        t1_med = self.analyzer.RIPENESS_MEDIUM_THRESH
        t2_large = self.analyzer.SIZE_THRESHOLDS["large"]
        t2_med = self.analyzer.SIZE_THRESHOLDS["medium"]

        if "Grade-1" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-1"].config(text=f"TC1 (≥{t1_good}%) & TC2 (≥{t2_large}mm)")
        if "Grade-2" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-2"].config(text=f"TC1 ({t1_med}-{t1_good-1}%) hoặc TC2 ({t2_med}-{t2_large-1}mm)")
        if "Grade-3" in self._grade_desc_labels:
            self._grade_desc_labels["Grade-3"].config(text=f"TC1 (<{t1_med}%) hoặc TC2 (<{t2_med}mm)")

    def _open_decision_rule_table_3tc(self):
        """Hiển thị bảng luật quyết định 3 tiêu chí và cho phép chỉnh tham số trực tiếp."""
        top = tk.Toplevel(self.win)
        top.title("Bảng luật quyết định - 3 tiêu chí x 3 mức")
        top.geometry("980x700")
        top.minsize(900, 560)
        top.transient(self.win)
        top.grab_set()
        top.configure(bg="#F8FAFC")

        container = tk.Frame(top, bg="#F8FAFC")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            container,
            text="BẢNG LUẬT QUYẾT ĐỊNH TỔNG HỢP 3 TIÊU CHÍ",
            font=("Arial", 11, "bold"),
            fg="#0F172A",
            bg="#F8FAFC",
        ).pack(anchor="w")

        # Khối tham số có thể chỉnh để tái tạo bảng theo luật mới.
        params_box = tk.LabelFrame(
            container,
            text="Tham số bảng luật (có thể thay đổi)",
            bg="#F8FAFC",
            fg="#0F172A",
            font=("Arial", 9, "bold"),
            padx=8,
            pady=6,
        )
        params_box.pack(fill="x", pady=(6, 8))

        runtime_cfg_latest = load_runtime_config().get("runtime", {})
        decision_rule_cfg = runtime_cfg_latest.get("decision_rule_table", {})

        t1_good_var = tk.IntVar(value=int(self.analyzer.RIPENESS_GOOD_THRESH))
        t1_med_var = tk.IntVar(value=int(self.analyzer.RIPENESS_MEDIUM_THRESH))
        t2_large_var = tk.IntVar(value=int(self.analyzer.SIZE_THRESHOLDS.get("large", 80)))
        t2_med_var = tk.IntVar(value=int(self.analyzer.SIZE_THRESHOLDS.get("medium", 60)))
        t3_good_var = tk.DoubleVar(value=float(self.analyzer.SHAPE_GOOD_THRESH))
        t3_med_var = tk.DoubleVar(value=float(self.analyzer.SHAPE_MEDIUM_THRESH))

        score_g1_var = tk.IntVar(value=int(decision_rule_cfg.get("score_grade1", 3)))
        score_g2_var = tk.IntVar(value=int(decision_rule_cfg.get("score_grade2", 2)))
        score_g3_var = tk.IntVar(value=int(decision_rule_cfg.get("score_grade3", 1)))
        min_g1_var = tk.IntVar(value=int(decision_rule_cfg.get("min_grade1", 8)))
        min_g2_var = tk.IntVar(value=int(decision_rule_cfg.get("min_grade2", 5)))

        def _add_param(row, col, label, var, from_, to_, inc=1.0, width=7, fmt=None):
            tk.Label(
                params_box,
                text=label,
                bg="#F8FAFC",
                fg="#334155",
                font=("Arial", 9),
            ).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=3)
            spin_kwargs = {
                "from_": from_,
                "to": to_,
                "textvariable": var,
                "width": width,
                "increment": inc,
                "font": ("Consolas", 9),
            }
            if fmt is not None:
                spin_kwargs["format"] = fmt
            ttk.Spinbox(params_box, **spin_kwargs).grid(row=row, column=col + 1, sticky="w", padx=(0, 12), pady=3)

        _add_param(0, 0, "TC1 Mức 1 (%):", t1_good_var, 0, 100)
        _add_param(0, 2, "TC1 Mức 2 (%):", t1_med_var, 0, 100)
        _add_param(0, 4, "TC2 Mức 1 (mm):", t2_large_var, 0, 200)
        _add_param(0, 6, "TC2 Mức 2 (mm):", t2_med_var, 0, 200)

        _add_param(1, 0, "TC3 Mức 1:", t3_good_var, 0.0, 1.0, 0.01, width=8, fmt="%.2f")
        _add_param(1, 2, "TC3 Mức 2:", t3_med_var, 0.0, 1.0, 0.01, width=8, fmt="%.2f")
        _add_param(1, 4, "Điểm Grade-1:", score_g1_var, 1, 9)
        _add_param(1, 6, "Điểm Grade-2:", score_g2_var, 1, 9)

        _add_param(2, 0, "Điểm Grade-3:", score_g3_var, 1, 9)
        _add_param(2, 2, "Ngưỡng Grade-1 (>=):", min_g1_var, 1, 27)
        _add_param(2, 4, "Ngưỡng Grade-2 (>=):", min_g2_var, 1, 27)

        note_var = tk.StringVar(value="")
        tk.Label(
            container,
            textvariable=note_var,
            font=("Arial", 9),
            fg="#334155",
            bg="#F8FAFC",
            justify="left",
            wraplength=940,
        ).pack(anchor="w", pady=(0, 6))

        cols = ("stt", "tc1", "tc2", "tc3", "tong_diem", "ket_luan")
        tree = ttk.Treeview(container, columns=cols, show="headings", height=20)
        tree.heading("stt", text="STT")
        tree.heading("tc1", text="TC1 - Độ chín (%Đỏ/%Vàng/%Xanh)")
        tree.heading("tc2", text="TC2 - Đường kính (mm)")
        tree.heading("tc3", text="TC3 - Độ tròn")
        tree.heading("tong_diem", text="Tổng điểm")
        tree.heading("ket_luan", text="Kết luận")

        tree.column("stt", width=55, anchor="center", stretch=False)
        tree.column("tc1", width=330, anchor="w")
        tree.column("tc2", width=220, anchor="w")
        tree.column("tc3", width=220, anchor="w")
        tree.column("tong_diem", width=95, anchor="center", stretch=False)
        tree.column("ket_luan", width=160, anchor="center")

        tree.tag_configure("grade1", foreground="#166534")
        tree.tag_configure("grade2", foreground="#B45309")
        tree.tag_configure("grade3", foreground="#B91C1C")

        ysb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=ysb.set)

        table_wrap = tk.Frame(container, bg="#F8FAFC")
        table_wrap.pack(fill="both", expand=True)
        tree.pack(in_=table_wrap, side="left", fill="both", expand=True)
        ysb.pack(in_=table_wrap, side="right", fill="y")

        def rebuild_table():
            try:
                t1_good = int(t1_good_var.get())
                t1_med = int(t1_med_var.get())
                t2_large = int(t2_large_var.get())
                t2_med = int(t2_med_var.get())
                t3_good = float(t3_good_var.get())
                t3_med = float(t3_med_var.get())
                score_g1 = int(score_g1_var.get())
                score_g2 = int(score_g2_var.get())
                score_g3 = int(score_g3_var.get())
                min_g1 = int(min_g1_var.get())
                min_g2 = int(min_g2_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror("Lỗi", "Tham số không hợp lệ. Vui lòng kiểm tra lại.", parent=top)
                return

            if t1_med >= t1_good:
                messagebox.showerror("Lỗi", "TC1: Mức 1 phải lớn hơn Mức 2.", parent=top)
                return
            if t2_med >= t2_large:
                messagebox.showerror("Lỗi", "TC2: Mức 1 phải lớn hơn Mức 2.", parent=top)
                return
            if not (0.0 <= t3_med < t3_good <= 1.0):
                messagebox.showerror("Lỗi", "TC3: cần thỏa 0.00 <= Mức 2 < Mức 1 <= 1.00.", parent=top)
                return
            if not (score_g1 > score_g2 > score_g3):
                messagebox.showerror("Lỗi", "Điểm phải theo thứ tự: Grade-1 > Grade-2 > Grade-3.", parent=top)
                return
            if min_g2 >= min_g1:
                messagebox.showerror("Lỗi", "Ngưỡng Grade-1 phải lớn hơn ngưỡng Grade-2.", parent=top)
                return

            for item in tree.get_children():
                tree.delete(item)

            tc1_map = {
                1: f"M1 - Chín cao: Đỏ >= {t1_good}% (Vàng+Xanh <= {100 - t1_good}%)",
                2: f"M2 - Trung gian: {t1_med}% <= Đỏ < {t1_good}%",
                3: f"M3 - Chưa chín: Đỏ < {t1_med}% (Vàng/Xanh chiếm ưu thế)",
            }
            tc2_map = {
                1: f"M1 - Lớn: ĐK >= {t2_large} mm",
                2: f"M2 - Vừa: {t2_med} <= ĐK < {t2_large} mm",
                3: f"M3 - Nhỏ: ĐK < {t2_med} mm",
            }
            tc3_map = {
                1: f"M1 - Tròn tốt: Độ tròn >= {t3_good:.2f}",
                2: f"M2 - Trung bình: {t3_med:.2f} <= Độ tròn < {t3_good:.2f}",
                3: f"M3 - Méo: Độ tròn < {t3_med:.2f}",
            }
            grade_by_level = {1: "Grade-1", 2: "Grade-2", 3: "Grade-3"}
            score_by_grade = {"Grade-1": score_g1, "Grade-2": score_g2, "Grade-3": score_g3}

            stt = 1
            for lv1 in (1, 2, 3):
                for lv2 in (1, 2, 3):
                    for lv3 in (1, 2, 3):
                        g1 = grade_by_level[lv1]
                        g2 = grade_by_level[lv2]
                        g3 = grade_by_level[lv3]
                        total_score = score_by_grade[g1] + score_by_grade[g2] + score_by_grade[g3]

                        if total_score >= min_g1:
                            final_grade = "Grade-1"
                        elif total_score >= min_g2:
                            final_grade = "Grade-2"
                        else:
                            final_grade = "Grade-3"

                        row_tag = "grade1" if final_grade == "Grade-1" else ("grade2" if final_grade == "Grade-2" else "grade3")
                        tree.insert(
                            "",
                            "end",
                            values=(
                                stt,
                                tc1_map[lv1],
                                tc2_map[lv2],
                                tc3_map[lv3],
                                total_score,
                                final_grade,
                            ),
                            tags=(row_tag,),
                        )
                        stt += 1

            note_var.set(
                f"TC1: Đỏ+Vàng+Xanh = 100%. Dùng %Đỏ để xếp mức (M1/M2/M3). | TC2 theo đường kính mm | TC3 theo chỉ số độ tròn (0-1). | Điểm: G1={score_g1}, G2={score_g2}, G3={score_g3} | Ngưỡng kết luận: Grade-1 if >={min_g1}, Grade-2 if >={min_g2}, còn lại Grade-3\n\n"
                f"💡 LUẬT QUYẾT ĐỊNH 10 FRAMES (khi quả táo xoay trên con lăn):\n"
                f"• Bước 1: Tự động loại bỏ các bức ảnh bị mờ hoặc bị con lăn che khuất.\n"
                f"• Bước 2: Đếm và lấy hạng táo (Grade 1/2/3) xuất hiện nhiều nhất làm hạng kết luận.\n"
                f"• Bước 3: Nếu tỉ lệ các hạng quá sát nút nhau (không chênh lệch rõ rệt), hệ thống tự động ưu tiên chọn hạng xấu hơn để đảm bảo an toàn sản phẩm."
            )




            # Lưu tự động ngay khi cập nhật bảng để lần mở sau giữ đúng giá trị mới nhất.
            self.analyzer.RIPENESS_GOOD_THRESH = t1_good
            self.analyzer.RIPENESS_MEDIUM_THRESH = t1_med
            self.analyzer.SIZE_THRESHOLDS["large"] = t2_large
            self.analyzer.SIZE_THRESHOLDS["medium"] = t2_med
            self.analyzer.SHAPE_GOOD_THRESH = round(t3_good, 2)
            self.analyzer.SHAPE_MEDIUM_THRESH = round(t3_med, 2)

            ok, cfg_msg = save_runtime_config({
                "analyzer": {
                    "ripeness": {"good_thresh": t1_good, "medium_thresh": t1_med},
                    "size": {"large_mm": t2_large, "medium_mm": t2_med},
                    "shape": {"good_thresh": round(t3_good, 2), "medium_thresh": round(t3_med, 2)},
                },
                "runtime": {
                    "decision_rule_table": {
                        "score_grade1": score_g1,
                        "score_grade2": score_g2,
                        "score_grade3": score_g3,
                        "min_grade1": min_g1,
                        "min_grade2": min_g2,
                    }
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không tự động lưu được bảng luật: {cfg_msg}", "WARNING")

        def save_thresholds_to_system():
            try:
                t1_good = int(t1_good_var.get())
                t1_med = int(t1_med_var.get())
                t2_large = int(t2_large_var.get())
                t2_med = int(t2_med_var.get())
                t3_good = round(float(t3_good_var.get()), 2)
                t3_med = round(float(t3_med_var.get()), 2)
                score_g1 = int(score_g1_var.get())
                score_g2 = int(score_g2_var.get())
                score_g3 = int(score_g3_var.get())
                min_g1 = int(min_g1_var.get())
                min_g2 = int(min_g2_var.get())
            except (tk.TclError, ValueError):
                messagebox.showerror("Lỗi", "Không thể lưu vì tham số ngưỡng không hợp lệ.", parent=top)
                return

            if t1_med >= t1_good or t2_med >= t2_large or not (0.0 <= t3_med < t3_good <= 1.0):
                messagebox.showerror("Lỗi", "Tham số ngưỡng chưa đúng, vui lòng kiểm tra lại.", parent=top)
                return
            if not (score_g1 > score_g2 > score_g3):
                messagebox.showerror("Lỗi", "Điểm phải theo thứ tự: Grade-1 > Grade-2 > Grade-3.", parent=top)
                return
            if min_g2 >= min_g1:
                messagebox.showerror("Lỗi", "Ngưỡng Grade-1 phải lớn hơn ngưỡng Grade-2.", parent=top)
                return

            self.analyzer.RIPENESS_GOOD_THRESH = t1_good
            self.analyzer.RIPENESS_MEDIUM_THRESH = t1_med
            self.analyzer.SIZE_THRESHOLDS["large"] = t2_large
            self.analyzer.SIZE_THRESHOLDS["medium"] = t2_med
            self.analyzer.SHAPE_GOOD_THRESH = t3_good
            self.analyzer.SHAPE_MEDIUM_THRESH = t3_med

            ok, cfg_msg = save_runtime_config({
                "analyzer": {
                    "ripeness": {"good_thresh": t1_good, "medium_thresh": t1_med},
                    "size": {"large_mm": t2_large, "medium_mm": t2_med},
                    "shape": {"good_thresh": t3_good, "medium_thresh": t3_med},
                },
                "runtime": {
                    "decision_rule_table": {
                        "score_grade1": score_g1,
                        "score_grade2": score_g2,
                        "score_grade3": score_g3,
                        "min_grade1": min_g1,
                        "min_grade2": min_g2,
                    }
                }
            })
            if not ok:
                self._log_event(f"⚠️ Không lưu được bảng luật vào config: {cfg_msg}", "WARNING")
                messagebox.showwarning("Cảnh báo", "Đã cập nhật trong phiên chạy, nhưng lưu config thất bại.", parent=top)
                return

            self._update_grade_descriptions()
            self._log_event("⚙️ Đã lưu tham số bảng luật (TC1/TC2/TC3 + điểm + ngưỡng kết luận).", "INFO")
            messagebox.showinfo("Thành công", "Đã lưu tham số bảng luật. Lần chạy sau sẽ giữ nguyên giá trị đã lưu.", parent=top)

        actions = tk.Frame(container, bg="#F8FAFC")
        actions.pack(fill="x", pady=(8, 0))

        tk.Button(
            actions,
            text="CẬP NHẬT BẢNG",
            font=("Arial", 9, "bold"),
            fg="#FFFFFF",
            bg="#0EA5E9",
            activebackground="#0284C7",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            command=rebuild_table,
            padx=14,
            pady=4,
        ).pack(side="left")

        tk.Button(
            actions,
            text="LƯU NGƯỠNG VÀO HỆ THỐNG",
            font=("Arial", 9, "bold"),
            fg="#FFFFFF",
            bg="#16A34A",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            command=save_thresholds_to_system,
            padx=14,
            pady=4,
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            actions,
            text="ĐÓNG",
            font=("Arial", 9, "bold"),
            fg="#FFFFFF",
            bg="#334155",
            activebackground="#1E293B",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            command=top.destroy,
            padx=16,
            pady=4,
        ).pack(side="right")

        rebuild_table()

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

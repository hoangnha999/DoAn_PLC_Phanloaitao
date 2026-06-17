import cv2
import numpy as np
import time
from collections import deque

try:
    from config.runtime_config import load_runtime_config
except ImportError:
    def load_runtime_config():
        return {}

from Processing.analyzer_modules.yolo_runtime import initialize_yolo_runtime


# Module bootstrap chịu trách nhiệm:
# 1) Đọc cấu hình runtime từ file JSON.
# 2) Ánh xạ cấu hình vào state của FruitAnalyzer.
# 3) Khởi tạo các cấu trúc runtime (deque, YOLO, bộ đo hiệu năng).


def apply_astra_pro_outdoor_profile(analyzer):
    """Áp profile tham số cho bối cảnh ngoài trời (Astra Pro)."""
    # Profile này là bộ override bảo thủ cho môi trường ngoài trời,
    # giúp hạn chế sai số khi ánh sáng mạnh và độ sâu biến thiên nhanh.
    p = analyzer.ASTRA_PRO_OUTDOOR_PROFILE
    analyzer.RIPENESS_GOOD_THRESH = int(p["ripeness_good_thresh"])
    analyzer.RIPENESS_MEDIUM_THRESH = int(p["ripeness_medium_thresh"])
    analyzer.PIXEL_TO_MM = float(p["pixel_to_mm"])
    analyzer.DEPTH_REFERENCE_MM = float(p["depth_reference_mm"])
    analyzer.ENABLE_DEPTH_SIZE_COMPENSATION = bool(p["enable_depth_size_compensation"])
    analyzer.REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT = bool(
        p.get("require_depth_for_size_measurement", analyzer.REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT)
    )
    analyzer.SIZE_CALIBRATION_GAIN = float(p["size_calibration_gain"])
    analyzer.MIN_APPLE_AREA_RATIO = float(p["min_apple_area_ratio"])
    analyzer.YOLO_CONF_THRESH = float(p["yolo_conf_thresh"])
    analyzer.YOLO_MIN_BBOX_AREA_RATIO = float(p["yolo_min_bbox_area_ratio"])
    analyzer.YOLO_MAX_BBOX_AREA_RATIO = float(p.get("yolo_max_bbox_area_ratio", analyzer.YOLO_MAX_BBOX_AREA_RATIO))
    analyzer.YOLO_MIN_APPLE_COLOR_RATIO = float(
        p.get("yolo_min_apple_color_ratio", analyzer.YOLO_MIN_APPLE_COLOR_RATIO)
    )
    analyzer.blur_threshold = float(p["blur_threshold"])
    # Nạp CLAHE từ profile ngoài trời (clip thường cao hơn trong nhà).
    analyzer.ENABLE_CLAHE = bool(p.get("enable_clahe", analyzer.ENABLE_CLAHE))
    analyzer.CLAHE_CLIP_LIMIT = float(p.get("clahe_clip_limit", analyzer.CLAHE_CLIP_LIMIT))
    analyzer.CLAHE_TILE_SIZE = int(p.get("clahe_tile_size", analyzer.CLAHE_TILE_SIZE))
    analyzer.CLAHE_APPLY_TO_YOLO = bool(p.get("clahe_apply_to_yolo", analyzer.CLAHE_APPLY_TO_YOLO))
    analyzer.CLAHE_APPLY_TO_HSV = bool(p.get("clahe_apply_to_hsv", analyzer.CLAHE_APPLY_TO_HSV))


def initialize_analyzer_state(analyzer):
    """Khởi tạo toàn bộ trạng thái runtime cho FruitAnalyzer từ config + mặc định class."""
    # Lấy nhánh analyzer trong runtime config; nếu thiếu thì dùng dict rỗng.
    analyzer_cfg = load_runtime_config().get("analyzer", {})

    # Tách từng nhóm cấu hình theo đúng miền chức năng.
    ripeness_cfg = analyzer_cfg.get("ripeness", {})
    shape_cfg = analyzer_cfg.get("shape", {})
    size_cfg = analyzer_cfg.get("size", {})
    hsv_cfg = analyzer_cfg.get("hsv", {})
    seg_cfg = analyzer_cfg.get("segmentation", {})
    yolo_cfg = analyzer_cfg.get("yolo", {})
    blur_cfg = analyzer_cfg.get("blur", {})
    # Nạp ngưỡng phân hạng TC1/TC3.
    analyzer.RIPENESS_GOOD_THRESH = int(ripeness_cfg.get("good_thresh", analyzer.RIPENESS_GOOD_THRESH))
    analyzer.RIPENESS_MEDIUM_THRESH = int(ripeness_cfg.get("medium_thresh", analyzer.RIPENESS_MEDIUM_THRESH))
    analyzer.SHAPE_GOOD_THRESH = float(shape_cfg.get("good_thresh", analyzer.SHAPE_GOOD_THRESH))
    analyzer.SHAPE_MEDIUM_THRESH = float(shape_cfg.get("medium_thresh", analyzer.SHAPE_MEDIUM_THRESH))

    # Nạp tham số TC2 (kích thước + ổn định hóa theo depth).
    analyzer.SIZE_THRESHOLDS = {
        "large": float(size_cfg.get("large_mm", analyzer.SIZE_THRESHOLDS["large"])),
        "medium": float(size_cfg.get("medium_mm", analyzer.SIZE_THRESHOLDS["medium"])),
    }
    analyzer.PIXEL_TO_MM = float(size_cfg.get("pixel_to_mm", analyzer.PIXEL_TO_MM))
    analyzer.DEPTH_REFERENCE_MM = float(size_cfg.get("depth_reference_mm", analyzer.DEPTH_REFERENCE_MM))
    analyzer.ENABLE_DEPTH_SIZE_COMPENSATION = bool(
        size_cfg.get("enable_depth_size_compensation", analyzer.ENABLE_DEPTH_SIZE_COMPENSATION)
    )
    analyzer.REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT = bool(
        size_cfg.get("require_depth_for_size_measurement", analyzer.REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT)
    )
    analyzer.SIZE_CALIBRATION_GAIN = float(size_cfg.get("size_calibration_gain", analyzer.SIZE_CALIBRATION_GAIN))
    analyzer.DEPTH_SMOOTH_WINDOW = int(size_cfg.get("depth_smooth_window", analyzer.DEPTH_SMOOTH_WINDOW))
    analyzer.DEPTH_SMOOTH_WINDOW = max(3, min(25, analyzer.DEPTH_SMOOTH_WINDOW))
    analyzer.DEPTH_MAX_DELTA_MM = float(size_cfg.get("depth_max_delta_mm", analyzer.DEPTH_MAX_DELTA_MM))
    analyzer.DEPTH_HOLD_FRAMES = int(size_cfg.get("depth_hold_frames", analyzer.DEPTH_HOLD_FRAMES))
    analyzer.DEPTH_HOLD_FRAMES = max(0, min(30, analyzer.DEPTH_HOLD_FRAMES))
    analyzer.ENABLE_DIAMETER_STABILIZER = bool(
        size_cfg.get("enable_diameter_stabilizer", analyzer.ENABLE_DIAMETER_STABILIZER)
    )
    analyzer.DIAMETER_MM_SMOOTH_WINDOW = int(
        size_cfg.get("diameter_mm_smooth_window", analyzer.DIAMETER_MM_SMOOTH_WINDOW)
    )
    analyzer.DIAMETER_MM_SMOOTH_WINDOW = max(3, min(25, analyzer.DIAMETER_MM_SMOOTH_WINDOW))
    analyzer.DIAMETER_MM_ALPHA = float(size_cfg.get("diameter_mm_alpha", analyzer.DIAMETER_MM_ALPHA))
    analyzer.DIAMETER_MM_ALPHA = float(np.clip(analyzer.DIAMETER_MM_ALPHA, 0.05, 0.9))
    analyzer.DIAMETER_MM_MAX_STEP = float(size_cfg.get("diameter_mm_max_step", analyzer.DIAMETER_MM_MAX_STEP))
    analyzer.DIAMETER_MM_MAX_STEP = max(0.1, min(15.0, analyzer.DIAMETER_MM_MAX_STEP))

    # Nạp ngưỡng HSV cho các dải màu chính.
    analyzer.LOWER_RED1 = np.array(hsv_cfg.get("red1_lower", analyzer.LOWER_RED1.tolist()), dtype=np.uint8)
    analyzer.UPPER_RED1 = np.array(hsv_cfg.get("red1_upper", analyzer.UPPER_RED1.tolist()), dtype=np.uint8)
    analyzer.LOWER_RED2 = np.array(hsv_cfg.get("red2_lower", analyzer.LOWER_RED2.tolist()), dtype=np.uint8)
    analyzer.UPPER_RED2 = np.array(hsv_cfg.get("red2_upper", analyzer.UPPER_RED2.tolist()), dtype=np.uint8)
    analyzer.LOWER_YELLOW = np.array(hsv_cfg.get("yellow_lower", analyzer.LOWER_YELLOW.tolist()), dtype=np.uint8)
    analyzer.UPPER_YELLOW = np.array(hsv_cfg.get("yellow_upper", analyzer.UPPER_YELLOW.tolist()), dtype=np.uint8)
    analyzer.LOWER_GREEN = np.array(hsv_cfg.get("green_lower", analyzer.LOWER_GREEN.tolist()), dtype=np.uint8)
    analyzer.UPPER_GREEN = np.array(hsv_cfg.get("green_upper", analyzer.UPPER_GREEN.tolist()), dtype=np.uint8)

    # Nạp cấu hình phân đoạn và ROI.
    analyzer.MIN_APPLE_AREA_RATIO = float(seg_cfg.get("min_apple_area_ratio", analyzer.MIN_APPLE_AREA_RATIO))
    analyzer.DEFECT_DARK_THRESH = int(seg_cfg.get("defect_dark_thresh", analyzer.DEFECT_DARK_THRESH))
    analyzer.DEFECT_BAD_RATIO = float(seg_cfg.get("defect_bad_ratio", analyzer.DEFECT_BAD_RATIO))
    analyzer.DEFECT_MEDIUM_RATIO = float(seg_cfg.get("defect_medium_ratio", analyzer.DEFECT_MEDIUM_RATIO))
    analyzer.ROI_WIDTH_RATIO = float(seg_cfg.get("roi_width_ratio", analyzer.ROI_WIDTH_RATIO))
    analyzer.ROI_HEIGHT_RATIO = float(seg_cfg.get("roi_height_ratio", analyzer.ROI_HEIGHT_RATIO))

    # Nạp cấu hình cổng YOLO.
    analyzer.YOLO_CONF_THRESH = float(yolo_cfg.get("conf_thresh", analyzer.YOLO_CONF_THRESH))
    analyzer.YOLO_PREDICT_CONF = float(yolo_cfg.get("predict_conf", analyzer.YOLO_PREDICT_CONF))
    analyzer.YOLO_PREDICT_IOU = float(yolo_cfg.get("predict_iou", getattr(analyzer, "YOLO_PREDICT_IOU", 0.65)))
    analyzer.YOLO_MIN_BBOX_AREA_RATIO = float(yolo_cfg.get("min_bbox_area_ratio", analyzer.YOLO_MIN_BBOX_AREA_RATIO))
    analyzer.YOLO_MAX_BBOX_AREA_RATIO = float(yolo_cfg.get("max_bbox_area_ratio", analyzer.YOLO_MAX_BBOX_AREA_RATIO))
    analyzer.YOLO_MIN_APPLE_COLOR_RATIO = float(
        yolo_cfg.get("min_apple_color_ratio", analyzer.YOLO_MIN_APPLE_COLOR_RATIO)
    )
    analyzer.YOLO_ENABLE_TRACKING = bool(yolo_cfg.get("enable_tracking", analyzer.YOLO_ENABLE_TRACKING))
    analyzer.YOLO_TRACKER_NAME = str(yolo_cfg.get("tracker_name", analyzer.YOLO_TRACKER_NAME))
    analyzer.YOLO_TRACK_PERSIST = bool(yolo_cfg.get("track_persist", analyzer.YOLO_TRACK_PERSIST))
    analyzer.YOLO_ROI_SHRINK_RATIO = float(yolo_cfg.get("roi_shrink_ratio", analyzer.YOLO_ROI_SHRINK_RATIO))

    # Nạp cấu hình tiền xử lý blur.
    analyzer.blur_threshold = float(blur_cfg.get("threshold", 100.0))
    analyzer.auto_sharpen = bool(blur_cfg.get("auto_sharpen", True))
    analyzer.sharpen_strength = float(blur_cfg.get("sharpen_strength", 1.5))

    # Nạp cấu hình CLAHE cân bằng sáng ngoài trời.
    clahe_cfg = analyzer_cfg.get("clahe", {})
    analyzer.ENABLE_CLAHE = bool(clahe_cfg.get("enable", analyzer.ENABLE_CLAHE))
    analyzer.CLAHE_CLIP_LIMIT = float(clahe_cfg.get("clip_limit", analyzer.CLAHE_CLIP_LIMIT))
    analyzer.CLAHE_TILE_SIZE = int(clahe_cfg.get("tile_size", analyzer.CLAHE_TILE_SIZE))
    analyzer.CLAHE_APPLY_TO_YOLO = bool(clahe_cfg.get("apply_to_yolo", analyzer.CLAHE_APPLY_TO_YOLO))
    analyzer.CLAHE_APPLY_TO_HSV = bool(clahe_cfg.get("apply_to_hsv", analyzer.CLAHE_APPLY_TO_HSV))
    analyzer.CLAHE_TILE_SIZE = max(2, min(32, analyzer.CLAHE_TILE_SIZE))
    analyzer.CLAHE_CLIP_LIMIT = max(0.5, min(8.0, analyzer.CLAHE_CLIP_LIMIT))

    # Nếu bật profile ngoài trời, dùng profile để override các giá trị liên quan.
    if analyzer.FORCE_ASTRA_PRO_OUTDOOR:
        apply_astra_pro_outdoor_profile(analyzer)

    # Nạp cấu hình chuyên biệt cho TC1.
    tc1_cfg = analyzer_cfg.get("tc1", {})
    analyzer.TC1_ENABLE_ADAPTIVE_HSV = bool(tc1_cfg.get("enable_adaptive_hsv", True))
    analyzer.TC1_ENABLE_TEMPORAL_SMOOTHING = bool(tc1_cfg.get("temporal_smoothing", True))
    analyzer.TC1_MIN_COLOR_PIXELS = int(tc1_cfg.get("min_color_pixels", 300))
    analyzer.TC1_SMOOTH_WINDOW = int(tc1_cfg.get("smoothing_window", 7))
    analyzer.TC1_SMOOTH_WINDOW = max(1, min(30, analyzer.TC1_SMOOTH_WINDOW))

    # Khởi tạo bộ nhớ ngắn hạn phục vụ làm mượt theo thời gian.
    analyzer.tc1_ratio_history = deque(maxlen=analyzer.TC1_SMOOTH_WINDOW)
    analyzer.depth_mm_history = deque(maxlen=analyzer.DEPTH_SMOOTH_WINDOW)
    analyzer.depth_missing_frames = 0
    analyzer.current_depth_mm = None
    analyzer.last_size_mode = "2d"
    analyzer.diameter_mm_history = deque(maxlen=analyzer.DIAMETER_MM_SMOOTH_WINDOW)
    analyzer.diameter_mm_ema = None
    analyzer.last_stable_diameter_mm = None
    # Bộ tách nền dùng cho tiện ích quan sát foreground.
    analyzer.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=50, detectShadows=False
    )

    # Khởi tạo runtime YOLO (model path, trạng thái, lý do).
    initialize_yolo_runtime(analyzer)

    # Bộ đo hiệu năng thời gian thực.
    analyzer.frame_times = deque(maxlen=30)
    analyzer.last_frame_time = time.perf_counter()
    analyzer.current_fps = 0.0
    analyzer.avg_processing_time_ms = 0.0

    # Bộ đệm phụ trợ cho anti-blur và đo kích thước.
    analyzer.blur_scores = deque(maxlen=10)
    analyzer.frame_buffer = deque(maxlen=5)
    analyzer.diameter_history = deque(maxlen=7)

    print("[ANALYZER] Anti-Motion Blur: ENABLED (Blur Detection + Auto Sharpening)")
    print("[ANALYZER] OK: Traditional analyzer initialized (HSV + Contour).")
    print(
        f"[ANALYZER]    TC1: Ripeness (Red >= {analyzer.RIPENESS_GOOD_THRESH}% -> Grade-1, "
        f">= {analyzer.RIPENESS_MEDIUM_THRESH}% -> Grade-2, else -> Grade-3)"
    )
    print(f"[ANALYZER]    TC1 Adaptive HSV: {'ON' if analyzer.TC1_ENABLE_ADAPTIVE_HSV else 'OFF'}")
    print(
        f"[ANALYZER]    TC1 Temporal Smoothing: "
        f"{'ON' if analyzer.TC1_ENABLE_TEMPORAL_SMOOTHING else 'OFF'} "
        f"(window={analyzer.TC1_SMOOTH_WINDOW})"
    )
    clahe_status = "ON" if analyzer.ENABLE_CLAHE else "OFF"
    print(
        f"[ANALYZER]    CLAHE Brightness Normalization: {clahe_status} "
        f"(clip={analyzer.CLAHE_CLIP_LIMIT}, tile={analyzer.CLAHE_TILE_SIZE}x{analyzer.CLAHE_TILE_SIZE}, "
        f"yolo={analyzer.CLAHE_APPLY_TO_YOLO}, hsv={analyzer.CLAHE_APPLY_TO_HSV})"
    )
    print("[ANALYZER] Performance Monitoring: ENABLED (FPS + Processing Time)")
    print("[ANALYZER] Defect analysis: ENABLED (dark-threshold fallback)")

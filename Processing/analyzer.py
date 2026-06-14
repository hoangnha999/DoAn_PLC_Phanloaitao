import numpy as np

from Processing.analyzer_modules.blur_ops import (
    detect_blur as detect_blur_mod,
    sharpen_image as sharpen_image_mod,
    advanced_deblur as advanced_deblur_mod,
    normalize_brightness as normalize_brightness_mod,
)
from Processing.analyzer_modules.tc1_ripeness import (
    adaptive_lower_hsv as adaptive_lower_hsv_mod,
    compute_tc1_ratios as compute_tc1_ratios_mod,
)
from Processing.analyzer_modules.tc2_size import (
    estimate_diameter_px as estimate_diameter_px_mod,
    pca_major_axis_px as pca_major_axis_px_mod,
    feret_stats_px as feret_stats_px_mod,
)
from Processing.analyzer_modules.grading import overall_grade as overall_grade_mod
from Processing.analyzer_modules.segmentation import segment_apple as segment_apple_mod
from Processing.analyzer_modules.bootstrap import (
    initialize_analyzer_state as initialize_analyzer_state_mod,
    apply_astra_pro_outdoor_profile as apply_astra_pro_outdoor_profile_mod,
)
from Processing.analyzer_modules.stabilization import (
    update_depth_context as update_depth_context_mod,
    stabilize_diameter_mm as stabilize_diameter_mm_mod,
    effective_pixel_to_mm as effective_pixel_to_mm_state_mod,
)
from Processing.analyzer_modules.yolo_runtime import run_yolo_inference as run_yolo_inference_mod
from Processing.analyzer_modules.visualization import (
    draw_results as draw_results_mod,
    draw_yolo_overlay as draw_yolo_overlay_mod,
    empty_detail as empty_detail_mod,
    get_foreground_mask as get_foreground_mask_mod,
)
from Processing.analyzer_modules.classification import (
    classify_ripeness as classify_ripeness_mod,
    classify_size as classify_size_mod,
)
from Processing.analyzer_modules.tc3_shape import classify_shape as classify_shape_mod
from Processing.analyzer_modules.pipeline import analyze_apple as analyze_apple_mod

# Quy ước dự án (theo yêu cầu hiện tại):
# - Comment và docstring phải dùng tiếng Việt có dấu.
# - Comment tập trung giải thích ý nghĩa xử lý, không ghi chú thừa.
# - analyzer.py giữ vai trò điều phối tổng quát, thuật toán chi tiết nằm trong analyzer_modules.

class FruitAnalyzer:
    """
    Phân loại táo ĐỎ theo đặc trưng VỎ BÊN NGOÀI bằng xử lý ảnh truyền thống (HSV):
      - Tiêu chí 1 (TC1): Màu sắc / Độ chín đều
            Đo tỉ lệ % vùng đỏ, vàng, xanh trên bề mặt quả.
            Đỏ đều → GOOD | Pha trộn → MEDIUM | Xanh/vàng nhiều → BAD
    - Tiêu chí 2 (TC2): Kích cỡ (đường kính mm)
        Đo từ đường viền quả bằng ước lượng lai (area-equivalent + ellipse + circle fallback).
            Lớn (≥80mm) → A | Vừa (60-80mm) → B | Nhỏ (<60mm) → C

    Ghi chú: Chỉ đánh giá đặc trưng bề mặt vỏ nhìn thấy trên ảnh 2D,
    không suy luận các chỉ số chất lượng bên trong.

    Chỉ dùng OpenCV, không cần YOLO hay Deep Learning.

    Vai trò của file này:
    - Định nghĩa cấu trúc tổng quát của bộ phân tích.
    - Giữ các hằng số mặc định cấp lớp.
    - Điều phối các module con đã tách trong analyzer_modules.
    """

    # ─── TC1 - Ngưỡng phân hạng độ chín (% vùng đỏ) ──────────
    RIPENESS_GOOD_THRESH = 85
    RIPENESS_MEDIUM_THRESH = 70

    # ─── TC3 - Ngưỡng phân hạng hình dáng (Độ tròn) ──────────
    SHAPE_GOOD_THRESH = 0.88
    SHAPE_MEDIUM_THRESH = 0.78

    # ─── TC2 - Kích thước (đường kính mm) ─────────────────────
    SIZE_THRESHOLDS = {"large": 80, "medium": 60}
    PIXEL_TO_MM = 0.42  # Đã ước lượng lại cho khoảng cách 45cm (cần tinh chỉnh thêm)
    DEPTH_REFERENCE_MM = 450.0  # Khoảng cách cố định hiện tại từ camera đến băng tải
    ENABLE_DEPTH_SIZE_COMPENSATION = True  # Đã bật
    REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT = False
    SIZE_CALIBRATION_GAIN = 2.8
    DEPTH_SMOOTH_WINDOW = 9
    DEPTH_MAX_DELTA_MM = 35.0
    DEPTH_HOLD_FRAMES = 6
    ENABLE_DIAMETER_STABILIZER = True
    DIAMETER_MM_SMOOTH_WINDOW = 9
    DIAMETER_MM_ALPHA = 0.35
    DIAMETER_MM_MAX_STEP = 2.5

    # ─── Ngưỡng HSV cho táo ĐỎ & VÀNG ────────────────────────
    LOWER_RED1 = np.array([0, 65, 40])
    UPPER_RED1 = np.array([15, 255, 255])
    LOWER_RED2 = np.array([160, 65, 40])
    UPPER_RED2 = np.array([180, 255, 255])
    LOWER_YELLOW = np.array([17, 75, 40])
    UPPER_YELLOW = np.array([32, 255, 255])
    LOWER_GREEN = np.array([35, 40, 30])
    UPPER_GREEN = np.array([90, 255, 255])

    # ─── Ngưỡng tách nền ─────────────────────────────────────
    MIN_APPLE_AREA_RATIO = 0.004  # Đã giảm để nhận táo nhỏ hơn ở 45cm
    DEFECT_DARK_THRESH = 35
    DEFECT_BAD_RATIO = 20.0
    DEFECT_MEDIUM_RATIO = 10.0
    # ─── ROI ─────────────────────────────────────────────────
    ROI_WIDTH_RATIO = 0.4
    ROI_HEIGHT_RATIO = 0.6
    # Vùng phát hiện trung tâm (Detection Zone) – tỷ lệ so với frame.
    # Tâm YOLO bbox phải nằm trong vùng này mới được xử lý phân tích.
    DETECTION_ZONE_WIDTH_RATIO = 0.55   # Rộng 55% chiều ngang frame
    DETECTION_ZONE_HEIGHT_RATIO = 0.70  # Cao 70% chiều dọc frame

    # ─── CLAHE Brightness Normalization ─────────────────────
    # Bật/tắt bước cân bằng sáng CLAHE trước khi đưa frame vào YOLO + HSV.
    # Hiệu quả cao khi chụp ngoài trời (ánh sáng mạnh, overexpose).
    ENABLE_CLAHE = True
    CLAHE_CLIP_LIMIT = 2.0      # Ngưỡng contrast clip (1.0=nhẹ, 4.0=mạnh)
    CLAHE_TILE_SIZE = 8         # Kích thước ô chia lưới CLAHE (pixel)
    CLAHE_APPLY_TO_YOLO = True  # Áp dụng CLAHE cho frame đưa vào YOLO
    CLAHE_APPLY_TO_HSV = True   # Áp dụng CLAHE cho frame tính màu HSV

    # ─── YOLO Detection ─────────────────────────────────────
    YOLO_CONF_THRESH = 0.10  # Đã giảm từ 0.25 xuống 0.10 theo yêu cầu
    YOLO_PREDICT_CONF = 0.05
    YOLO_MIN_BBOX_AREA_RATIO = 0.002  # Đã giảm từ 0.007
    YOLO_MAX_BBOX_AREA_RATIO = 0.60
    YOLO_MIN_APPLE_COLOR_RATIO = 0.01  # Đã giảm từ 0.02
    YOLO_ENABLE_TRACKING = True
    YOLO_TRACKER_NAME = "bytetrack.yaml"
    YOLO_TRACK_PERSIST = True
    YOLO_ROI_SHRINK_RATIO = 0.08
    FAR_DISTANCE_MM_THRESHOLD = 450.0
    FAR_YOLO_CONF_SCALE = 0.72
    FAR_YOLO_MIN_BBOX_AREA_SCALE = 0.30
    FAR_MIN_APPLE_AREA_SCALE = 0.35
    FAR_MIN_APPLE_COLOR_RATIO_SCALE = 0.60

    # Bật profile ngoài trời để override một số tham số nhạy sáng/depth.
    FORCE_ASTRA_PRO_OUTDOOR = True
    # Bộ profile tham chiếu cho Astra Pro khi chạy ngoài trời.
    ASTRA_PRO_OUTDOOR_PROFILE = {
        "ripeness_good_thresh": 85,
        "ripeness_medium_thresh": 70,
        "pixel_to_mm": 0.28,
        "depth_reference_mm": 600.0,
        "enable_depth_size_compensation": True,
        "require_depth_for_size_measurement": False,
        "size_calibration_gain": 2.8,
        "min_apple_area_ratio": 0.012,
        "yolo_conf_thresh": 0.45,
        "yolo_min_bbox_area_ratio": 0.007,
        "yolo_max_bbox_area_ratio": 0.60,
        "yolo_min_apple_color_ratio": 0.02,
        "blur_threshold": 100.0,
        # CLAHE: bật mạnh hơn khi ngoài trời (clip cao hơn môi trường trong nhà)
        "enable_clahe": True,
        "clahe_clip_limit": 2.5,
        "clahe_tile_size": 8,
        "clahe_apply_to_yolo": True,
        "clahe_apply_to_hsv": True,
    }

    def __init__(self):
        """Khởi tạo state runtime của analyzer thông qua module bootstrap."""
        initialize_analyzer_state_mod(self)

    def _apply_astra_pro_outdoor_profile(self):
        """Áp profile ngoài trời; dùng khi cần ép tham số vận hành bảo thủ."""
        apply_astra_pro_outdoor_profile_mod(self)

    def update_depth_context(self, depth_info=None):
        """Cập nhật context độ sâu (Z) cho các phép đo kích thước ở pipeline."""
        update_depth_context_mod(self, depth_info)

    def _stabilize_diameter_mm(self, diameter_mm):
        """Làm mượt đường kính mm để giảm nhiễu đo theo từng frame."""
        return stabilize_diameter_mm_mod(self, diameter_mm)

    def _effective_pixel_to_mm(self):
        """Lấy hệ số px->mm hiệu dụng theo trạng thái depth hiện tại."""
        return effective_pixel_to_mm_state_mod(self)

    def _run_yolo_inference(self, frame):
        """Chạy YOLO theo mode cấu hình (track/predict) với fallback an toàn."""
        return run_yolo_inference_mod(self, frame)

    def _apply_retinex(self, frame):
        # Đã gỡ bỏ Retinex vì gây nhiễu màu nền
        return frame

    # ═══════════════════════════════════════════════════════════
    #  MOTION BLUR DETECTION & DEBLURRING
    # ═══════════════════════════════════════════════════════════
    def detect_blur(self, frame):
        """
        Phát hiện ảnh mờ (motion blur) bằng phương pháp Laplacian Variance.
        Trả về điểm số và trạng thái (True nếu mờ).
        """
        return detect_blur_mod(frame, self.blur_threshold, self.blur_scores)
    
    def sharpen_image(self, frame, strength=1.5):
        """
        Làm sắc nét ảnh để giảm motion blur (Unsharp Masking).
          
        Args:
            frame: khung hình BGR
            strength: hệ số sharpening (1.0-3.0)
                     1.0 = nhẹ, 1.5 = trung bình, 2.0+ = mạnh
        
        Returns:
            sharpened: ảnh đã làm sắc nét
        """
        return sharpen_image_mod(frame, strength)
    
    def advanced_deblur(self, frame):
        """
        Deblurring nâng cao sử dụng Wiener Filter approximation.
        Hiệu quả hơn với motion blur nhưng tốn thời gian hơn.
        
        Args:
            frame: khưng hình BGR bị blur
            
        Returns:
            deblurred: ảnh đã khử blur
        """
        return advanced_deblur_mod(frame)

    def normalize_brightness(self, frame):
        """Cân bằng ánh sáng bằng CLAHE trên kênh L (LAB) để xử lý overexpose ngoài trời.

        Chỉ thay đổi kênh độ sáng L; giữ nguyên màu sắc (a, b) nên không nhầm lẫn HSV.
        Gọi hàm này trước khi đưa frame vào YOLO hoặc tính màu HSV khi ENABLE_CLAHE=True.
        """
        return normalize_brightness_mod(
            frame,
            clip_limit=self.CLAHE_CLIP_LIMIT,
            tile_size=self.CLAHE_TILE_SIZE,
        )

    def _adaptive_lower_hsv(self, hsv, apple_mask, lower_ref):
        """
        Điều chỉnh ngưỡng lower HSV theo điều kiện sáng hiện tại của vùng táo.
        Chỉ dịch kênh S/V để tăng ổn định trước thay đổi ánh sáng.
        """
        return adaptive_lower_hsv_mod(
            hsv,
            apple_mask,
            lower_ref,
            enable_adaptive_hsv=self.TC1_ENABLE_ADAPTIVE_HSV,
            min_color_pixels=self.TC1_MIN_COLOR_PIXELS,
        )

    def _compute_tc1_ratios(self, hsv, apple_mask):
        """Tính tỉ lệ đỏ-vàng-xanh cho TC1 với Adaptive HSV + Temporal Smoothing."""
        return compute_tc1_ratios_mod(
            hsv,
            apple_mask,
            self.LOWER_RED1,
            self.UPPER_RED1,
            self.LOWER_RED2,
            self.UPPER_RED2,
            self.LOWER_YELLOW,
            self.UPPER_YELLOW,
            self.LOWER_GREEN,
            self.UPPER_GREEN,
            self.tc1_ratio_history,
            enable_adaptive_hsv=self.TC1_ENABLE_ADAPTIVE_HSV,
            min_color_pixels=self.TC1_MIN_COLOR_PIXELS,
            enable_temporal_smoothing=self.TC1_ENABLE_TEMPORAL_SMOOTHING,
        )

    # ═══════════════════════════════════════════════════════════
    #  HÀM PHÂN TÍCH CHÍNH
    # ═══════════════════════════════════════════════════════════
    def analyze_apple(self, frame):
        """Điểm vào phân tích 1 frame; toàn bộ luồng chi tiết nằm ở module pipeline."""
        return analyze_apple_mod(self, frame)

    def _estimate_diameter_px(self, contour, circularity, fallback_circle_diameter):
        """Ước lượng đường kính contour-first, bền vững với táo méo."""
        return estimate_diameter_px_mod(contour, fallback_circle_diameter)

    def _pca_major_axis_px(self, contour):
        """Ước lượng trục chính (major axis) từ PCA theo pixel."""
        return pca_major_axis_px_mod(contour)

    def _feret_stats_px(self, contour):
        """Tính Feret max/min/p90 theo nhiều hướng (0-175 độ, bước 5 độ)."""
        return feret_stats_px_mod(contour)

    def _segment_apple(self, frame):
        """Tách táo từ module segmentation chuyên biệt.

        Hàm này chỉ chịu trách nhiệm truyền đầy đủ tham số runtime hiện tại
        sang module con và nhận lại kết quả segment.
        """
        return segment_apple_mod(
            frame,
            min_apple_area_ratio=self.MIN_APPLE_AREA_RATIO,
            lower_red1=self.LOWER_RED1,
            upper_red1=self.UPPER_RED1,
            lower_red2=self.LOWER_RED2,
            upper_red2=self.UPPER_RED2,
            lower_yellow=self.LOWER_YELLOW,
            upper_yellow=self.UPPER_YELLOW,
            lower_green=self.LOWER_GREEN,
            upper_green=self.UPPER_GREEN,
            yolo_conf_thresh=self.YOLO_CONF_THRESH,
            yolo_predict_conf=self.YOLO_PREDICT_CONF,
            yolo_min_bbox_area_ratio=self.YOLO_MIN_BBOX_AREA_RATIO,
            yolo_max_bbox_area_ratio=self.YOLO_MAX_BBOX_AREA_RATIO,
            yolo_min_apple_color_ratio=self.YOLO_MIN_APPLE_COLOR_RATIO,
            yolo_enable_tracking=self.YOLO_ENABLE_TRACKING,
            yolo_tracker_name=self.YOLO_TRACKER_NAME,
            yolo_track_persist=self.YOLO_TRACK_PERSIST,
            yolo_roi_shrink_ratio=self.YOLO_ROI_SHRINK_RATIO,
            current_depth_mm=self.current_depth_mm,
            far_distance_mm_threshold=self.FAR_DISTANCE_MM_THRESHOLD,
            far_yolo_conf_scale=self.FAR_YOLO_CONF_SCALE,
            far_yolo_min_bbox_area_scale=self.FAR_YOLO_MIN_BBOX_AREA_SCALE,
            far_min_apple_area_scale=self.FAR_MIN_APPLE_AREA_SCALE,
            far_min_apple_color_ratio_scale=self.FAR_MIN_APPLE_COLOR_RATIO_SCALE,
            use_yolo=self.use_yolo,
            yolo_model=self.yolo_model,
            yolo_status=self.yolo_status,
            yolo_reason=self.yolo_reason,
            yolo_model_path=self.yolo_model_path,
            run_yolo_inference_cb=self._run_yolo_inference,
            detection_zone_width_ratio=self.DETECTION_ZONE_WIDTH_RATIO,
            detection_zone_height_ratio=self.DETECTION_ZONE_HEIGHT_RATIO,
        )

    # ═══════════════════════════════════════════════════════════
    #  PHÂN HẠNG
    # ═══════════════════════════════════════════════════════════
    def _classify_ripeness(self, red_ratio):
        """
        Phân hạng TC1 - Độ chín đều (dựa trên % vùng đỏ).
        
        Returns: (label, grade)
            label: tên hiển thị ("CHÍN ĐỀU" / "VỪA CHÍN" / "CHƯA CHÍN")
            grade: hạng ("Grade-1" / "Grade-2" / "Grade-3")
        """
        return classify_ripeness_mod(red_ratio, self.RIPENESS_GOOD_THRESH, self.RIPENESS_MEDIUM_THRESH)

    def _classify_size(self, diameter_mm):
        """
        Phân hạng TC2 - Kích cỡ (dựa trên đường kính mm).
        
        Returns: (label, grade)
            label: tên hiển thị ("LỚN (A)" / "VỪA (B)" / "NHỎ (C)")
            grade: hạng ("A" / "B" / "C")
        """
        return classify_size_mod(diameter_mm, self.SIZE_THRESHOLDS)

    def _classify_shape(self, circularity):
        """Phân hạng TC3 - Hình dáng (độ tròn)."""
        return classify_shape_mod(circularity, self.SHAPE_GOOD_THRESH, self.SHAPE_MEDIUM_THRESH)

    def _overall_grade(self, tc1_grade, tc2_grade, tc3_grade="Grade-1"):
        """
        Tổng hợp các tiêu chí theo logic bảo thủ:
        - Chỉ cần 1 cái Grade-3 = Grade-3
        - Có Grade-2 và không có Grade-3 = Grade-2
        - Tất cả Grade-1 = Grade-1
        """
        return overall_grade_mod(tc1_grade, tc2_grade, tc3_grade)

    # ═══════════════════════════════════════════════════════════
    #  VẼ KẾT QUẢ LÊN KHUNG HÌNH
    # ═══════════════════════════════════════════════════════════
    def _draw_results(self, frame, contour, cx, cy, radius_px,
                      red_r, yellow_r, green_r,
                      ripeness_label, size_label, diameter_mm,
                      grade, yellow_cnts=None, red_cnts=None,
                      mask_other=None,
                      shape_label="", yolo_info=None):
        """Vẽ lớp overlay kết quả lên khung hình đầu ra.

        Analyzer giữ interface tổng quát, còn phần dựng hình chi tiết
        được triển khai trong module visualization.
        """
        return draw_results_mod(
            self,
            frame,
            contour,
            cx,
            cy,
            radius_px,
            red_r,
            yellow_r,
            green_r,
            ripeness_label,
            size_label,
            diameter_mm,
            grade,
            yellow_cnts=yellow_cnts,
            red_cnts=red_cnts,
            mask_other=mask_other,
            shape_label=shape_label,
            yolo_info=yolo_info,
        )

    def _draw_yolo_overlay(self, frame, yolo_info=None):
        """Vẽ overlay YOLO để quan sát vùng detect/candidate trong khung hình."""
        return draw_yolo_overlay_mod(self, frame, yolo_info)

    # ═══════════════════════════════════════════════════════════
    #  TIỆN ÍCH
    # ═══════════════════════════════════════════════════════════
    def _empty_detail(self):
        """Tạo detail mặc định khi không có táo, giúp downstream xử lý an toàn."""
        return empty_detail_mod()

    def get_foreground_mask(self, frame):
        """Trả về foreground mask phục vụ quan sát/debug luồng camera."""
        return get_foreground_mask_mod(self, frame)

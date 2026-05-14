import cv2
import numpy as np
import time
from collections import deque
import sys
import os

# Import Apple3DAnalyzer từ modules (optional - không crash nếu thiếu thư viện)
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from modules.apple_3d import Apple3DAnalyzer
    APPLE_3D_AVAILABLE = True
except ImportError as e:
    print(f"[ANALYZER] Warning: 3D Analysis not available: {e}")
    print("[ANALYZER] -> Install: pip install open3d scipy")
    APPLE_3D_AVAILABLE = False
    Apple3DAnalyzer = None


class FruitAnalyzer:
    """
    Phân loại táo ĐỎ theo 2 tiêu chí bằng xử lý ảnh truyền thống (HSV):
      - Tiêu chí 1 (TC1): Màu sắc / Độ chín đều
            Đo tỉ lệ % vùng đỏ, vàng, xanh trên bề mặt quả.
            Đỏ đều → GOOD | Pha trộn → MEDIUM | Xanh/vàng nhiều → BAD
      - Tiêu chí 2 (TC2): Kích cỡ (đường kính mm)
            Đo từ đường viền quả bằng minEnclosingCircle.
            Lớn (≥80mm) → A | Vừa (60-80mm) → B | Nhỏ (<60mm) → C

    Chỉ dùng OpenCV, không cần YOLO hay Deep Learning.
    """

    # ─── TC1 - Ngưỡng phân hạng độ chín (% vùng đỏ) ──────────
    RIPENESS_GOOD_THRESH = 80     # ≥ 80% đỏ → Grade-1
    RIPENESS_MEDIUM_THRESH = 70   # 70-79% đỏ → Grade-2
                                  # < 60% đỏ → Grade-3

    # ─── TC3 - Ngưỡng phân hạng hình dáng (Độ tròn) ──────────
    # Học từ bài báo MDPI 2025: Táo càng tròn giá trị càng cao
    SHAPE_GOOD_THRESH = 0.88      # Tròn đều → Grade-1
    SHAPE_MEDIUM_THRESH = 0.78    # Hơi méo → Grade-2
                                  # < 0.78 → Grade-3 (Méo)

    # ─── TC2 - Kích thước (đường kính mm) ─────────────────────
    SIZE_THRESHOLDS = {"large": 80, "medium": 60}
    # Tăng từ 0.09 lên 0.32 để táo hiện ~65-75mm khi dùng webcam/không có depth
    PIXEL_TO_MM = 0.32  
    
    # Thông số tiêu cự (Focal Length) chuẩn của Astra Pro (640x480)
    # H_FOV = 60 độ -> f = 320 / tan(30) = 554.26
    # Thực tế OpenNI thường calibration ở mức ~580 cho kết quả mm chính xác hơn
    H_FOCAL_LENGTH = 580.0 

    # ─── Ngưỡng HSV cho táo ĐỎ ────────────────────────────────
    # ─── Ngưỡng HSV cho táo ĐỎ & VÀNG (Cân bằng lại để bắt nhạy hơn) ─────
    LOWER_RED1 = np.array([0, 65, 40])
    UPPER_RED1 = np.array([15, 255, 255])
    LOWER_RED2 = np.array([160, 65, 40])
    UPPER_RED2 = np.array([180, 255, 255])
    LOWER_YELLOW = np.array([17, 75, 40])
    UPPER_YELLOW = np.array([32, 255, 255])
    LOWER_GREEN = np.array([35, 40, 30])
    UPPER_GREEN = np.array([90, 255, 255])

    # ─── Ngưỡng tách nền (segmentation) ──────────────────────
    MIN_APPLE_AREA_RATIO = 0.02   # Quả táo phải ≥ 2% diện tích ảnh
    DEFECT_DARK_THRESH = 35       # Phải thật sự tối (đen/nâu sẫm) mới tính là vết thâm
    DEFECT_BAD_RATIO = 20.0       # Vết thâm > 20% diện tích mới đánh Grade-3
    DEFECT_MEDIUM_RATIO = 10.0      # Vết thâm > 10% diện tích hạ xuống Grade-2

    # ─── ROI (Region of Interest) ──────────────────────────
    ROI_WIDTH_RATIO = 0.4         # ROI chiếm 40% chiều ngang (giảm từ 60%)
    ROI_HEIGHT_RATIO = 0.6        # ROI chiếm 60% chiều dọc (giảm từ 80%)

    def __init__(self):
        """Khởi tạo FruitAnalyzer - chế độ xử lý ảnh truyền thống."""
        # Background Subtractor (cho chức năng tách nền)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=False
        )
        
        # ─── Performance Monitoring (Machine Vision Industrial Standard) ───
        self.frame_times = deque(maxlen=30)  # Lưu 30 frame gần nhất để tính FPS
        self.last_frame_time = time.perf_counter()
        self.current_fps = 0.0
        self.avg_processing_time_ms = 0.0
        
        # ═══ MOTION BLUR DETECTION & DEBLURRING ═══════════════════════════
        self.blur_threshold = 100.0       # Laplacian variance < 100 = Blurry
        self.blur_scores = deque(maxlen=10)  # Lưu 10 blur scores gần nhất
        self.frame_buffer = deque(maxlen=5)  # Buffer 5 frames để chọn frame tốt nhất
        self.auto_sharpen = True          # Tự động sharpen khi detect blur
        print("[ANALYZER] Anti-Motion Blur: ENABLED (Blur Detection + Auto Sharpening)")
        
        # ─── 3D Analysis Module (Astra Pro Depth) ───
        if APPLE_3D_AVAILABLE:
            try:
                self.analyzer_3d = Apple3DAnalyzer()
                self.last_point_cloud = None  # Lưu point cloud gần nhất để visualization
                self.last_depth_frame = None  # Lưu depth frame
                self.last_apple_mask = None   # Lưu mask
                print("[ANALYZER] 3D Shape Analysis: ENABLED (Sphericity + Dent Detection)")
            except Exception as e:
                print(f"[ANALYZER] Warning: 3D Analysis init failed: {e}")
                self.analyzer_3d = None
                self.last_point_cloud = None
        else:
            self.analyzer_3d = None
            self.last_point_cloud = None
            print("[ANALYZER] 3D Shape Analysis: DISABLED (missing library)")
        
        print("[ANALYZER] OK: Traditional analyzer initialized (HSV + Contour).")
        print(f"[ANALYZER]    TC1: Ripeness (Red >= {self.RIPENESS_GOOD_THRESH}% -> Grade-1, "
              f">= {self.RIPENESS_MEDIUM_THRESH}% -> Grade-2, else -> Grade-3)")
        print("[ANALYZER] Performance Monitoring: ENABLED (FPS + Processing Time)")
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Lưu vào buffer để theo dõi xu hướng
        self.blur_scores.append(blur_score)
        
        # Ngưỡng phân loại
        is_blurry = blur_score < self.blur_threshold
        
        return blur_score, is_blurry
    
    def sharpen_image(self, frame, strength=1.5):
        """
        Làm sắc nét ảnh để giảm motion blur (Unsharp Masking).
        
        Phương pháp: 
         # Downsample mạnh để đạt tốc độ Real-time (mỗi 4 pixels lấy 1)
        # 640x480 / 16 = ~19,200 points (đủ cho Convex Hull chạy nhanh)
        step = 4
. Tính hiệu ảnh gốc - ảnh mờ = Chi tiết cạnh (mask)
          3. Cộng mask vào ảnh gốc với trọng số
          
        Args:
            frame: khung hình BGR
            strength: hệ số sharpening (1.0-3.0)
                     1.0 = nhẹ, 1.5 = trung bình, 2.0+ = mạnh
        
        Returns:
            sharpened: ảnh đã làm sắc nét
        """
        # Làm mờ ảnh
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        
        # Unsharp masking: sharp = original + strength * (original - blurred)
        sharpened = cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)
        
        return sharpened
    
    def advanced_deblur(self, frame):
        """
        Deblurring nâng cao sử dụng Wiener Filter approximation.
        Hiệu quả hơn với motion blur nhưng tốn thời gian hơn.
        
        Args:
            frame: khung hình BGR bị blur
            
        Returns:
            deblurred: ảnh đã khử blur
        """
        # Chuyển sang grayscale để xử lý nhanh hơn
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Tạo Motion Blur Kernel (giả định blur theo phương ngang - băng chuyền)
        # Kích thước kernel phụ thuộc vào tốc độ băng chuyền
        kernel_size = 15
        kernel_motion_blur = np.zeros((kernel_size, kernel_size))
        kernel_motion_blur[int((kernel_size-1)/2), :] = np.ones(kernel_size)
        kernel_motion_blur = kernel_motion_blur / kernel_size
        
        # Deconvolution bằng Wiener Filter (OpenCV không có sẵn, dùng xấp xỉ)
        # Thay vào đó dùng bilateral filter + sharpening
        deblurred_gray = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Sharpen
        kernel_sharpen = np.array([[-1,-1,-1],
                                   [-1, 9,-1],
                                   [-1,-1,-1]])
        deblurred_gray = cv2.filter2D(deblurred_gray, -1, kernel_sharpen)
        
        # Convert lại BGR (dùng ảnh gốc cho màu, chỉ thay channel sáng)
        deblurred = frame.copy()
        hsv = cv2.cvtColor(deblurred, cv2.COLOR_BGR2HSV)
        hsv[:, :, 2] = deblurred_gray  # Thay channel V (Value/Brightness)
        deblurred = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        return deblurred

    # ═══════════════════════════════════════════════════════════
    #  HÀM PHÂN TÍCH CHÍNH
    # ═══════════════════════════════════════════════════════════
    def analyze_apple(self, frame, depth_frame=None):
        """
        Phân tích quả táo đỏ bằng xử lý ảnh truyền thống (HSV).

        Args:
            frame: khung hình BGR từ camera/ảnh

        Returns:
            res_frame      : khung hình đã vẽ kết quả
            defect_area    : diện tích vết thâm (pixel)
            red_ratio      : tỉ lệ % vùng đỏ
            grade          : hạng tổng hợp (GOOD / MEDIUM / BAD)
            detail_info    : dict chứa thông tin chi tiết 2 tiêu chí
        """
        # ══════════════════════════════════════════════
        #  PERFORMANCE TIMING START (Industrial Standard)
        # ══════════════════════════════════════════════
        t_start = time.perf_counter()
        
        empty_detail = self._empty_detail()
        if frame is None:
            return None, 0, 0, "UNKNOWN", empty_detail

        # ══════════════════════════════════════════════
        #  MOTION BLUR DETECTION & AUTO-SHARPENING
        # ══════════════════════════════════════════════
        blur_score, is_blurry = self.detect_blur(frame)
        
        # Nếu ảnh bị blur và bật auto-sharpen → Sharpen
        if is_blurry and self.auto_sharpen:
            frame = self.sharpen_image(frame, strength=1.5)
            blur_status = "BLURRY→SHARPENED"
        elif is_blurry:
            blur_status = "BLURRY"
        else:
            blur_status = "SHARP"
        
        # Lưu blur info để hiển thị
        blur_info = {
            "blur_score": blur_score,
            "is_blurry": is_blurry,
            "status": blur_status
        }

        h_img, w_img = frame.shape[:2]

        # ── BƯỚC 1: Tách quả táo khỏi nền ──
        # Truyền thêm depth_frame để lọc 3D nếu có
        apple_mask, main_contour = self._segment_apple(frame, depth_frame)

        if apple_mask is None or main_contour is None:
            return frame, 0, 0, "NO_APPLE", empty_detail

        apple_area = cv2.contourArea(main_contour)

        # ══════════════════════════════════════════════
        #  TC1: MÀU SẮC / ĐỘ CHÍN ĐỀU
        # ══════════════════════════════════════════════
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # Đếm pixel ĐỎ
        mask_red = cv2.add(
            cv2.inRange(hsv, self.LOWER_RED1, self.UPPER_RED1),
            cv2.inRange(hsv, self.LOWER_RED2, self.UPPER_RED2),
        )
        mask_red = cv2.bitwise_and(mask_red, apple_mask)
        red_pixels = cv2.countNonZero(mask_red)
        red_cnts, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Đếm pixel VÀNG và tìm vùng để khoanh
        mask_yellow = cv2.inRange(hsv, self.LOWER_YELLOW, self.UPPER_YELLOW)
        mask_yellow = cv2.bitwise_and(mask_yellow, apple_mask)
        yellow_pixels = cv2.countNonZero(mask_yellow)
        yellow_cnts, _ = cv2.findContours(mask_yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Đếm pixel XANH LÁ
        mask_green = cv2.inRange(hsv, self.LOWER_GREEN, self.UPPER_GREEN)
        mask_green = cv2.bitwise_and(mask_green, apple_mask)
        green_pixels = cv2.countNonZero(mask_green)

        # Tính tổng số pixel màu nhận diện được (Để chuẩn hóa 100%)
        total_detected = red_pixels + yellow_pixels + green_pixels
        
        # Tính tỉ lệ % (Dựa trên tổng vùng màu đã thấy ở khung hình hiện tại)
        if total_detected > 0:
            red_ratio = (red_pixels / total_detected) * 100
            yellow_ratio = (yellow_pixels / total_detected) * 100
            green_ratio = (green_pixels / total_detected) * 100
        else:
            red_ratio = yellow_ratio = green_ratio = 0

        ripeness_label, ripeness_grade = self._classify_ripeness(red_ratio)

        # ── BỔ SUNG TC3: HÌNH DÁNG (SHAPE) ──
        # Tính độ tròn của viền thực tế
        perimeter = cv2.arcLength(main_contour, True)
        area = cv2.contourArea(main_contour)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        shape_label, shape_grade = self._classify_shape(circularity)

        # ══════════════════════════════════════════════
        #  TC2: KÍCH CỠ (ĐƯỜNG KÍNH) + BÙ TRỪ CHIỀU SÂU
        # ══════════════════════════════════════════════
        (cx, cy), radius_px = cv2.minEnclosingCircle(main_contour)
        diameter_px = radius_px * 2


        # Tính toán mm (Ưu tiên dùng Depth nếu có Astra Pro)
        dist_mm_debug = 0
        used_3d = False
        
        if depth_frame is not None:
            # Astra Pro Depth và RGB thường có độ lệch.
            # Thay vì lấy 1 điểm, ta lấy trung bình của toàn bộ vùng quả táo để tăng độ chính xác
            try:
                # Đảm bảo depth_frame và apple_mask cùng kích thước
                if depth_frame.shape[:2] != apple_mask.shape[:2]:
                    depth_frame = cv2.resize(depth_frame, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
                
                # Chỉ lấy các điểm có chiều sâu > 0 bên trong quả táo
                valid_mask = cv2.bitwise_and(apple_mask, (depth_frame > 0).astype(np.uint8) * 255)
                
                # Lấy giá trị các điểm chiều sâu hợp lệ bên trong vùng táo
                vals = depth_frame[valid_mask > 0]
                
                if len(vals) > 50: # Cần ít nhất 50 điểm để tin cậy
                    dist_mm = np.median(vals)
                    dist_mm_debug = dist_mm
                    used_3d = True
                    diameter_mm = (diameter_px * dist_mm) / self.H_FOCAL_LENGTH
                else:
                    diameter_mm = diameter_px * self.PIXEL_TO_MM
            except:
                diameter_mm = diameter_px * self.PIXEL_TO_MM
        else:
            diameter_mm = diameter_px * self.PIXEL_TO_MM

        size_label, size_grade = self._classify_size(diameter_mm)

        # ══════════════════════════════════════════════
        #  KIỂM TRA VẾT THÂM ĐA GÓC NHÌN (DEFECT)
        # ══════════════════════════════════════════════
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, self.DEFECT_DARK_THRESH, 255, cv2.THRESH_BINARY_INV)
        dark_mask = cv2.bitwise_and(dark_mask, apple_mask)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        
        # -- THUẬT TOÁN ÁNH XẠ BỀ MẶT CẦU 3D (Spherical Surface Mapping) --
        # Học từ bài báo Foods 2022: Bù đắp diện tích vết thâm bị thu nhỏ ở rìa quả táo
        y_idx, x_idx = np.nonzero(dark_mask)
        if len(x_idx) > 0 and radius_px > 0:
            # Khoảng cách từ tâm quả táo đến các điểm thâm
            distances = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)
            
            # Tính hệ số bù (Weight) dựa trên độ cong của hình cầu
            # Trọng số W = R / sqrt(R^2 - d^2). Cắt ngưỡng để tránh chia 0.
            R2_minus_d2 = np.clip(radius_px**2 - distances**2, a_min=1.0, a_max=None)
            weights = radius_px / np.sqrt(R2_minus_d2)
            weights = np.clip(weights, 1.0, 3.0) # Tối đa nhân x3 diện tích ở rìa để tránh nhiễu
            
            defect_area = np.sum(weights)
        else:
            defect_area = 0
        
        defect_ratio = (defect_area / apple_area) * 100 if apple_area > 0 else 0

        # ══════════════════════════════════════════════
        #  XẾP HẠNG TỔNG HỢP (Kết hợp 3 tiêu chí từ bài báo 2025)
        # ══════════════════════════════════════════════
        grade = self._overall_grade(ripeness_grade, size_grade, shape_grade)

        # Xác định vùng bị loại bỏ (Màu khác/Bóng tối) để vẽ lên frame
        mask_other = cv2.bitwise_and(apple_mask, cv2.bitwise_not(cv2.bitwise_or(mask_red, cv2.bitwise_or(mask_yellow, mask_green))))
        
        # ══════════════════════════════════════════════
        #  VẼ KẾT QUẢ LÊN KHUNG HÌNH
        # ══════════════════════════════════════════════
        res_frame = self._draw_results(
            frame, main_contour, cx, cy, radius_px,
            red_ratio, yellow_ratio, green_ratio,
            ripeness_label, size_label, diameter_mm,
            grade, defect_area, yellow_cnts=yellow_cnts,
            red_cnts=red_cnts, # Truyền thêm red_cnts
            dist_mm=dist_mm_debug, used_3d=used_3d,
            mask_other=mask_other,
            shape_label=shape_label
        )

        # ══════════════════════════════════════════════
        #  PERFORMANCE TIMING END & FPS CALCULATION
        # ══════════════════════════════════════════════
        t_end = time.perf_counter()
        processing_time_ms = (t_end - t_start) * 1000  # Chuyển sang milliseconds
        
        # Tính FPS từ khoảng thời gian giữa các frame
        current_time = time.perf_counter()
        frame_interval = current_time - self.last_frame_time
        if frame_interval > 0:
            instant_fps = 1.0 / frame_interval
            self.frame_times.append(instant_fps)
            # FPS trung bình của 30 frame gần nhất (làm mượt)
            self.current_fps = sum(self.frame_times) / len(self.frame_times)
        self.last_frame_time = current_time
        
        # ══════════════════════════════════════════════
        #  PHÂN TÍCH 3D (NẾU CÓ DEPTH DATA)
        # ══════════════════════════════════════════════
        result_3d = {}
        if depth_frame is not None and apple_mask is not None and self.analyzer_3d is not None:
            try:
                result_3d = self.analyzer_3d.analyze_complete(depth_frame, apple_mask)
                if result_3d["success"]:
                    # Lưu dữ liệu để visualization sau
                    self.last_point_cloud = result_3d.get("point_cloud", None)
                    self.last_depth_frame = depth_frame
                    self.last_apple_mask = apple_mask
                    print(f"[3D] OK: Sphericity={result_3d['sphericity']:.3f}, Dents={result_3d['dent_count']}, Volume={result_3d['volume_cm3']:.1f}cm3")
            except Exception as e:
                print(f"[3D] Warning: Error: {e}")
                result_3d = {"success": False}
        
        # ══════════════════════════════════════════════
        #  THÔNG TIN CHI TIẾT (dict cho GUI)
        # ══════════════════════════════════════════════
        detail_info = {
            "red_ratio": red_ratio,
            "yellow_ratio": yellow_ratio,
            "green_ratio": green_ratio,
            "ripeness_label": ripeness_label,
            "ripeness_grade": ripeness_grade,
            "diameter_px": diameter_px,
            "diameter_mm": diameter_mm,
            "size_label": size_label,
            "size_grade": size_grade,
            "shape_label": shape_label,
            "shape_grade": shape_grade,
            # Performance Metrics (Machine Vision Industrial Standard)
            "processing_time_ms": processing_time_ms,
            "fps": self.current_fps,
            # Motion Blur Detection (Anti-Blur System)
            "blur_score": blur_info["blur_score"],
            "blur_status": blur_info["status"],
            "is_blurry": blur_info["is_blurry"],
            # 3D Metrics (Astra Pro Depth Analysis)
            "3d_analysis": result_3d,
        }

        return res_frame, defect_area, red_ratio, grade, detail_info

    def _segment_apple(self, frame, depth_frame=None):
        """
        THUẬT TOÁN TỔNG HỢP (Consensus Master Algorithm) cải tiến:
        - Sử dụng Depth Map để loại bỏ nền 3D.
        - Sử dụng Màu lấy mẫu (Sampling) để tự thích nghi ánh sáng.
        """
        h, w = frame.shape[:2]
        min_area = h * w * self.MIN_APPLE_AREA_RATIO

        # Tiền xử lý
        blurred = cv2.GaussianBlur(frame, (9, 9), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        
        # 0. ROI (Region of Interest) - Chỉ bắt táo ở trung tâm
        roi_w = int(w * self.ROI_WIDTH_RATIO)
        roi_h = int(h * self.ROI_HEIGHT_RATIO)
        roi_x = (w - roi_w) // 2
        roi_y = (h - roi_h) // 2
        mask_roi = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(mask_roi, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), 255, -1)
        
        # 0. MASK CHIỀU SÂU (3D Background Subtraction)
        mask_depth = np.ones((h, w), dtype=np.uint8) * 255
        if depth_frame is not None:
            try:
                if depth_frame.shape[:2] != (h, w):
                    d_res = cv2.resize(depth_frame, (w, h), interpolation=cv2.INTER_NEAREST)
                else:
                    d_res = depth_frame
                # Chỉ loại bỏ các điểm có Depth = 0 (vùng mù)
                mask_depth = (d_res > 0).astype(np.uint8) * 255
            except: pass

        # 1. MASK MÀU TÁO (Mặc định - Cân bằng lại)
        mask_r1 = cv2.inRange(hsv, self.LOWER_RED1, self.UPPER_RED1)
        mask_r2 = cv2.inRange(hsv, self.LOWER_RED2, self.UPPER_RED2)
        mask_y  = cv2.inRange(hsv, self.LOWER_YELLOW, self.UPPER_YELLOW)
        mask_apple_colors = cv2.bitwise_or(mask_r1, cv2.bitwise_or(mask_r2, mask_y))
            
        # Kết hợp Màu + Chiều sâu
        mask_apple_colors = cv2.bitwise_and(mask_apple_colors, mask_depth)

        # 2. LOẠI BỎ MÀU XANH LÁ (Băng chuyền hoặc lá cây)
        mask_green = cv2.inRange(hsv, self.LOWER_GREEN, self.UPPER_GREEN)
        mask_not_green = cv2.bitwise_not(mask_green)

        # 3. LOẠI BỎ BÓNG TỐI & VÙNG QUÁ TỐI (LAB Lightness)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        _, mask_bright = cv2.threshold(lab[:, :, 0], 40, 255, cv2.THRESH_BINARY) 

        # 4. KẾT HỢP TỔNG LỰC (Hybrid Consensus)
        combined = cv2.bitwise_and(mask_apple_colors, cv2.bitwise_and(mask_not_green, mask_bright))
        
        # 4.1 Áp dụng ROI để chỉ bắt táo ở trung tâm
        combined = cv2.bitwise_and(combined, mask_roi)

        # 5. LÀM SẠCH (Morphology)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)
        # Thêm một chút giãn nở để bù đắp các pixel bị mất ở rìa
        opened = cv2.dilate(opened, np.ones((3,3), np.uint8), iterations=1)

        # 6. TÌM HÌNH TRÒN (Hough Circles) - Ưu tiên hàng đầu nếu có
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(
            cv2.medianBlur(gray, 7), cv2.HOUGH_GRADIENT, dp=1.2, minDist=200,
            param1=50, param2=35, minRadius=int(h*0.1), maxRadius=int(h*0.45)
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i in circles[0, :]:
                # Kiểm tra xem vòng tròn này có nằm trong vùng màu đã lọc không
                c_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.circle(c_mask, (i[0], i[1]), i[2], 255, -1)
                if cv2.countNonZero(cv2.bitwise_and(opened, c_mask)) > (np.pi * i[2]**2 * 0.3):
                    # Nếu khớp > 30%, tin tưởng tuyệt đối vào Hough Circles
                    contours, _ = cv2.findContours(c_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    return c_mask, contours[0]

        # 7. DỰ PHÒNG (Contour Analysis): Nếu Hough Circles không tìm thấy
        contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None

        best_cnt = None
        max_score = -1

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area: continue
            
            # Tính độ tròn
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0: continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            
            # Tính độ đặc (Solidity)
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            
            # Tính tỷ lệ cạnh (Aspect Ratio)
            x, y, w_rect, h_rect = cv2.boundingRect(cnt)
            aspect_ratio = float(w_rect) / h_rect
            
            # ĐIỀU KIỆN CÂN BẰNG: Tròn > 0.6 và tỷ lệ cạnh hợp lý
            if circularity > 0.62 and solidity > 0.82 and (0.7 < aspect_ratio < 1.4):
                # Score = Diện tích (nhưng không được quá to so với ảnh)
                if area < (h * w * 0.35): # Loại bỏ vật thể chiếm > 35% khung hình
                    score = area * circularity
                    if score > max_score:
                        max_score = score
                        best_cnt = cnt

        if best_cnt is not None:
            hull = cv2.convexHull(best_cnt)
            apple_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(apple_mask, [hull], -1, 255, -1)
            return apple_mask, hull

        return None, None    # ═══════════════════════════════════════════════════════════
    #  PHÂN HẠNG
    # ═══════════════════════════════════════════════════════════
    def _classify_ripeness(self, red_ratio):
        """
        Phân hạng TC1 - Độ chín đều (dựa trên % vùng đỏ).
        
        Returns: (label, grade)
            label: tên hiển thị ("CHÍN ĐỀU" / "VỪA CHÍN" / "CHƯA CHÍN")
            grade: hạng ("Grade-1" / "Grade-2" / "Grade-3")
        """
        if red_ratio >= self.RIPENESS_GOOD_THRESH:
            return "CHÍN ĐỀU", "Grade-1"
        elif red_ratio >= self.RIPENESS_MEDIUM_THRESH:
            return "VỪA CHÍN", "Grade-2"
        else:
            return "CHƯA CHÍN", "Grade-3"

    def _classify_size(self, diameter_mm):
        """
        Phân hạng TC2 - Kích cỡ (dựa trên đường kính mm).
        
        Returns: (label, grade)
            label: tên hiển thị ("LỚN (A)" / "VỪA (B)" / "NHỎ (C)")
            grade: hạng ("A" / "B" / "C")
        """
        if diameter_mm >= self.SIZE_THRESHOLDS["large"]:
            return "LỚN (A)", "Grade-1"
        elif diameter_mm >= self.SIZE_THRESHOLDS["medium"]:
            return "VỪA (B)", "Grade-2"
        else:
            return "NHỎ (C)", "Grade-3"

    def _classify_shape(self, circularity):
        """Phân hạng TC3 - Hình dáng (độ tròn)."""
        if circularity >= self.SHAPE_GOOD_THRESH:
            return "TRÒN ĐỀU", "Grade-1"
        elif circularity >= self.SHAPE_MEDIUM_THRESH:
            return "HƠI MÉO", "Grade-2"
        else:
            return "MÉO / DỊ DẠNG", "Grade-3"

    def _overall_grade(self, tc1_grade, tc2_grade, tc3_grade="Grade-1"):
        """
        Tổng hợp 3 tiêu chí theo logic:
        - Chỉ cần 1 cái Grade-3 = Grade-3
        - Có Grade-2 và không có Grade-3 = Grade-2
        - Tất cả Grade-1 = Grade-1
        """
        # Thứ tự ưu tiên: Grade-3 > Grade-2 > Grade-1
        all_grades = [tc1_grade, tc2_grade, tc3_grade]
        if "Grade-3" in all_grades:
            return "Grade-3"
        if "Grade-2" in all_grades:
            return "Grade-2"
        return "Grade-1"

    # ═══════════════════════════════════════════════════════════
    #  VẼ KẾT QUẢ LÊN KHUNG HÌNH
    # ═══════════════════════════════════════════════════════════
    def _draw_results(self, frame, contour, cx, cy, radius_px,
                      red_r, yellow_r, green_r,
                      ripeness_label, size_label, diameter_mm,
                      grade, defect_area, yellow_cnts=None, red_cnts=None,
                      dist_mm=0, used_3d=False, mask_other=None,
                      shape_label=""):
        """Vẽ kết quả phân tích lên khung hình."""
        res = frame.copy()
        h_f, w_f = res.shape[:2]

        # Màu theo hạng
        color_map = {"Grade-1": (0, 255, 0), "Grade-2": (0, 255, 255), "Grade-3": (0, 0, 255)}
        color = color_map.get(grade, (255, 255, 255))

        # Vẽ đường viền quả táo
        cv2.drawContours(res, [contour], -1, color, 2)

        # Vẽ khoanh vùng màu vàng và đỏ
        if yellow_cnts:
            cv2.drawContours(res, yellow_cnts, -1, (0, 255, 255), 1)
        if red_cnts:
            cv2.drawContours(res, red_cnts, -1, (0, 0, 255), 1)
            
        # Vẽ vùng bị loại bỏ (Màu khác) bằng màu xám mờ
        if mask_other is not None:
            overlay = res.copy()
            overlay[mask_other > 0] = (100, 100, 100) # Màu xám
            cv2.addWeighted(overlay, 0.4, res, 0.6, 0, res)

        # Vẽ vòng tròn bao quanh (thể hiện kích cỡ)
        cv2.circle(res, (int(cx), int(cy)), int(radius_px), (255, 255, 0), 2)
        
        # Hiển thị đường kính trực tiếp lên quả táo
        cv2.line(res, (int(cx - radius_px), int(cy)), (int(cx + radius_px), int(cy)), (255, 255, 0), 2)
        
        # Hiển thị thông tin đường kính
        if used_3d:
            info_text = f"D = {diameter_mm:.1f} mm (Z={int(dist_mm)}mm)"
            c_text = (0, 255, 255)
        else:
            info_text = f"D = {diameter_mm:.1f} mm (NO DEPTH)"
            c_text = (0, 165, 255) # Màu cam cảnh báo
            
        cv2.putText(res, info_text, (int(cx - 80), int(cy - 15)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, c_text, 2)

        # ─── VẼ ROI (Region of Interest) ───
        roi_w = int(w_f * self.ROI_WIDTH_RATIO)
        roi_h = int(h_f * self.ROI_HEIGHT_RATIO)
        roi_x = (w_f - roi_w) // 2
        roi_y = (h_f - roi_h) // 2
        # Vẽ hình chữ nhật nét đứt (giả lập bằng 1 pixel)
        cv2.rectangle(res, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (200, 200, 200), 1)
        cv2.putText(res, "CENTER DETECTION ROI", (roi_x, roi_y - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

        return res

    # ═══════════════════════════════════════════════════════════
    #  TIỆN ÍCH
    # ═══════════════════════════════════════════════════════════
    def _empty_detail(self):
        """Trả về dict rỗng khi không phát hiện được quả táo."""
        return {
            "red_ratio": 0, "yellow_ratio": 0, "green_ratio": 0,
            "ripeness_label": "---", "ripeness_grade": "---",
            "diameter_px": 0, "diameter_mm": 0,
            "size_label": "---", "size_grade": "---",
            "shape_label": "---", "shape_grade": "---",
        }

    def get_foreground_mask(self, frame):
        """Tách nền (Background) và vật thể (Foreground) bằng MOG2."""
        if frame is None:
            return None
        mask = self.bg_subtractor.apply(frame)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask

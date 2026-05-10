import cv2
import numpy as np


class FruitAnalyzer:
    """
    Phân loại táo ĐỎ theo 2 tiêu chí bằng xử lý ảnh truyền thống (HSV):
      - Tiêu chí 1 (TC1): Màu sắc / Độ chín đều
            Đo tỉ lệ % vùng đỏ, vàng, xanh trên bề mặt quả.
            Đỏ đều → GOOD | Pha trộn → MEDIUM | Xanh/vàng nhiều → BAD
      - Tiêu chí 2 (TC2): Kích cỡ (đường kính mm)
            Đo từ đường viền quả bằng minEnclosingCircle.
            Lớn (≥75mm) → A | Vừa (55-75mm) → B | Nhỏ (<55mm) → C

    Chỉ dùng OpenCV, không cần YOLO hay Deep Learning.
    """

    # ─── TC1 - Ngưỡng phân hạng độ chín (% vùng đỏ) ──────────
    RIPENESS_GOOD_THRESH = 80     # ≥ 80% đỏ → Chín đều (Đỏ đều là tốt nhất)
    RIPENESS_MEDIUM_THRESH = 60   # 60-80% đỏ → Vừa chín (Giảm dần)
                                  # < 60% đỏ → Chưa chín (Xanh nhiều)

    # ─── TC2 - Kích thước (đường kính mm) ─────────────────────
    SIZE_THRESHOLDS = {"large": 75, "medium": 60}
    PIXEL_TO_MM = 0.09  # Calibrate lại: 1 pixel ~ 0.09mm (kích thước thực tế khoảng 60-80mm)

    # ─── Ngưỡng HSV cho táo ĐỎ ────────────────────────────────
    # Dải ĐỎ 1 (H = 0..12)
    LOWER_RED1 = np.array([0, 50, 50])
    UPPER_RED1 = np.array([12, 255, 255])
    # Dải ĐỎ 2 (H = 155..180, vòng tròn HSV)
    LOWER_RED2 = np.array([155, 50, 50])
    UPPER_RED2 = np.array([180, 255, 255])
    # Dải VÀNG (H = 13..35)
    LOWER_YELLOW = np.array([13, 40, 50])
    UPPER_YELLOW = np.array([35, 255, 255])
    # Dải XANH LÁ (H = 36..85)
    LOWER_GREEN = np.array([36, 30, 40])
    UPPER_GREEN = np.array([85, 255, 255])

    # ─── Ngưỡng tách nền (segmentation) ──────────────────────
    MIN_APPLE_AREA_RATIO = 0.02   # Quả táo phải ≥ 2% diện tích ảnh
    DEFECT_DARK_THRESH = 35       # Phải thật sự tối (đen/nâu sẫm) mới tính là vết thâm
    DEFECT_BAD_RATIO = 8.0        # Vết thâm > 8% diện tích → đánh BAD
    DEFECT_MEDIUM_RATIO = 2.5     # Vết thâm > 2.5% diện tích → hạ xuống MEDIUM

    def __init__(self):
        """Khởi tạo FruitAnalyzer - chế độ xử lý ảnh truyền thống."""
        # Bộ đệm để làm mượt (Temporal Smoothing) cho đối tượng dao động
        self.history_cx = []
        self.history_cy = []
        self.history_r = []
        self.MAX_HISTORY = 10 # Số khung hình để lấy trung bình
        
        # Background Subtractor (cho chức năng tách nền)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=False
        )
        print("[ANALYZER] ✅ Khởi tạo bộ phân tích truyền thống (HSV + Contour).")
        print(f"[ANALYZER]    TC1: Độ chín đều (Đỏ ≥{self.RIPENESS_GOOD_THRESH}%→GOOD, "
              f"≥{self.RIPENESS_MEDIUM_THRESH}%→MEDIUM, còn lại→BAD)")
        print(f"[ANALYZER]    TC2: Kích cỡ (≥{self.SIZE_THRESHOLDS['large']}mm→A, "
              f"≥{self.SIZE_THRESHOLDS['medium']}mm→B, còn lại→C)")

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
        empty_detail = self._empty_detail()
        if frame is None:
            return None, 0, 0, "UNKNOWN", empty_detail

        h_img, w_img = frame.shape[:2]

        # ── BƯỚC 1: Tách quả táo khỏi nền ──
        apple_mask, main_contour = self._segment_apple(frame)

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

        # Đếm pixel VÀNG
        mask_yellow = cv2.inRange(hsv, self.LOWER_YELLOW, self.UPPER_YELLOW)
        mask_yellow = cv2.bitwise_and(mask_yellow, apple_mask)
        yellow_pixels = cv2.countNonZero(mask_yellow)

        # Đếm pixel XANH LÁ
        mask_green = cv2.inRange(hsv, self.LOWER_GREEN, self.UPPER_GREEN)
        mask_green = cv2.bitwise_and(mask_green, apple_mask)
        green_pixels = cv2.countNonZero(mask_green)

        # Tính tỉ lệ %
        red_ratio = (red_pixels / apple_area) * 100 if apple_area > 0 else 0
        yellow_ratio = (yellow_pixels / apple_area) * 100 if apple_area > 0 else 0
        green_ratio = (green_pixels / apple_area) * 100 if apple_area > 0 else 0

        # Phân hạng TC1
        ripeness_label, ripeness_grade = self._classify_ripeness(red_ratio)

        # ══════════════════════════════════════════════
        #  TC2: KÍCH CỠ (ĐƯỜNG KÍNH) + BÙ TRỪ CHIỀU SÂU
        # ══════════════════════════════════════════════
        (raw_cx, raw_cy), raw_radius = cv2.minEnclosingCircle(main_contour)
        
        # Làm mượt dao động
        self.history_cx.append(raw_cx); self.history_cy.append(raw_cy); self.history_r.append(raw_radius)
        if len(self.history_cx) > self.MAX_HISTORY:
            self.history_cx.pop(0); self.history_cy.pop(0); self.history_r.pop(0)
            
        cx = sum(self.history_cx)/len(self.history_cx)
        cy = sum(self.history_cy)/len(self.history_cy)
        radius_px = sum(self.history_r)/len(self.history_r)
        diameter_px = radius_px * 2

        # Tính toán mm (Ưu tiên dùng Depth nếu có Astra Pro)
        if depth_frame is not None:
            # Lấy khoảng cách tại tâm quả táo (mm)
            dist_mm = depth_frame[int(cy), int(cx)]
            if dist_mm > 0:
                # Công thức: Real_Size = (Pixel_Size * Distance) / Focal_Length
                # Hệ số 0.0015 là hằng số tiêu cự giả định cho Astra Pro, cần tinh chỉnh
                diameter_mm = diameter_px * dist_mm * 0.0015 
            else:
                diameter_mm = diameter_px * self.PIXEL_TO_MM
        else:
            # Nếu dùng Webcam thường: Dùng hệ số Calib cố định
            diameter_mm = diameter_px * self.PIXEL_TO_MM

        size_label, size_grade = self._classify_size(diameter_mm)

        # ══════════════════════════════════════════════
        #  KIỂM TRA VẾT THÂM / KHUYẾT TẬT
        # ══════════════════════════════════════════════
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        _, dark_mask = cv2.threshold(gray, self.DEFECT_DARK_THRESH, 255, cv2.THRESH_BINARY_INV)
        dark_mask = cv2.bitwise_and(dark_mask, apple_mask)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        defect_area = cv2.countNonZero(dark_mask)
        defect_ratio = (defect_area / apple_area) * 100 if apple_area > 0 else 0

        # ══════════════════════════════════════════════
        #  XẾP HẠNG TỔNG HỢP (Ưu tiên Màu sắc đỏ đều)
        # ══════════════════════════════════════════════
        grade = self._overall_grade(ripeness_grade, size_grade)

        # ══════════════════════════════════════════════
        #  VẼ KẾT QUẢ LÊN KHUNG HÌNH
        # ══════════════════════════════════════════════
        res_frame = self._draw_results(
            frame, main_contour, cx, cy, radius_px,
            red_ratio, yellow_ratio, green_ratio,
            ripeness_label, size_label, diameter_mm,
            grade, defect_area
        )

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
        }

        return res_frame, defect_area, red_ratio, grade, detail_info

    def _segment_apple(self, frame):
        """
        THUẬT TOÁN TỔNG HỢP (Consensus Master Algorithm):
        Kết hợp ưu điểm của tất cả các thuật toán phổ biến trên mạng:
        1. YCrCb: Kênh Cr cực kỳ nhạy với màu Đỏ, giúp tách táo khỏi nền nâu/trắng.
        2. HSV: Lọc màu sắc đa dạng (Đỏ, Vàng, Xanh).
        3. Saturation: Loại bỏ hoàn toàn các vùng xỉn màu (nền, bóng đổ).
        4. Geometric Scoring: Chấm điểm dựa trên độ tròn và diện tích.
        """
        h, w = frame.shape[:2]
        min_area = h * w * self.MIN_APPLE_AREA_RATIO

        # Tiền xử lý
        blurred = cv2.GaussianBlur(frame, (9, 9), 0)
        
        # 1. MASK MÀU SẮC (HSV) - Cải tiến dải màu
        # 1. MASK MÀU TÁO (HSV - Đỏ, Hồng, Cam, Vàng)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        # Kết hợp nhiều dải màu để bắt được cả táo đỏ nhạt, táo hồng
        mask_apple_colors = cv2.add(
            cv2.inRange(hsv, (0, 50, 40), (20, 255, 255)),   # Đỏ tươi, Cam
            cv2.inRange(hsv, (160, 40, 40), (180, 255, 255)) # Đỏ thẫm, Hồng
        )
        mask_apple_colors = cv2.add(mask_apple_colors, cv2.inRange(hsv, (21, 40, 40), (35, 255, 255))) # Vàng

        # 2. LOẠI BỎ MÀU XANH LÁ (Nếu có băng chuyền)
        mask_green = cv2.inRange(hsv, (36, 30, 30), (95, 255, 255))
        mask_not_green = cv2.bitwise_not(mask_green)

        # 3. LOẠI BỎ BÓNG TỐI & VÙNG QUÁ TỐI (LAB Lightness)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
        _, mask_bright = cv2.threshold(lab[:, :, 0], 40, 255, cv2.THRESH_BINARY) 

        # 4. KẾT HỢP TỔNG LỰC (Hybrid Consensus)
        # Ưu tiên màu táo, nhưng phải đủ sáng và không phải màu xanh băng chuyền
        combined = cv2.bitwise_and(mask_apple_colors, cv2.bitwise_and(mask_not_green, mask_bright))

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
            solidity = area / cv2.contourArea(hull) if cv2.contourArea(hull) > 0 else 0
            
            # Score = Diện tích * Độ tròn * Độ đặc
            score = area * circularity * solidity
            
            if circularity > 0.35 and score > max_score:
                max_score = score
                best_cnt = cnt

        if best_cnt is not None:
            hull = cv2.convexHull(best_cnt)
            apple_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(apple_mask, [hull], -1, 255, -1)
            return apple_mask, hull

        return None, None

    # ═══════════════════════════════════════════════════════════
    #  PHÂN HẠNG
    # ═══════════════════════════════════════════════════════════
    def _classify_ripeness(self, red_ratio):
        """
        Phân hạng TC1 - Độ chín đều (dựa trên % vùng đỏ).
        
        Returns: (label, grade)
            label: tên hiển thị ("CHÍN ĐỀU" / "VỪA CHÍN" / "CHƯA CHÍN")
            grade: hạng ("GOOD" / "MEDIUM" / "BAD")
        """
        if red_ratio >= self.RIPENESS_GOOD_THRESH:
            return "CHÍN ĐỀU", "GOOD"
        elif red_ratio >= self.RIPENESS_MEDIUM_THRESH:
            return "VỪA CHÍN", "MEDIUM"
        else:
            return "CHƯA CHÍN", "BAD"

    def _classify_size(self, diameter_mm):
        """
        Phân hạng TC2 - Kích cỡ (dựa trên đường kính mm).
        
        Returns: (label, grade)
            label: tên hiển thị ("LỚN (A)" / "VỪA (B)" / "NHỎ (C)")
            grade: hạng ("A" / "B" / "C")
        """
        if diameter_mm >= self.SIZE_THRESHOLDS["large"]:
            return "LỚN (A)", "GOOD"
        elif diameter_mm >= self.SIZE_THRESHOLDS["medium"]:
            return "VỪA (B)", "MEDIUM"
        else:
            return "NHỎ (C)", "BAD"

    def _overall_grade(self, tc1_grade, tc2_grade):
        """
        Tổng hợp 2 tiêu chí theo logic:
        - GOOD + GOOD = GOOD
        - Chỉ cần 1 cái BAD = BAD
        - Có MEDIUM và không có BAD = MEDIUM
        """
        # Thứ tự ưu tiên: BAD > MEDIUM > GOOD
        if tc1_grade == "BAD" or tc2_grade == "BAD":
            return "BAD"
        if tc1_grade == "MEDIUM" or tc2_grade == "MEDIUM":
            return "MEDIUM"
        return "GOOD"

    # ═══════════════════════════════════════════════════════════
    #  VẼ KẾT QUẢ LÊN KHUNG HÌNH
    # ═══════════════════════════════════════════════════════════
    def _draw_results(self, frame, contour, cx, cy, radius_px,
                      red_r, yellow_r, green_r,
                      ripeness_label, size_label, diameter_mm,
                      grade, defect_area):
        """Vẽ kết quả phân tích lên khung hình."""
        res = frame.copy()
        h_f, w_f = res.shape[:2]

        # Màu theo hạng
        color_map = {"GOOD": (0, 255, 0), "MEDIUM": (0, 255, 255), "BAD": (0, 0, 255)}
        color = color_map.get(grade, (255, 255, 255))

        # Vẽ đường viền quả táo
        cv2.drawContours(res, [contour], -1, color, 2)

        # Vẽ vòng tròn bao quanh (thể hiện kích cỡ)
        cv2.circle(res, (int(cx), int(cy)), int(radius_px), (255, 255, 0), 2)
        
        # Hiển thị đường kính trực tiếp lên quả táo
        cv2.line(res, (int(cx - radius_px), int(cy)), (int(cx + radius_px), int(cy)), (255, 255, 0), 2)
        cv2.putText(res, f"D = {diameter_mm:.1f} mm", (int(cx - 45), int(cy - 10)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # ── Thông tin TC1 ──
        cv2.putText(res, f"TC1 MAU SAC: {ripeness_label} ({red_r:.1f}% Do)",
                    (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(res, f"    Vang: {yellow_r:.1f}%  Xanh: {green_r:.1f}%",
                    (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

        # ── Thông tin TC2 ──
        cv2.putText(res, f"TC2 KICH CO: {size_label} (D={diameter_mm:.0f}mm)",
                    (5, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)

        # ── Vết thâm ──
        if defect_area > 0:
            cv2.putText(res, f"Vet tham: {defect_area}px",
                        (5, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

        # ── Kết quả tổng hợp ──
        y_grade = 100 if defect_area > 0 else 80
        cv2.putText(res, f"KET QUA: {grade}", (5, y_grade),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Badge
        cv2.putText(res, "XU LY ANH TRUYEN THONG", (w_f - 265, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

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

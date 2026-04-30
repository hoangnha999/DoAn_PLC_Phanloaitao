import cv2
import numpy as np

class FruitAnalyzer:
    def __init__(self):
        # 1. Ngưỡng màu ĐỎ (Táo chín) - 2 dải trong HSV
        self.lower_red1 = np.array([0, 100, 80])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([160, 100, 80])
        self.upper_red2 = np.array([180, 255, 255])
        
        # 2. Ngưỡng màu VÀNG/XANH (Táo chưa chín hoặc đang chín)
        self.lower_yellow = np.array([15, 50, 50])
        self.upper_yellow = np.array([35, 255, 255]) # Dải màu vàng/xanh nhạt
        
        # Bộ trừ nền (Background Subtractor)
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=False)

    def analyze_apple(self, frame):
        """
        Phân tích theo lộ trình: Tách nền -> Tính tỉ lệ Đỏ/Vàng -> Phân loại.
        """
        if frame is None:
            return None, 0, 0, "UNKNOWN"

        # 1. Tiền xử lý: Làm mượt để giảm nhiễu (GaussianBlur)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 2. Tách quả táo khỏi nền (Segmentation)
        # Sử dụng Value channel kết hợp Morphological để lấy form quả táo
        gray = hsv[:,:,2]
        _, broad_mask = cv2.threshold(gray, 35, 255, cv2.THRESH_BINARY)
        
        kernel = np.ones((5, 5), np.uint8)
        broad_mask = cv2.morphologyEx(broad_mask, cv2.MORPH_CLOSE, kernel) # Lấp lỗ hổng
        
        contours_apple, _ = cv2.findContours(broad_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_apple:
            return frame, 0, 0, "NO_APPLE"
            
        main_apple_cnt = max(contours_apple, key=cv2.contourArea)
        apple_area = cv2.contourArea(main_apple_cnt)
        
        if apple_area < 800:
            return frame, 0, 0, "NO_APPLE"

        apple_mask = np.zeros_like(broad_mask)
        cv2.drawContours(apple_mask, [main_apple_cnt], -1, 255, -1)

        # 3. Trích xuất đặc trưng màu sắc (Feature Extraction)
        # --- Màu Đỏ ---
        mask_red = cv2.add(cv2.inRange(hsv, self.lower_red1, self.upper_red1),
                           cv2.inRange(hsv, self.lower_red2, self.upper_red2))
        mask_red = cv2.bitwise_and(mask_red, apple_mask)
        red_pixels = cv2.countNonZero(mask_red)
        
        # --- Màu Vàng/Xanh ---
        mask_yellow = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
        mask_yellow = cv2.bitwise_and(mask_yellow, apple_mask)
        yellow_pixels = cv2.countNonZero(mask_yellow)
        
        # Tính tỉ lệ %
        red_ratio = (red_pixels / apple_area) * 100
        yellow_ratio = (yellow_pixels / apple_area) * 100

        # 4. Phát hiện vết thâm đen (Defects)
        _, dark_mask = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
        dark_mask = cv2.bitwise_and(dark_mask, apple_mask)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        
        defect_area = cv2.countNonZero(dark_mask)
        res_frame = frame.copy()

        # 5. Phân loại theo Logic yêu cầu
        # Good: Red > 80%
        # Medium: Red 40% - 80%
        # Bad: Red < 40% hoặc có vết thâm lớn
        
        if red_ratio > 80 and defect_area < 50:
            grade = "GOOD"
            color = (0, 255, 0)
        elif red_ratio > 40 and defect_area < 200:
            grade = "MEDIUM"
            color = (0, 255, 255)
        else:
            grade = "BAD"
            color = (0, 0, 255)

        # Hiển thị thông tin visual
        cv2.drawContours(res_frame, [main_apple_cnt], -1, color, 2)
        cv2.putText(res_frame, f"CHIN (DO): {red_ratio:.1f}%", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(res_frame, f"CHUA CHIN (VANG): {yellow_ratio:.1f}%", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(res_frame, f"KET QUA: {grade}", (5, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return res_frame, defect_area, red_ratio, grade

    def get_foreground_mask(self, frame):
        """Tách nền (Background) và vật thể (Foreground)."""
        if frame is None: return None
        mask = self.bg_subtractor.apply(frame)
        # Khử nhiễu
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask

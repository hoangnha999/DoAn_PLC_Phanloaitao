import cv2
import numpy as np

class FruitAnalyzer:
    def __init__(self):
        # Ngưỡng màu để nhận diện quả táo đỏ (HSV)
        self.lower_red1 = np.array([0, 100, 100])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([160, 100, 100])
        self.upper_red2 = np.array([180, 255, 255])

    def analyze_apple(self, frame):
        """
        Phân tích quả táo: Phát hiện thâm đen + Độ chín (độ đỏ).
        Trả về: (frame_result, defect_area, ripeness_percent, grade)
        """
        if frame is None:
            return None, 0, 0, "UNKNOWN"

        # 1. Tiền xử lý
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 2. Nhận diện TOÀN BỘ QUẢ TÁO (để tính diện tích tổng)
        # Dùng Value channel để tách vật thể khỏi nền dễ hơn
        gray = hsv[:,:,2]
        _, broad_mask = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
        
        # Tìm contour lớn nhất
        contours_apple, _ = cv2.findContours(broad_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours_apple:
            return frame, 0, 0, "NO_APPLE"
            
        main_apple_cnt = max(contours_apple, key=cv2.contourArea)
        apple_area = cv2.contourArea(main_apple_cnt)
        
        if apple_area < 1000:
            return frame, 0, 0, "NO_APPLE"

        # Mask quả táo
        apple_mask = np.zeros_like(broad_mask)
        cv2.drawContours(apple_mask, [main_apple_cnt], -1, 255, -1)

        # 3. Tính ĐỘ CHÍN (Độ đỏ chín đều)
        mask_red1 = cv2.inRange(hsv, self.lower_red1, self.upper_red1)
        mask_red2 = cv2.inRange(hsv, self.lower_red2, self.upper_red2)
        red_mask = cv2.add(mask_red1, mask_red2)
        red_mask = cv2.bitwise_and(red_mask, apple_mask)
        
        red_area = np.sum(red_mask > 0)
        ripeness_percent = (red_area / apple_area) * 100

        # 4. Phát hiện VẾT THÂM ĐEN
        _, dark_mask = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
        dark_mask = cv2.bitwise_and(dark_mask, apple_mask)
        
        kernel = np.ones((3, 3), np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)
        
        contours_defect, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        defect_area = 0
        res_frame = frame.copy()
        
        for cnt in contours_defect:
            area = cv2.contourArea(cnt)
            if area > 40:
                defect_area += area
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(res_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # 5. PHÂN LOẠI TỔNG HỢP (Chín đều + Thâm đen)
        # Tiêu chuẩn phân hạng (Có thể tùy chỉnh):
        # - LOẠI 1 (GOOD): Chín > 90% diện tích VÀ Thâm < 30
        # - LOẠI 2 (MEDIUM): Chín 60% - 90% HOẶC Thâm 30 - 200
        # - LOẠI 3 (BAD): Chín < 60% (còn xanh) HOẶC Thâm > 200
        
        if ripeness_percent >= 90 and defect_area < 30:
            grade = "GOOD"
            color_res = (0, 255, 0) # Xanh lá
        elif ripeness_percent < 60 or defect_area > 200:
            grade = "BAD"
            color_res = (0, 0, 255) # Đỏ
        else:
            grade = "MEDIUM"
            color_res = (0, 255, 255) # Vàng

        # Hiển thị thông số chi tiết lên Frame
        cv2.putText(res_frame, f"DO CHIN: {ripeness_percent:.1f}%", (5, 15), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        cv2.putText(res_frame, f"VET THAM: {int(defect_area)}", (5, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        cv2.putText(res_frame, f"PHAN LOAI: {grade}", (5, 45), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_res, 2)

        return res_frame, defect_area, ripeness_percent, grade

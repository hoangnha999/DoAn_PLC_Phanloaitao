import cv2
import numpy as np


# Module TC3: tính độ tròn và ánh xạ sang nhãn/grade hình dáng.


def compute_circularity(contour):
    """Tính circularity của contour theo công thức (4*pi*area)/(perimeter^2)."""
    # Contour rỗng hoặc không tồn tại thì không thể tính độ tròn.
    if contour is None or len(contour) == 0:
        return 0.0

    # Chu vi contour (close=True vì contour là đường khép kín).
    perimeter = float(cv2.arcLength(contour, True))
    # Tránh chia cho 0.
    if perimeter <= 0.0:
        return 0.0

    # Diện tích contour.
    area = float(cv2.contourArea(contour))
    # Công thức circularity chuẩn trong hình học phẳng.
    circularity = (4.0 * np.pi * area) / (perimeter * perimeter)
    # Ép kiểu float thường để thuận tiện khi lưu JSON/log.
    return float(circularity)


def classify_shape(circularity, good_thresh=0.88, medium_thresh=0.78):
    """Phân hạng TC3 theo circularity với nhãn tiếng Việt."""
    # Circularity càng gần 1.0 thì càng tròn đều.
    if circularity >= float(good_thresh):
        return "TRÒN ĐỀU", "Grade-1"
    # Mức trung gian: hơi méo.
    if circularity >= float(medium_thresh):
        return "HƠI MÉO", "Grade-2"
    # Thấp hơn ngưỡng medium: méo/dị dạng.
    return "MÉO / DỊ DẠNG", "Grade-3"


def evaluate_shape(contour, good_thresh=0.88, medium_thresh=0.78):
    """Trả về bộ kết quả (circularity, shape_label, shape_grade) cho một contour."""
    # Bước 1: tính chỉ số độ tròn.
    circularity = compute_circularity(contour)
    # Bước 2: phân hạng theo ngưỡng cấu hình.
    shape_label, shape_grade = classify_shape(circularity, good_thresh, medium_thresh)
    # Trả về đầy đủ để pipeline chỉ cần một lần gọi.
    return circularity, shape_label, shape_grade

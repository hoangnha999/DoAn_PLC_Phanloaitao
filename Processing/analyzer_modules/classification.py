from Processing.analyzer_modules.tc3_shape import classify_shape  # Backward-compatible re-export


# Module này gom các hàm ánh xạ từ chỉ số đo lường sang nhãn hiển thị + grade.
# TC3 được re-export từ tc3_shape để tránh trùng lặp logic phân hạng hình dáng.


def classify_ripeness(red_ratio, good_thresh=85, medium_thresh=70):
    """Phân hạng TC1 (độ chín) theo tỉ lệ màu đỏ."""
    # Nếu tỉ lệ đỏ vượt ngưỡng cao: quả chín đều.
    if red_ratio >= float(good_thresh):
        return "CHÍN ĐỀU", "Grade-1"
    # Nếu chỉ đạt ngưỡng trung bình: quả vừa chín.
    if red_ratio >= float(medium_thresh):
        return "VỪA CHÍN", "Grade-2"
    # Còn lại: chưa chín.
    return "CHƯA CHÍN", "Grade-3"


def classify_size(diameter_mm, thresholds):
    """Phân hạng TC2 (kích cỡ) theo đường kính mm."""
    # Đường kính >= ngưỡng large: loại lớn (A).
    if diameter_mm >= float(thresholds["large"]):
        return "LỚN (A)", "Grade-1"
    # Đường kính >= ngưỡng medium: loại vừa (B).
    if diameter_mm >= float(thresholds["medium"]):
        return "VỪA (B)", "Grade-2"
    # Còn lại: loại nhỏ (C).
    return "NHỎ (C)", "Grade-3"

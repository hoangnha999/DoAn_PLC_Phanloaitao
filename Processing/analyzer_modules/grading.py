def overall_grade(*grades):
    """Tổng hợp grade cuối từ nhiều tiêu chí theo nguyên tắc bảo thủ."""
    # Cho phép gọi linh hoạt số lượng tiêu chí, nhưng vẫn giữ tương thích ngược.
    all_grades = [g for g in grades if isinstance(g, str)] or ["Grade-1"]
    # Chỉ cần một tiêu chí ở mức xấu nhất thì kết quả cuối cùng là Grade-3.
    if "Grade-3" in all_grades:
        return "Grade-3"
    # Nếu không có Grade-3 nhưng có Grade-2 thì xếp Grade-2.
    if "Grade-2" in all_grades:
        return "Grade-2"
    # Còn lại: tất cả đều đạt Grade-1.
    return "Grade-1"

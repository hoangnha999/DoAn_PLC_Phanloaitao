import cv2
import numpy as np


# Module TC1: tính tỉ lệ màu đỏ/vàng/xanh trên vùng vỏ táo.
# Mục tiêu chính:
# 1) Tách các vùng màu theo ngưỡng HSV.
# 2) Chuẩn hóa thành tỉ lệ phần trăm.
# 3) Làm mượt theo thời gian để giảm nhấp nháy giữa các frame.


def adaptive_lower_hsv(hsv, apple_mask, lower_ref, enable_adaptive_hsv=True, min_color_pixels=300):
    """Điều chỉnh ngưỡng thấp S/V theo ánh sáng thực tế của vùng quả hiện tại."""
    # Nếu tắt chế độ adaptive, hoặc chưa có mask quả,
    # trả về ngưỡng tham chiếu ban đầu để giữ hành vi ổn định.
    if not enable_adaptive_hsv or apple_mask is None:
        return lower_ref

    # Chỉ lấy pixel nằm trong vùng quả (mask > 0).
    valid = apple_mask > 0
    # Nếu số pixel hợp lệ quá ít, thống kê percentile sẽ nhiễu,
    # nên không điều chỉnh ngưỡng.
    if int(np.count_nonzero(valid)) < int(min_color_pixels):
        return lower_ref

    # Trích riêng kênh S (độ bão hòa) và V (độ sáng) trong vùng quả.
    sat_vals = hsv[:, :, 1][valid]
    val_vals = hsv[:, :, 2][valid]
    # Trường hợp phòng thủ: mảng rỗng thì trả về ngưỡng gốc.
    if sat_vals.size == 0 or val_vals.size == 0:
        return lower_ref

    # Dùng percentile 25 để phản ánh vùng tối/ít bão hòa,
    # đồng thời giảm ảnh hưởng outlier quá sáng/quá tối.
    s_p25 = float(np.percentile(sat_vals, 25))
    v_p25 = float(np.percentile(val_vals, 25))

    # Chuyển percentile thành hệ số scale quanh mốc tham chiếu.
    # Clamp trong [0.80, 1.20] để tránh dao động ngưỡng quá mạnh.
    s_scale = float(np.clip(s_p25 / 70.0, 0.80, 1.20))
    v_scale = float(np.clip(v_p25 / 45.0, 0.80, 1.20))

    # Tạo bản sao để cập nhật ngưỡng thấp S/V, giữ nguyên kênh H.
    adapted = lower_ref.copy()
    # Ép kiểu uint8 và chặn biên [20, 255] để tránh ngưỡng quá thấp/không hợp lệ.
    adapted[1] = np.uint8(np.clip(int(round(float(lower_ref[1]) * s_scale)), 20, 255))
    adapted[2] = np.uint8(np.clip(int(round(float(lower_ref[2]) * v_scale)), 20, 255))
    return adapted


def compute_tc1_ratios(
    hsv,
    apple_mask,
    lower_red1,
    upper_red1,
    lower_red2,
    upper_red2,
    lower_yellow,
    upper_yellow,
    lower_green,
    upper_green,
    ratio_history,
    enable_adaptive_hsv=True,
    min_color_pixels=300,
    enable_temporal_smoothing=True,
):
    """Tính tỉ lệ đỏ/vàng/xanh với Adaptive HSV và làm mượt theo thời gian."""
    # Bước 1: điều chỉnh ngưỡng thấp từng dải màu theo điều kiện sáng hiện tại.
    red1 = adaptive_lower_hsv(hsv, apple_mask, lower_red1, enable_adaptive_hsv, min_color_pixels)
    red2 = adaptive_lower_hsv(hsv, apple_mask, lower_red2, enable_adaptive_hsv, min_color_pixels)
    yellow = adaptive_lower_hsv(hsv, apple_mask, lower_yellow, enable_adaptive_hsv, min_color_pixels)
    green = adaptive_lower_hsv(hsv, apple_mask, lower_green, enable_adaptive_hsv, min_color_pixels)

    # Bước 2: tạo mask đỏ từ 2 dải Hue đỏ (vì đỏ nằm ở hai đầu vòng Hue).
    # Sau đó chỉ giữ pixel thuộc vùng quả.
    mask_red = cv2.add(cv2.inRange(hsv, red1, upper_red1), cv2.inRange(hsv, red2, upper_red2))
    mask_red = cv2.bitwise_and(mask_red, apple_mask)
    red_pixels = cv2.countNonZero(mask_red)
    # Lấy contour để phục vụ overlay trực quan trên GUI.
    red_cnts, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Bước 3: tạo mask vàng và thống kê số pixel vàng.
    mask_yellow = cv2.inRange(hsv, yellow, upper_yellow)
    mask_yellow = cv2.bitwise_and(mask_yellow, apple_mask)
    yellow_pixels = cv2.countNonZero(mask_yellow)
    yellow_cnts, _ = cv2.findContours(mask_yellow, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Bước 4: tạo mask xanh và thống kê số pixel xanh.
    mask_green = cv2.inRange(hsv, green, upper_green)
    mask_green = cv2.bitwise_and(mask_green, apple_mask)
    green_pixels = cv2.countNonZero(mask_green)

    # Bước 5: chuẩn hóa thành tỉ lệ % trên tổng pixel màu hợp lệ.
    total = red_pixels + yellow_pixels + green_pixels
    if total > 0:
        red_raw = (red_pixels / total) * 100.0
        yellow_raw = (yellow_pixels / total) * 100.0
        green_raw = (green_pixels / total) * 100.0
    else:
        # Không có pixel màu nào hợp lệ thì gán 0 để tránh chia 0.
        red_raw = yellow_raw = green_raw = 0.0

    # Bước 6: đưa giá trị raw vào lịch sử để phục vụ temporal smoothing.
    ratio_history.append((red_raw, yellow_raw, green_raw))

    # Bước 7: làm mượt theo thời gian bằng median trên cửa sổ lịch sử.
    # Median bền vững hơn mean khi có frame nhiễu đột biến.
    if enable_temporal_smoothing and len(ratio_history) >= 2:
        hist = np.array(ratio_history, dtype=np.float32)
        red_ratio = float(np.median(hist[:, 0]))
        yellow_ratio = float(np.median(hist[:, 1]))
        green_ratio = float(np.median(hist[:, 2]))
    else:
        # Nếu chưa đủ lịch sử hoặc tắt smoothing thì dùng giá trị raw hiện tại.
        red_ratio, yellow_ratio, green_ratio = red_raw, yellow_raw, green_raw

    # Bước 8: trả về đầy đủ dữ liệu trung gian + dữ liệu đã chuẩn hóa.
    # Pipeline dùng tỉ lệ để phân hạng, GUI dùng mask/contour để hiển thị.
    return {
        "mask_red": mask_red,
        "mask_yellow": mask_yellow,
        "mask_green": mask_green,
        "red_cnts": red_cnts,
        "yellow_cnts": yellow_cnts,
        "red_ratio": red_ratio,
        "yellow_ratio": yellow_ratio,
        "green_ratio": green_ratio,
        "red_ratio_raw": red_raw,
        "yellow_ratio_raw": yellow_raw,
        "green_ratio_raw": green_raw,
    }


def classify_ripeness(red_ratio, good_thresh=85, medium_thresh=70):
    """Phân hạng độ chín dựa trên tỉ lệ đỏ."""
    # Nếu tỉ lệ đỏ vượt ngưỡng tốt: táo chín đều.
    if red_ratio >= float(good_thresh):
        return "CHIN DEU", "Grade-1"
    # Nếu chỉ đạt ngưỡng trung bình: táo vừa chín.
    if red_ratio >= float(medium_thresh):
        return "VUA CHIN", "Grade-2"
    # Còn lại: táo chưa chín.
    return "CHUA CHIN", "Grade-3"

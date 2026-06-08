import cv2
import numpy as np


# Module tiền xử lý ảnh mờ: đo độ mờ và tăng nét khung hình.
# Tất cả hàm trong file này chỉ thay đổi chất lượng ảnh đầu vào,
# không thực hiện phân hạng chất lượng quả.


def detect_blur(frame, blur_threshold, blur_scores=None):
    """Phát hiện ảnh mờ bằng phương sai Laplacian.

    Giá trị Laplacian variance càng cao thì biên ảnh càng rõ (ảnh nét hơn).
    """
    # Chuyển ảnh màu BGR sang ảnh xám để đo biên đơn giản và ổn định hơn.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Tính phương sai của Laplacian: cao => nhiều cạnh sắc, thấp => ảnh mờ.
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

    # Nếu có cấu trúc lưu lịch sử, append để theo dõi xu hướng độ mờ theo thời gian.
    if blur_scores is not None:
        blur_scores.append(blur_score)

    # So với ngưỡng cấu hình để quyết định frame hiện tại có bị mờ hay không.
    is_blurry = blur_score < float(blur_threshold)
    return float(blur_score), bool(is_blurry)


def sharpen_image(frame, strength=1.5):
    """Làm nét bằng kỹ thuật unsharp masking để giảm mờ chuyển động."""
    # Tạo bản làm mờ nhẹ để đóng vai trò "nền" trong phép trừ tăng biên.
    blurred = cv2.GaussianBlur(frame, (0, 0), 3)
    # Tăng trọng số ảnh gốc, trừ ảnh mờ => biên nổi rõ hơn.
    return cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)


def advanced_deblur(frame):
    """Khử mờ xấp xỉ bằng bilateral filter + sharpen trên kênh sáng V."""
    # Xử lý trên ảnh xám để giảm chi phí tính toán và tránh lệch màu trực tiếp.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Bilateral filter giúp giảm nhiễu nhưng vẫn giữ biên tương đối tốt.
    deblurred_gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # Kernel sharpen kinh điển: tâm dương lớn, xung quanh âm để nhấn cạnh.
    kernel_sharpen = np.array([[-1, -1, -1],
                               [-1, 9, -1],
                               [-1, -1, -1]])
    # Áp dụng kernel làm nét trên ảnh xám đã được lọc nhiễu.
    deblurred_gray = cv2.filter2D(deblurred_gray, -1, kernel_sharpen)

    # Tạo bản sao để ghi lại kênh sáng sau khi làm nét.
    deblurred = frame.copy()
    # Chuyển sang HSV để thay kênh V (độ sáng) mà giữ nguyên sắc độ màu.
    hsv = cv2.cvtColor(deblurred, cv2.COLOR_BGR2HSV)
    # Gán kênh V bằng kết quả đã khử mờ/làm nét.
    hsv[:, :, 2] = deblurred_gray
    # Chuyển lại BGR để tương thích toàn bộ pipeline hiện tại.
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

import cv2
import numpy as np


# Module TC2: ước lượng kích thước đường kính (pixel -> mm) và phân hạng.


def effective_pixel_to_mm(
    pixel_to_mm,
    calibration_gain,
    enable_depth,
    require_depth_for_size,
    current_depth_mm,
    depth_reference_mm,
):
    """Tính hệ số mm/px hiệu dụng, có thể bù theo độ sâu (depth)."""
    # Hệ số nền sau khi áp gain hiệu chuẩn.
    base = float(pixel_to_mm) * float(calibration_gain)
    # Nếu tắt bù depth.
    if not bool(enable_depth):
        # Nếu hệ thống bắt buộc có depth thì không cho phép đo size bằng 2D.
        if bool(require_depth_for_size):
            return None, "depth_required_disabled"
        return base, "2d_gain"

    # Có bật depth nhưng chưa có Z hợp lệ hoặc reference sai.
    if current_depth_mm is None or float(depth_reference_mm) <= 1e-6:
        if bool(require_depth_for_size):
            return None, "depth_required_no_z"
        return base, "2d_gain"

    # Scale theo tỉ lệ khoảng cách hiện tại so với mốc reference.
    scale = float(current_depth_mm) / float(depth_reference_mm)
    # Clamp để tránh bùng giá trị khi depth nhiễu/lỗi.
    scale = float(np.clip(scale, 0.5, 2.0))
    return base * scale, "depth_assisted"


def feret_stats_px(contour):
    """Tính Feret max/min/p90 trên nhiều góc lấy mẫu."""
    # Cần ít nhất 3 điểm để tạo đa giác có ý nghĩa.
    if contour is None or len(contour) < 3:
        return 0.0, 0.0, 0.0

    # Dùng convex hull để giảm ảnh hưởng của các lõm nhỏ cục bộ.
    hull = cv2.convexHull(contour)
    pts = hull.reshape(-1, 2).astype(np.float32)
    if pts.shape[0] < 3:
        return 0.0, 0.0, 0.0

    # Lấy mẫu góc 0..175 độ, bước 5 độ.
    angles = np.deg2rad(np.arange(0, 180, 5, dtype=np.float32))
    dirs = np.stack((np.cos(angles), np.sin(angles)), axis=1)
    # Chiếu điểm lên mỗi hướng rồi lấy độ rộng span theo hướng đó.
    projections = pts @ dirs.T
    spans = projections.max(axis=0) - projections.min(axis=0)

    # Trả về thống kê Feret: lớn nhất, nhỏ nhất và bách phân vị 90.
    return float(np.max(spans)), float(np.min(spans)), float(np.percentile(spans, 90))


def pca_major_axis_px(contour):
    """Ước lượng chiều dài trục chính bằng PCA."""
    # PCA cần đủ số điểm để ma trận hiệp phương sai ổn định.
    if contour is None or len(contour) < 5:
        return 0.0

    pts = contour.reshape(-1, 2).astype(np.float32)
    if pts.shape[0] < 5:
        return 0.0

    # Đưa dữ liệu về quanh tâm trước khi tính covariance.
    pts_centered = pts - pts.mean(axis=0, keepdims=True)
    cov = np.cov(pts_centered.T)
    try:
        # Eigenvector ứng với eigenvalue lớn nhất là trục chính.
        vals, vecs = np.linalg.eigh(cov)
    except Exception:
        return 0.0

    idx = int(np.argmax(vals))
    axis = vecs[:, idx]
    # Chiếu lên trục chính, hiệu max-min chính là chiều dài ước lượng.
    projections = pts_centered @ axis
    return max(0.0, float(np.max(projections) - np.min(projections)))


def estimate_diameter_px(contour, fallback_circle_diameter):
    """Ước lượng đường kính bền vững cho quả không tròn hoàn hảo."""
    # Diện tích contour là nền tảng ổn định nhất để bắt đầu.
    area = float(cv2.contourArea(contour))
    if area <= 1.0:
        return float(max(1.0, fallback_circle_diameter))

    # Đường kính từ hình tròn tương đương diện tích.
    diameter_area = float(np.sqrt((4.0 * area) / np.pi))

    # Ước lượng thêm bằng fitEllipse nếu contour đủ điểm.
    diameter_ellipse = diameter_area
    if contour is not None and len(contour) >= 5:
        try:
            (_, _), (axis_a, axis_b), _ = cv2.fitEllipse(contour)
            if axis_a > 0 and axis_b > 0:
                diameter_ellipse = float((axis_a + axis_b) / 2.0)
        except Exception:
            diameter_ellipse = diameter_area

    # Ước lượng theo Feret P90 (ít nhạy nhiễu hơn Feret max).
    feret_max, _, feret_p90 = feret_stats_px(contour)
    diameter_feret = feret_p90 if feret_p90 > 0 else (feret_max if feret_max > 0 else diameter_area)

    # Ước lượng thêm theo chiều dài trục chính PCA.
    diameter_pca = pca_major_axis_px(contour)
    if diameter_pca <= 0:
        diameter_pca = diameter_ellipse

    # Trộn nhiều ước lượng để bền vững hơn với quả méo.
    diameter_non_round = (
        (0.35 * diameter_area)
        + (0.25 * diameter_ellipse)
        + (0.30 * diameter_feret)
        + (0.10 * diameter_pca)
    )
    # Clamp quanh area-equivalent để tránh estimate phi thực tế.
    diameter_non_round = float(np.clip(diameter_non_round, 0.80 * diameter_area, 1.35 * max(1.0, diameter_area)))

    # Trộn nhẹ với fallback hình tròn để tăng ổn định theo frame.
    diameter_fused = (0.92 * diameter_non_round) + (0.08 * float(fallback_circle_diameter))
    return float(max(1.0, diameter_fused))


def classify_size(diameter_mm, thresholds):
    """Phân hạng kích cỡ theo ngưỡng mm."""
    # >= ngưỡng large => loại lớn.
    if diameter_mm >= float(thresholds["large"]):
        return "LON (A)", "Grade-1"
    # >= ngưỡng medium => loại vừa.
    if diameter_mm >= float(thresholds["medium"]):
        return "VUA (B)", "Grade-2"
    # Còn lại => loại nhỏ.
    return "NHO (C)", "Grade-3"

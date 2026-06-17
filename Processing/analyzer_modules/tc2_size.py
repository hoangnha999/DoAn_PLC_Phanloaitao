import cv2  # Nhập thư viện OpenCV hỗ trợ xử lý ảnh và các hàm hình học
import numpy as np  # Nhập thư viện NumPy phục vụ tính toán số học và xử lý mảng


# Module TC2: ước lượng kích thước đường kính (từ đơn vị pixel sang mm) và phân hạng chất lượng quả.


def effective_pixel_to_mm(
    pixel_to_mm,
    calibration_gain,
    enable_depth,
    require_depth_for_size,
    current_depth_mm,
    depth_reference_mm,
):
    """Tính hệ số đổi từ pixel sang mm hiệu dụng, có thể bù trừ theo thông số độ sâu (depth) thực tế."""
    # Tính hệ số pixel-to-mm cơ bản bằng cách nhân hệ số gốc với hệ số hiệu chuẩn gain
    base = float(pixel_to_mm) * float(calibration_gain)
    
    # Kiểm tra xem có tắt tính năng bù trừ theo độ sâu (depth) hay không
    if not bool(enable_depth):
        # Nếu hệ thống bắt buộc phải có độ sâu mới cho đo kích thước mà chế độ này lại tắt
        if bool(require_depth_for_size):
            # Trả về giá trị lỗi thông báo thiếu thông tin độ sâu cần thiết
            return None, "depth_required_disabled"
        # Trả về hệ số cơ bản không bù trừ và nhãn nhận diện đo 2D
        return base, "2d_gain"

    # Trường hợp có bật độ sâu nhưng giá trị độ sâu hiện tại bị rỗng (None) hoặc khoảng cách tham chiếu không hợp lệ (<=0)
    if current_depth_mm is None or float(depth_reference_mm) <= 1e-6:
        # Nếu hệ thống bắt buộc phải có độ sâu hợp lệ mới cho phép đo size
        if bool(require_depth_for_size):
            # Trả về lỗi thông báo không lấy được khoảng cách Z
            return None, "depth_required_no_z"
        # Fallback về hệ số cơ bản đo 2D nếu không bắt buộc
        return base, "2d_gain"

    # Bù trừ khoảng cách từ camera đến tâm quả táo thay vì đến đỉnh quả táo:
    # Tâm quả táo nằm ở trung điểm giữa đỉnh quả táo (current_depth_mm) và mặt băng tải (depth_reference_mm)
    # Gán giá trị khoảng cách hiện tại vào biến z_center
    z_center = float(current_depth_mm)
    # Gán giá trị khoảng cách tham chiếu mặt băng tải vào biến depth_ref_val
    depth_ref_val = float(depth_reference_mm)
    # Nếu khoảng cách tham chiếu hợp lệ (>50mm) và khoảng cách đo được nhỏ hơn khoảng cách tham chiếu
    if depth_ref_val > 50.0 and z_center < depth_ref_val:
        # Áp dụng công thức trung bình cộng để ước lượng vị trí tâm quả táo
        z_center = (z_center + depth_ref_val) / 2.0

    # Tính hệ số tỷ lệ scale dựa trên khoảng cách từ tâm quả táo thực tế so với khoảng cách tham chiếu
    scale = z_center / depth_ref_val
    # Giới hạn giá trị tỷ lệ scale trong khoảng từ [0.5, 2.0] để tránh sai lệch quá lớn do nhiễu cảm biến
    scale = float(np.clip(scale, 0.5, 2.0))
    # Trả về hệ số hiệu chỉnh sau khi bù trừ và nhãn nhận diện đo có hỗ trợ độ sâu
    return base * scale, "depth_assisted"


def feret_stats_px(contour):
    """Tính toán các chỉ số đường kính Feret lớn nhất, nhỏ nhất và bách phân vị 90 (đơn vị pixel) trên nhiều hướng lấy mẫu."""
    # Kiểm tra tính hợp lệ của đường viền (contour), cần ít nhất 3 điểm để tạo thành đa giác khép kín
    if contour is None or len(contour) < 3:
        # Trả về giá trị 0 cho cả 3 chỉ số Feret nếu contour không hợp lệ
        return 0.0, 0.0, 0.0

    # Tìm bao lồi (convex hull) của đường viền để loại bỏ các vùng lõm cục bộ do răng cưa hoặc nhiễu phân đoạn
    hull = cv2.convexHull(contour)
    # Chuyển đổi định dạng bao lồi thành mảng 2D chứa tọa độ x, y kiểu số thực float32
    pts = hull.reshape(-1, 2).astype(np.float32)
    # Kiểm tra xem số điểm bao lồi có đủ tối thiểu 3 điểm hay không
    if pts.shape[0] < 3:
        # Trả về 0 nếu số lượng điểm bao lồi không đủ để tính toán hình học
        return 0.0, 0.0, 0.0

    # Tạo mảng chứa các góc lấy mẫu từ 0 đến 175 độ với bước nhảy 5 độ và chuyển sang đơn vị radian
    angles = np.deg2rad(np.arange(0, 180, 5, dtype=np.float32))
    # Tạo các vector hướng chiếu (cos(theta), sin(theta)) tương ứng với các góc lấy mẫu
    dirs = np.stack((np.cos(angles), np.sin(angles)), axis=1)
    # Thực hiện phép nhân ma trận để chiếu tất cả các điểm bao lồi lên các hướng vector đã tạo
    projections = pts @ dirs.T
    # Tính độ rộng nhịp (span) của bao lồi trên từng hướng bằng hiệu giữa giá trị chiếu lớn nhất và nhỏ nhất
    spans = projections.max(axis=0) - projections.min(axis=0)

    # Trả về giá trị cực đại của nhịp (Feret max), cực tiểu của nhịp (Feret min) và bách phân vị 90 (Feret P90)
    return float(np.max(spans)), float(np.min(spans)), float(np.percentile(spans, 90))


def pca_major_axis_px(contour):
    """Ước lượng chiều dài trục chính (đơn vị pixel) của quả táo dựa trên phân tích thành phần chính (PCA)."""
    # Yêu cầu đường viền contour phải có tối thiểu 5 điểm để đảm bảo tính toán ma trận hiệp phương sai ổn định
    if contour is None or len(contour) < 5:
        # Trả về 0 nếu contour không đủ điểm thực hiện PCA
        return 0.0

    # Chuyển đổi tọa độ các điểm contour thành mảng 2D kiểu số thực float32
    pts = contour.reshape(-1, 2).astype(np.float32)
    # Kiểm tra lại số điểm thực tế trong mảng
    if pts.shape[0] < 5:
        # Trả về 0 nếu mảng tọa độ quá ít điểm
        return 0.0

    # Chuẩn hóa tịnh tiến dữ liệu bằng cách trừ đi tọa độ trọng tâm (mean) để đưa dữ liệu về gốc tọa độ
    pts_centered = pts - pts.mean(axis=0, keepdims=True)
    # Tính ma trận hiệp phương sai 2x2 từ các tọa độ điểm đã chuẩn tâm
    cov = np.cov(pts_centered.T)
    try:
        # Thực hiện phân rã trị riêng và vectơ riêng trên ma trận hiệp phương sai thực đối xứng
        vals, vecs = np.linalg.eigh(cov)
    except Exception:
        # Trả về 0 nếu phép toán đại số tuyến tính bị lỗi (ví dụ ma trận suy biến)
        return 0.0

    # Tìm chỉ số của trị riêng (eigenvalue) lớn nhất, đại diện cho hướng biến thiên mạnh nhất của hình dáng
    idx = int(np.argmax(vals))
    # Lấy vectơ riêng (eigenvector) tương ứng làm vector định hướng của trục chính quả táo
    axis = vecs[:, idx]
    # Chiếu tọa độ các điểm đã chuẩn tâm lên vector trục chính này
    projections = pts_centered @ axis
    # Chiều dài trục chính được tính bằng khoảng cách giữa điểm chiếu xa nhất và gần nhất trên trục
    return max(0.0, float(np.max(projections) - np.min(projections)))


def estimate_diameter_px(contour, fallback_circle_diameter):
    """Ước lượng đường kính của quả táo (đơn vị pixel) kết hợp nhiều phương pháp hình học khác nhau."""
    # Tính toán diện tích của đường viền (contour) quả táo
    area = float(cv2.contourArea(contour))
    # Nếu diện tích quá nhỏ (nhỏ hơn hoặc bằng 1 pixel) thì không hợp lệ
    if area <= 1.0:
        # Trả về đường kính hình tròn dự phòng fallback
        return float(max(1.0, fallback_circle_diameter))

    # Phương pháp 1: Tính đường kính tương đương dựa trên diện tích hình tròn (Area-equivalent diameter)
    # Công thức: d = sqrt(4 * S / pi)
    diameter_area = float(np.sqrt((4.0 * area) / np.pi))

    # Phương pháp 2: Tính đường kính thông qua khớp elip (fitEllipse)
    # Gán giá trị mặc định ban đầu cho đường kính elip bằng đường kính diện tích
    diameter_ellipse = diameter_area
    # Khớp elip yêu cầu đường viền contour có ít nhất 5 điểm
    if contour is not None and len(contour) >= 5:
        try:
            # Khớp elip để lấy thông số tâm, độ dài hai trục elip (trục lớn, trục bé) và góc xoay
            (_, _), (axis_a, axis_b), _ = cv2.fitEllipse(contour)
            # Nếu độ dài hai trục đều dương hợp lệ
            if axis_a > 0 and axis_b > 0:
                # Tính đường kính elip trung bình cộng của hai trục
                diameter_ellipse = float((axis_a + axis_b) / 2.0)
        except Exception:
            # Nếu khớp elip lỗi (do contour tự cắt nhau,...) thì dùng đường kính diện tích làm dự phòng
            diameter_ellipse = diameter_area

    # Phương pháp 3: Ướg lượng đường kính theo bách phân vị Feret P90 để giảm nhiễu gai ở viền
    feret_max, _, feret_p90 = feret_stats_px(contour)
    # Nếu Feret P90 hợp lệ thì lấy, nếu không lấy Feret max, cuối cùng lấy đường kính diện tích
    diameter_feret = feret_p90 if feret_p90 > 0 else (feret_max if feret_max > 0 else diameter_area)

    # Phương pháp 4: Ước lượng đường kính dựa trên chiều dài trục chính PCA
    diameter_pca = pca_major_axis_px(contour)
    # Nếu PCA không tính toán được hoặc lỗi thì dự phòng bằng đường kính elip
    if diameter_pca <= 0:
        diameter_pca = diameter_ellipse

    # Trộn kết quả của 4 phương pháp trên theo tỷ lệ trọng số được cấu hình tối ưu để triệt tiêu sai số
    diameter_non_round = (
        (0.35 * diameter_area)      # Trọng số 35% cho đường kính tính từ diện tích hình tròn
        + (0.25 * diameter_ellipse)  # Trọng số 25% cho đường kính tính từ elip khớp viền
        + (0.30 * diameter_feret)    # Trọng số 30% cho đường kính đo theo khoảng Feret P90
        + (0.10 * diameter_pca)      # Trọng số 10% cho chiều dài tính bằng PCA
    )
    # Giới hạn kích thước ước lượng trong khoảng an toàn xung quanh đường kính diện tích nhằm tránh nhiễu gai lớn
    diameter_non_round = float(np.clip(diameter_non_round, 0.80 * diameter_area, 1.35 * max(1.0, diameter_area)))

    # Trộn thêm 8% đường kính từ vòng tròn ngoại tiếp tối thiểu (fallback_circle_diameter) để tăng tính ổn định qua các frame
    diameter_fused = (0.92 * diameter_non_round) + (0.08 * float(fallback_circle_diameter))
    # Trả về kết quả đường kính cuối cùng (đơn vị pixel) đảm bảo tối thiểu là 1.0 pixel
    return float(max(1.0, diameter_fused))


def classify_size(diameter_mm, thresholds):
    """Phân hạng kích cỡ quả táo sang hạng tương ứng dựa trên đường kính thực tế tính bằng mm."""
    # Nếu đường kính thực tế lớn hơn hoặc bằng ngưỡng quy định của hạng lớn (large_mm)
    if diameter_mm >= float(thresholds["large"]):
        # Trả về kết quả xếp loại là "LỚN (A)" và phân hạng Grade-1
        return "LON (A)", "Grade-1"
    # Nếu đường kính thực tế lớn hơn hoặc bằng ngưỡng hạng vừa (medium_mm)
    if diameter_mm >= float(thresholds["medium"]):
        # Trả về kết quả xếp loại là "VỪA (B)" và phân hạng Grade-2
        return "VUA (B)", "Grade-2"
    # Các trường hợp nhỏ hơn ngưỡng medium_mm đều xếp vào loại nhỏ
    # Trả về kết quả xếp loại là "NHỎ (C)" và phân hạng Grade-3
    return "NHO (C)", "Grade-3"

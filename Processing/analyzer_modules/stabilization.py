import numpy as np

from Processing.analyzer_modules.tc2_size import effective_pixel_to_mm as effective_pixel_to_mm_mod


# Module stabilization gom các phép làm mượt theo thời gian:
# - Làm mượt độ sâu Z.
# - Làm mượt đường kính mm.
# - Quy đổi px->mm theo trạng thái depth hiện tại.


def update_depth_context(analyzer, depth_info=None):
    """Cập nhật ngữ cảnh depth hiện tại với bộ lọc giữ ổn định theo thời gian."""
    # Nếu không có depth_info hợp lệ, tăng bộ đếm mất dữ liệu.
    if not isinstance(depth_info, dict):
        analyzer.depth_missing_frames += 1
        if analyzer.depth_missing_frames > analyzer.DEPTH_HOLD_FRAMES:
            analyzer.current_depth_mm = None
        return

    # Ưu tiên lấy z_distance_mm; nếu không có thì thử đổi từ mét sang mm.
    z_mm = depth_info.get("z_distance_mm", None)
    if z_mm is None:
        z_m = depth_info.get("z_distance_m", None)
        if z_m is not None:
            z_mm = float(z_m) * 1000.0

    # Ép kiểu an toàn để tránh lỗi do dữ liệu nhập không chuẩn.
    try:
        z_mm = float(z_mm)
    except Exception:
        z_mm = None

    # Loại bỏ giá trị depth bất thường ngoài dải làm việc.
    if z_mm is None or z_mm <= 50.0 or z_mm > 3000.0:
        analyzer.depth_missing_frames += 1
        if analyzer.depth_missing_frames > analyzer.DEPTH_HOLD_FRAMES:
            analyzer.current_depth_mm = None
        return

    # Có depth hợp lệ -> reset bộ đếm mất dữ liệu.
    analyzer.depth_missing_frames = 0

    # Giới hạn bước nhảy depth giữa hai frame để tránh rung số đo.
    if analyzer.current_depth_mm is not None and analyzer.DEPTH_MAX_DELTA_MM > 0:
        diff = float(z_mm) - float(analyzer.current_depth_mm)
        if abs(diff) > float(analyzer.DEPTH_MAX_DELTA_MM):
            z_mm = float(analyzer.current_depth_mm) + float(
                np.clip(diff, -analyzer.DEPTH_MAX_DELTA_MM, analyzer.DEPTH_MAX_DELTA_MM)
            )

    # Bù trừ khoảng cách từ camera đến tâm quả táo thay vì đỉnh quả táo:
    # Tâm quả táo nằm ở trung điểm giữa đỉnh quả táo (z_mm) và mặt băng tải (depth_reference_mm).
    # Công thức: Z_center = (z_mm + depth_reference_mm) / 2.0
    depth_ref = getattr(analyzer, "DEPTH_REFERENCE_MM", 0)
    if depth_ref > 50.0 and z_mm < depth_ref:
        z_mm = (z_mm + float(depth_ref)) / 2.0

    # Lọc median theo cửa sổ lịch sử để tăng ổn định.
    analyzer.depth_mm_history.append(z_mm)
    analyzer.current_depth_mm = float(np.median(analyzer.depth_mm_history))


def stabilize_diameter_mm(analyzer, diameter_mm):
    """Làm mượt đường kính mm bằng median + EMA + giới hạn bước nhảy."""
    # Phòng thủ kiểu dữ liệu đầu vào.
    if diameter_mm is None:
        return 0.0

    try:
        diameter_mm = float(diameter_mm)
    except Exception:
        return 0.0

    if diameter_mm <= 0.0:
        return 0.0

    # Cho phép bypass toàn bộ bộ ổn định khi cấu hình tắt.
    if not analyzer.ENABLE_DIAMETER_STABILIZER:
        return diameter_mm

    # Bước 1: median filter trên lịch sử ngắn hạn.
    analyzer.diameter_mm_history.append(diameter_mm)
    med_mm = float(np.median(analyzer.diameter_mm_history))

    # Bước 2: EMA để làm mượt xu hướng.
    if analyzer.diameter_mm_ema is None:
        analyzer.diameter_mm_ema = med_mm
    else:
        a = float(analyzer.DIAMETER_MM_ALPHA)
        analyzer.diameter_mm_ema = (a * med_mm) + ((1.0 - a) * float(analyzer.diameter_mm_ema))

    # Bước 3: trộn median và EMA.
    fused = (0.6 * med_mm) + (0.4 * float(analyzer.diameter_mm_ema))

    # Khởi tạo mốc ổn định đầu tiên.
    if analyzer.last_stable_diameter_mm is None:
        analyzer.last_stable_diameter_mm = fused
        return fused

    # Bước 4: giới hạn bước nhảy tối đa giữa 2 lần cập nhật.
    max_step = float(analyzer.DIAMETER_MM_MAX_STEP)
    delta = fused - float(analyzer.last_stable_diameter_mm)
    if abs(delta) > max_step:
        fused = float(analyzer.last_stable_diameter_mm) + (max_step if delta > 0 else -max_step)

    analyzer.last_stable_diameter_mm = fused
    return fused


def effective_pixel_to_mm(analyzer):
    """Tính hệ số quy đổi px->mm hiệu dụng và ghi nhận mode đo kích thước."""
    # Hàm tc2_size trả về cả hệ số và mode đo để pipeline ghi log/telemetry.
    px_to_mm, mode = effective_pixel_to_mm_mod(
        analyzer.PIXEL_TO_MM,
        analyzer.SIZE_CALIBRATION_GAIN,
        analyzer.ENABLE_DEPTH_SIZE_COMPENSATION,
        analyzer.REQUIRE_DEPTH_FOR_SIZE_MEASUREMENT,
        analyzer.current_depth_mm,
        analyzer.DEPTH_REFERENCE_MM,
    )
    analyzer.last_size_mode = mode
    return px_to_mm

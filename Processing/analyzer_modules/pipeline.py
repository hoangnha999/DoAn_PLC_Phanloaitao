import time

import cv2
import numpy as np

from Processing.analyzer_modules.tc3_shape import evaluate_shape as evaluate_shape_mod


# Pipeline tổng thể: nhận frame -> tách táo -> tính TC1/TC2/TC3 -> tổng hợp kết quả.


def analyze_apple(analyzer, frame):
    """Luồng phân tích chính cho một khung hình táo."""
    # (Đã bỏ apply_astra_pro_outdoor_profile mỗi frame vì nó sẽ ghi đè thiết lập của người dùng)
    # Bắt đầu đo thời gian xử lý frame.
    t_start = time.perf_counter()

    # Tạo detail rỗng để trả về an toàn khi frame lỗi.
    empty_detail = analyzer._empty_detail()
    if frame is None:
        return None, 0, 0, "UNKNOWN", empty_detail

    # Đánh giá độ mờ ngay đầu pipeline.
    blur_score, is_blurry = analyzer.detect_blur(frame)

    # Nếu frame mờ và được phép, thực hiện sharpen để cứu dữ liệu.
    if is_blurry and analyzer.auto_sharpen:
        frame = analyzer.sharpen_image(frame, strength=analyzer.sharpen_strength)
        blur_status = "BLURRY→SHARPENED"
    elif is_blurry:
        blur_status = "BLURRY"
    else:
        blur_status = "SHARP"

    blur_info = {
        "blur_score": blur_score,
        "is_blurry": is_blurry,
        "status": blur_status,
    }

    # Áp CLAHE cân bằng sáng nếu được cấu hình bật.
    # CLAHE chỉ thay đổi kênh độ sáng L trong LAB, giữ nguyên màu sắc.
    clahe_applied = False
    frame_for_seg = frame   # Frame đưa vào YOLO segmentation
    frame_for_hsv = frame   # Frame dùng để tính màu HSV (TC1)
    if getattr(analyzer, "ENABLE_CLAHE", False):
        if getattr(analyzer, "CLAHE_APPLY_TO_YOLO", True):
            frame_for_seg = analyzer.normalize_brightness(frame)
            clahe_applied = True
        if getattr(analyzer, "CLAHE_APPLY_TO_HSV", True):
            frame_for_hsv = analyzer.normalize_brightness(frame)
            clahe_applied = True

    # Tách quả táo (gate bởi YOLO + mask màu), dùng frame đã CLAHE nếu được bật.
    apple_mask, main_contour, yolo_info = analyzer._segment_apple(frame_for_seg)

    # Không thấy táo -> trả về no-apple với detail mặc định.
    if apple_mask is None or main_contour is None:
        frame = analyzer._draw_yolo_overlay(frame, yolo_info)
        return frame, 0, 0, "NO_APPLE", empty_detail

    # Diện tích contour dùng cho các thống kê khác.
    apple_area = cv2.contourArea(main_contour)

    # Làm trơn nhiễu rồi đổi HSV; dùng frame_for_hsv (có thể đã CLAHE) để tốt hơn khi sáng mạnh.
    blurred = cv2.GaussianBlur(frame_for_hsv, (5, 5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    # TC1: tính các tỉ lệ đỏ/vàng/xanh.
    tc1 = analyzer._compute_tc1_ratios(hsv, apple_mask)
    mask_red = tc1["mask_red"]
    mask_yellow = tc1["mask_yellow"]
    mask_green = tc1["mask_green"]
    red_cnts = tc1["red_cnts"]
    yellow_cnts = tc1["yellow_cnts"]
    red_ratio = tc1["red_ratio"]
    yellow_ratio = tc1["yellow_ratio"]
    green_ratio = tc1["green_ratio"]

    # Ánh xạ kết quả TC1 sang nhãn hiển thị + grade.
    ripeness_label, ripeness_grade = analyzer._classify_ripeness(red_ratio)

    # TC3: tính circularity và phân hạng hình dáng.
    circularity, shape_label, shape_grade = evaluate_shape_mod(
        main_contour,
        analyzer.SHAPE_GOOD_THRESH,
        analyzer.SHAPE_MEDIUM_THRESH,
    )

    # Lấy tâm contour bằng moments; fallback về minEnclosingCircle nếu moments lỗi.
    moments = cv2.moments(main_contour)
    if moments.get("m00", 0.0) > 1e-6:
        cx = float(moments["m10"] / moments["m00"])
        cy = float(moments["m01"] / moments["m00"])
    else:
        (cx, cy), _ = cv2.minEnclosingCircle(main_contour)

    # TC2: ước lượng đường kính contour-first + lọc median theo lịch sử.
    (_, _), radius_px_fallback = cv2.minEnclosingCircle(main_contour)
    diameter_px_circle = radius_px_fallback * 2.0
    diameter_px = analyzer._estimate_diameter_px(
        main_contour,
        circularity,
        fallback_circle_diameter=diameter_px_circle,
    )
    analyzer.diameter_history.append(float(diameter_px))
    diameter_px = float(np.median(analyzer.diameter_history))

    measured_radius_px = diameter_px / 2.0
    # Đổi px -> mm (có thể depth-assisted).
    px_to_mm_eff = analyzer._effective_pixel_to_mm()
    if px_to_mm_eff is None:
        diameter_mm = 0.0
        diameter_mm_raw = 0.0
        size_label, size_grade = "NO_DEPTH", "Grade-3"
    else:
        diameter_mm_raw = diameter_px * px_to_mm_eff
        diameter_mm = analyzer._stabilize_diameter_mm(diameter_mm_raw)
        size_label, size_grade = analyzer._classify_size(diameter_mm)

    # Tổng hợp grade theo nguyên tắc bảo thủ từ 3 tiêu chí chính.
    grade = analyzer._overall_grade(ripeness_grade, size_grade, shape_grade)

    # Vùng màu khác (không đỏ/vàng/xanh) để debug trực quan.
    mask_other = cv2.bitwise_and(
        apple_mask,
        cv2.bitwise_not(cv2.bitwise_or(mask_red, cv2.bitwise_or(mask_yellow, mask_green))),
    )

    # Vẽ overlay kết quả lên frame.
    res_frame = analyzer._draw_results(
        frame,
        main_contour,
        cx,
        cy,
        measured_radius_px,
        red_ratio,
        yellow_ratio,
        green_ratio,
        ripeness_label,
        size_label,
        diameter_mm,
        grade,
        yellow_cnts=yellow_cnts,
        red_cnts=red_cnts,
        mask_other=mask_other,
        shape_label=shape_label,
        yolo_info=yolo_info,
    )

    t_end = time.perf_counter()
    # Tổng thời gian xử lý một frame.
    processing_time_ms = (t_end - t_start) * 1000

    # Cập nhật FPS trung bình động bằng cửa sổ frame_times.
    current_time = time.perf_counter()
    frame_interval = current_time - analyzer.last_frame_time
    if frame_interval > 0:
        instant_fps = 1.0 / frame_interval
        analyzer.frame_times.append(instant_fps)
        analyzer.current_fps = sum(analyzer.frame_times) / len(analyzer.frame_times)
    analyzer.last_frame_time = current_time

    # Gói detail trả về đầy đủ cho GUI/db/log/session decision.
    detail_info = {
        "red_ratio": red_ratio,
        "yellow_ratio": yellow_ratio,
        "green_ratio": green_ratio,
        "center_x": float(cx),
        "center_y": float(cy),
        "frame_width": int(frame.shape[1]),
        "frame_height": int(frame.shape[0]),
        "red_ratio_raw": tc1["red_ratio_raw"],
        "yellow_ratio_raw": tc1["yellow_ratio_raw"],
        "green_ratio_raw": tc1["green_ratio_raw"],
        "ripeness_label": ripeness_label,
        "ripeness_grade": ripeness_grade,
        "diameter_px": diameter_px,
        "diameter_mm_raw": diameter_mm_raw,
        "diameter_mm": diameter_mm,
        "pixel_to_mm_effective": float(px_to_mm_eff) if px_to_mm_eff is not None else 0.0,
        "size_label": size_label,
        "size_grade": size_grade,
        "shape_label": shape_label,
        "shape_grade": shape_grade,
        "circularity": circularity,
        "processing_time_ms": processing_time_ms,
        "fps": analyzer.current_fps,
        "blur_score": blur_info["blur_score"],
        "blur_status": blur_info["status"],
        "is_blurry": blur_info["is_blurry"],
        "yolo_enabled": analyzer.use_yolo,
        "yolo_detected": bool(yolo_info.get("detected", False)),
        "yolo_confidence": float(yolo_info.get("conf", 0.0)),
        "yolo_class": yolo_info.get("class_name", "apple"),
        "track_id": yolo_info.get("track_id", None),
        "yolo_tracker_mode": yolo_info.get("tracker_mode", "predict"),
        "active_tracks": int(yolo_info.get("active_tracks", 0)),
        "z_distance_mm": analyzer.current_depth_mm,
        "size_measure_mode": analyzer.last_size_mode,
        "analysis_mode": "external_peel_only",
        "tc1_adaptive_hsv": bool(analyzer.TC1_ENABLE_ADAPTIVE_HSV),
        "tc1_temporal_smoothing": bool(analyzer.TC1_ENABLE_TEMPORAL_SMOOTHING),
        "tc1_smoothing_window": int(analyzer.TC1_SMOOTH_WINDOW),
        "clahe_enabled": bool(getattr(analyzer, "ENABLE_CLAHE", False)),
        "clahe_applied": bool(clahe_applied),
        "clahe_clip_limit": float(getattr(analyzer, "CLAHE_CLIP_LIMIT", 2.0)),
    }

    # Output chuẩn của pipeline.
    return res_frame, 0, red_ratio, grade, detail_info

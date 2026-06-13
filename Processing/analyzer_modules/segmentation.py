import cv2
import numpy as np


# Module segmentation: chỉ cho phép phân tích khi YOLO gate xác nhận có táo,
# sau đó tinh chỉnh mask vỏ táo bằng màu + hình thái học.


def segment_apple(
    frame,
    *,
    min_apple_area_ratio,
    lower_red1,
    upper_red1,
    lower_red2,
    upper_red2,
    lower_yellow,
    upper_yellow,
    lower_green,
    upper_green,
    yolo_conf_thresh,
    yolo_predict_conf,
    yolo_min_bbox_area_ratio,
    yolo_max_bbox_area_ratio,
    yolo_min_apple_color_ratio,
    yolo_enable_tracking,
    yolo_tracker_name,
    yolo_track_persist,
    yolo_roi_shrink_ratio,
    current_depth_mm,
    far_distance_mm_threshold,
    far_yolo_conf_scale,
    far_yolo_min_bbox_area_scale,
    far_min_apple_area_scale,
    far_min_apple_color_ratio_scale,
    use_yolo,
    yolo_model,
    yolo_status,
    yolo_reason,
    yolo_model_path,
    run_yolo_inference_cb,
    detection_zone_width_ratio=0.55,
    detection_zone_height_ratio=0.70,
):
    """Phân đoạn lai (hybrid) với điều kiện bắt buộc qua cổng YOLO.

    detection_zone_width_ratio / detection_zone_height_ratio:
        Tỉ lệ so với kích thước frame để tạo vùng phát hiện trung tâm.
        Chỉ YOLO bbox có tâm nằm trong vùng này mới được xử lý tiếp.
    """

    def _fallback_from_yolo_bbox():
        """Fallback segmentation dựa trên bbox YOLO, bền hơn khi nền có con lăn đen."""
        bbox = yolo_info.get("bbox") or yolo_info.get("bbox_raw")
        if not bbox:
            return None, None

        try:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            x1 = int(np.clip(x1, 0, w - 1))
            y1 = int(np.clip(y1, 0, h - 1))
            x2 = int(np.clip(x2, 0, w - 1))
            y2 = int(np.clip(y2, 0, h - 1))
            if x2 <= x1 or y2 <= y1:
                return None, None

            bw = max(1, x2 - x1)
            bh = max(1, y2 - y1)

            # Dùng ellipse core lệch nhẹ lên trên để giảm nhiễu vùng con lăn ở đáy.
            cx = x1 + bw // 2
            cy = y1 + int(round(bh * 0.48))
            rx = max(3, int(round(bw * 0.42)))
            ry = max(3, int(round(bh * 0.40)))

            core = np.zeros((h, w), dtype=np.uint8)
            cv2.ellipse(core, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)

            # Chặn vùng quá tối (đen) để giảm dính con lăn/băng tải đen.
            hsv_full = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            s_ch = hsv_full[:, :, 1]
            v_ch = hsv_full[:, :, 2]
            # Pixel hợp lệ: không quá tối và có một mức bão hòa nhất định.
            non_dark = cv2.inRange(v_ch, 28, 255)
            sat_ok = cv2.inRange(s_ch, 18, 255)
            mask_valid = cv2.bitwise_and(non_dark, sat_ok)

            candidate = cv2.bitwise_and(core, mask_valid)
            candidate = cv2.bitwise_and(candidate, yolo_mask)

            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, k, iterations=2)
            candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, k, iterations=1)

            cnts, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                return None, None

            best = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(best) < effective_min_area * 0.45:
                return None, None

            fallback_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(fallback_mask, [best], -1, 255, -1)
            yolo_info["reason"] = "segmentation fallback: yolo-ellipse core"
            return fallback_mask, best
        except Exception:
            return None, None
    # Kích thước frame và ngưỡng diện tích contour tối thiểu.
    h, w = frame.shape[:2]
    min_area = h * w * float(min_apple_area_ratio)

    # ─── Vùng phát hiện trung tâm (Detection Zone) ────────────────────────
    # Chỉ YOLO bbox có TÂM nằm trong vùng hình chữ nhật này mới được chấp nhận.
    dz_w = int(w * float(np.clip(detection_zone_width_ratio, 0.1, 1.0)))
    dz_h = int(h * float(np.clip(detection_zone_height_ratio, 0.1, 1.0)))
    dz_x1 = (w - dz_w) // 2
    dz_y1 = (h - dz_h) // 2
    dz_x2 = dz_x1 + dz_w
    dz_y2 = dz_y1 + dz_h

    # Nới ngưỡng khi táo ở xa để tránh rớt detect do vật thể biểu kiến quá nhỏ.
    is_far_distance = False
    try:
        if current_depth_mm is not None and float(current_depth_mm) >= float(far_distance_mm_threshold):
            is_far_distance = True
    except Exception:
        is_far_distance = False

    effective_min_area = float(min_area)
    effective_yolo_conf_thresh = float(yolo_conf_thresh)
    effective_yolo_min_bbox_area_ratio = float(yolo_min_bbox_area_ratio)
    effective_yolo_min_apple_color_ratio = float(yolo_min_apple_color_ratio)
    if is_far_distance:
        effective_min_area = float(min_area) * float(np.clip(far_min_apple_area_scale, 0.15, 1.0))
        effective_yolo_conf_thresh = max(0.15, float(yolo_conf_thresh) * float(np.clip(far_yolo_conf_scale, 0.40, 1.0)))
        effective_yolo_min_bbox_area_ratio = float(yolo_min_bbox_area_ratio) * float(
            np.clip(far_yolo_min_bbox_area_scale, 0.15, 1.0)
        )
        effective_yolo_min_apple_color_ratio = max(
            0.004,
            float(yolo_min_apple_color_ratio) * float(np.clip(far_min_apple_color_ratio_scale, 0.30, 1.0)),
        )

    # yolo_mask là ROI sau khi chọn bbox tốt nhất từ YOLO.
    yolo_mask = None
    # Metadata phục vụ debug/giám sát ở GUI và log.
    yolo_info = {
        "enabled": bool(use_yolo and yolo_model is not None),
        "detected": False,
        "conf": 0.0,
        "bbox": None,
        "bbox_raw": None,
        "class_name": "apple",
        "track_id": None,
        "active_tracks": 0,
        "box_count": 0,
        "candidates": [],
        "status": yolo_status,
        "reason": yolo_reason,
        "model_path": yolo_model_path,
        "tracker_mode": "predict",
        "tracker_name": yolo_tracker_name,
        "gate_conf_thresh": float(effective_yolo_conf_thresh),
        "gate_min_bbox_area_ratio": float(effective_yolo_min_bbox_area_ratio),
        "gate_min_apple_color_ratio": float(effective_yolo_min_apple_color_ratio),
        "depth_mm": float(current_depth_mm) if current_depth_mm is not None else None,
        "far_distance_mode": bool(is_far_distance),
        # Vùng phát hiện trung tâm (để visualization vẽ lên frame)
        "detection_zone": (dz_x1, dz_y1, dz_x2, dz_y2),
    }

    # Khối gate YOLO: tìm bbox táo hợp lệ trước khi segmentation chi tiết.
    if use_yolo and yolo_model is not None:
        try:
            # Chạy inference (predict/track tùy mode).
            results, infer_mode, track_warn = run_yolo_inference_cb(frame)
            yolo_info["tracker_mode"] = infer_mode
            if track_warn:
                yolo_info["reason"] = f"tracking fallback: {track_warn}"

            # Biến lưu candidate tốt nhất và candidate ưu tiên class apple rõ ràng.
            best_box = None
            best_conf = 0.0
            best_class_name = "apple"
            best_track_id = None
            preferred_box = None
            preferred_conf = 0.0
            preferred_class_name = "apple"
            preferred_track_id = None
            reject_reason = ""

            boxes = list(results.boxes) if results.boxes is not None else []
            yolo_info["box_count"] = len(boxes)
            names_map = results.names if hasattr(results, "names") and isinstance(results.names, dict) else {}
            single_class_model = len(names_map) == 1 and len(boxes) > 0
            min_bbox_area = h * w * float(effective_yolo_min_bbox_area_ratio)
            max_bbox_area = h * w * float(np.clip(float(yolo_max_bbox_area_ratio), 0.05, 1.0))

            # Duyệt từng bbox để lọc theo class, diện tích và confidence.
            for box in boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0]) if hasattr(box, "cls") else -1
                class_name = "apple"
                track_id = None
                if hasattr(box, "id") and box.id is not None:
                    try:
                        track_id = int(box.id[0])
                    except Exception:
                        track_id = None

                if names_map:
                    class_name = str(names_map.get(cls_id, class_name))

                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                bx1, by1, bx2, by2 = xyxy
                bw = max(0, int(bx2) - int(bx1))
                bh = max(0, int(by2) - int(by1))
                bbox_area = bw * bh

                # Nhận diện class táo theo tên class hoặc single-class model.
                name_lower = class_name.lower()
                is_apple_class = single_class_model or ("apple" in name_lower or "tao" in name_lower)

                yolo_info["candidates"].append(
                    {
                        "bbox": (int(bx1), int(by1), int(bx2), int(by2)),
                        "conf": float(conf),
                        "class_name": class_name,
                        "track_id": track_id,
                        "is_apple_class": bool(is_apple_class),
                        "bbox_area": float(bbox_area),
                    }
                )

                # Loại bỏ khung không phải táo.
                if not is_apple_class:
                    reject_reason = f"class '{class_name}' is not apple"
                    continue

                # Loại bỏ bbox quá nhỏ/quá lớn (không phù hợp vật thể thật).
                if bbox_area < min_bbox_area:
                    reject_reason = f"bbox too small: {bbox_area}px < {int(min_bbox_area)}px"
                    continue

                if bbox_area > max_bbox_area:
                    reject_reason = f"bbox too large: {bbox_area}px > {int(max_bbox_area)}px"
                    continue

                # Cập nhật candidate tốt nhất theo confidence.
                if conf > best_conf:
                    best_conf = conf
                    best_box = box
                    best_class_name = class_name
                    best_track_id = track_id

                # Candidate ưu tiên nếu class name thể hiện rõ là apple/táo.
                if ("apple" in name_lower or "tao" in name_lower) and conf > preferred_conf:
                    preferred_conf = conf
                    preferred_box = box
                    preferred_class_name = class_name
                    preferred_track_id = track_id

            # Nếu có candidate ưu tiên thì ghi đè candidate chung.
            if preferred_box is not None:
                best_box = preferred_box
                best_conf = preferred_conf
                best_class_name = preferred_class_name
                best_track_id = preferred_track_id

            # Thống kê số đối tượng đang được tracker gán id.
            yolo_info["active_tracks"] = sum(1 for c in yolo_info["candidates"] if c.get("track_id") is not None)

            # Gate pass khi có bbox hợp lệ và confidence đạt ngưỡng.
            if best_box is not None and best_conf >= float(effective_yolo_conf_thresh):
                xyxy = best_box.xyxy[0].cpu().numpy().astype(int)
                bx1, by1, bx2, by2 = xyxy

                # ─── Kiểm tra tâm bbox có nằm trong Detection Zone ────────
                bbox_cx = (int(bx1) + int(bx2)) // 2
                bbox_cy = (int(by1) + int(by2)) // 2
                if not (dz_x1 <= bbox_cx <= dz_x2 and dz_y1 <= bbox_cy <= dz_y2):
                    yolo_info["reason"] = (
                        f"yolo gate blocked: center ({bbox_cx},{bbox_cy}) "
                        f"outside detection zone ({dz_x1},{dz_y1})-({dz_x2},{dz_y2})"
                    )
                    return None, None, yolo_info

                # Gate theo tỉ lệ màu táo trong bbox để chặn false-positive nền/tường.
                x1 = int(np.clip(bx1, 0, w - 1))
                y1 = int(np.clip(by1, 0, h - 1))
                x2 = int(np.clip(bx2, 0, w - 1))
                y2 = int(np.clip(by2, 0, h - 1))
                if x2 <= x1 or y2 <= y1:
                    yolo_info["reason"] = "yolo gate blocked: invalid bbox geometry"
                    return None, None, yolo_info

                roi = frame[y1:y2, x1:x2]
                if roi.size > 0:
                    # Tính ratio màu "giống táo" bên trong bbox YOLO.
                    hsv_roi = cv2.cvtColor(cv2.GaussianBlur(roi, (5, 5), 0), cv2.COLOR_BGR2HSV)
                    roi_r1 = cv2.inRange(hsv_roi, lower_red1, upper_red1)
                    roi_r2 = cv2.inRange(hsv_roi, lower_red2, upper_red2)
                    roi_y = cv2.inRange(hsv_roi, lower_yellow, upper_yellow)
                    roi_apple = cv2.bitwise_or(roi_r1, cv2.bitwise_or(roi_r2, roi_y))
                    color_ratio = float(cv2.countNonZero(roi_apple)) / float(roi_apple.size)
                    yolo_info["apple_color_ratio"] = float(color_ratio)
                    if color_ratio < float(effective_yolo_min_apple_color_ratio):
                        yolo_info["reason"] = (
                            f"yolo gate blocked: apple-color ratio {color_ratio:.4f} "
                            f"< {float(effective_yolo_min_apple_color_ratio):.4f}"
                        )
                        return None, None, yolo_info

                # Thu nhỏ ROI một chút để loại bớt viền bbox.
                bw = max(1, int(bx2) - int(bx1))
                bh = max(1, int(by2) - int(by1))
                shrink_x = int(round(bw * float(np.clip(float(yolo_roi_shrink_ratio), 0.0, 0.25))))
                shrink_y = int(round(bh * float(np.clip(float(yolo_roi_shrink_ratio), 0.0, 0.25))))
                sx1 = int(np.clip(int(bx1) + shrink_x, 0, w - 1))
                sy1 = int(np.clip(int(by1) + shrink_y, 0, h - 1))
                sx2 = int(np.clip(int(bx2) - shrink_x, 0, w - 1))
                sy2 = int(np.clip(int(by2) - shrink_y, 0, h - 1))

                if sx2 <= sx1 or sy2 <= sy1:
                    sx1, sy1, sx2, sy2 = int(bx1), int(by1), int(bx2), int(by2)

                # Ghi nhận thông tin detect thành công.
                yolo_info.update(
                    {
                        "detected": True,
                        "conf": float(best_conf),
                        "bbox_raw": (int(bx1), int(by1), int(bx2), int(by2)),
                        "bbox": (sx1, sy1, sx2, sy2),
                        "class_name": best_class_name,
                        "track_id": best_track_id,
                    }
                )

                yolo_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.rectangle(yolo_mask, (sx1, sy1), (sx2, sy2), 255, -1)
            else:
                # Ghi lý do gate fail để thuận tiện debug.
                if best_box is None and reject_reason:
                    yolo_info["reason"] = f"yolo gate blocked: {reject_reason}"
                elif best_box is not None:
                    yolo_info["reason"] = (
                        f"yolo gate blocked: conf {best_conf:.3f} < {float(effective_yolo_conf_thresh):.2f}"
                    )
                else:
                    yolo_info["reason"] = "yolo gate blocked: no apple candidate"
        except Exception as e:
                # Bắt lỗi inference nhưng không làm crash toàn pipeline.
            yolo_info["reason"] = f"predict error: {e}"

            # Hệ thống hiện tại bắt buộc phải qua YOLO gate.
    if not yolo_info["enabled"]:
        yolo_info["reason"] = "yolo gate blocked: model unavailable"
        return None, None, yolo_info

    # Gate chưa pass thì dừng sớm.
    if not yolo_info["detected"] or yolo_mask is None:
        if not yolo_info.get("reason"):
            yolo_info["reason"] = "yolo gate blocked: no apple detected"
        return None, None, yolo_info

    # Sau gate pass: segmentation fine-grained theo màu/hình thái học.
    blurred = cv2.GaussianBlur(frame, (9, 9), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    mask_roi = yolo_mask

    # Mask màu táo (đỏ/vàng).
    mask_r1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask_r2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask_y = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_apple_colors = cv2.bitwise_or(mask_r1, cv2.bitwise_or(mask_r2, mask_y))

    # Loại bỏ vùng xanh và vùng quá tối.
    mask_green = cv2.inRange(hsv, lower_green, upper_green)
    mask_not_green = cv2.bitwise_not(mask_green)

    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2LAB)
    _, mask_bright = cv2.threshold(lab[:, :, 0], 40, 255, cv2.THRESH_BINARY)

    # Kết hợp điều kiện màu + độ sáng + ROI YOLO.
    combined = cv2.bitwise_and(mask_apple_colors, cv2.bitwise_and(mask_not_green, mask_bright))
    combined = cv2.bitwise_and(combined, mask_roi)

    # Đóng/mở hình thái học để làm sạch mask.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)
    opened = cv2.dilate(opened, np.ones((3, 3), np.uint8), iterations=1)

    # Tìm contour ứng viên.
    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        fb_mask, fb_cnt = _fallback_from_yolo_bbox()
        if fb_mask is not None and fb_cnt is not None:
            x_ref, y_ref, w_ref, h_ref = cv2.boundingRect(fb_cnt)
            yolo_info["bbox_refined"] = (int(x_ref), int(y_ref), int(x_ref + w_ref), int(y_ref + h_ref))
            return fb_mask, fb_cnt, yolo_info

        # Fallback HoughCircles khi mask màu thất bại.
        gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
        circles = cv2.HoughCircles(
            cv2.medianBlur(gray, 7),
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=200,
            param1=50,
            param2=35,
            minRadius=int(h * (0.06 if is_far_distance else 0.1)),
            maxRadius=int(h * 0.45),
        )
        if circles is not None:
            circles = np.uint16(np.around(circles))
            i = circles[0, 0]
            c_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(c_mask, (i[0], i[1]), i[2], 255, -1)
            h_contours, _ = cv2.findContours(c_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if h_contours:
                return c_mask, h_contours[0], yolo_info
        return None, None, yolo_info

    # Chọn contour tốt nhất theo area + circularity, kèm ràng buộc solidity/aspect.
    best_cnt = None
    max_score = -1

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < effective_min_area:
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter ** 2)

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        x, y, w_rect, h_rect = cv2.boundingRect(cnt)
        aspect_ratio = float(w_rect) / h_rect

        if circularity > 0.45 and solidity > 0.76 and (0.6 < aspect_ratio < 1.6):
            if area < (h * w * 0.35):
                # Score ưu tiên contour lớn và tròn hơn.
                score = area * (0.7 + 0.3 * circularity)
                if score > max_score:
                    max_score = score
                    best_cnt = cnt

    if best_cnt is not None:
        # Làm mượt contour để mask đẹp và ổn định hơn.
        best_cnt = cv2.approxPolyDP(best_cnt, epsilon=1.8, closed=True)
        apple_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(apple_mask, [best_cnt], -1, 255, -1)

        # Ghi bbox tinh chỉnh từ contour đã segment.
        x_ref, y_ref, w_ref, h_ref = cv2.boundingRect(best_cnt)
        if w_ref > 0 and h_ref > 0:
            yolo_info["bbox_refined"] = (int(x_ref), int(y_ref), int(x_ref + w_ref), int(y_ref + h_ref))
        return apple_mask, best_cnt, yolo_info

    fb_mask, fb_cnt = _fallback_from_yolo_bbox()
    if fb_mask is not None and fb_cnt is not None:
        x_ref, y_ref, w_ref, h_ref = cv2.boundingRect(fb_cnt)
        yolo_info["bbox_refined"] = (int(x_ref), int(y_ref), int(x_ref + w_ref), int(y_ref + h_ref))
        return fb_mask, fb_cnt, yolo_info

    # Không có contour đạt tiêu chí.
    return None, None, yolo_info

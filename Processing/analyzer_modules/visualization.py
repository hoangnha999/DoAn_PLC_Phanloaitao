import cv2
import numpy as np


def draw_results(
    analyzer,
    frame,
    contour,
    cx,
    cy,
    radius_px,
    red_r,
    yellow_r,
    green_r,
    ripeness_label,
    size_label,
    diameter_mm,
    grade,
    yellow_cnts=None,
    red_cnts=None,
    mask_other=None,
    shape_label="",
    yolo_info=None,
):
    """Vẽ kết quả phân tích chính lên frame đầu ra."""
    res = frame.copy()

    color_map = {"Grade-1": (0, 255, 0), "Grade-2": (0, 255, 255), "Grade-3": (0, 0, 255)}
    color = color_map.get(grade, (255, 255, 255))

    cv2.drawContours(res, [contour], -1, color, 2)

    if yellow_cnts:
        cv2.drawContours(res, yellow_cnts, -1, (0, 255, 255), 1)
    if red_cnts:
        cv2.drawContours(res, red_cnts, -1, (0, 0, 255), 1)

    if mask_other is not None:
        overlay = res.copy()
        overlay[mask_other > 0] = (100, 100, 100)
        cv2.addWeighted(overlay, 0.4, res, 0.6, 0, res)

    if contour is not None and len(contour) >= 5:
        rrect = cv2.minAreaRect(contour)
        box_pts = cv2.boxPoints(rrect).astype(np.int32)
        cv2.polylines(res, [box_pts], True, (255, 255, 0), 2)

        (rx, ry), (rw, rh), ang = rrect
        major_len = max(rw, rh)
        theta = np.deg2rad(ang if rw >= rh else (ang + 90.0))
        dx = 0.5 * major_len * np.cos(theta)
        dy = 0.5 * major_len * np.sin(theta)
        p1 = (int(rx - dx), int(ry - dy))
        p2 = (int(rx + dx), int(ry + dy))
        cv2.line(res, p1, p2, (255, 255, 0), 2)
    else:
        cv2.line(res, (int(cx - radius_px), int(cy)), (int(cx + radius_px), int(cy)), (255, 255, 0), 2)

    info_text = f"D = {diameter_mm:.1f} mm"
    c_text = (0, 255, 255)
    cv2.putText(res, info_text, (int(cx - 80), int(cy - 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c_text, 2)

    center_xy = (int(cx), int(cy))
    cv2.circle(res, center_xy, 4, (255, 0, 255), -1)
    cv2.circle(res, center_xy, 10, (255, 0, 255), 1)
    cv2.putText(
        res,
        f"C({int(cx)},{int(cy)})",
        (int(cx + 8), int(cy + 18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (255, 0, 255),
        1,
    )

    res = draw_yolo_overlay(analyzer, res, yolo_info)
    return res


def draw_yolo_overlay(analyzer, frame, yolo_info=None):
    """Vẽ overlay YOLO gồm candidate boxes và box được chấp nhận cuối cùng."""
    if yolo_info is None:
        return frame

    out = frame.copy()

    for cand in yolo_info.get("candidates", [])[:5]:
        bbox = cand.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 165, 255), 1)

    if yolo_info.get("detected"):
        bbox = yolo_info.get("bbox_refined") or yolo_info.get("bbox")
        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(out, (x1, y1), (x2, y2), (50, 220, 50), 2)

            class_name = str(yolo_info.get("class_name", "apple"))
            conf = float(yolo_info.get("conf", 0.0))
            label = f"{class_name} {conf:.2f}"
            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            y_top = max(0, y1 - th - baseline - 6)
            cv2.rectangle(out, (x1, y_top), (x1 + tw + 8, y_top + th + baseline + 6), (50, 220, 50), -1)
            cv2.putText(out, label, (x1 + 4, y_top + th + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2)

    return out


def empty_detail():
    """Trả về detail mặc định khi không phát hiện được quả táo."""
    return {
        "red_ratio": 0,
        "yellow_ratio": 0,
        "green_ratio": 0,
        "ripeness_label": "---",
        "ripeness_grade": "---",
        "diameter_px": 0,
        "diameter_mm": 0,
        "size_label": "---",
        "size_grade": "---",
        "shape_label": "---",
        "shape_grade": "---",
        "circularity": 0.0,
    }


def get_foreground_mask(analyzer, frame):
    """Tách foreground bằng MOG2 để dùng cho debug/quan sát."""
    if frame is None:
        return None
    mask = analyzer.bg_subtractor.apply(frame)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=2)
    return mask

def grade_rank(grade):
    # Thứ tự mức độ: số lớn hơn nghĩa là xấu hơn.
    order = {"Grade-1": 1, "Grade-2": 2, "Grade-3": 3}
    # Giá trị mặc định 99 để đẩy grade lạ xuống cuối.
    return order.get(grade, 99)


def compute_frame_quality_weight(detail_info, blur_threshold=100.0):
    # Lấy các thông số chất lượng khung hình.
    blur_score = float(detail_info.get("blur_score", 0.0))
    yolo_conf = float(detail_info.get("yolo_confidence", 0.0))
    is_blurry = bool(detail_info.get("is_blurry", False))
    circularity = float(detail_info.get("circularity", 1.0))

    # Chuẩn hóa blur về [0,1], dùng mốc 2x threshold để tránh cắt ngưỡng quá gắt.
    blur_quality = max(0.0, min(1.0, blur_score / max(1.0, float(blur_threshold) * 2.0)))
    # Chuẩn hóa yolo_conf về [0,1], bỏ qua vùng confidence rất thấp.
    yolo_quality = max(0.0, min(1.0, (yolo_conf - 0.20) / 0.80))

    # Trộn điểm theo tỉ trọng: blur 50%, yolo 35%, circularity 15%.
    circ_quality = max(0.0, min(1.0, (circularity - 0.30) / 0.70))
    quality_score = (0.50 * blur_quality) + (0.35 * yolo_quality) + (0.15 * circ_quality)
    # Nếu khung mờ thì phạt thêm hệ số giảm chất lượng.
    if is_blurry:
        quality_score *= 0.75

    # Phạt nặng frame có circularity quá thấp (contour méo, segment sai).
    # Frame 3 với circularity=0.361 sẽ bị phạt: quality *= 0.30
    CIRCULARITY_REJECT_THRESH = 0.50
    if circularity < CIRCULARITY_REJECT_THRESH:
        penalty = max(0.10, circularity / CIRCULARITY_REJECT_THRESH)
        quality_score *= penalty

    # Clamp về [0,1] và đặt cận dưới cho weight để frame không bị bỏ qua hoàn toàn.
    quality_score = max(0.0, min(1.0, quality_score))
    weight = max(0.05, quality_score)
    return quality_score, weight


def fuse_session_decision(session_entries, min_quality_score, min_valid_frames, margin_delta):
    # Bảng điểm tích lũy cho từng grade.
    score_map = {"Grade-1": 0.0, "Grade-2": 0.0, "Grade-3": 0.0}
    total_weight = 0.0
    valid_entries = []

    # Lọc các bản ghi đạt chất lượng tối thiểu và tích lũy trọng số.
    for rec in session_entries:
        grade = str(rec.get("grade", ""))
        quality = float(rec.get("quality_score", 0.0))
        weight = float(rec.get("weight", 0.0))

        if grade not in score_map or quality < float(min_quality_score):
            continue

        valid_entries.append(rec)
        score_map[grade] += max(0.0, weight)
        total_weight += max(0.0, weight)

    # Nếu không đủ dữ liệu hợp lệ thì fallback theo grade xấu nhất đã xuất hiện.
    if not valid_entries or len(valid_entries) < int(min_valid_frames) or total_weight <= 1e-9:
        all_grades = [str(r.get("grade", "")) for r in session_entries if str(r.get("grade", "")) in score_map]
        fallback = "Grade-3" if not all_grades else sorted(all_grades, key=grade_rank)[-1]
        return fallback, {
            "method": "fallback_worst_grade",
            "reason": "insufficient_valid_frames",
            "valid_count": len(valid_entries),
            "required_valid": int(min_valid_frames),
            "scores": score_map,
            "normalized": {"Grade-1": 0.0, "Grade-2": 0.0, "Grade-3": 0.0},
            "margin": 0.0,
        }

    # Chuẩn hóa điểm thành tỉ lệ đóng góp.
    normalized = {k: (v / total_weight) for k, v in score_map.items()}
    # Sắp xếp giảm dần để lấy top-1 và top-2.
    ranked = sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)
    top1_grade, top1_score = ranked[0]
    top2_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top1_score - top2_score

    # Nếu khoảng cách giữa 2 top quá nhỏ thì kết luận chưa chắc chắn, fallback bảo thủ.
    if margin < float(margin_delta):
        valid_grades = [str(r.get("grade", "")) for r in valid_entries]
        fallback = sorted(valid_grades, key=grade_rank)[-1]
        return fallback, {
            "method": "fallback_worst_grade",
            "reason": "low_margin",
            "valid_count": len(valid_entries),
            "required_valid": int(min_valid_frames),
            "scores": score_map,
            "normalized": normalized,
            "margin": float(margin),
        }

    # Margin đạt yêu cầu -> chấp nhận kết quả voting trọng số.
    return top1_grade, {
        "method": "weighted_voting",
        "reason": "ok",
        "valid_count": len(valid_entries),
        "required_valid": int(min_valid_frames),
        "scores": score_map,
        "normalized": normalized,
        "margin": float(margin),
    }


def compute_temporal_stability(grade_sequence):
    # Lọc grade hợp lệ để tránh nhiễu dữ liệu.
    seq = [g for g in grade_sequence if g in ("Grade-1", "Grade-2", "Grade-3")]
    # 0/1 phần tử thì xem như ổn định tuyệt đối.
    if len(seq) <= 1:
        return 1.0, 0

    # Đếm số lần đổi nhãn giữa hai frame liên tiếp.
    changes = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    # Độ ổn định = 1 - tỉ lệ đổi nhãn.
    stability = 1.0 - (changes / float(len(seq) - 1))
    return max(0.0, min(1.0, stability)), changes


def aggregate_track_decisions(sample_records, *, single_fruit_station_mode, decision_min_quality_score, track_min_frames):
    # Tập grade hợp lệ để kiểm tra nhanh.
    grade_set = {"Grade-1", "Grade-2", "Grade-3"}

    # Nhánh 1: chế độ trạm 1 quả (không cần tách theo track id).
    if single_fruit_station_mode:
        sequence = []
        score_map = {"Grade-1": 0.0, "Grade-2": 0.0, "Grade-3": 0.0}
        total_weight = 0.0

        # Tổng hợp theo thời gian cho một đối tượng duy nhất.
        for rec in sample_records:
            grade = str(rec.get("grade", ""))
            if grade not in grade_set:
                continue

            quality = float(rec.get("quality_score", 0.0))
            if quality < float(decision_min_quality_score):
                continue

            weight = float(rec.get("decision_weight", rec.get("weight", 0.0)))
            w = max(0.05, weight)
            sequence.append(grade)
            score_map[grade] += w
            total_weight += w

        # Nếu quá ít frame hợp lệ thì chưa đưa ra kết luận track.
        if len(sequence) < int(track_min_frames) or total_weight <= 1e-9:
            return {
                "total_tracks": 0,
                "defect_tracks": 0,
                "defect_ratio": 0.0,
                "temporal_stability": 0.0,
                "tracks": {},
                "decision_entries": [],
            }

        # Chọn grade có tổng trọng số cao nhất.
        final_grade = max(score_map.items(), key=lambda kv: kv[1])[0]
        stability, label_changes = compute_temporal_stability(sequence)
        normalized = {k: (v / total_weight) for k, v in score_map.items()}
        confidence = float(normalized.get(final_grade, 0.0))
        defect_tracks = 0 if final_grade == "Grade-1" else 1

        return {
            "total_tracks": 1,
            "defect_tracks": defect_tracks,
            "defect_ratio": float(defect_tracks),
            "temporal_stability": float(stability),
            "tracks": {
                "station_1": {
                    "track_id": "station_1",
                    "frames": len(sequence),
                    "final_grade": final_grade,
                    "label_changes": int(label_changes),
                    "temporal_stability": float(stability),
                    "score_map": score_map,
                    "normalized": normalized,
                    "confidence": confidence,
                    "is_defect": bool(defect_tracks == 1),
                }
            },
            "decision_entries": [
                {
                    "grade": final_grade,
                    "quality_score": confidence,
                    "weight": max(0.2, float(len(sequence)) * max(0.2, confidence)),
                }
            ],
        }

    # Nhánh 2: chế độ nhiều track. Gom bản ghi theo track id.
    per_track = {}
    for rec in sample_records:
        track_id = rec.get("track_id", None)
        grade = str(rec.get("grade", ""))
        quality = float(rec.get("quality_score", 0.0))
        weight = float(rec.get("decision_weight", rec.get("weight", 0.0)))

        # Bỏ qua bản ghi không hợp lệ.
        if track_id is None or grade not in grade_set:
            continue
        try:
            track_id = int(track_id)
        except Exception:
            continue
        if track_id < 0 or quality < float(decision_min_quality_score):
            continue

        key = str(track_id)
        # Khởi tạo cấu trúc track nếu chưa có.
        info = per_track.setdefault(key, {
            "track_id": track_id,
            "sequence": [],
            "score_map": {"Grade-1": 0.0, "Grade-2": 0.0, "Grade-3": 0.0},
            "total_weight": 0.0,
        })

        # Tích lũy dữ liệu theo từng track.
        info["sequence"].append(grade)
        w = max(0.05, weight)
        info["score_map"][grade] += w
        info["total_weight"] += w

    track_outputs = {}
    defect_tracks = 0
    stability_values = []
    decision_entries = []

    # Duyệt từng track để kết luận final grade + confidence.
    for key, info in per_track.items():
        seq = info["sequence"]
        if len(seq) < int(track_min_frames):
            continue

        score_map = info["score_map"]
        final_grade = max(score_map.items(), key=lambda kv: kv[1])[0]
        stability, label_changes = compute_temporal_stability(seq)

        if final_grade != "Grade-1":
            defect_tracks += 1

        stability_values.append(stability)
        total_w = max(info["total_weight"], 1e-9)
        normalized = {k: (v / total_w) for k, v in score_map.items()}
        confidence = normalized.get(final_grade, 0.0)

        track_outputs[key] = {
            "track_id": info["track_id"],
            "frames": len(seq),
            "final_grade": final_grade,
            "label_changes": int(label_changes),
            "temporal_stability": float(stability),
            "score_map": score_map,
            "normalized": normalized,
            "confidence": float(confidence),
            "is_defect": bool(final_grade != "Grade-1"),
        }

        # decision_entries sẽ được dùng ở bước fusion cấp session.
        decision_entries.append({
            "grade": final_grade,
            "quality_score": confidence,
            "weight": max(0.05, float(len(seq)) * max(0.2, confidence)),
        })

    # Tổng hợp KPI theo toàn bộ track hợp lệ.
    total_tracks = len(track_outputs)
    defect_ratio = (defect_tracks / total_tracks) if total_tracks > 0 else 0.0
    temporal_stability = (sum(stability_values) / len(stability_values)) if stability_values else 0.0

    return {
        "total_tracks": total_tracks,
        "defect_tracks": defect_tracks,
        "defect_ratio": float(defect_ratio),
        "temporal_stability": float(temporal_stability),
        "tracks": track_outputs,
        "decision_entries": decision_entries,
    }

import sqlite3
import os
import cv2
import json
import csv
import shutil
import numpy as np
from datetime import datetime

class AppDatabase:
    """Module quản lý cơ sở dữ liệu SQLite cho hệ thống phân loại."""
    
    def __init__(self, db_dir):
        self.img_dir = os.path.join(db_dir, "history_images")
        if not os.path.exists(self.img_dir):
            os.makedirs(self.img_dir)
            
        self.db_path = os.path.join(db_dir, "database.db")
        self._init_db()

    def _init_db(self):
        """Khởi tạo bảng nếu chưa có."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Thêm diameter_mm REAL vào bảng
                conn.execute('''CREATE TABLE IF NOT EXISTS phan_loai_history
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              thoi_gian TEXT,
                              ket_qua TEXT,
                              diameter_mm REAL,
                              duong_dan_anh TEXT,
                              ty_le_yield TEXT)''')
                
                # Kiểm tra xem cột diameter_mm đã tồn tại chưa (đề phòng db cũ)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(phan_loai_history)")
                columns = [info[1] for info in cursor.fetchall()]
                if 'diameter_mm' not in columns:
                    conn.execute("ALTER TABLE phan_loai_history ADD COLUMN diameter_mm REAL DEFAULT 0")
                if 'nha_vuon' not in columns:
                    conn.execute("ALTER TABLE phan_loai_history ADD COLUMN nha_vuon TEXT DEFAULT ''")
                if 'ma_lo' not in columns:
                    conn.execute("ALTER TABLE phan_loai_history ADD COLUMN ma_lo TEXT DEFAULT ''")

                # Bảng lưu chi tiết 10 ảnh cho mỗi lần phân loại
                conn.execute('''CREATE TABLE IF NOT EXISTS phan_loai_session_10
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              history_id INTEGER,
                              frame_idx INTEGER,
                              thoi_gian TEXT,
                              trigger_source TEXT,
                              ket_qua TEXT,
                              ripeness_pct REAL,
                              diameter_mm REAL,
                              shape_label TEXT,
                              yolo_conf REAL,
                              detail_json TEXT,
                              duong_dan_anh TEXT,
                              FOREIGN KEY(history_id) REFERENCES phan_loai_history(id))''')

                # Đảm bảo cột detail_json tồn tại cho DB cũ
                cursor.execute("PRAGMA table_info(phan_loai_session_10)")
                s_columns = [info[1] for info in cursor.fetchall()]
                if 'detail_json' not in s_columns:
                    conn.execute("ALTER TABLE phan_loai_session_10 ADD COLUMN detail_json TEXT DEFAULT ''")
        except Exception as e:
            print(f"[DB] Lỗi khởi tạo DB: {e}")

    def save_record(self, grade, frame_to_save, diameter_mm=0, orchard_name="", lot_code=""):
        """Lưu bản ghi phân loại và hình ảnh với tên app_x.jpg tăng dần."""
        if grade in ("NO_APPLE", "UNKNOWN", "", None):
            return False, "Không lưu các trạng thái rác", None, None
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Lấy số thứ tự tiếp theo dựa trên ID hoặc số lượng bản ghi
                cursor.execute("SELECT COUNT(*) FROM phan_loai_history")
                next_id = cursor.fetchone()[0] + 1
                
                filename = f"app_{next_id}.jpg"
                filepath = os.path.join(self.img_dir, filename)
                
                # Lưu ảnh xuống thư mục
                if frame_to_save is not None:
                    cv2.imwrite(filepath, frame_to_save)
                
                # Lưu thông tin vào SQL
                t_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO phan_loai_history (thoi_gian, ket_qua, diameter_mm, duong_dan_anh, ty_le_yield, nha_vuon, ma_lo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (t_str, grade, diameter_mm, filepath, "", orchard_name, lot_code)
                )
                history_id = cursor.lastrowid
                
            return True, f"SQL Saved: [{grade}] -> {filename}", filepath, history_id
        except Exception as e:
            return False, f"SQL Error: {e}", None, None

    def save_session_10_records(self, history_id, session_records):
        """Lưu chi tiết 10 ảnh theo history_id để có thể truy xuất khi double-click lịch sử."""
        if not history_id or not session_records:
            return False, "Không có dữ liệu session để lưu"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM phan_loai_session_10 WHERE history_id=?", (history_id,))

                # Chuẩn hóa đúng 10 frame/1 trái để phục vụ xuất báo cáo theo thùng.
                source_records = sorted(
                    list(session_records),
                    key=lambda x: int(x.get("frame_idx", 0) or 0),
                )
                source_records = [r for r in source_records if int(r.get("frame_idx", 0) or 0) > 0]
                if not source_records:
                    return False, "Không có frame hợp lệ trong session"

                normalized_records = []
                for i in range(10):
                    if i < len(source_records):
                        base = dict(source_records[i])
                        padded = False
                    else:
                        base = dict(source_records[-1])
                        padded = True
                    base["frame_idx"] = i + 1
                    base["_is_padded"] = padded
                    normalized_records.append(base)

                base_main_img = os.path.join(self.img_dir, f"app_{history_id}.jpg")
                base_main_frame = cv2.imread(base_main_img) if os.path.isfile(base_main_img) else None
                fallback_frame = None

                for rec in normalized_records:
                    frame_idx = int(rec.get("frame_idx", 0))
                    if frame_idx <= 0:
                        continue

                    img_path = ""
                    preview = rec.get("preview_frame")
                    if preview is None:
                        preview = fallback_frame
                    if preview is None:
                        preview = base_main_frame

                    # Nếu vẫn không có ảnh, tạo ảnh placeholder để luôn đủ 10 tấm.
                    if preview is None:
                        preview = np.zeros((480, 640, 3), dtype=np.uint8)
                        preview[:] = (20, 20, 20)
                        cv2.putText(
                            preview,
                            f"NO FRAME {frame_idx}",
                            (180, 240),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 255, 255),
                            2,
                        )

                    if preview is not None:
                        img_name = f"app_{history_id}_f{frame_idx}.jpg"
                        img_path = os.path.join(self.img_dir, img_name)
                        cv2.imwrite(img_path, preview)
                        fallback_frame = preview

                        # Lưu thêm ảnh raw (chưa vẽ overlay) nếu có
                        raw_frame_val = rec.get("preview_frame_raw")
                        if raw_frame_val is not None:
                            raw_img_name = f"app_{history_id}_f{frame_idx}_raw.jpg"
                            cv2.imwrite(os.path.join(self.img_dir, raw_img_name), raw_frame_val)

                        # Lưu thêm ảnh mask phân đoạn (binary) nếu có
                        mask_frame_val = rec.get("preview_frame_mask")
                        if mask_frame_val is not None:
                            mask_img_name = f"app_{history_id}_f{frame_idx}_mask.png"
                            cv2.imwrite(os.path.join(self.img_dir, mask_img_name), mask_frame_val)

                    cur.execute(
                        """
                        INSERT INTO phan_loai_session_10
                        (history_id, frame_idx, thoi_gian, trigger_source, ket_qua,
                         ripeness_pct, diameter_mm, shape_label, yolo_conf, detail_json, duong_dan_anh)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            history_id,
                            frame_idx,
                            rec.get("timestamp", ""),
                            rec.get("trigger_source", ""),
                            rec.get("grade", ""),
                            float(rec.get("ripeness_pct", 0.0)),
                            float(rec.get("diameter_mm", 0.0)),
                            rec.get("shape", ""),
                            float(rec.get("yolo_conf", 0.0)),
                            json.dumps({
                                "red_ratio": rec.get("red_ratio", 0.0),
                                "yellow_ratio": rec.get("yellow_ratio", 0.0),
                                "green_ratio": rec.get("green_ratio", 0.0),
                                "ripeness_label": rec.get("ripeness_label", "-"),
                                "ripeness_grade": rec.get("ripeness_grade", "-"),
                                "pixel_to_mm_effective": rec.get("pixel_to_mm_effective", 0.0),
                                "z_distance_mm": rec.get("z_distance_mm", None),
                                "size_measure_mode": rec.get("size_measure_mode", ""),
                                "analysis_mode": rec.get("analysis_mode", ""),
                                "tc1_adaptive_hsv": rec.get("tc1_adaptive_hsv", False),
                                "tc1_temporal_smoothing": rec.get("tc1_temporal_smoothing", False),
                                "tc1_smoothing_window": rec.get("tc1_smoothing_window", 0),
                                "size_label": rec.get("size_label", "-"),
                                "size_grade": rec.get("size_grade", "-"),
                                "shape_label": rec.get("shape", "-"),
                                "shape_grade": rec.get("shape_grade", "-"),
                                "circularity": rec.get("circularity", 0.0),
                                "yolo_class": rec.get("yolo_class", "apple"),
                                "yolo_enabled": rec.get("yolo_enabled", False),
                                "yolo_detected": rec.get("yolo_detected", False),
                                "processing_time_ms": rec.get("processing_time_ms", 0.0),
                                "fps": rec.get("fps", 0.0),
                                "blur_status": rec.get("blur_status", "-"),
                                "blur_score": rec.get("blur_score", 0.0),
                                "track_id": rec.get("track_id", None),
                                "active_tracks": rec.get("active_tracks", 0),
                                "yolo_tracker_mode": rec.get("yolo_tracker_mode", "predict"),
                                "track_final_grade": rec.get("track_final_grade", ""),
                                "track_temporal_stability": rec.get("track_temporal_stability", 0.0),
                                "track_confidence": rec.get("track_confidence", 0.0),
                                "track_frames": rec.get("track_frames", 0),
                                "session_total_tracks": rec.get("session_total_tracks", 0),
                                "session_defect_tracks": rec.get("session_defect_tracks", 0),
                                "session_defect_ratio": rec.get("session_defect_ratio", 0.0),
                                "session_temporal_stability": rec.get("session_temporal_stability", 0.0),
                                "decision_method": rec.get("decision_method", "weighted_voting"),
                                "is_padded": bool(rec.get("_is_padded", False)),
                            }, ensure_ascii=False),
                            img_path,
                        )
                    )
            return True, "Đã lưu chi tiết 10 ảnh (chuẩn hóa đủ 10 tấm)"
        except Exception as e:
            return False, f"Lỗi lưu session 10 ảnh: {e}"

    def get_session_10_by_history_id(self, history_id):
        """Lấy chi tiết 10 ảnh theo bản ghi lịch sử."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT frame_idx, thoi_gian, trigger_source, ket_qua,
                              ripeness_pct, diameter_mm, shape_label, yolo_conf, detail_json, duong_dan_anh
                    FROM phan_loai_session_10
                    WHERE history_id=?
                    ORDER BY frame_idx ASC
                    """,
                    (history_id,)
                )
                rows = cur.fetchall()
                parsed = []
                for r in rows:
                    extra = {}
                    raw_json = r[8] or ""
                    if raw_json:
                        try:
                            extra = json.loads(raw_json)
                        except Exception:
                            extra = {}

                    item = {
                        "frame_idx": r[0],
                        "timestamp": r[1],
                        "trigger_source": r[2],
                        "grade": r[3],
                        "ripeness_pct": r[4],
                        "diameter_mm": r[5],
                        "shape": r[6],
                        "yolo_conf": r[7],
                        "image_path": r[9],
                    }
                    item.update(extra)
                    parsed.append(item)
                return parsed
        except Exception as e:
            print(f"[DB] Lỗi lấy session 10 ảnh: {e}")
            return []

    def get_stats(self):
        """Lấy số lượng đếm."""
        stats = {"Grade-1": 0, "Grade-2": 0, "Grade-3": 0, "TOTAL": 0}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                for grade in ["Grade-1", "Grade-2", "Grade-3"]:
                    cur.execute("SELECT COUNT(*) FROM phan_loai_history WHERE ket_qua=?", (grade,))
                    count = cur.fetchone()[0]
                    stats[grade] = count
                    stats["TOTAL"] += count
        except Exception as e:
            print(f"Error fetching stats: {e}")
        return stats

    def get_history(self, limit=1000):
        """Lấy toàn bộ lịch sử phân loại."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, thoi_gian, ket_qua, diameter_mm, duong_dan_anh, ty_le_yield, nha_vuon, ma_lo "
                    "FROM phan_loai_history ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
                return cur.fetchall()
        except Exception as e:
            print(f"[DB] Lỗi lấy lịch sử: {e}")
            return []

    def get_recent_records(self, limit=50):
        """Lấy danh sách các bản ghi gần nhất."""
        return self.get_history(limit)

    def clear_all(self):
        """Xóa toàn bộ lịch sử."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM phan_loai_history")
            return True, "Đã xóa toàn bộ lịch sử."
        except Exception as e:
            return False, f"Lỗi xóa CSDL: {e}"

    def export_history_dataset(self, export_base_dir, start_time=None, end_time=None, grades=None):
        """
        Xuất lịch sử SQL cực chi tiết + báo cáo theo từng thùng (10 quả/thùng).

        Cấu trúc xuất chính:
        - export_xxx/records.csv
        - export_xxx/frame_details.csv
        - export_xxx/summary_by_grade.csv
        - export_xxx/summary_by_bin.csv
        - export_xxx/summary_by_bin_kpi.csv
        - export_xxx/by_time/YYYY-MM-DD/Grade-X/<ảnh>
        - export_xxx/by_bin/Grade-X/thung_Gx_Tyyy/
            - bao_cao_thung.csv
            - bao_cao_thung_tom_tat.json
            - <ảnh và frame chi tiết>
        """
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_root = os.path.join(export_base_dir, f"export_{ts}")
            os.makedirs(export_root, exist_ok=True)

            where_clauses = []
            params = []

            if start_time:
                where_clauses.append("thoi_gian >= ?")
                params.append(start_time)
            if end_time:
                where_clauses.append("thoi_gian <= ?")
                params.append(end_time)
            if grades:
                grades = [str(g) for g in grades if str(g).strip()]
                if grades:
                    placeholders = ",".join(["?"] * len(grades))
                    where_clauses.append(f"ket_qua IN ({placeholders})")
                    params.extend(grades)

            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)

            query = (
                "SELECT id, thoi_gian, ket_qua, diameter_mm, duong_dan_anh, ty_le_yield, nha_vuon, ma_lo "
                f"FROM phan_loai_history {where_sql} ORDER BY thoi_gian ASC, id ASC"
            )

            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

                history_ids = [int(r[0]) for r in rows]
                session_by_history = {hid: [] for hid in history_ids}
                if history_ids:
                    placeholders = ",".join(["?"] * len(history_ids))
                    cur.execute(
                        f"""
                        SELECT history_id, frame_idx, thoi_gian, trigger_source, ket_qua,
                               ripeness_pct, diameter_mm, shape_label, yolo_conf, detail_json, duong_dan_anh
                        FROM phan_loai_session_10
                        WHERE history_id IN ({placeholders})
                        ORDER BY history_id ASC, frame_idx ASC
                        """,
                        tuple(history_ids),
                    )
                    for srow in cur.fetchall():
                        hid = int(srow[0])
                        detail_json = {}
                        raw_detail = srow[9] or ""
                        if raw_detail:
                            try:
                                detail_json = json.loads(raw_detail)
                            except Exception:
                                detail_json = {}

                        session_by_history.setdefault(hid, []).append(
                            {
                                "frame_idx": int(srow[1] or 0),
                                "timestamp": srow[2] or "",
                                "trigger_source": srow[3] or "",
                                "grade": srow[4] or "",
                                "ripeness_pct": float(srow[5] or 0.0),
                                "diameter_mm": float(srow[6] or 0.0),
                                "shape_label": srow[7] or "",
                                "yolo_conf": float(srow[8] or 0.0),
                                "detail": detail_json,
                                "image_path": srow[10] or "",
                            }
                        )

            records_csv = os.path.join(export_root, "records.csv")
            frame_details_csv = os.path.join(export_root, "frame_details.csv")
            summary_csv = os.path.join(export_root, "summary_by_grade.csv")
            bin_summary_csv = os.path.join(export_root, "summary_by_bin.csv")
            bin_kpi_csv = os.path.join(export_root, "summary_by_bin_kpi.csv")

            grade_stats = {}
            grade_counter = {}
            bin_stats = {}
            bin_report_map = {}
            exported_count = 0
            missing_images = 0
            exported_frame_images = 0
            missing_frame_images = 0
            exported_detail_json = 0
            fruits_full_10 = 0

            def _safe_slug(text, max_len=30):
                raw = str(text or "").strip()
                if not raw:
                    return ""
                return raw.replace(" ", "_").replace("/", "-").replace("\\", "-")[:max_len]

            def _detail_val(detail, key, default=""):
                if not isinstance(detail, dict):
                    return default
                return detail.get(key, default)

            def _grade_code(grade):
                g = str(grade or "").strip()
                if g == "Grade-1":
                    return "G1"
                if g == "Grade-2":
                    return "G2"
                if g == "Grade-3":
                    return "G3"
                return "GX"

            def _bin_code(grade, bin_no):
                if int(bin_no or 0) <= 0:
                    return "-"
                return f"{_grade_code(grade)}-T{int(bin_no):03d}"

            def _to_float(value, default=0.0):
                try:
                    return float(value)
                except Exception:
                    return default

            with open(records_csv, "w", newline="", encoding="utf-8-sig") as f_csv:
                writer = csv.writer(f_csv)
                writer.writerow([
                    "id",
                    "thoi_gian",
                    "ket_qua",
                    "ma_thung",
                    "thung_so",
                    "vi_tri_trong_thung",
                    "diameter_mm",
                    "nha_vuon",
                    "ma_lo",
                    "ty_le_yield",
                    "source_image",
                    "exported_image_by_time",
                    "exported_image_by_bin",
                    "frame_count",
                    "detail_json_path",
                ])

                with open(frame_details_csv, "w", newline="", encoding="utf-8-sig") as f_frame:
                    frame_writer = csv.writer(f_frame)
                    frame_writer.writerow([
                        "history_id",
                        "frame_idx",
                        "timestamp",
                        "trigger_source",
                        "ket_qua_frame",
                        "ket_qua_final",
                        "ma_thung",
                        "thung_so",
                        "vi_tri_trong_thung",
                        "red_ratio",
                        "yellow_ratio",
                        "green_ratio",
                        "ripeness_label",
                        "ripeness_grade",
                        "pixel_to_mm_effective",
                        "z_distance_mm",
                        "size_measure_mode",
                        "analysis_mode",
                        "tc1_adaptive_hsv",
                        "tc1_temporal_smoothing",
                        "tc1_smoothing_window",
                        "diameter_mm",
                        "size_label",
                        "size_grade",
                        "shape_label",
                        "shape_grade",
                        "circularity",
                        "yolo_enabled",
                        "yolo_detected",
                        "yolo_class",
                        "yolo_conf",
                        "track_id",
                        "active_tracks",
                        "yolo_tracker_mode",
                        "processing_time_ms",
                        "fps",
                        "blur_status",
                        "blur_score",
                        "track_final_grade",
                        "track_temporal_stability",
                        "track_confidence",
                        "track_frames",
                        "session_total_tracks",
                        "session_defect_tracks",
                        "session_defect_ratio",
                        "session_temporal_stability",
                        "decision_method",
                        "is_padded",
                        "detail_json_raw",
                        "source_frame_image",
                        "exported_frame_image",
                    ])

                    for row in rows:
                        rec_id, thoi_gian, ket_qua, diameter_mm, img_path, ty_le_yield, nha_vuon, ma_lo = row
                        rec_id = int(rec_id)
                        grade = str(ket_qua or "UNKNOWN").strip() or "UNKNOWN"

                        grade_counter[grade] = grade_counter.get(grade, 0) + 1
                        grade_idx = int(grade_counter[grade])
                        bin_no = ((grade_idx - 1) // 10) + 1
                        pos_in_bin = ((grade_idx - 1) % 10) + 1
                        bin_code = _bin_code(grade, bin_no)

                        bin_key = (grade, bin_no)
                        bstat = bin_stats.setdefault(bin_key, {"count": 0, "diameter_sum": 0.0})
                        bstat["count"] += 1

                        grade_stat = grade_stats.setdefault(grade, {"count": 0, "diameter_sum": 0.0})
                        grade_stat["count"] += 1
                        try:
                            d_mm = float(diameter_mm or 0.0)
                        except Exception:
                            d_mm = 0.0
                        grade_stat["diameter_sum"] += d_mm
                        bstat["diameter_sum"] += d_mm

                        date_bucket = "unknown-date"
                        time_bucket = "unknown-time"
                        if thoi_gian:
                            ts_text = str(thoi_gian)
                            if len(ts_text) >= 10:
                                date_bucket = ts_text[:10]
                            if len(ts_text) >= 19:
                                time_bucket = ts_text[11:19].replace(":", "-")

                        safe_orchard = _safe_slug(nha_vuon)
                        safe_lot = _safe_slug(ma_lo)
                        orchard_part = f"_{safe_orchard}" if safe_orchard else ""
                        lot_part = f"_{safe_lot}" if safe_lot else ""

                        by_time_dir = os.path.join(export_root, "by_time", date_bucket, grade)
                        os.makedirs(by_time_dir, exist_ok=True)
                        by_bin_dir = os.path.join(export_root, "by_bin", grade, f"thung_{bin_code.replace('-', '_')}")
                        os.makedirs(by_bin_dir, exist_ok=True)

                        bin_report = bin_report_map.setdefault(
                            bin_key,
                            {
                                "grade": grade,
                                "bin_no": bin_no,
                                "bin_code": bin_code,
                                "bin_dir": by_bin_dir,
                                "fruits": [],
                                "orchards": set(),
                                "lots": set(),
                                "first_time": "",
                                "last_time": "",
                                "total_frames": 0,
                                "total_padded_frames": 0,
                                "total_yolo_detected_frames": 0,
                                "total_defect_frames": 0,
                                "sum_diameter": 0.0,
                                "sum_ripeness": 0.0,
                            },
                        )

                        img_name = f"{rec_id:06d}_{time_bucket}{orchard_part}{lot_part}.jpg"
                        exported_img_time = os.path.join(by_time_dir, img_name)
                        exported_img_bin = os.path.join(by_bin_dir, f"{pos_in_bin:02d}_id_{img_name}")

                        exported_img_time_value = ""
                        exported_img_bin_value = ""
                        try:
                            if img_path and os.path.isfile(img_path):
                                shutil.copy2(img_path, exported_img_time)
                                shutil.copy2(img_path, exported_img_bin)
                                exported_img_time_value = exported_img_time
                                exported_img_bin_value = exported_img_bin
                                exported_count += 1
                            else:
                                missing_images += 1
                        except Exception:
                            missing_images += 1

                        detail_frames = session_by_history.get(rec_id, [])
                        detail_frames = sorted(detail_frames, key=lambda x: int(x.get("frame_idx", 0) or 0))

                        # Ép đủ đúng 10 frame cho mỗi trái khi export.
                        if detail_frames:
                            norm_frames = []
                            for i in range(10):
                                if i < len(detail_frames):
                                    fr = dict(detail_frames[i])
                                    is_padded = bool(fr.get("detail", {}).get("is_padded", False))
                                else:
                                    fr = dict(detail_frames[-1])
                                    is_padded = True
                                fr["frame_idx"] = i + 1
                                detail_map = fr.get("detail", {})
                                if not isinstance(detail_map, dict):
                                    detail_map = {}
                                detail_map["is_padded"] = is_padded
                                fr["detail"] = detail_map
                                norm_frames.append(fr)
                            detail_frames = norm_frames
                        else:
                            # Record cũ không có session_10: tạo đủ 10 frame từ ảnh chính.
                            synth = []
                            for i in range(10):
                                synth.append(
                                    {
                                        "frame_idx": i + 1,
                                        "timestamp": thoi_gian or "",
                                        "trigger_source": "legacy_synth",
                                        "grade": grade,
                                        "ripeness_pct": 0.0,
                                        "diameter_mm": d_mm,
                                        "shape_label": "",
                                        "yolo_conf": 0.0,
                                        "detail": {"is_padded": True},
                                        "image_path": img_path or "",
                                    }
                                )
                            detail_frames = synth
                        frames_dir = os.path.join(by_bin_dir, f"{pos_in_bin:02d}_id_{rec_id:06d}_frames")
                        os.makedirs(frames_dir, exist_ok=True)

                        detail_json_export_path = ""
                        detail_json_payload = {
                            "history_id": rec_id,
                            "thoi_gian": thoi_gian,
                            "ket_qua": grade,
                            "ma_thung": bin_code,
                            "thung_so": bin_no,
                            "vi_tri_trong_thung": pos_in_bin,
                            "diameter_mm": d_mm,
                            "nha_vuon": nha_vuon,
                            "ma_lo": ma_lo,
                            "ty_le_yield": ty_le_yield,
                            "frames": [],
                        }

                        fruit_frame_count = 0
                        fruit_padded_frames = 0
                        fruit_yolo_detected_frames = 0
                        fruit_defect_frames = 0
                        fruit_ripeness_sum = 0.0

                        for fr in detail_frames:
                            detail = fr.get("detail", {})
                            frame_idx = int(fr.get("frame_idx", 0))
                            src_frame_img = fr.get("image_path", "")
                            exported_frame_img = ""
                            if src_frame_img and os.path.isfile(src_frame_img):
                                frame_img_name = f"frame_{frame_idx:02d}.jpg"
                                exported_frame_img = os.path.join(frames_dir, frame_img_name)
                                try:
                                    shutil.copy2(src_frame_img, exported_frame_img)
                                    exported_frame_images += 1
                                except Exception:
                                    exported_frame_img = ""
                                    missing_frame_images += 1
                            elif detail_frames:
                                # Fallback ảnh frame bằng ảnh chính nếu có.
                                if img_path and os.path.isfile(img_path):
                                    frame_img_name = f"frame_{frame_idx:02d}.jpg"
                                    exported_frame_img = os.path.join(frames_dir, frame_img_name)
                                    try:
                                        shutil.copy2(img_path, exported_frame_img)
                                        exported_frame_images += 1
                                    except Exception:
                                        exported_frame_img = ""
                                        missing_frame_images += 1
                                else:
                                    # Tạo placeholder để luôn đủ đúng 10 file frame.
                                    frame_img_name = f"frame_{frame_idx:02d}.jpg"
                                    exported_frame_img = os.path.join(frames_dir, frame_img_name)
                                    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
                                    placeholder[:] = (20, 20, 20)
                                    cv2.putText(
                                        placeholder,
                                        f"NO FRAME {frame_idx}",
                                        (180, 240),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        1.0,
                                        (0, 255, 255),
                                        2,
                                    )
                                    try:
                                        cv2.imwrite(exported_frame_img, placeholder)
                                        exported_frame_images += 1
                                    except Exception:
                                        exported_frame_img = ""
                                        missing_frame_images += 1

                            frame_payload = {
                                "frame_idx": frame_idx,
                                "timestamp": fr.get("timestamp", ""),
                                "trigger_source": fr.get("trigger_source", ""),
                                "ket_qua_frame": fr.get("grade", ""),
                                "red_ratio": _detail_val(detail, "red_ratio", fr.get("ripeness_pct", 0.0)),
                                "yellow_ratio": _detail_val(detail, "yellow_ratio", 0.0),
                                "green_ratio": _detail_val(detail, "green_ratio", 0.0),
                                "ripeness_label": _detail_val(detail, "ripeness_label", ""),
                                "ripeness_grade": _detail_val(detail, "ripeness_grade", ""),
                                "pixel_to_mm_effective": _detail_val(detail, "pixel_to_mm_effective", 0.0),
                                "z_distance_mm": _detail_val(detail, "z_distance_mm", None),
                                "size_measure_mode": _detail_val(detail, "size_measure_mode", ""),
                                "analysis_mode": _detail_val(detail, "analysis_mode", ""),
                                "tc1_adaptive_hsv": _detail_val(detail, "tc1_adaptive_hsv", False),
                                "tc1_temporal_smoothing": _detail_val(detail, "tc1_temporal_smoothing", False),
                                "tc1_smoothing_window": _detail_val(detail, "tc1_smoothing_window", 0),
                                "diameter_mm": fr.get("diameter_mm", 0.0),
                                "size_label": _detail_val(detail, "size_label", ""),
                                "size_grade": _detail_val(detail, "size_grade", ""),
                                "shape_label": _detail_val(detail, "shape_label", fr.get("shape_label", "")),
                                "shape_grade": _detail_val(detail, "shape_grade", ""),
                                "circularity": _detail_val(detail, "circularity", 0.0),
                                "yolo_enabled": _detail_val(detail, "yolo_enabled", False),
                                "yolo_detected": _detail_val(detail, "yolo_detected", False),
                                "yolo_class": _detail_val(detail, "yolo_class", "apple"),
                                "yolo_conf": fr.get("yolo_conf", 0.0),
                                "track_id": _detail_val(detail, "track_id", ""),
                                "active_tracks": _detail_val(detail, "active_tracks", 0),
                                "yolo_tracker_mode": _detail_val(detail, "yolo_tracker_mode", "predict"),
                                "processing_time_ms": _detail_val(detail, "processing_time_ms", 0.0),
                                "fps": _detail_val(detail, "fps", 0.0),
                                "blur_status": _detail_val(detail, "blur_status", ""),
                                "blur_score": _detail_val(detail, "blur_score", 0.0),
                                "track_final_grade": _detail_val(detail, "track_final_grade", ""),
                                "track_temporal_stability": _detail_val(detail, "track_temporal_stability", 0.0),
                                "track_confidence": _detail_val(detail, "track_confidence", 0.0),
                                "track_frames": _detail_val(detail, "track_frames", 0),
                                "session_total_tracks": _detail_val(detail, "session_total_tracks", 0),
                                "session_defect_tracks": _detail_val(detail, "session_defect_tracks", 0),
                                "session_defect_ratio": _detail_val(detail, "session_defect_ratio", 0.0),
                                "session_temporal_stability": _detail_val(detail, "session_temporal_stability", 0.0),
                                "decision_method": _detail_val(detail, "decision_method", "weighted_voting"),
                                "is_padded": bool(_detail_val(detail, "is_padded", False)),
                                "detail_json_raw": json.dumps(detail, ensure_ascii=False),
                                "source_frame_image": src_frame_img,
                                "exported_frame_image": exported_frame_img,
                            }
                            detail_json_payload["frames"].append(frame_payload)

                            fruit_frame_count += 1
                            if bool(frame_payload["is_padded"]):
                                fruit_padded_frames += 1
                            if bool(frame_payload["yolo_detected"]):
                                fruit_yolo_detected_frames += 1
                            if str(frame_payload["ket_qua_frame"]).strip() == "Grade-3":
                                fruit_defect_frames += 1
                            fruit_ripeness_sum += _to_float(frame_payload["red_ratio"], 0.0)

                            frame_writer.writerow([
                                rec_id,
                                frame_payload["frame_idx"],
                                frame_payload["timestamp"],
                                frame_payload["trigger_source"],
                                frame_payload["ket_qua_frame"],
                                grade,
                                bin_code,
                                bin_no,
                                pos_in_bin,
                                frame_payload["red_ratio"],
                                frame_payload["yellow_ratio"],
                                frame_payload["green_ratio"],
                                frame_payload["ripeness_label"],
                                frame_payload["ripeness_grade"],
                                frame_payload["pixel_to_mm_effective"],
                                frame_payload["z_distance_mm"],
                                frame_payload["size_measure_mode"],
                                frame_payload["analysis_mode"],
                                frame_payload["tc1_adaptive_hsv"],
                                frame_payload["tc1_temporal_smoothing"],
                                frame_payload["tc1_smoothing_window"],
                                frame_payload["diameter_mm"],
                                frame_payload["size_label"],
                                frame_payload["size_grade"],
                                frame_payload["shape_label"],
                                frame_payload["shape_grade"],
                                frame_payload["circularity"],
                                frame_payload["yolo_enabled"],
                                frame_payload["yolo_detected"],
                                frame_payload["yolo_class"],
                                frame_payload["yolo_conf"],
                                frame_payload["track_id"],
                                frame_payload["active_tracks"],
                                frame_payload["yolo_tracker_mode"],
                                frame_payload["processing_time_ms"],
                                frame_payload["fps"],
                                frame_payload["blur_status"],
                                frame_payload["blur_score"],
                                frame_payload["track_final_grade"],
                                frame_payload["track_temporal_stability"],
                                frame_payload["track_confidence"],
                                frame_payload["track_frames"],
                                frame_payload["session_total_tracks"],
                                frame_payload["session_defect_tracks"],
                                frame_payload["session_defect_ratio"],
                                frame_payload["session_temporal_stability"],
                                frame_payload["decision_method"],
                                frame_payload["is_padded"],
                                frame_payload["detail_json_raw"],
                                frame_payload["source_frame_image"],
                                frame_payload["exported_frame_image"],
                            ])

                        try:
                            detail_json_export_path = os.path.join(by_bin_dir, f"{pos_in_bin:02d}_id_{rec_id:06d}_detail.json")
                            with open(detail_json_export_path, "w", encoding="utf-8") as f_json:
                                json.dump(detail_json_payload, f_json, ensure_ascii=False, indent=2)
                            exported_detail_json += 1
                        except Exception:
                            detail_json_export_path = ""

                        writer.writerow([
                            rec_id,
                            thoi_gian,
                            grade,
                            bin_code,
                            bin_no,
                            pos_in_bin,
                            diameter_mm,
                            nha_vuon,
                            ma_lo,
                            ty_le_yield,
                            img_path,
                            exported_img_time_value,
                            exported_img_bin_value,
                            len(detail_frames),
                            detail_json_export_path,
                        ])

                        fruit_avg_ripeness = (fruit_ripeness_sum / fruit_frame_count) if fruit_frame_count > 0 else 0.0
                        bin_report["fruits"].append(
                            {
                                "history_id": rec_id,
                                "thoi_gian": thoi_gian,
                                "vi_tri_trong_thung": pos_in_bin,
                                "ket_qua": grade,
                                "diameter_mm": d_mm,
                                "frame_count": fruit_frame_count,
                                "padded_frames": fruit_padded_frames,
                                "yolo_detected_frames": fruit_yolo_detected_frames,
                                "defect_frames": fruit_defect_frames,
                                "avg_ripeness_red_ratio": fruit_avg_ripeness,
                                "nha_vuon": nha_vuon or "",
                                "ma_lo": ma_lo or "",
                                "image_by_bin": exported_img_bin_value,
                                "detail_json_path": detail_json_export_path,
                            }
                        )
                        if nha_vuon:
                            bin_report["orchards"].add(str(nha_vuon))
                        if ma_lo:
                            bin_report["lots"].add(str(ma_lo))
                        if thoi_gian:
                            ts = str(thoi_gian)
                            if not bin_report["first_time"] or ts < bin_report["first_time"]:
                                bin_report["first_time"] = ts
                            if not bin_report["last_time"] or ts > bin_report["last_time"]:
                                bin_report["last_time"] = ts
                        bin_report["total_frames"] += fruit_frame_count
                        bin_report["total_padded_frames"] += fruit_padded_frames
                        bin_report["total_yolo_detected_frames"] += fruit_yolo_detected_frames
                        bin_report["total_defect_frames"] += fruit_defect_frames
                        bin_report["sum_diameter"] += d_mm
                        bin_report["sum_ripeness"] += fruit_avg_ripeness

                        if len(detail_frames) == 10:
                            fruits_full_10 += 1

            with open(summary_csv, "w", newline="", encoding="utf-8-sig") as f_sum:
                writer = csv.writer(f_sum)
                writer.writerow(["ket_qua", "so_luong", "so_thung_10", "so_qua_thung_cuoi", "duong_kinh_trung_binh_mm"])
                for grade, info in sorted(grade_stats.items(), key=lambda x: x[0]):
                    cnt = int(info.get("count", 0))
                    avg_mm = (float(info.get("diameter_sum", 0.0)) / cnt) if cnt > 0 else 0.0
                    bins = (cnt + 9) // 10
                    last_bin_count = 0 if cnt == 0 else (cnt % 10 if (cnt % 10) != 0 else 10)
                    writer.writerow([grade, cnt, bins, last_bin_count, round(avg_mm, 2)])

            with open(bin_summary_csv, "w", newline="", encoding="utf-8-sig") as f_bin:
                writer = csv.writer(f_bin)
                writer.writerow(["ket_qua", "ma_thung", "thung_so", "so_qua", "duong_kinh_trung_binh_mm"])
                for (grade, bin_no), info in sorted(bin_stats.items(), key=lambda x: (x[0][0], x[0][1])):
                    cnt = int(info.get("count", 0))
                    avg_mm = (float(info.get("diameter_sum", 0.0)) / cnt) if cnt > 0 else 0.0
                    writer.writerow([grade, _bin_code(grade, bin_no), bin_no, cnt, round(avg_mm, 2)])

            with open(bin_kpi_csv, "w", newline="", encoding="utf-8-sig") as f_bin_kpi:
                writer = csv.writer(f_bin_kpi)
                writer.writerow([
                    "ket_qua",
                    "ma_thung",
                    "thung_so",
                    "so_qua",
                    "day_thung_10_qua",
                    "thoi_gian_bat_dau",
                    "thoi_gian_ket_thuc",
                    "nha_vuon",
                    "ma_lo",
                    "duong_kinh_tb_mm",
                    "do_chin_tb_red_ratio",
                    "tong_so_frame",
                    "ty_le_frame_yolo_detected",
                    "ty_le_frame_pad",
                    "ty_le_frame_loi_grade3",
                    "muc_do_day_du_du_lieu",
                ])

                for _, info in sorted(bin_report_map.items(), key=lambda x: (x[0][0], x[0][1])):
                    fruit_count = len(info["fruits"])
                    total_frames = int(info["total_frames"] or 0)
                    yolo_rate = (float(info["total_yolo_detected_frames"]) / total_frames) if total_frames > 0 else 0.0
                    padded_rate = (float(info["total_padded_frames"]) / total_frames) if total_frames > 0 else 0.0
                    defect_rate = (float(info["total_defect_frames"]) / total_frames) if total_frames > 0 else 0.0
                    avg_diameter = (float(info["sum_diameter"]) / fruit_count) if fruit_count > 0 else 0.0
                    avg_ripeness = (float(info["sum_ripeness"]) / fruit_count) if fruit_count > 0 else 0.0
                    completeness = (1.0 - padded_rate)

                    writer.writerow([
                        info["grade"],
                        info["bin_code"],
                        info["bin_no"],
                        fruit_count,
                        "YES" if fruit_count == 10 else "NO",
                        info["first_time"],
                        info["last_time"],
                        " | ".join(sorted(info["orchards"])),
                        " | ".join(sorted(info["lots"])),
                        round(avg_diameter, 2),
                        round(avg_ripeness, 4),
                        total_frames,
                        round(yolo_rate, 4),
                        round(padded_rate, 4),
                        round(defect_rate, 4),
                        round(completeness, 4),
                    ])

                    bin_manifest_csv = os.path.join(info["bin_dir"], "bao_cao_thung.csv")
                    with open(bin_manifest_csv, "w", newline="", encoding="utf-8-sig") as f_bin_detail:
                        b_writer = csv.writer(f_bin_detail)
                        b_writer.writerow([
                            "vi_tri_trong_thung",
                            "history_id",
                            "thoi_gian",
                            "ket_qua",
                            "diameter_mm",
                            "frame_count",
                            "padded_frames",
                            "yolo_detected_frames",
                            "defect_frames",
                            "avg_ripeness_red_ratio",
                            "nha_vuon",
                            "ma_lo",
                            "image_by_bin",
                            "detail_json_path",
                        ])
                        for fruit in sorted(info["fruits"], key=lambda x: int(x["vi_tri_trong_thung"])):
                            b_writer.writerow([
                                fruit["vi_tri_trong_thung"],
                                fruit["history_id"],
                                fruit["thoi_gian"],
                                fruit["ket_qua"],
                                round(_to_float(fruit["diameter_mm"], 0.0), 2),
                                fruit["frame_count"],
                                fruit["padded_frames"],
                                fruit["yolo_detected_frames"],
                                fruit["defect_frames"],
                                round(_to_float(fruit["avg_ripeness_red_ratio"], 0.0), 4),
                                fruit["nha_vuon"],
                                fruit["ma_lo"],
                                fruit["image_by_bin"],
                                fruit["detail_json_path"],
                            ])

                    bin_summary_json = os.path.join(info["bin_dir"], "bao_cao_thung_tom_tat.json")
                    try:
                        with open(bin_summary_json, "w", encoding="utf-8") as f_bin_json:
                            json.dump(
                                {
                                    "metadata": {
                                        "ma_thung": info["bin_code"],
                                        "ket_qua": info["grade"],
                                        "thung_so": info["bin_no"],
                                        "thoi_gian_bat_dau": info["first_time"],
                                        "thoi_gian_ket_thuc": info["last_time"],
                                        "nha_vuon": sorted(info["orchards"]),
                                        "ma_lo": sorted(info["lots"]),
                                    },
                                    "kpi": {
                                        "so_qua": fruit_count,
                                        "day_thung_10_qua": bool(fruit_count == 10),
                                        "duong_kinh_tb_mm": round(avg_diameter, 2),
                                        "do_chin_tb_red_ratio": round(avg_ripeness, 4),
                                        "tong_so_frame": total_frames,
                                        "ty_le_frame_yolo_detected": round(yolo_rate, 4),
                                        "ty_le_frame_pad": round(padded_rate, 4),
                                        "ty_le_frame_loi_grade3": round(defect_rate, 4),
                                        "muc_do_day_du_du_lieu": round(completeness, 4),
                                    },
                                    "traceability": {
                                        "who": {
                                            "nha_vuon": sorted(info["orchards"]),
                                        },
                                        "what": {
                                            "doi_tuong": "apple_bin",
                                            "ket_qua": info["grade"],
                                            "ma_thung": info["bin_code"],
                                        },
                                        "when": {
                                            "bat_dau": info["first_time"],
                                            "ket_thuc": info["last_time"],
                                        },
                                        "where": {
                                            "ma_lo": sorted(info["lots"]),
                                        },
                                        "why": {
                                            "muc_dich": "bao_cao_phan_loai_theo_thung_10_qua",
                                            "decision_basis": "tong_hop_frame_details_va_ket_qua_cuoi",
                                        },
                                    },
                                },
                                f_bin_json,
                                ensure_ascii=False,
                                indent=2,
                            )
                    except Exception:
                        pass

            return True, {
                "export_root": export_root,
                "records_csv": records_csv,
                "frame_details_csv": frame_details_csv,
                "summary_csv": summary_csv,
                "bin_summary_csv": bin_summary_csv,
                "bin_kpi_csv": bin_kpi_csv,
                "row_count": len(rows),
                "image_exported": exported_count,
                "image_missing": missing_images,
                "frame_image_exported": exported_frame_images,
                "frame_image_missing": missing_frame_images,
                "detail_json_exported": exported_detail_json,
                "bin_count_total": len(bin_stats),
                "fruits_full_10": fruits_full_10,
            }
        except Exception as e:
            return False, str(e)

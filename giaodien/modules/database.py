import sqlite3
import os
import cv2
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
        except Exception as e:
            print(f"[DB] Lỗi khởi tạo DB: {e}")

    def save_record(self, grade, frame_to_save, diameter_mm=0):
        """Lưu bản ghi phân loại và hình ảnh với tên app_x.jpg tăng dần."""
        if grade in ("NO_APPLE", "UNKNOWN", "", None):
            return False, "Không lưu các trạng thái rác", None
            
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
                conn.execute("INSERT INTO phan_loai_history (thoi_gian, ket_qua, diameter_mm, duong_dan_anh, ty_le_yield) VALUES (?, ?, ?, ?, ?)",
                          (t_str, grade, diameter_mm, filepath, ""))
                
            return True, f"SQL Saved: [{grade}] -> {filename}", filepath
        except Exception as e:
            return False, f"SQL Error: {e}", None

    def get_stats(self):
        """Lấy số lượng đếm."""
        stats = {"GOOD": 0, "MEDIUM": 0, "BAD": 0, "TOTAL": 0}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                for grade in ["GOOD", "MEDIUM", "BAD"]:
                    cur.execute("SELECT COUNT(*) FROM phan_loai_history WHERE ket_qua=?", (grade,))
                    count = cur.fetchone()[0]
                    stats[grade] = count
                    stats["TOTAL"] += count
        except Exception as e:
            print(f"Error fetching stats: {e}")
        return stats

    def get_history(self, limit=1000):
        """Lấy toàn bộ lịch sử phân loại cho Dashboard."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, thoi_gian, ket_qua, diameter_mm, duong_dan_anh, ty_le_yield FROM phan_loai_history ORDER BY id DESC LIMIT ?", (limit,))
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

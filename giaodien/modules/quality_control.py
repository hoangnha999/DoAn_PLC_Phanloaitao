"""
Module Quality Control - Machine Vision Industrial Standard
Quản lý Ground Truth Labeling và tính toán các chỉ số Accuracy Metrics.

Tính năng:
- Ground Truth Labeling: Operator xác nhận kết quả phân loại thực tế
- Confusion Matrix: Ma trận nhầm lẫn giữa predicted vs actual
- Accuracy Metrics: Precision, Recall, F1-Score, Overall Accuracy
- Repeatability Test: Kiểm tra độ lặp lại khi phân loại cùng 1 quả nhiều lần
"""

import sqlite3
import numpy as np
from collections import defaultdict


class QualityController:
    """Controller để quản lý chất lượng phân loại theo chuẩn công nghiệp."""
    
    def __init__(self, db_path):
        """
        Khởi tạo Quality Controller.
        
        Args:
            db_path: Đường dẫn đến database SQLite
        """
        self.db_path = db_path
        self._ensure_ground_truth_column()
        print("[QUALITY] ✅ Quality Control Module initialized (Ground Truth + Metrics)")
    
    def _ensure_ground_truth_column(self):
        """Đảm bảo cột ground_truth tồn tại trong database."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Kiểm tra xem cột ground_truth đã tồn tại chưa
            c.execute("PRAGMA table_info(phan_loai_history)")
            columns = [col[1] for col in c.fetchall()]
            
            if 'ground_truth' not in columns:
                c.execute("ALTER TABLE phan_loai_history ADD COLUMN ground_truth TEXT DEFAULT NULL")
                conn.commit()
                print("[QUALITY] ✅ Đã thêm cột 'ground_truth' vào database")
            
            conn.close()
        except Exception as e:
            print(f"[QUALITY] ⚠️ Lỗi khi kiểm tra database: {e}")
    
    def set_ground_truth(self, record_id, actual_grade):
        """
        Cập nhật Ground Truth (kết quả thực tế) cho 1 bản ghi.
        
        Args:
            record_id: ID của bản ghi trong database
            actual_grade: Kết quả thực tế (Grade-1, Grade-2, Grade-3)
        
        Returns:
            bool: True nếu thành công
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("UPDATE phan_loai_history SET ground_truth = ? WHERE id = ?",
                     (actual_grade, record_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[QUALITY] ❌ Lỗi set ground truth: {e}")
            return False
    
    def get_confusion_matrix(self):
        """
        Tính toán Confusion Matrix từ dữ liệu đã có Ground Truth.
        
        Returns:
            dict: {
                'matrix': [[TP_G1, FP_G2, FP_G3], ...],  # 3x3 matrix
                'labels': ['Grade-1', 'Grade-2', 'Grade-3'],
                'total_labeled': số lượng bản ghi đã được gán Ground Truth
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Lấy tất cả bản ghi đã có ground_truth
            c.execute("""
                SELECT ket_qua, ground_truth 
                FROM phan_loai_history 
                WHERE ground_truth IS NOT NULL
            """)
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            # Tạo Confusion Matrix
            labels = ['Grade-1', 'Grade-2', 'Grade-3']
            matrix = np.zeros((3, 3), dtype=int)
            
            for predicted, actual in rows:
                pred_idx = labels.index(predicted) if predicted in labels else -1
                actual_idx = labels.index(actual) if actual in labels else -1
                
                if pred_idx >= 0 and actual_idx >= 0:
                    matrix[actual_idx][pred_idx] += 1  # Row = Actual, Col = Predicted
            
            return {
                'matrix': matrix.tolist(),
                'labels': labels,
                'total_labeled': len(rows)
            }
        except Exception as e:
            print(f"[QUALITY] ❌ Lỗi tính Confusion Matrix: {e}")
            return None
    
    def calculate_metrics(self):
        """
        Tính toán Precision, Recall, F1-Score cho từng grade.
        
        Returns:
            dict: {
                'Grade-1': {'precision': 0.95, 'recall': 0.92, 'f1_score': 0.93},
                'Grade-2': {...},
                'Grade-3': {...},
                'overall_accuracy': 0.94,
                'total_samples': 150
            }
        """
        cm_data = self.get_confusion_matrix()
        if not cm_data:
            return None
        
        matrix = np.array(cm_data['matrix'])
        labels = cm_data['labels']
        total = cm_data['total_labeled']
        
        metrics = {}
        
        # Tính cho từng grade
        for i, grade in enumerate(labels):
            TP = matrix[i][i]  # True Positive
            FP = matrix[:, i].sum() - TP  # False Positive (cột i, trừ TP)
            FN = matrix[i, :].sum() - TP  # False Negative (hàng i, trừ TP)
            
            precision = TP / (TP + FP) if (TP + FP) > 0 else 0
            recall = TP / (TP + FN) if (TP + FN) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            metrics[grade] = {
                'precision': round(precision, 4),
                'recall': round(recall, 4),
                'f1_score': round(f1_score, 4),
                'true_positive': int(TP),
                'false_positive': int(FP),
                'false_negative': int(FN)
            }
        
        # Overall Accuracy
        correct = np.trace(matrix)  # Tổng các phần tử trên đường chéo
        overall_accuracy = correct / total if total > 0 else 0
        
        metrics['overall_accuracy'] = round(overall_accuracy, 4)
        metrics['total_samples'] = total
        
        return metrics
    
    def get_unlabeled_records(self, limit=50):
        """
        Lấy danh sách các bản ghi chưa được gán Ground Truth.
        
        Args:
            limit: Số lượng bản ghi tối đa
        
        Returns:
            list: [(id, thoi_gian, ket_qua, duong_dan_anh), ...]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                SELECT id, thoi_gian, ket_qua, duong_dan_anh
                FROM phan_loai_history
                WHERE ground_truth IS NULL
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = c.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"[QUALITY] ❌ Lỗi lấy unlabeled records: {e}")
            return []
    
    def get_metrics_summary_text(self):
        """
        Tạo báo cáo văn bản tóm tắt các metrics.
        
        Returns:
            str: Báo cáo dạng text
        """
        metrics = self.calculate_metrics()
        if not metrics:
            return "Chưa có dữ liệu Ground Truth để tính toán metrics."
        
        lines = []
        lines.append("═" * 60)
        lines.append("  QUALITY CONTROL REPORT - MACHINE VISION METRICS")
        lines.append("═" * 60)
        lines.append(f"Total Samples: {metrics['total_samples']}")
        lines.append(f"Overall Accuracy: {metrics['overall_accuracy']*100:.2f}%")
        lines.append("")
        lines.append("─" * 60)
        lines.append(f"{'Grade':<12} {'Precision':<12} {'Recall':<12} {'F1-Score':<12}")
        lines.append("─" * 60)
        
        for grade in ['Grade-1', 'Grade-2', 'Grade-3']:
            m = metrics[grade]
            lines.append(f"{grade:<12} {m['precision']:<12.4f} {m['recall']:<12.4f} {m['f1_score']:<12.4f}")
        
        lines.append("═" * 60)
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Test module
    qc = QualityController("fruit_grading.db")
    print(qc.get_metrics_summary_text())

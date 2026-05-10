import matplotlib.pyplot as plt
import numpy as np
import cv2
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk

class DataVisualizer:
    """
    Module hỗ trợ vẽ các biểu đồ phân tích cho hệ thống phân loại táo.
    Sử dụng Matplotlib để tạo biểu đồ và tích hợp vào Tkinter.
    """
    
    @staticmethod
    def plot_color_histogram(frame, mask=None):
        """
        Vẽ biểu đồ Histogram của các kênh màu (R, G, B).
        Nếu có mask, chỉ tính toán histogram trong vùng quả táo.
        """
        plt.figure(figsize=(5, 4))
        colors = ('b', 'g', 'r')
        for i, col in enumerate(colors):
            hist = cv2.calcHist([frame], [i], mask, [256], [0, 256])
            plt.plot(hist, color=col)
            plt.xlim([0, 256])
        
        plt.title('Color Histogram')
        plt.xlabel('Pixel Value')
        plt.ylabel('Frequency')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Lưu ra ảnh tạm để hiển thị hoặc trả về figure
        return plt.gcf()

    @staticmethod
    def show_stats_dashboard(history_data):
        """
        Hiển thị cửa sổ Dashboard thống kê từ dữ liệu lịch sử.
        history_data: list các dict hoặc kết quả từ database.
        """
        if not history_data:
            print("[VISUALIZER] Không có dữ liệu để thống kê.")
            return

        # 1. Chuẩn bị dữ liệu
        grades = [row.get('grade', 'UNKNOWN') for row in history_data]
        diameters = [row.get('diameter_mm', 0) for row in history_data]
        
        unique_grades, counts = np.unique(grades, return_counts=True)
        
        # 2. Tạo giao diện biểu đồ
        root = tk.Toplevel()
        root.title("DASHBOARD THỐNG KÊ PHÂN LOẠI")
        root.geometry("1000x600")
        root.configure(bg="#F1F5F9")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # Biểu đồ Tròn: Tỷ lệ các hạng
        colors_pie = {'GOOD': '#10B981', 'MEDIUM': '#F59E0B', 'BAD': '#EF4444', 'UNKNOWN': '#64748B'}
        current_colors = [colors_pie.get(g, '#64748B') for g in unique_grades]
        
        ax1.pie(counts, labels=unique_grades, autopct='%1.1f%%', startangle=140, colors=current_colors)
        ax1.set_title("Tỷ lệ phân hạng Táo")

        # Biểu đồ Cột: Phân phối kích thước
        ax2.hist(diameters, bins=15, color='#3B82F6', edgecolor='white')
        ax2.set_title("Phân phối kích thước (mm)")
        ax2.set_xlabel("Đường kính")
        ax2.set_ylabel("Số lượng")

        plt.tight_layout()

        # Nhúng vào Tkinter
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        btn_close = tk.Button(root, text="Đóng Dashboard", command=root.destroy, 
                              bg="#EF4444", fg="white", font=("Arial", 10, "bold"), pady=10)
        btn_close.pack(fill="x")

    @staticmethod
    def create_accuracy_report(predicted_grades, actual_grades):
        """
        Tạo Confusion Matrix để đánh giá độ chính xác.
        """
        from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
        
        cm = confusion_matrix(actual_grades, predicted_grades, labels=["GOOD", "MEDIUM", "BAD"])
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["GOOD", "MEDIUM", "BAD"])
        
        fig, ax = plt.subplots(figsize=(6, 5))
        disp.plot(cmap=plt.cm.Blues, ax=ax)
        ax.set_title("Ma trận nhầm lẫn (Đánh giá độ chính xác)")
        
        return fig

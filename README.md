# Hệ Thống Phân Loại Hạng Chất Lượng Trái Cây (🍎 Apple Grading System)

Dự án sử dụng Python (Tkinter) để tạo giao diện giám sát và điều khiển hệ thống phân loại trái cây, kết nối với PLC Siemens S7-1200.

## 🌟 Tính năng chính (Features)
*   **Giao diện chuyên nghiệp**: Hiển thị thông tin đồ án, khoa và thành viên.
*   **Camera Stream**: Tự động bật camera khi chạy, hiển thị song song ảnh màu và ảnh xám (Grayscale).
*   **Thống kê phân loại**: Theo dõi số lượng 3 hạng (Good, Medium, Bad) thời gian thực.
*   **Điều khiển PLC S7-1200**: Hỗ trợ kết nối qua Snap7, nút START/STOP và đọc dữ liệu từ Merker.

---

## 🛠 Yêu cầu hệ thống (Prerequisites)
1.  **Python 3.10+**
2.  **Thư viện cần thiết**:
    *   `Pillow` (Xử lý ảnh hiển thị trên GUI)
    *   `opencv-python` (Xử lý stream camera)
    *   `python-snap7` (Giao tiếp với PLC Siemens)

---

## 🚀 Hướng dẫn cài đặt và chạy (Installation & Running)

### Bước 1: Tải mã nguồn
Tải dự án về máy bằng cách tải file `.zip` hoặc dùng lệnh:
```bash
git clone https://github.com/hoangnha999/DoAn_PLC_Phanloaitao.git
cd DoAn_PLC_Phanloaitao
```

### Bước 2: Cài đặt thư viện
Mở Terminal/PowerShell và chạy lệnh:
```bash
pip install Pillow opencv-python python-snap7
```

### Bước 3: Chạy chương trình
```bash
python main.py
```

---

## 🔌 Hướng dẫn kết nối PLC S7-1200 (PLC Connection Guide)

1.  **Cấu hình PLC trên TIA Portal**:
    *   Vào **Properties** của CPU -> **Protection & Security** -> **Connection mechanisms**.
    *   Tích chọn: **"Permit access with PUT/GET communication from remote partner"**.
2.  **Cấu hình IP**:
    *   Đảm bảo máy tính và PLC cùng lớp mạng (Ví dụ: PLC `192.168.0.1`, PC `192.168.0.100`).
3.  **Địa chỉ dữ liệu (Mặc định trong code)**:
    *   **MW10**: Số lượng hạng GOOD (Kiểu Int)
    *   **MW12**: Số lượng hạng MEDIUM (Kiểu Int)
    *   **MW14**: Số lượng hạng BAD (Kiểu Int)
    *   **M0.0**: Lệnh START (Boolean)
    *   **M0.1**: Lệnh STOP (Boolean)

---

## 📁 Cấu trúc thư mục (Project Structure)
*   `main.py`: File code chính của ứng dụng.
*   `images/`: Thư mục chứa logo và hình ảnh minh họa.
*   `README.md`: File hướng dẫn này.

---

## 👤 Thông tin tác giả
*   **GVHD**: TS. Lê Chí Kiên
*   **Sinh viên thực hiện**:
    *   Mai Hoàng Nhã (23151284)
    *   Mai Nguyễn Minh Nhật (23151287)

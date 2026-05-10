# 🍎 Hệ Thống Phân Loại Táo Tự Động (Apple Sorting Dashboard)

Chào mừng bạn đến với dự án Phân loại Táo tự động. Đây là hệ thống kết hợp giữa **Xử lý ảnh OpenCV** và **Điều khiển PLC S7-1200** để phân loại táo dựa trên màu sắc và kích thước.

---

## 🛠 HƯỚNG DẪN CÀI ĐẶT VÀ CHẠY (Dành cho người mới)

Nếu bạn vừa tải bộ code này về, hãy thực hiện theo các bước sau để khởi động hệ thống:

### Bước 1: Tải mã nguồn về máy
- Bạn có thể tải file **.zip** của dự án này và giải nén ra thư mục bất kỳ.

### Bước 2: Cài đặt Python
- Đảm bảo máy bạn đã cài **Python 3.11** hoặc các bản 3.x mới hơn.
- Nếu chưa có, tải tại: [python.org](https://www.python.org/downloads/)

### Bước 3: Cài đặt các thư viện cần thiết
Mở cửa sổ **Terminal** (hoặc Command Prompt/PowerShell) tại thư mục vừa giải nén và chạy lệnh sau để cài toàn bộ thư viện:

```powershell
pip install opencv-python numpy pillow python-snap7
```

### Bước 4: Khởi chạy ứng dụng
Vẫn tại cửa sổ Terminal đó, bạn gõ lệnh sau để mở phần mềm:

```powershell
python giaodien/main.py
```

---

## 📖 CÁCH SỬ DỤNG CƠ BẢN

1.  **Vào màn hình chính:** Nhấn nút **START** ở màn hình chào mừng.
2.  **Chọn nguồn dữ liệu:**
    - Nếu có camera: Vào **CÀI ĐẶT** -> Chọn Camera tương ứng.
    - Nếu không có camera: Nhấn nút **📂 MỞ FILE** ở thanh bên trái để chọn một file **Ảnh** hoặc **Video** táo có sẵn trong máy để test.
3.  **Vận hành:** Nhấn **▶ BẬT CAMERA** (hoặc BẬT FILE). 
    - Hệ thống sẽ tự động theo dõi quả táo khi nó xoay và di chuyển.
    - Kết quả cuối cùng sẽ tự động xuất hiện ở bảng thống kê bên trái và lưu vào **LỊCH SỬ SQL**.
4.  **Làm mới:** Nếu muốn xóa kết quả cũ để bắt đầu lượt mới, nhấn **🔄 LÀM MỚI HỆ THỐNG**.

---

## ⚖️ TIÊU CHUẨN PHÂN LOẠI HIỆN TẠI

Hệ thống đang được cấu hình rất khắt khe để đảm bảo chất lượng:
- **Hạng GOOD (Tốt):** Táo đỏ chín đều (≥ 80%) và kích thước lớn (≥ 75mm).
- **Hạng MEDIUM (Vừa):** Táo chín vừa hoặc kích thước trung bình.
- **Hạng BAD (Loại):** Chỉ cần một mặt bị xanh (< 60%) hoặc kích thước nhỏ (< 60mm) là bị loại ngay.

---

## 📂 CƠ CẤU THƯ MỤC CHÍNH
- `giaodien/main.py`: File chạy chính.
- `giaodien/Processing/analyzer.py`: Chứa "bộ não" xử lý ảnh của hệ thống.
- `giaodien/history_images/`: Nơi lưu trữ ảnh chụp các quả táo đã phân loại.

---
*Dự án thực hiện bởi hoangnha999. Mọi thắc mắc vui lòng liên hệ tác giả!*

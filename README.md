# 🍎 Hệ Thống Phân Loại Trái Cây (Apple Classification System)

Hệ thống giám sát và phân loại trái cây (táo) tự động kết hợp xử lý ảnh (Computer Vision) và điều khiển công nghiệp (PLC S7-1200).

## 🚀 Tính Năng Chính
- **Giám sát thời gian thực:** Stream camera tốc độ cao với bộ đệm Live Buffer (0.1s/khung hình) tạo hiệu ứng film-strip.
- **Phân tích chất lượng táo:**
    - **Độ chín (Ripeness):** Tính toán % diện tích vỏ đỏ để đánh giá độ chín đều.
    - **Phát hiện lỗi (Defects):** Tự động khoanh vùng và nhận diện các vết thâm đen, bầm dập trên vỏ táo.
- **Phân hạng tự động:**
    - **LOẠI 1 (GOOD):** Chín > 90%, không vết thâm.
    - **LOẠI 2 (MEDIUM):** Chín 60-90% hoặc có vết thâm nhỏ.
    - **LOẠI 3 (BAD):** Chưa chín (< 60%) hoặc có vết thâm lớn.
- **Quản lý dữ liệu:**
    - Lưu lịch sử phân loại vào CSDL **SQLite**.
    - Chụp ảnh minh chứng cho từng sản phẩm.
    - Xuất danh sách lịch sử trực tiếp trên giao diện.
- **Hỗ trợ đa nguồn:** 
    - Camera (Astra Pro, Webcam).
    - Phân tích trực tiếp từ **File Ảnh** hoặc **File Video** có sẵn trong máy.
- **Kết nối PLC S7-1200:** Giao tiếp qua Snap7 để điều khiển băng chuyền và nhận tín hiệu cảm biến.

## 🛠 Công Nghệ Sử Dụng
- **Ngôn ngữ:** Python 3.11
- **Giao diện:** Tkinter (Modern Flat UI)
- **Xử lý ảnh:** OpenCV, Pillow
- **Cơ sở dữ liệu:** SQLite3
- **Kết nối PLC:** Snap7 (S7-1200)

## 📂 Cấu Trúc Thư Mục
- `giaodien/main.py`: File chạy chính của ứng dụng.
- `giaodien/Processing/`: Chứa thuật toán xử lý ảnh (`analyzer.py`).
- `giaodien/history_images/`: Thư mục lưu trữ ảnh chụp lịch sử.
- `giaodien/database.db`: File cơ sở dữ liệu SQLite.

## 📖 Hướng Dẫn Sử Dụng
1. **Khởi động:** Chạy lệnh `python giaodien/main.py`.
2. **Chọn nguồn:** Vào tab **CÀI ĐẶT** để chọn Camera hoặc dùng nút **📂 MỞ FILE** ở sidebar để chọn ảnh/video.
3. **Phân tích:** Đưa táo vào vùng **ANALYSIS ZONE** để hệ thống tự động soi lỗi và độ chín.
4. **Lưu trữ:** Bấm **CHỤP LƯU SQL** để ghi lại kết quả vào nhật ký.

---
*Dồ án được thực hiện bởi hoangnha999.*

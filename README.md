# 🍎 Dự Án Hệ Thống Phân Loại Táo Tự Động (Apple Grading System)

Dự án này là một hệ thống giám sát và phân loại táo thông minh, kết hợp giữa **Xử lý ảnh (Computer Vision)** và **Điều khiển công nghiệp (PLC S7-1200)**. Hệ thống sử dụng thư viện OpenCV để phân tích màu sắc, kích thước và chất lượng quả táo, sau đó gửi tín hiệu điều khiển xuống PLC để thực hiện hành động phân loại vật lý.

---

## 🏗️ Cấu Trúc Dự Án (Project Structure)

Thư mục chính được tổ chức như sau:

```text
DOAN_PLC_Phanloaitao/
├── giaodien/                # Thư mục chính chứa mã nguồn ứng dụng
│   ├── main.py              # Điểm khởi chạy chương trình (Entry Point)
│   ├── Processing/          # Xử lý hình ảnh và thuật toán phân tích
│   │   └── analyzer.py      # "Bộ não" phân tích táo (màu sắc, kích thước, độ chín)
│   ├── modules/             # Các module chức năng bổ trợ
│   │   ├── gui_app.py       # Giao diện chính (Tkinter) với các bảng điều khiển
│   │   ├── camera.py        # Quản lý kết nối và luồng video từ Camera/File
│   │   ├── plc.py           # Giao tiếp với PLC S7-1200 qua giao thức Snap7
│   │   ├── database.py      # Quản lý lưu trữ lịch sử bằng SQLite
│   │   └── ...              # Các module khác (Visualizer, Quality Control...)
│   ├── config/              # Chứa các file cấu hình hệ thống
│   ├── images/              # Tài nguyên hình ảnh giao diện
│   ├── history_images/      # Kho lưu trữ ảnh các quả táo đã được phân loại
│   └── database.db          # Cơ sở dữ liệu SQLite lưu lịch sử phân loại
├── dataset/                 # Dữ liệu mẫu (ảnh/video) để thử nghiệm
├── replace_font.py          # Script hỗ trợ xử lý font chữ giao diện
└── README.md                # Tài liệu hướng dẫn (file này)
```

---

## 📥 Hướng Dẫn Tải Và Cài Đặt (Installation)

### 1. Yêu cầu hệ thống
*   **Hệ điều hành:** Windows (khuyến nghị cho tương thích PLC Snap7).
*   **Python:** Phiên bản 3.11 trở lên.

### 2. Tải mã nguồn
*   Cách 1: Tải file `.zip` từ GitHub và giải nén.
*   Cách 2: Sử dụng Git để clone dự án:
    ```bash
    git clone https://github.com/hoangnha999/DoAn_PLC_Phanloaitao.git
    ```

### 3. Cài đặt thư viện (Dependencies)
Mở Terminal/Command Prompt tại thư mục dự án và chạy lệnh sau:
```bash
pip install opencv-python numpy pillow python-snap7
```

---

## 🚀 Hướng Dẫn Chạy Dự Án Trên VS Code

Để có trải nghiệm lập trình và chạy tốt nhất, hãy làm theo các bước sau trong **VS Code**:

### Bước 1: Mở dự án
1. Mở VS Code.
2. Chọn `File` -> `Open Folder...` -> Chọn thư mục `DOAN_PLC_Phanloaitao`.

### Bước 2: Cấu hình môi trường (Khuyến nghị)
1. Mở Terminal trong VS Code (`Ctrl + ~`).
2. Nếu bạn muốn dùng môi trường ảo (Virtual Environment):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install opencv-python numpy pillow python-snap7
   ```

### Bước 3: Chạy chương trình
Có 2 cách để chạy:
1. **Qua Terminal:** Gõ lệnh sau và nhấn Enter:
   ```powershell
   python giaodien/main.py
   ```
2. **Qua giao diện VS Code:**
   - Mở file `giaodien/main.py`.
   - Nhấn nút **Play** (hình tam giác) ở góc trên bên phải màn hình.

---

## 🛠️ Các Thao Tác Cơ Bản

1.  **Kết nối Camera:** Vào tab **Cài đặt**, chọn nguồn Camera (Astra Pro hoặc USB Cam).
2.  **Mở File mẫu:** Nếu không có phần cứng, nhấn **📂 MỞ FILE (ẢNH/VIDEO)** ở thanh điều khiển nhanh để nạp dữ liệu từ thư mục `dataset`.
3.  **Vận hành:** 
    - Nhấn **▶ BẬT CAMERA** để bắt đầu luồng xử lý.
    - Nhấn **▶ START** (trong phần PLC) để bắt đầu chu trình phân loại.
4.  **Xem lịch sử:** Chuyển qua tab **Lịch sử** để xem danh sách các quả táo đã phân loại kèm hình ảnh minh chứng.
5.  **Tùy chỉnh khung nhìn:** Bạn có thể kéo các đường biên (thanh xám) giữa các vùng Log, Camera, Thống kê để thay đổi kích thước các ô theo ý muốn.

---

## 📝 Lưu ý quan trọng
*   Nếu sử dụng PLC thực, hãy đảm bảo IP máy tính và PLC cùng lớp mạng (mặc định cấu hình trong phần mềm là `192.168.0.1`).
*   Nếu gặp lỗi thiếu `snap7.dll`, hãy tải thư viện Snap7 chính thức và copy file `.dll` vào thư mục hệ thống hoặc thư mục dự án.

---
*Phát triển bởi hoangnha999*

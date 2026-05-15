# 🍎 HỆ THỐNG PHÂN LOẠI TÁO TỰ ĐỘNG (APPLE GRADING SYSTEM)

## 🌳 CẤU TRÚC THƯ MỤC (PROJECT TREE)

```text
DOAN_PLC_Phanloaitao/
├── 📂 dataset/               # Dữ liệu Video/Ảnh mẫu để chạy thử
├── 📂 giaodien/              # Thư mục chứa mã nguồn chính
│   ├── 📄 main.py            # << FILE CHẠY CHÍNH >>
│   ├── 📄 database.db        # Cơ sở dữ liệu SQLite lưu lịch sử
│   ├── 📂 Processing/        # Thuật toán xử lý ảnh (bộ não)
│   │   └── 📄 analyzer.py    # Xử lý độ chín, kích thước, màu sắc
│   ├── 📂 modules/           # Các module chức năng hệ thống
│   │   ├── 📄 gui_app.py     # Giao diện người dùng & Logic chính
│   │   ├── 📄 camera.py      # Điều khiển Camera & Video stream
│   │   ├── 📄 plc.py         # Kết nối & Điều khiển PLC S7-1200
│   │   └── 📄 database.py    # Xử lý truy vấn dữ liệu SQL
│   ├── 📂 images/            # Icon và hình ảnh giao diện
│   └── 📂 history_images/    # Ảnh các quả táo đã phân loại
├── 📄 .gitignore             # Các file bỏ qua không up lên git
└── 📄 README.md              # Hướng dẫn sử dụng này
```

---

## 📥 1. DANH SÁCH CẦN CÀI ĐẶT (PREREQUISITES)

Khi mới tải code về, máy bạn sẽ **thiếu** các thành phần sau để chạy được chương trình. Hãy cài đặt theo thứ tự:

### 🟢 Bước 1: Cài đặt Python 3.11 (Bắt buộc)
1.  Tải tại: [python.org](https://www.python.org/downloads/)
2.  **Lưu ý cực kỳ quan trọng:** Khi cài đặt, phải tích vào ô **`Add Python to PATH`**.

### 🔵 Bước 2: Cài đặt các Thư viện lập trình (Libraries)
Mở Terminal (hoặc Command Prompt) và copy lệnh sau để cài những thứ còn thiếu:
```bash
pip install opencv-python numpy pillow python-snap7
```
*Giải thích các thư viện này:*
*   `opencv-python`: Để xử lý hình ảnh, nhận diện quả táo.
*   `numpy`: Để tính toán toán học cho các pixel ảnh.
*   `pillow`: Để hiển thị hình ảnh lên giao diện người dùng.
*   `python-snap7`: Để gửi lệnh điều khiển xuống PLC S7-1200.

### 🟡 Bước 3: Cài đặt VS Code (Công cụ chạy code)
1.  Tải tại: [code.visualstudio.com](https://code.visualstudio.com/)
2.  Đây là phần mềm tốt nhất để bạn mở và chạy dự án này.

---

## 🚀 2. CÁCH CHẠY PHẦN MỀM TRÊN VS CODE

1.  **Mở Thư mục**: Trong VS Code, chọn `File` -> `Open Folder...` -> Chọn thư mục `DOAN_PLC_Phanloaitao`.
2.  **Mở Terminal**: Nhấn phím `Ctrl` + `~` (phím cạnh số 1).
3.  **Dán lệnh chạy**: Copy dòng dưới đây dán vào Terminal rồi nhấn **Enter**:
    ```bash
    python giaodien/main.py
    ```

---

## 🛠️ 3. HƯỚNG DẪN VẬN HÀNH NHANH

| Tính năng | Cách thực hiện |
| :--- | :--- |
| **Chạy thử video** | Nhấn `📂 MỞ FILE` -> Chọn video trong thư mục `dataset`. |
| **Bật Camera** | Nhấn nút `▶ BẬT CAMERA` (hoặc Bật File). |
| **Kết nối PLC** | Vào tab `Cài đặt` -> Nhập IP PLC -> Nhấn `Kết nối`. |
| **Chỉnh khung hình** | Kéo các thanh xám giữa các vùng để thay đổi kích thước ô. |

---

## 📝 4. CÁC THIẾU SÓT THƯỜNG GẶP (TROUBLESHOOTING)

*   **Thiếu `snap7.dll`**: Nếu bạn kết nối PLC mà bị báo lỗi "Can't find snap7.dll", bạn cần tải file này trên mạng và copy vào `C:\Windows\System32`.
*   **Lỗi Python**: Nếu gõ lệnh `python` mà máy báo "not recognized", nghĩa là bạn đã quên tích vào "Add Python to PATH" ở Bước 1. Hãy cài lại Python.
*   **Lỗi Camera**: Nếu không thấy hình, hãy kiểm tra xem Camera đã cắm chắc chắn vào cổng USB chưa.

---
*Phát triển bởi hoangnha999*

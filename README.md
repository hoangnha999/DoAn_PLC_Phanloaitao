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

## 📥 1. HƯỚNG DẪN CÀI ĐẶT (CHO NGƯỜI MỚI)

### 🟢 Bước 1: Cài đặt Python (Động cơ chạy code)
1.  Tải Python tại: [python.org](https://www.python.org/downloads/)
2.  **Lưu ý cực kỳ quan trọng:** Khi chạy file cài đặt, bạn **PHẢI TÍCH CHỌN** vào ô `Add Python to PATH` rồi mới nhấn `Install Now`.

### 🔵 Bước 2: Cài đặt VS Code (Công cụ mở code)
1.  Tải tại: [code.visualstudio.com](https://code.visualstudio.com/)
2.  Cài đặt bình thường như các phần mềm khác.

### 🟡 Bước 3: Tải và Giải nén Code
1.  Tải code từ GitHub (nút `Code` -> `Download ZIP`).
2.  Giải nén vào một thư mục dễ nhớ (Ví dụ: ổ `D:`).

---

## 🚀 2. CÁCH CHẠY PHẦN MỀM TRÊN VS CODE

Hãy làm theo đúng 4 hành động sau:

1.  **Mở Folder**: Trong VS Code, chọn `File` -> `Open Folder...` -> Chọn thư mục `DOAN_PLC_Phanloaitao`.
2.  **Mở Terminal**: Nhấn phím `Ctrl` + `~` (phím cạnh số 1).
3.  **Cài thư viện**: Copy dòng dưới đây, dán vào Terminal rồi nhấn **Enter**:
    ```bash
    pip install opencv-python numpy pillow python-snap7
    ```
4.  **Chạy App**: Tìm file `giaodien/main.py`, mở nó ra và nhấn nút **Play** (hình tam giác) ở góc trên bên phải.

---

## 🛠️ 3. HƯỚNG DẪN VẬN HÀNH NHANH

| Hành động | Cách thực hiện |
| :--- | :--- |
| **Chạy thử video** | Nhấn `📂 MỞ FILE` -> Chọn video trong thư mục `dataset`. |
| **Bắt đầu xử lý** | Nhấn nút `▶ BẬT CAMERA` (hoặc Bật File). |
| **Kết nối PLC** | Vào tab `Cài đặt` -> Nhập IP PLC -> Nhấn `Kết nối`. |
| **Chỉnh giao diện** | Rê chuột vào các thanh xám và kéo để thay đổi kích thước các ô. |

---

## 📝 4. MỘT SỐ LƯU Ý KHI GẶP LỖI

*   **Không chạy được lệnh `python`**: Do bạn chưa chọn `Add Python to PATH` lúc cài đặt. Hãy gỡ ra cài lại.
*   **Lỗi Camera**: Đảm bảo Camera đã được cắm vào máy trước khi nhấn nút "Bật Camera".
*   **Snap7 Error**: Nếu kết nối PLC thật, bạn cần file `snap7.dll` đặt trong thư mục `C:\Windows\System32`.

---
*Dự án được thực hiện bởi hoangnha999. Chúc bạn vận hành thành công!*

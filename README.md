# 🍎 HỆ THỐNG PHÂN LOẠI TÁO TỰ ĐỘNG (APPLE GRADING SYSTEM)

Chào mừng bạn! Đây là hướng dẫn từng bước để cài đặt và vận hành hệ thống phân loại táo thông minh. Bản hướng dẫn này được thiết kế để **ngay cả người không biết về kỹ thuật** cũng có thể làm được.

---

## 📂 1. CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE)

Dưới đây là sơ đồ các thư mục quan trọng để bạn dễ hình dung:

*   📂 **`dataset/`**: Nơi chứa các Video/Ảnh mẫu để bạn chạy thử nghiệm (Dùng khi không có Camera thật).
*   📂 **`giaodien/`**: Thư mục chứa toàn bộ mã nguồn của phần mềm.
    *   📄 `main.py`: **File chính để khởi động chương trình.**
    *   📂 `Processing/`: Chứa thuật toán "bộ não" xử lý hình ảnh quả táo.
    *   📂 `modules/`: Chứa các bộ phận điều khiển Camera, PLC và Database.
    *   📂 `images/`: Chứa các icon và hình ảnh minh họa cho giao diện.
    *   📂 `history_images/`: Nơi tự động lưu ảnh các quả táo đã được phân loại thành công.
*   📄 `README.md`: Bản hướng dẫn bạn đang xem.

---

## 📥 2. HƯỚNG DẪN CÀI ĐẶT (CHO NGƯỜI MỚI)

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

## 🚀 3. CÁCH CHẠY PHẦN MỀM TRÊN VS CODE

Hãy làm theo đúng 4 hành động sau:

1.  **Mở Folder**: Trong VS Code, chọn `File` -> `Open Folder...` -> Chọn thư mục vừa giải nén.
2.  **Mở Terminal**: Nhấn phím `Ctrl` + `~` (nằm cạnh số 1).
3.  **Cài thư viện**: Copy dòng dưới đây, dán vào Terminal rồi nhấn **Enter**:
    ```bash
    pip install opencv-python numpy pillow python-snap7
    ```
4.  **Chạy App**: Tìm file `giaodien/main.py`, mở nó ra và nhấn nút **Play** (hình tam giác) ở góc trên bên phải.

---

## 🛠️ 4. HƯỚNG DẪN VẬN HÀNH NHANH

| Hành động | Cách thực hiện |
| :--- | :--- |
| **Chạy thử video** | Nhấn `📂 MỞ FILE` -> Chọn video trong thư mục `dataset`. |
| **Bắt đầu xử lý** | Nhấn nút `▶ BẬT CAMERA` (hoặc Bật File). |
| **Kết nối PLC** | Vào tab `Cài đặt` -> Nhập IP PLC -> Nhấn `Kết nối`. |
| **Chỉnh giao diện** | Rê chuột vào các thanh xám và kéo để thay đổi kích thước các ô. |

---

## 📝 5. MỘT SỐ LƯU Ý KHI GẶP LỖI

*   **Không chạy được lệnh `python`**: Do bạn chưa chọn `Add Python to PATH` lúc cài đặt. Hãy gỡ ra cài lại.
*   **Lỗi Camera**: Đảm bảo Camera đã được cắm vào máy trước khi nhấn nút "Bật Camera".
*   **Snap7 Error**: Nếu kết nối PLC thật, bạn cần file `snap7.dll` đặt trong thư mục `C:\Windows\System32`.

---
*Dự án được thực hiện bởi hoangnha999. Chúc bạn vận hành thành công!*

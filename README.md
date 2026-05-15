# 🍎 Dự Án Hệ Thống Phân Loại Táo Tự Động (Apple Grading System)

Chào mừng bạn đến với hệ thống phân loại táo thông minh! Đây là hướng dẫn cực kỳ chi tiết dành cho người mới bắt đầu (ngay cả khi bạn chưa từng lập trình) để có thể cài đặt và chạy được phần mềm này.

---

## 🏗️ 1. Cấu Trúc Dự Án (Tổng Quan)

Khi mở thư mục dự án, bạn sẽ thấy các thành phần chính sau:
- **`giaodien/main.py`**: Đây là file "công tắc" để mở phần mềm.
- **`giaodien/Processing/`**: Chứa thuật toán nhận diện quả táo, tính toán độ chín và kích thước.
- **`giaodien/modules/`**: Chứa các bộ phận điều khiển camera, kết nối PLC và lưu trữ dữ liệu.
- **`dataset/`**: Thư mục chứa các video và ảnh mẫu để bạn dùng thử nếu không có camera thực tế.
- **`history_images/`**: Nơi phần mềm sẽ tự lưu lại ảnh chụp các quả táo sau khi phân loại xong.

---

## 📥 2. Hướng Dẫn Cài Đặt Từ A-Z (Cho Người Mới)

### Bước 2.1: Cài đặt Python (Bắt buộc)
Python là "động cơ" để chạy mã nguồn này.
1. Truy cập: [python.org](https://www.python.org/downloads/)
2. Nhấn nút **Download Python 3.x.x**.
3. **QUAN TRỌNG:** Khi chạy file cài đặt, hãy tích vào ô **"Add Python to PATH"** trước khi nhấn "Install Now". Nếu quên bước này, máy tính sẽ không nhận lệnh `python`.

### Bước 2.2: Cài đặt Visual Studio Code (VS Code)
Đây là phần mềm dùng để mở và chạy code chuyên nghiệp nhưng rất dễ dùng.
1. Truy cập: [code.visualstudio.com](https://code.visualstudio.com/)
2. Tải về và cài đặt bình thường.

### Bước 2.3: Tải mã nguồn về máy
1. Nhấn nút **Code** (màu xanh) trên GitHub và chọn **Download ZIP**.
2. Giải nén file vừa tải về vào một thư mục (ví dụ: ổ `D:` hoặc `Desktop`).

---

## 🚀 3. Cách Chạy Phần Mềm Trên VS Code (Cầm Tay Chỉ Việc)

1. **Mở VS Code.**
2. Chọn menu **File** -> **Open Folder...** -> Tìm đến thư mục dự án bạn vừa giải nén và nhấn **Select Folder**.
3. **Mở Terminal:** Nhấn tổ hợp phím `Ctrl` + `~` (phím cạnh số 1) để hiện bảng đen ở dưới cùng.
4. **Cài đặt thư viện:** Hãy copy dòng lệnh bên dưới, dán vào bảng đen đó rồi nhấn **Enter**:
   ```bash
   pip install opencv-python numpy pillow python-snap7
   ```
   *(Đợi máy chạy một lúc cho đến khi hiện lại dòng dấu nhắc lệnh)*

5. **Chạy phần mềm:** 
   - Tìm file `main.py` trong thư mục `giaodien` ở cột bên trái, nhấn chuột vào nó.
   - Nhấn nút **Play** (hình tam giác nhỏ) ở góc trên cùng bên phải màn hình.
   - **Xong!** Giao diện phần mềm sẽ hiện lên.

---

## 🛠️ 4. Hướng Dẫn Vận Hành (Dành Cho Người Mới)

Nếu bạn không có Camera hoặc PLC thật, hãy làm theo các bước sau để xem phần mềm hoạt động:

1. **Nạp dữ liệu thử nghiệm:**
   - Trên giao diện phần mềm, nhấn nút **📂 MỞ FILE (ẢNH/VIDEO)**.
   - Tìm vào thư mục `dataset`, chọn một video quả táo.
2. **Bắt đầu chạy:**
   - Nhấn nút **▶ BẬT CAMERA** (Lúc này phần mềm sẽ bắt đầu phân tích video).
   - Bạn sẽ thấy khung hình video hiện lên và phần mềm tự vẽ vòng tròn quanh quả táo.
3. **Theo dõi kết quả:**
   - Nhìn sang bảng bên trái, các thông số **Độ chín** và **Kích thước** sẽ nhảy liên tục.
   - Khi video kết thúc hoặc quả táo đi qua, kết quả sẽ được chốt vào bảng **Grade 1, 2 hoặc 3**.
4. **Điều chỉnh giao diện:**
   - Bạn thấy các thanh xám ngăn cách giữa các vùng không? Hãy **rê chuột vào đó và kéo** để phóng to khung Camera hoặc thu nhỏ bảng Log tùy ý.

---

## 📝 5. Giải Quyết Lỗi Thường Gặp

- **Lỗi "python is not recognized":** Do lúc cài Python bạn quên tích vào "Add Python to PATH". Hãy gỡ Python ra cài lại và nhớ tích vào ô đó.
- **Lỗi thiếu `snap7.dll`:** Đây là lỗi khi kết nối PLC. Nếu bạn chỉ test xử lý ảnh thì có thể bỏ qua. Nếu muốn kết nối thật, hãy tải file `snap7.dll` trên mạng và bỏ vào thư mục `C:\Windows\System32`.

---
*Chúc bạn thực hiện thành công! Nếu gặp khó khăn, hãy kiểm tra kỹ từng bước hướng dẫn ở trên.*

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

## 🚀 Hướng dẫn cài đặt và chạy (Chi tiết cho người mới)

Nếu bạn không biết sử dụng Git, hãy làm theo các bước đơn giản dưới đây:

### Bước 1: Tải mã nguồn về máy
*   **Cách 1 (Đơn giản nhất):** Truy cập link GitHub [DoAn_PLC_Phanloaitao](https://github.com/hoangnha999/DoAn_PLC_Phanloaitao). Nhấn vào nút xanh **Code** -> Chọn **Download ZIP**. Sau khi tải về, hãy giải nén file ra thư mục.
*   **Cách 2 (Dùng Git):** Chạy lệnh `git clone https://github.com/hoangnha999/DoAn_PLC_Phanloaitao.git`

### Bước 2: Cài đặt Python
*   Nếu máy bạn chưa có Python, hãy tải tại [python.org](https://www.python.org/downloads/) (Chọn bản 3.10 hoặc mới hơn). 
*   **Lưu ý quan trọng:** Khi cài đặt, hãy tích chọn vào ô **"Add Python to PATH"**.

### Bước 3: Cài đặt các thư viện hỗ trợ
Mở thư mục dự án vừa giải nén. Nhấn phím `Shift` + `Chuột phải` vào vùng trống trong thư mục và chọn **"Open PowerShell window here"** (hoặc Terminal), sau đó copy và dán lệnh sau:
```bash
pip install Pillow opencv-python python-snap7
```

### Bước 4: Chạy chương trình
Vẫn tại cửa sổ đó, nhập lệnh sau để mở giao diện:
```bash
python giaodien/main.py
```
*(Hoặc bạn có thể chuột phải vào file `main.py` trong thư mục `giaodien` và chọn "Open with Python")*

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

## 📊 Kết quả và Giải thích Giao diện (Interface Explained)

Hệ thống bao gồm 2 màn hình chính với các chức năng riêng biệt:

### 1. Màn hình Giới thiệu (Presentation Screen)
Đây là màn hình đầu tiên khi khởi động ứng dụng:
*   **Header**: Hiển thị Logo và tên Trường, Khoa, Ngành đào tạo.
*   **Tên Đề tài**: "Hệ thống phân loại hạng chất lượng trái cây" (Chữ đỏ nổi bật).
*   **Hình ảnh minh họa**: Hệ thống băng chuyền phân loại thực tế.
*   **Thông tin**: Tên GV hướng dẫn và các sinh viên thực hiện.
*   **Nút điều khiển**: 
    *   `Chạy chương trình`: Để chuyển sang giao diện điều khiển chính.
    *   `Kết thúc`: Đóng ứng dụng.

### 2. Màn hình Điều khiển & Giám sát (Control & Monitoring Screen)
Màn hình này xuất hiện sau khi nhấn "Chạy chương trình":

#### ⬅️ Bảng bên trái (Left Panel - Thống kê)
*   **Bộ đếm (Counters)**: Hiển thị số lượng táo đã phân loại theo 3 hạng:
    *   **✅ GOOD**: Táo đạt chất lượng cao.
    *   **🟡 MEDIUM**: Táo hạng trung bình.
    *   **❌ BAD**: Táo lỗi/hỏng.
*   **Tổng số**: Tổng cộng số táo đã đi qua hệ thống.
*   **Reset**: Đặt lại tất cả bộ đếm về 0.
*   **Nguồn Camera**: Danh sách chọn (Default, IP Cam,...) và nút bật/tắt Camera.

#### ↗️ Bảng bên phải (Right Panel - Camera Stream)
*   **Khung trên (Color)**: Hiển thị video thực tế từ camera với màu sắc đầy đủ.
*   **Khung dưới (Grayscale)**: Hiển thị ảnh xám (đen trắng) dùng để xử lý thuật toán nhận dạng dễ dàng hơn.

#### ⬇️ Thanh dưới cùng (Bottom Bar - PLC Control)
*   **Kết nối PLC**: Nhập IP (mặc định `192.168.0.1`), Rack, Slot và nhấn nút Connect.
*   **Điều khiển PLC**:
    *   `▶ START`: Gửi tín hiệu chạy hệ thống cơ khí/băng chuyền.
    *   `⏹ STOP`: Dừng hệ thống khẩn cấp.
*   **Trạng thái**: Đèn báo trạng thái kết nối PLC thời gian thực.

---

## 📁 Cấu trúc thư mục (Project Structure)
*   `giaodien/main.py`: File code chính của ứng dụng.
*   `giaodien/images/`: Thư mục chứa logo và hình ảnh minh họa.
*   `README.md`: File hướng dẫn này.

---

## 👤 Thông tin tác giả
*   **GVHD**: TS. Lê Chí Kiên
*   **Sinh viên thực hiện**:
    *   Mai Hoàng Nhã (23151284)
    *   Mai Nguyễn Minh Nhật (23151287)

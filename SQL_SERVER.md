# 🗄️ Hướng Dẫn Cấu Hình SQL Server Cho Hệ Thống Phân Loại Táo

Dự án hỗ trợ lưu trữ dữ liệu lịch sử phân loại trên hai hệ quản trị cơ sở dữ liệu: **SQLite** (mặc định cho môi trường thử nghiệm nhanh, không cần cài đặt) và **Microsoft SQL Server** (khuyến nghị cho môi trường chạy thực tế công nghiệp hoặc kết nối hệ thống SCADA/HMI tập trung).

Tài liệu này hướng dẫn chi tiết cách cài đặt, cấu hình và khắc phục lỗi khi chuyển đổi sang sử dụng SQL Server.

---

## 📌 1. Yêu Cầu Chuẩn Bị (Prerequisites)

Để ứng dụng kết nối được tới Microsoft SQL Server, hệ thống của bạn cần cài đặt các thành phần sau:

1. **Microsoft SQL Server**: Bản Express, Developer hoặc Enterprise (khuyến nghị SQL Server 2019 hoặc mới hơn).
2. **Microsoft SQL Server Management Studio (SSMS)**: Để quản lý trực quan CSDL.
3. **Microsoft ODBC Driver for SQL Server**:
   - Dự án mặc định cấu hình dùng **ODBC Driver 17 for SQL Server**.
   - Nếu máy tính chưa có, tải và cài đặt từ trang chủ Microsoft: [Download Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).
4. **Thư viện python `pyodbc`**:
   - Đã được định nghĩa sẵn trong `requirements.txt`.
   - Cài đặt bằng lệnh: `pip install pyodbc`

---

## 🗂️ 2. Khởi Tạo Cơ Sở Dữ Liệu Trên SQL Server

Hệ thống được thiết kế theo luồng **Auto-Initialization** (Tự động khởi tạo cấu trúc). Bạn **chỉ cần tạo một Database trống** trên SQL Server, phần mềm sẽ tự tạo bảng và cấu trúc dữ liệu khi chạy lần đầu tiên.

### Các bước thực hiện:
1. Mở **SSMS** và kết nối tới SQL Server của bạn.
2. Nhấp chuột phải vào mục **Databases** -> Chọn **New Database...**
3. Nhập tên Database là: `AppleClassification` (hoặc tên tùy ý theo cấu hình của bạn).
4. Nhấn **OK** để hoàn tất.

---

## ⚙️ 3. Cấu Hình Kết Nối Trên Phần Mềm

Mọi thiết lập kết nối được lưu trữ tại file cấu hình: [system_config.json](file:///d:/DOAN_PLC_Phanloaitao/giaodien/config/system_config.json) ở khóa `"database"`.

### Cách 1: Sử dụng quyền Windows (Windows Authentication - Khuyên dùng)
Đây là cách đơn giản nhất khi SQL Server chạy cục bộ trên cùng máy tính với phần mềm.

Mở file `system_config.json` và cập nhật khối `"database"` như sau:

```json
  "database": {
    "type": "sqlserver",
    "sqlserver": {
      "driver": "ODBC Driver 17 for SQL Server",
      "server": "LOCALHOST\\SQLEXPRESS",
      "database": "AppleClassification",
      "username": "",
      "password": "",
      "trusted_connection": true
    }
  }
```

*Lưu ý: Thay thế `LOCALHOST\\SQLEXPRESS` bằng tên Server Instance thực tế của bạn (Ví dụ: `DESKTOP-RF2G40K\\SQLEXPRESS`).*

### Cách 2: Sử dụng tài khoản SQL Server (SQL Server Authentication)
Dùng khi CSDL nằm trên một máy chủ khác trong mạng LAN/Internet.

```json
  "database": {
    "type": "sqlserver",
    "sqlserver": {
      "driver": "ODBC Driver 17 for SQL Server",
      "server": "192.168.1.100,1433",
      "database": "AppleClassification",
      "username": "sa",
      "password": "your_secure_password",
      "trusted_connection": false
    }
  }
```

---

## 📐 4. Cấu Trúc Bảng Dữ Liệu (Database Schema)

Khi khởi chạy thành công, phần mềm sẽ tự động sinh ra 2 bảng có liên kết khóa ngoại với nhau:

### Bảng 1: Lịch sử phân loại chung (`phan_loai_history`)
Lưu trữ thông tin tổng quát của từng lượt phân loại quả táo.

| Tên Cột | Kiểu Dữ Liệu | Mô Tả |
|---|---|---|
| `id` | `INT IDENTITY(1,1) PRIMARY KEY` | Khóa chính tự tăng |
| `thoi_gian` | `NVARCHAR(50)` | Thời điểm phân loại (`YYYY-MM-DD HH:MM:SS`) |
| `ket_qua` | `NVARCHAR(100)` | Kết quả xếp hạng cuối (`Grade-1`, `Grade-2`, `Grade-3`) |
| `diameter_mm` | `FLOAT` | Đường kính trung bình đo được (mm) |
| `duong_dan_anh` | `NVARCHAR(500)` | Đường dẫn tới ảnh đại diện kết quả phân loại |
| `ty_le_yield` | `NVARCHAR(100)` | Tỉ lệ Yield (hiện tại để trống hoặc dùng mở rộng) |
| `nha_vuon` | `NVARCHAR(250)` | Tên nhà vườn/nhà cung cấp |
| `ma_lo` | `NVARCHAR(250)` | Mã lô hàng táo đang chạy |
| `ground_truth` | `NVARCHAR(250)` | Nhãn thực tế do Operator gán lại để kiểm tra sai số |

### Bảng 2: Chi tiết 10 khung ảnh (`phan_loai_session_10`)
Lưu chi tiết toàn bộ 10 khung hình chụp trong phiên xoay để phục vụ kiểm tra chất lượng nâng cao (Quality Control). Có khóa ngoại tham chiếu đến bảng lịch sử chính.

| Tên Cột | Kiểu Dữ Liệu | Mô Tả |
|---|---|---|
| `id` | `INT IDENTITY(1,1) PRIMARY KEY` | Khóa chính tự tăng |
| `history_id` | `INT` | Khóa ngoại tham chiếu sang `phan_loai_history(id)` |
| `frame_idx` | `INT` | Số thứ tự khung hình từ 1 đến 10 |
| `thoi_gian` | `NVARCHAR(50)` | Thời gian chụp khung hình |
| `trigger_source` | `NVARCHAR(100)` | Nguồn kích hoạt chụp (`PLC_Sensor`, `Manual`) |
| `ket_qua` | `NVARCHAR(100)` | Kết quả phân loại riêng của khung hình này |
| `ripeness_pct` | `FLOAT` | Độ chín đỏ (%) |
| `diameter_mm` | `FLOAT` | Đường kính ước lượng của khung hình này (mm) |
| `shape_label` | `NVARCHAR(100)` | Hình dạng méo hay tròn |
| `yolo_conf` | `FLOAT` | Độ tin cậy của mô hình YOLOv8 trên khung hình này |
| `detail_json` | `NVARCHAR(MAX)` | Dữ liệu thô JSON lưu trữ toàn bộ chỉ số phụ hỗ trợ vẽ biểu đồ |
| `duong_dan_anh` | `NVARCHAR(500)` | Đường dẫn file ảnh riêng của khung hình |

---

## 🛠️ 5. Khắc Phục Sự Cố Kết Nối (Troubleshooting)

### 1. Lỗi: `[Microsoft][ODBC Driver Manager] Data source name not found and no default driver specified`
- **Nguyên nhân**: Máy tính chưa cài đặt ODBC Driver bản 17, hoặc trong `system_config.json` chỉ định phiên bản driver không khớp với bản đã cài trên OS.
- **Xử lý**: Kiểm tra lại phiên bản ODBC đã cài trong máy (mở Control Panel -> Administrative Tools -> ODBC Data Sources -> Tab Drivers). Nếu máy cài ODBC Driver 18, đổi giá trị driver trong cấu hình thành `"ODBC Driver 18 for SQL Server"`.

### 2. Lỗi: `[Microsoft][ODBC SQL Server Driver] Communication link failure / Named Pipes Provider: Could not open a connection to SQL Server`
- **Nguyên nhân**: SQL Server đang tắt, hoặc tính năng kết nối mạng TCP/IP chưa được bật.
- **Xử lý**:
  1. Mở **SQL Server Configuration Manager**.
  2. Chọn mục **SQL Server Services** -> Đảm bảo trạng thái service của instance là **Running**.
  3. Chọn **SQL Server Network Configuration** -> **Protocols for SQLEXPRESS** -> Đảm bảo **TCP/IP** và **Named Pipes** đã ở trạng thái **Enabled**.
  4. Khởi động lại service SQL Server.

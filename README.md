# HỆ THỐNG PHÂN LOẠI TÁO TỰ ĐỘNG

Dự án nhận dạng và phân loại táo theo 3 tiêu chí chính:
- TC1: Độ chín (tỉ lệ màu đỏ)
- TC2: Kích thước (đường kính mm)
- TC3: Hình dáng (độ tròn)

Hệ thống có giao diện vận hành, luồng xử lý ảnh riêng, và có thể kết nối PLC S7-1200.

## 1. Cấu trúc dự án

Dự án đã được tổ chức theo 3 thư mục chính để dễ bảo trì, tách rõ:
- Dữ liệu (dataset)
- Ứng dụng giao diện vận hành (giaodien)
- Core xử lý ảnh (Processing)

### 1.1 Cây thư mục chi tiết

```text
DOAN_PLC_Phanloaitao/
├── dataset/
│   ├── train/               # Ảnh nguồn để tạo nhãn/huấn luyện
│   ├── yolo_dataset/        # Dataset theo định dạng YOLO (images/labels/dataset.yaml)
│   └── ...
├── giaodien/
│   ├── main.py              # Entry point chạy app
│   ├── modules/
│   │   ├── gui_app.py       # Điều phối GUI + gọi FruitAnalyzer
│   │   ├── camera.py        # Quản lý camera/stream
│   │   ├── plc.py           # Kết nối PLC
│   │   └── database.py      # Lưu lịch sử, truy vấn, export
│   ├── config/              # Cấu hình runtime
│   ├── images/              # Tài nguyên hình giao diện
│   ├── history_images/      # Ảnh kết quả đã xử lý
│   └── dataset/             # Dataset phục vụ GUI/nội bộ (nếu có)
├── Processing/
│   ├── analyzer.py          # Facade trung tâm của engine xử lý ảnh
│   └── analyzer_modules/
│       ├── pipeline.py      # Pipeline tổng hợp TC1/TC2/TC3
│       ├── segmentation.py  # Tách quả táo
│       ├── yolo_runtime.py  # Nạp/chạy YOLO và fallback
│       ├── tc1_ripeness.py  # Độ chín
│       ├── tc2_size.py      # Kích thước
│       ├── tc3_shape.py     # Hình dáng
│       ├── stabilization.py # Ổn định đo đạc theo thời gian
│       └── ...
├── auto_label.py            # Script tạo nhãn tự động
└── README.md                # Tài liệu hướng dẫn
```

### 1.2 Vai trò của 3 thư mục chính

1. dataset/
- Chứa dữ liệu đầu vào (ảnh/video) và dữ liệu huấn luyện.
- Không chứa logic app.
- Nên backup trước khi thao tác xóa/sửa lớn.

2. giaodien/
- Chứa ứng dụng vận hành, nhận frame, hiển thị kết quả, kết nối PLC và DB.
- Không nên để logic xử lý ảnh phức tạp tại đây.
- Chỉ nên giữ logic điều phối và I/O.

3. Processing/
- Chứa toàn bộ logic xử lý ảnh mang tính core.
- Có thể test độc lập mà không phụ thuộc GUI.
- Dễ mở rộng thêm module mới (ví dụ: thêm tiêu chí TC4).

### 1.3 Quan hệ phụ thuộc

Chiều phụ thuộc chuẩn:

```text
giaodien  --->  Processing  --->  dataset (đọc dữ liệu/cấu hình cần thiết)
```

Nguyên tắc:
- Processing không phụ thuộc vào GUI (tránh coupling ngược).
- dataset không chứa code logic.
- giaodien là lớp trên cùng, gọi core để lấy kết quả hiển thị.

### 1.4 Entry points quan trọng

- Chạy app: giaodien/main.py
- Core analyzer: Processing/analyzer.py
- Script tạo nhãn: auto_label.py

## 2. Yêu cầu môi trường

- Windows 10/11
- Python 3.10 hoặc 3.11
- Khuyến nghị dùng virtual environment (.venv)

## 3. Cài đặt nhanh

Mở terminal tại thư mục gốc dự án và chạy:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu bạn không dùng YOLO, có thể bỏ qua việc cài đặt `ultralytics` trong `requirements.txt`.

## 4. Chạy chương trình

```bash
python giaodien/main.py
```

Sau khi mở giao diện:
- Mở video test trong dataset để kiểm tra nhanh
- Hoặc bật camera trực tiếp
- Nếu sử dụng PLC: vào phần cài đặt để nhập IP và kết nối

## 5. Các tệp và thư mục quan trọng

- giaodien/main.py: entrypoint giao diện
- giaodien/modules/gui_app.py: luồng điều khiển GUI và tích hợp analyzer
- Processing/analyzer.py: analyzer tổng
- Processing/analyzer_modules/: các module tc1/tc2/tc3, segmentation, yolo, pipeline
- dataset/: dữ liệu train/test và yolo dataset

## 6. Dọn dẹp an toàn, không mất dữ liệu

Nguyên tắc an toàn:
- KHÔNG xóa dataset/
- KHÔNG xóa Processing/
- KHÔNG xóa giaodien/modules/

Chỉ nên xóa:
- __pycache__
- các thư mục trung gian rỗng

Lệnh gợi ý để xóa cache Python trong dự án:

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

Nếu cần dọn sâu hơn, hãy backup trước (copy cả thư mục dự án hoặc commit git).

## 7. Lỗi thường gặp

1. Lỗi không import được snap7
- Kiểm tra đã cài python-snap7
- Nếu cần, cài thêm thư viện runtime theo hướng dẫn của python-snap7

2. Không mở được camera
- Kiểm tra camera có đang bị app khác chiếm hay không
- Thử đổi index camera trong phần cài đặt

3. Chạy được GUI nhưng không detect táo
- Kiểm tra đường dẫn model (nếu dùng YOLO)
- Kiểm tra ảnh đầu vào có đủ ánh sáng, ít nhiễu motion blur

4. Chậm hoặc giật khung hình
- Giảm độ phân giải camera
- Đóng bớt app nền
- Nếu cần, tắt các tác vụ không cần thiết trong luồng debug

## 8. Quy trình cập nhật khuyến nghị

1. Tạo nhanh một bản backup
2. Chỉnh code
3. Chạy lại python giaodien/main.py để smoke test
4. Nếu ổn định mới xóa các thư mục cache

---

Tác giả: hoangnha999

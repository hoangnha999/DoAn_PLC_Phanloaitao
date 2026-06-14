# HỆ THỐNG PHÂN LOẠI TÁO TỰ ĐỘNG

Dự án nhận dạng và phân loại táo theo 3 tiêu chí chính:
- TC1: Độ chín (tỉ lệ màu đỏ)
- TC2: Kích thước (đường kính mm)
- TC3: Hình dáng (độ tròn)

Hệ thống có giao diện vận hành, luồng xử lý ảnh riêng, và có thể kết nối PLC S7-1200.

## 1. Cấu trúc dự án

Dự án đã được tổ chức theo các thư mục chính để dễ bảo trì, tách rõ:
- Dữ liệu (dataset, yolo_dataset)
- Ứng dụng giao diện vận hành (giaodien)
- Core xử lý ảnh (Processing)
- Driver điều khiển camera (OpenNI2)

### 1.1 Cây thư mục chi tiết (đầy đủ các tệp tin)

```text
DOAN_PLC_Phanloaitao/
├── dataset/
│   └── dataset_apple/
│       ├── Image/                 # Thư mục chứa các ảnh quả táo gốc chưa phân chia
│       └── Label/                 # Thư mục chứa file nhãn của tập gốc
├── yolo_dataset/                  # Tập dữ liệu YOLO đã phân chia tỉ lệ 80/20
│   ├── dataset.yaml               # File cấu hình đường dẫn và nhãn lớp cho YOLOv8
│   ├── images/
│   │   ├── train/                 # Tập ảnh dùng để huấn luyện mô hình (893 ảnh)
│   │   └── val/                   # Tập ảnh dùng để kiểm thử mô hình (224 ảnh)
│   └── labels/
│       ├── train/                 # File nhãn YOLO tương ứng với tập train (893 file)
│       └── val/                   # File nhãn YOLO tương ứng với tập val (224 file)
├── giaodien/
│   ├── main.py                    # Điểm khởi chạy (Entry Point) giao diện GUI vận hành
│   ├── best.pt                    # Trọng số mô hình YOLOv8n đã huấn luyện tối ưu
│   ├── database.db                # Cơ sở dữ liệu SQLite lưu lịch sử phân loại táo
│   ├── history_images/            # Nơi lưu trữ ảnh chụp quả táo thực tế sau phân loại
│   ├── config/                    # Thư mục chứa các cấu hình hệ thống
│   │   ├── runtime_config.py      # Cấu hình các ngưỡng diện tích, camera khi chạy
│   │   ├── system_config.json     # Lưu trữ cấu hình hệ thống dạng tệp JSON
│   │   └── system_config.json.bak # File cấu hình dự phòng của hệ thống
│   ├── images/                    # Tài nguyên hình ảnh tĩnh của giao diện
│   │   ├── conveyor_system.png    # Hình ảnh mô phỏng băng tải hệ thống
│   │   ├── faculty_logo.png        # Logo khoa Cơ khí/Điện tử
│   │   └── ute_logo.png            # Logo trường UTE
│   └── modules/                   # Các khối xử lý logic chức năng cho giao diện
│       ├── camera.py              # Quản lý luồng video (Astra Pro/Camera thường)
│       ├── database.py            # Kết nối SQLite, lưu lịch sử, xuất báo cáo ra Excel
│       ├── gui_app.py             # Điều phối giao diện Tkinter chính
│       ├── plc.py                 # Truyền thông PLC S7-1200 qua thư viện Snap7
│       └── quality_control.py     # Thống kê chất lượng phân hạng táo
├── Processing/
│   ├── __init__.py
│   ├── analyzer.py                # Facade trung tâm của engine xử lý ảnh FruitAnalyzer
│   └── analyzer_modules/          # Thuật toán chi tiết của lõi xử lý ảnh
│       ├── __init__.py
│       ├── blur_ops.py            # Kiểm tra ảnh mờ (deblur), phát hiện ảnh nhòe
│       ├── bootstrap.py           # Khởi tạo trạng thái ban đầu của bộ phân tích
│       ├── classification.py      # Phân loại độ chín vỏ và phân hạng kích thước táo
│       ├── grading.py             # Logic tổng hợp 3 tiêu chí phân hạng táo (Grade 1/2/3)
│       ├── pipeline.py            # Luồng pipeline xử lý tuần tự trên từng khung hình
│       ├── segmentation.py        # Tách quả táo (kết hợp YOLOv8 và lọc màu HSV)
│       ├── session_decision.py    # Phán quyết kết quả phân hạng dựa trên chuỗi 10 khung hình
│       ├── stabilization.py       # Bộ ổn định đường kính táo và lọc nhiễu chiều sâu Z
│       ├── tc1_ripeness.py        # Tiêu chí 1: Đo độ chín theo tỷ lệ màu đỏ vỏ quả
│       ├── tc2_size.py            # Tiêu chí 2: Ước lượng đường kính táo (mm)
│       ├── tc3_shape.py           # Tiêu chí 3: Đánh giá độ tròn đều (Circularity)
│       ├── visualization.py       # Vẽ bounding box, overlay mask màu lên màn hình
│       └── yolo_runtime.py        # Nạp mô hình YOLOv8 và thực hiện Object Tracking
├── OpenNI2/                       # Thư viện để giao tiếp với camera chiều sâu Astra Pro
│   └── Redist/                    # Các tệp thực thi và DLL của thư viện OpenNI2
│       ├── OpenNI2/
│       │   └── Drivers/           # Trình điều khiển camera (orbbec.dll, OniFile.dll)
│       ├── DepthUtils.lib
│       ├── NiViewer.exe           # Phần mềm hiển thị chiều sâu trực quan để test
│       ├── OpenNI2.dll            # Thư viện liên kết động chính
│       ├── OpenNI2.lib
│       ├── PS1080Console.exe
│       ├── XnLib.lib
│       └── glut64.dll
├── image/                         # Thư mục chứa hình ảnh tài liệu dự án
│   └── README/
│       ├── 1781008683436.png
│       └── yolo_predict_test.png  # Hình ảnh kết quả nhận diện thực tế của YOLOv8
├── .gitignore                     # Cấu hình bỏ qua các tệp tạm của Git
├── NHAT_KY_DO_AN.md               # Nhật ký cập nhật, sửa lỗi và phát triển đồ án
├── README.md                      # Tài liệu hướng dẫn sử dụng này
├── replace_font.py                # File script thay đổi font chữ hiển thị giao diện
├── requirements.txt               # Danh sách thư viện Python cần cài đặt
├── split_dataset.py               # Script phân chia tự động tập dataset gốc
├── test_openni.log                # Log ghi lại quá trình test camera OpenNI2
└── test_openni.py                 # File python để test nhanh kết nối camera đo chiều sâu
```

### 1.2 Vai trò của các thư mục chính

1. dataset/
- Chứa dữ liệu đầu vào gốc (ảnh/video).
- Không chứa logic ứng dụng.

2. yolo_dataset/
- Dữ liệu đã gán nhãn theo đúng định dạng YOLOv8 để huấn luyện.

3. giaodien/
- Chứa ứng dụng vận hành, nhận frame, hiển thị kết quả, kết nối PLC và DB.
- Không chứa logic xử lý ảnh phức tạp tại đây (chỉ giữ logic điều phối và I/O).

4. Processing/
- Chứa toàn bộ logic xử lý ảnh mang tính lõi (core).
- Có thể chạy và test độc lập mà không cần khởi động GUI.

### 1.3 Quan hệ phụ thuộc

Chiêu phụ thuộc chuẩn:

```text
giaodien  --->  Processing  --->  dataset/yolo_dataset (đọc dữ liệu/cấu hình)
```

Nguyên tắc:
- Processing không phụ thuộc vào GUI (tránh coupling ngược).
- giaodien là lớp trên cùng, gọi core Processing để lấy kết quả hiển thị.

### 1.4 Entry points quan trọng

- Chạy app: `giaodien/main.py`
- Core analyzer: `Processing/analyzer.py`
- Script phân chia dataset: `split_dataset.py`

## 2. Yêu cầu môi trường

- Windows 10/11
- Python 3.10 hoặc 3.11
- Khuyến nghị dùng virtual environment (.venv)

## 3. Cài đặt nhanh (Dành cho người mới tải dự án)

Sau khi clone/download dự án về máy, bạn mở terminal (như PowerShell hoặc CMD) tại thư mục gốc của dự án và làm theo các bước sau:

**Bước 1: Tạo môi trường ảo (Virtual Environment)**
```powershell
python -m venv .venv
```

**Bước 2: Kích hoạt môi trường ảo**
Nếu bạn dùng **PowerShell** (thường báo lỗi màu đỏ không cho chạy script), hãy chạy lệnh cấp quyền này trước:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Sau đó kích hoạt môi trường ảo:
```powershell
.venv\Scripts\activate
```
*(Nếu thành công, bạn sẽ thấy chữ `(.venv)` xuất hiện ở đầu dòng lệnh)*

**Bước 3: Nâng cấp pip và cài đặt thư viện**
Copy và dán lệnh sau để cài đặt tất cả các thư viện cần thiết:
```powershell
python -m pip install --upgrade pip
pip install opencv-python numpy pillow python-snap7 ultralytics openni
```

## 4. Chạy chương trình

Sau khi cài đặt xong, bạn gõ lệnh sau để khởi chạy phần mềm:
```powershell
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

## 9. Vai trò và thông tin mô hình YOLOv8 trong dự án

Dự án này sử dụng phương pháp **Phân đoạn lai (Hybrid Segmentation)** kết hợp giữa trí tuệ nhân tạo **YOLOv8** (Deep Learning) và thuật toán xử lý ảnh truyền thống (**OpenCV HSV**).

### 9.1 Vai trò của YOLOv8 trong luồng xử lý
- **Cổng chặn thông minh (YOLO Gate):** Tránh nhận diện sai các vật thể không phải táo (ví dụ: tay người vận hành, nền băng tải, bụi bẩn). Hệ thống chỉ thực hiện phân tích khi YOLOv8 phát hiện quả táo với độ tự tin (Confidence) đạt ngưỡng.
- **Giới hạn vùng xử lý (ROI):** Bounding Box từ YOLOv8 được dùng làm khung vùng quan tâm. OpenCV chỉ tính toán các tiêu chí độ chín, kích thước, hình dáng bên trong vùng này, giúp giảm tải thuật toán và tránh nhiễu bên ngoài.
- **Phân vùng phát hiện trung tâm (Detection Zone):** Chỉ cho phép xử lý và đẩy kết quả xuống PLC khi tâm của quả táo nằm trong khu vực trung tâm băng tải (tránh chụp/gửi trùng lặp).
- **Cơ chế dự phòng (Fallback):** Khi ánh sáng thay đổi quá mạnh hoặc màu táo bị lẫn với nền khiến thuật toán OpenCV HSV không tìm được contour táo, hệ thống sẽ tự động vẽ mặt nạ hình học dạng elip dựa trên Bounding Box của YOLOv8 để tiếp tục đo đạc kích thước mà không bị gián đoạn.

### 9.2 Vị trí File Model và tham số cấu hình
- **Đường dẫn tệp tin:** Hệ thống tự động nạp mô hình từ tệp `giaodien/best.pt` (mô hình đã được train và tải về).
- **Các thông số cấu hình chính (trong `giaodien/config` và `Processing/analyzer.py`):**
  - `YOLO_CONF_THRESH`: Ngưỡng độ tin cậy tối thiểu để nhận dạng quả táo (mặc định cấu hình `0.45` cho ngoài trời hoặc tùy chỉnh).
  - `DETECTION_ZONE_WIDTH_RATIO` / `DETECTION_ZONE_HEIGHT_RATIO`: Tỷ lệ vùng phát hiện trung tâm (mặc định là `0.55` chiều rộng và `0.70` chiều cao của khung hình).
  - `YOLO_MIN_APPLE_COLOR_RATIO`: Tỉ lệ diện tích màu sắc giống táo tối thiểu nằm trong bounding box để loại trừ các nhận diện giả lập.

### 9.3 Thông số huấn luyện & Hiệu năng mô hình (YOLOv8 Training)
Mô hình hiện tại đang tích hợp chạy thực tế đã được huấn luyện với các thông số kỹ thuật sau:
- **Tập dữ liệu (Dataset):** Gồm 1117 ảnh quả táo thực tế tại băng tải, phân chia 80% học máy (893 ảnh) và 20% thi thử/kiểm thử (224 ảnh).
- **Phần cứng huấn luyện:** Google Colab GPU Nvidia Tesla T4 (15GB VRAM).
- **Cấu hình Huấn luyện:**
  - Kiến trúc: **YOLOv8n (Nano)** gọn nhẹ, tối ưu tốc độ chạy thực tế (Real-time).
  - Tham số: `epochs=150` (sử dụng Cosine Learning Rate decay), `batch=16`, `imgsz=640`.
  - Cơ chế tự dừng sớm: `patience=15` (Dừng khi sau 15 epoch không có cải thiện độ chính xác).
- **Kết quả huấn luyện:**
  - Huấn luyện tự động dừng sớm (Early Stopping) ở **Epoch thứ 90** (Mô hình tốt nhất đạt được ở **Epoch 75**).
  - Thời gian huấn luyện: **~31 phút** (0.515 giờ).
  - Độ chính xác mô hình thu được (Validation Metrics):
    - **Precision (Độ chính xác dự báo):** `99.9%`
    - **Recall (Tỉ lệ tìm kiếm đủ táo):** `99.6%`
    - **mAP50 (Chỉ số trùng khớp IoU >= 50%):** `99.5%`
    - **mAP50-95 (Độ chính xác định vị bbox tối ưu):** `93.9%`

*Ví dụ kết quả nhận diện thực tế của mô hình trên tập validation (độ tự tin đạt 95%):*

![Kết quả nhận diện YOLOv8](image/README/yolo_predict_test.png)

---

Tác giả: hoangnha999



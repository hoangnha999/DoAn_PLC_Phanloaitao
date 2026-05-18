# 🚀 BẢN THIẾT KẾ CHI TIẾT: NÂNG CẤP DỰ ÁN PHÂN LOẠI TÁO 3D SỬ DỤNG SENSOR FUSION & PLC S7-1200

Dưới đây là bản đề xuất thiết kế kỹ thuật chi tiết nhất, tối ưu hóa toàn bộ hệ thống từ **Phần cứng (Hardware)**, **Thuật toán (Algorithms)**, **Giao diện (GUI)** cho tới **Ý tưởng tích hợp & Điều khiển tự động** dựa trên việc tích hợp camera độ sâu **Orbbec Astra Pro** và các giải pháp thực tiễn từ dây chuyền phân loại táo công nghiệp hiện đại.

---

## 📁 CẤU TRÚC HỆ THỐNG KHUYÊN DÙNG (PROPOSED SYSTEM PIPELINE)

```mermaid
graph TD
    subgraph PHẦN CỨNG (HARDWARE)
        Conroller[PLC S7-1200] -->|Pulse/Modbus| Motor[Băng tải con lăn tự xoay]
        Astra[Camera Astra Pro] -->|Cảm biến màu RGB| DarkBox[Buồng tối cách ly]
        Astra -->|Cảm biến chiều sâu Depth| DarkBox
    end

    subgraph THUẬT TOÁN (ALGORITHMS - SENSOR FUSION)
        Stream[Đồng bộ luồng ảnh Align] --> DepthFilter[Tách nền 3D Depth Mask]
        DepthFilter --> SizeCalc[Đo đường kính thực & thể tích mm]
        DepthFilter --> SurfaceCalc[Phân tích pháp tuyến & vết lõm 3D]
        DepthFilter --> HSVCalc[Phân tích màu vỏ HSV & đốm thối]
        Consensus[Đồng thuận đa khung hình 10-Sample] --> Decisions{Phân loại hạt nhân}
        SizeCalc --> Consensus
        SurfaceCalc --> Consensus
        HSVCalc --> Consensus
    end

    subgraph GIAO DIỆN (GUI - TKINTER)
        Decisions --> UI_3D[Bản đồ độ sâu giả màu Pseudo-color]
        Decisions --> UI_Stats[Thống kê sản lượng & Tốc độ quả/phút]
        Decisions --> UI_Calib[Bảng hiệu chuẩn thông số vật lý]
    end

    subgraph ĐIỀU KHIỂN & CHẤP HÀNH (ACTUATORS)
        Decisions -->|Truyền thông DB10 snap7| Conroller
        Conroller -->|Độ trễ hành trình Tracker| Piston1[Xy lanh 1 - GOOD]
        Conroller -->|Độ trễ hành trình Tracker| Piston2[Xy lanh 2 - MEDIUM]
        Conroller -->|Độ trễ hành trình Tracker| Piston3[Xy lanh 3 - BAD]
    end
```

---

## 🛠️ PHẦN 1: THIẾT KẾ & CẢI TIẾN PHẦN CỨNG (HARDWARE DESIGN)

### 1.1. Chế tạo Buồng Tối Cách Ly Ánh Sáng (Controlled Light Box)
Để loại bỏ 100% hiện tượng sai lệch màu sắc do ánh sáng môi trường thay đổi (bóng mây che, bật/tắt đèn tuýp nhà xưởng), buồng tối cần được thiết kế:
*   **Vật liệu khung:** Tấm nhựa Formex đen (dày 5-8mm) hoặc Mica đen nhám để hấp thụ ánh sáng, triệt tiêu phản xạ.
*   **Kích thước:** Bao phủ chiều dài băng tải khoảng 40-50cm tại vùng camera quét.
*   **Hệ thống chiếu sáng:**
    *   Sử dụng dải **LED Strobe Light** (đèn LED chớp) màu trắng ấm (Warm White, CRI > 90) công suất cao. 
    *   Đèn được đặt góc nghiêng 45 độ từ hai bên sườn buồng chiếu xuống để triệt tiêu hiện tượng lóa sáng (glare/specular reflection) trên vỏ quả táo khi ướt hoặc bóng.

### 1.2. Cơ Cấu Băng Tải Con Lăn Tự Xoay Quả Táo (Pocket Roller Conveyor)
Để camera Astra Pro quét được 100% diện tích bề mặt (tránh góc khuất ở mặt dưới):
*   **Thiết kế con lăn:** Thay vì băng tải cao su phẳng, sử dụng chuỗi con lăn hình quả trám đôi (chén rãnh). Quả táo sẽ nằm gọn trong khe giữa hai con lăn.
*   **Nguyên lý xoay tự động:** Khi xích băng tải tịnh tiến, một cơ cấu thanh răng/đai ma sát phía dưới sẽ gạt vào trục con lăn, ép các con lăn tự xoay quanh trục của nó. Từ đó quả táo tự động xoay tròn đều khi đi qua buồng quét của camera.

### 1.3. Cơ Cấu Đẩy Xy Lanh Khí Nén Mềm (Soft Sorting Actuators)
*   **Tránh dập táo:** Sử dụng xy lanh khí nén tác động kép có gắn **đệm cao su bọt biển** ở đầu đẩy.
*   **Lực đẩy mềm:** Điều chỉnh áp suất khí nén qua van giảm áp (Regulator) ở mức vừa phải (2.5 - 3.5 bar), lực đẩy vừa đủ để gạt nhẹ quả táo lăn vào máng dốc mà không làm nứt quả.
*   **Máng trượt hứng táo:** Lót lớp mút xốp eva hoặc thảm cao su mềm để giảm chấn thương khi táo rơi tự do.

---

## 🧠 PHẦN 2: THUẬT TOÁN XỬ LÝ ẢNH CHUYÊN SÂU (ADVANCED ALGORITHMS)

Sử dụng thư viện **OpenNI2 / pyastra** để kết xuất luồng dữ liệu 3D đồng bộ với RGB.

### 2.1. Thuật Toán Hợp Nhất Cảm Biến (RGB-D Sensor Fusion Alignment)
Ống kính màu (RGB) và ống kính hồng ngoại (Depth IR) nằm cách nhau một khoảng vật lý nhỏ trên thân Astra Pro. Ta cần đồng bộ hóa tọa độ của chúng:
```python
# Giả mã đồng bộ hai luồng bằng Astra SDK / OpenCV
from openni import openni2
# Khởi tạo luồng màu và độ sâu
depth_stream.set_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
```
*   **Ý nghĩa:** Sau khi align, điểm ảnh màu tại tọa độ $(x, y)$ sẽ ánh xạ chính xác 1-1 với giá trị độ sâu $z$ tại $(x, y)$ đó.

### 2.2. Tách Nền Không Gian 3D (3D Depth Segmentation)
*   Mặt băng tải luôn cố định ở khoảng cách $Z_{conveyor}$ (VD: 550mm).
*   **Thuật toán tạo Mask:**
    $$\text{Mask}(x,y) = \begin{cases} 255 & \text{nếu } Z_{min} \le Z(x,y) \le Z_{max} \\ 0 & \text{ngược lại} \end{cases}$$
    Trong đó: $Z_{min} = 350\text{mm}$ (đỉnh quả táo), $Z_{max} = 520\text{mm}$ (khoảng cách sát mép băng tải để loại bỏ nền).
*   **Kết quả:** Mask 3D siêu sạch, không hề bị dính viền bóng hoặc màu của xích băng tải.

### 2.3. Thuật Toán Đo Kích Thước & Thể Tích Thực (True Size & Volume Calculation)
Quy đổi tọa độ điểm ảnh sang hệ tọa độ thế giới thực (World Coordinates) sử dụng tiêu cự của Camera Astra Pro ($f_x, f_y$):
*   Tọa độ thực:
    $$X_{world} = \frac{(x - c_x) \times Z}{f_x}, \quad Y_{world} = \frac{(y - c_y) \times Z}{f_y}$$
*   **Đo đường kính:** Lấy khoảng cách Euclide lớn nhất giữa hai điểm biên đối diện trên ảnh mask. Đơn vị đầu ra là **Milimet (mm)** thực tế.
*   **Ước lượng thể tích:** Coi quả táo là hình cầu khuyết, tích phân tổng thể tích bằng cách cộng dồn các lớp độ sâu của từng pixel:
    $$V = \sum_{pixel} (Z_{conveyor} - Z(x,y)) \times \text{Area}_{pixel}$$

### 2.4. Phát Hiện Vết Lõm / Dập 3D (3D Surface Defect & Dent Detection)
Quả táo bình thường có bề mặt cong đều trơn tru. Ta dùng thuật toán toán học để phát hiện vết lõm sâu:
*   **Thuật toán Surface Normal (Vector pháp tuyến):** Tính độ thay đổi pháp tuyến bề mặt tại mỗi điểm $N = \nabla Z(x,y)$.
*   **Phát hiện bất thường:** Tại vết lõm/vết dập dẹt, vector pháp tuyến $\vec{N}$ sẽ đột ngột thay đổi hướng một cách dị biệt so với hình cầu hoàn mỹ. 
*   Nếu tổng số pixel dị biệt vượt ngưỡng $\theta$, kết luận quả táo bị dập (BAD).

### 2.5. Chiến Lược Đồng Thuận Đa Khung Hình (Multi-frame Consensus Strategy)
Để tránh phán đoán sai do quả táo xoay chưa hết mặt:
*   Khi quả táo đi qua vùng quét, camera ghi lại liên tiếp **10 khung hình (10 samples)**.
*   Hệ thống chạy thuật toán phân tích trên cả 10 khung hình.
*   **Bầu chọn số đông (Majority Voting):** Quyết định cuối cùng được đưa ra dựa trên kết quả đồng thuận cao nhất của các khung hình, loại bỏ các khung hình lỗi do nhiễu hoặc chớp đèn.

---

## 🖥️ PHẦN 3: THIẾT KẾ GIAO DIỆN GIÁM SÁT CAO CẤP (ADVANCED GUI)

Giao diện Tkinter hiện tại cần nâng cấp các widget chuyên nghiệp:

### 3.1. Trực Quan Hóa Bản Đồ Nhiệt Độ Sâu (Pseudo-color Depth Visualization)
*   Chuyển luồng ảnh xám Depth (16-bit) sang ảnh 8-bit màu giả (Pseudo-color) bằng bản đồ màu **OpenCV Colormap (JET hoặc RAINBOW)**.
*   **Trực quan:** Trên giao diện, quả táo sẽ hiện lên sinh động với gam màu thay đổi từ Đỏ (gần camera nhất - đỉnh quả) sang Xanh dương (xa camera nhất - chân quả). Người dùng có thể nhìn thấy ngay các vùng lõm sâu có màu sắc bất thường.

### 3.2. Bảng Hiệu Chuẩn Hệ Thống (Calibration & Tuning Panel)
*   **Thanh trượt cấu hình:** Cho phép kéo thả trực quan để tinh chỉnh các thông số trực tiếp khi vận hành:
    *   Ngưỡng khoảng cách lọc vật thể: $Z_{min}$ và $Z_{max}$ (mm).
    *   Ngưỡng phân loại kích thước: Size Lớn (mm), Size Vừa (mm).
    *   Thời gian xung trễ của Xy lanh PLC (ms).
*   **Nút Lưu Cấu Hình:** Tự động ghi lại các cấu hình vào file JSON hoặc SQLite để áp dụng cho các lần khởi động sau.

### 3.3. Biểu Đồ Thống Kê Sản Lượng Động (Dynamic Real-time Charts)
*   Nhúng biểu đồ tròn (Pie Chart) hiển thị tỷ lệ táo đỏ/táo xanh, táo GOOD/MEDIUM/BAD.
*   Biểu đồ cột (Bar Chart) thống kê số lượng táo chạy qua theo từng giờ làm việc.
*   **Widget Thông lượng (Throughput Meter):** Hiển thị số lượng táo xử lý/phút (quả/phút) để giám sát hiệu suất hoạt động của nhà máy.

---

## 🔌 PHẦN 4: ĐỒNG BỘ ĐIỀU KHIỂN PLC S7-1200 & PHẦN MỀM

Việc đồng bộ hóa tốc độ băng tải vật lý và tốc độ xử lý phần mềm máy tính cực kỳ quan trọng để đảm bảo xy lanh gạt đúng quả táo.

### 4.1. Thuật Toán Bám Vết Vật Thể (Shift-Register/Delay Tracking Algorithm)
Từ khi camera chụp ảnh quả táo tại vị trí quét cho tới khi quả táo trôi đến vị trí của xy lanh số 1 (GOOD), số 2 (MEDIUM), số 3 (BAD) sẽ mất một khoảng thời gian trễ $T_{delay}$:
*   **Nếu băng tải chạy tốc độ cố định:**
    $$T_{delay} = \frac{L(\text{Khoảng cách từ Camera đến Xylanh})}{v(\text{Vận tốc băng tải})}$$
    Thời gian trễ này được cài đặt bằng hàm `Timer` hoặc `TON` trong chương trình PLC S7-1200.
*   **Nếu băng tải chạy tốc độ thay đổi (Dùng biến tần):**
    *   Gắn một **Encoder** đo tốc độ vào trục động cơ băng tải.
    *   Đọc số xung Encoder truyền về High-Speed Counter (HSC) của S7-1200.
    *   Python gửi kết quả phân loại (1, 2, 3) xuống DB10 kèm số xung cần dịch chuyển. PLC chỉ cần đếm đủ số xung dịch chuyển sẽ kích hoạt xy lanh tương ứng. Phương pháp này chính xác 100% bất kể băng tải chạy nhanh hay chậm.

---

## 📈 LỢI ÍCH KHI ĐỒ ÁN ĐƯỢC NÂNG CẤP THÀNH CÔNG

1.  **Độ Tin Cậy Cao:** Hệ thống không còn sợ nhiễu ánh sáng bên ngoài trường học, bảo vệ đồ án trước hội đồng thành công mỹ mãn.
2.  **Tính Học Thuật & Ứng Dụng Thực Tế Vượt Trội:** Việc áp dụng kết hợp **Depth Camera (3D) + PLC Snap7** là đề tài cực kỳ hiếm và rất được các thầy cô đánh giá cao vì nó tiệm cận trực tiếp với các dây chuyền phân loại lớn của thế giới.
3.  **Kỹ năng bổ sung cực lớn:** Nắm vững được các kỹ thuật cao cấp về đồng bộ camera, tính toán không gian 3D, truyền thông công nghiệp thời gian thực.

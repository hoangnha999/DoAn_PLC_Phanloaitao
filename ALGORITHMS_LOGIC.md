# TỔNG HỢP THUẬT TOÁN & LOGIC XỬ LÝ (APPLE GRADING SYSTEM)

Tài liệu này tổng hợp toàn bộ các thuật toán và logic xử lý hình ảnh được áp dụng trong hệ thống phân loại táo thông minh, dựa trên các nghiên cứu khoa học mới nhất từ tạp chí MDPI (2021-2025).

---

## 1. Hệ thống Phân loại 3 Tiêu chí (Grading Criteria)
Hệ thống đánh giá chất lượng quả táo dựa trên 3 trụ cột chính:
- **TC1: Độ chín (Ripeness):** Tính toán dựa trên % diện tích màu đỏ trên bề mặt.
- **TC2: Kích thước (Size):** Đo đường kính thực tế (mm) bằng xử lý ảnh kết hợp cảm biến chiều sâu (Depth).
- **TC3: Hình dáng (Shape):** Đánh giá độ tròn (Circularity) để loại bỏ các quả bị méo, dị dạng.

---

## 2. Các Thuật toán Tiên tiến đã áp dụng

### 2.1. Xử lý Đa góc nhìn (Multi-Dimensional View Processing)
*   **Nguồn gốc:** Học hỏi từ bài báo *Foods 2023, 12, 2117*.
*   **Logic:** Vì táo lăn trên băng chuyền, camera sẽ chụp được nhiều góc độ. Hệ thống sử dụng bộ nhớ đệm (History Buffer) để lưu trữ 10 khung hình liên tiếp.
    *   **Màu sắc:** Lấy **Trung bình** của 10 khung hình để có cái nhìn tổng thể về độ đỏ của toàn bộ bề mặt.
    *   **Vết thâm:** Lấy **Giá trị lớn nhất (MAX)**. Chỉ cần một góc quay lộ ra vết thâm, hệ thống sẽ ghi nhớ và đánh BAD ngay lập tức.

### 2.2. Ánh xạ Bề mặt Cầu 3D (Spherical Surface Mapping)
*   **Nguồn gốc:** Học hỏi từ bài báo *Foods 2022, 11, 3150*.
*   **Logic:** Giải quyết vấn đề "vết thâm ở rìa quả táo trông nhỏ hơn thực tế".
*   **Cách thức:** Sử dụng công thức toán học tính khoảng cách từ tâm quả táo đến điểm thâm. Các pixel ở rìa sẽ được nhân hệ số trọng số (Weight) từ **1.0 đến 3.0** để bù đắp diện tích bị khuất do độ cong của hình cầu.

### 2.3. Thuật toán Tổng hợp (Consensus Master Algorithm)
*   Sử dụng sự kết hợp của:
    *   **HSV Color Masking:** Lọc dải màu đỏ, vàng, xanh.
    *   **Morphological Filtering:** Sử dụng phép đóng (Close) và mở (Open) để loại bỏ nhiễu và sever (cắt bỏ) cuống táo khỏi viền.
    *   **Depth Filtering:** Sử dụng dữ liệu từ camera Astra Pro để tách biệt hoàn toàn quả táo khỏi nền (Background Subtraction) trong không gian 3D.

### 2.4. Cơ chế Auto-Reset & Temporal Smoothing
*   **Temporal Smoothing:** Làm mượt dao động của vòng tròn bao quanh táo để tránh hiện tượng nhảy kết quả loạn xạ.
*   **Auto-Reset:** Tự động xóa bộ nhớ đệm nếu phát hiện tọa độ tâm táo nhảy đột ngột (>100px). Điều này cho phép hệ thống hoạt động chính xác cả khi test bằng ảnh tĩnh lẫn video/camera thời gian thực.

---

## 3. Tài liệu Tham khảo (Scientific References)
Hệ thống được phát triển dựa trên các nghiên cứu sau:
1.  **MDPI Foods (2025):** *Innovative Apple Grading Technology Driven by Intelligent Vision and Machine Learning* (Volume 14, Issue 2).
2.  **MDPI Foods (2023):** *Apple Grading Based on Multi-Dimensional View Processing and Deep Learning* (Volume 12, Issue 11).
3.  **MDPI Foods (2022):** *Real-Time Grading of Defect Apples Using Semantic Segmentation & Pruned YOLO V4* (Volume 11, Issue 19).
4.  **Horticulturae (2021):** *Infield Apple Detection and Grading Based on Multi-Feature Fusion* (Volume 7, Issue 9).

---
*Tài liệu được tổng hợp bởi AI Assistant (Antigravity) phục vụ cho Đồ án Tốt nghiệp - Hệ thống Phân loại Táo PLC.*

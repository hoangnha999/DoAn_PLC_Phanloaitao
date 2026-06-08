import os
import sys
import shutil
import random
import cv2
import numpy as np

# Cấu hình UTF-8 cho console để tránh lỗi UnicodeEncodeError trên Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Thêm cả project root và 'giaodien' vào sys.path để import ổn định
# sau khi tách Processing ra thư mục gốc.
project_root = os.path.abspath('.')
giaodien_dir = os.path.join(project_root, 'giaodien')
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if giaodien_dir not in sys.path:
    sys.path.insert(0, giaodien_dir)

try:
    from Processing.analyzer import FruitAnalyzer
    print("[SUCCESS] Đã import thành công FruitAnalyzer từ Processing/analyzer.py")
except ImportError as e:
    print(f"[ERROR] Không thể import FruitAnalyzer: {e}")
    sys.exit(1)

def auto_label_and_split():
    # Cấu hình đường dẫn
    src_img_dir = os.path.join('dataset', 'train', 'images')
    dest_dataset_dir = os.path.join('dataset', 'yolo_dataset')
    
    # Tạo các thư mục đích cho YOLO
    for split in ['train', 'val']:
        os.makedirs(os.path.join(dest_dataset_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(dest_dataset_dir, 'labels', split), exist_ok=True)
        
    if not os.path.exists(src_img_dir):
        print(f"[ERROR] Thư mục chứa ảnh gốc không tồn tại: {src_img_dir}")
        return

    # Lấy danh sách ảnh
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    all_images = [f for f in os.listdir(src_img_dir) if f.lower().endswith(image_extensions)]
    total_images = len(all_images)
    
    if total_images == 0:
        print(f"[WARNING] Không tìm thấy ảnh nào trong thư mục: {src_img_dir}")
        return
        
    print(f"Tìm thấy {total_images} ảnh gốc. Bắt đầu xử lý...")

    # Khởi tạo bộ phân tích truyền thống để lấy thuật toán phân đoạn
    analyzer = FruitAnalyzer()
    
    # Trộn ngẫu nhiên danh sách để chia train/val
    random.seed(42)
    random.shuffle(all_images)
    
    # Chia tỉ lệ 80% train, 20% val
    split_idx = int(total_images * 0.8)
    train_images = all_images[:split_idx]
    val_images = all_images[split_idx:]
    
    splits = {
        'train': train_images,
        'val': val_images
    }
    
    success_count = 0
    skipped_count = 0

    for split_name, img_list in splits.items():
        print(f"\n--- Đang xử lý tập dữ liệu: {split_name.upper()} ({len(img_list)} ảnh) ---")
        
        for idx, img_name in enumerate(img_list):
            src_img_path = os.path.join(src_img_dir, img_name)
            
            # Đọc ảnh
            img = cv2.imread(src_img_path)
            if img is None:
                print(f"[WARNING] Không thể đọc ảnh: {src_img_path}")
                continue
                
            h, w = img.shape[:2]
            
            # Sử dụng thuật toán _segment_apple để tách nền quả táo
            # Mặc định là không có depth_frame cho ảnh tĩnh
            apple_mask, hull = analyzer._segment_apple(img, depth_frame=None)
            
            # Xác định đường dẫn lưu ảnh mới
            dest_img_path = os.path.join(dest_dataset_dir, 'images', split_name, img_name)
            shutil.copy(src_img_path, dest_img_path)
            
            # Xác định tên file nhãn (.txt)
            base_name, _ = os.path.splitext(img_name)
            label_file_path = os.path.join(dest_dataset_dir, 'labels', split_name, f"{base_name}.txt")
            
            # Nếu nhận diện được quả táo bằng OpenCV
            if hull is not None and len(hull) > 0:
                # Lấy bounding box (x, y, w, h)
                bx, by, bw, bh = cv2.boundingRect(hull)
                
                # Chuyển đổi sang định dạng YOLO normalized (center_x, center_y, width, height)
                x_center = (bx + bw / 2.0) / w
                y_center = (by + bh / 2.0) / h
                x_width = bw / w
                y_height = bh / h
                
                # Class 0 đại diện cho 'apple' (quả táo)
                class_id = 0
                
                # Ghi vào file label dạng YOLO: class_id center_x center_y width height
                with open(label_file_path, 'w', encoding='utf-8') as lf:
                    lf.write(f"{class_id} {x_center:.6f} {y_center:.6f} {x_width:.6f} {y_height:.6f}\n")
                
                success_count += 1
            else:
                # Nếu không nhận diện được quả táo (ảnh nền hoặc không phát hiện bằng HSV)
                # Ta tạo file label rỗng (YOLO coi đây là background image để giảm false positive)
                open(label_file_path, 'w').close()
                skipped_count += 1
                
            if (idx + 1) % 50 == 0 or (idx + 1) == len(img_list):
                print(f" Đã xử lý {idx + 1}/{len(img_list)} ảnh...")

    print(f"\n[HOÀN THÀNH] Đã xử lý tổng cộng {total_images} ảnh:")
    print(f" - Thành công (tạo nhãn táo): {success_count} ảnh")
    print(f" - Bỏ qua/Tạo nhãn rỗng (background): {skipped_count} ảnh")
    print(f" - Dữ liệu YOLO được lưu tại: {os.path.abspath(dest_dataset_dir)}")
    
    # Tạo file dataset.yaml cho YOLOv8
    yaml_path = os.path.join(dest_dataset_dir, 'dataset.yaml')
    yaml_content = f"""path: {os.path.abspath(dest_dataset_dir)} # Đường dẫn tuyệt đối tới dataset
train: images/train
val: images/val

names:
  0: apple
"""
    with open(yaml_path, 'w', encoding='utf-8') as yf:
        yf.write(yaml_content)
    print(f" - Đã tạo file cấu hình YOLO: {os.path.abspath(yaml_path)}")

if __name__ == '__main__':
    auto_label_and_split()

import os
import sys
import shutil
import random
import argparse
import re
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

def _extract_image_index(file_name):
    """Tách số thứ tự từ tên file, ví dụ app_(123).jpg -> 123."""
    base_name, _ = os.path.splitext(file_name)
    match = re.search(r'(\d+)', base_name)
    if not match:
        return None
    return int(match.group(1))


def _resolve_source_image_dir(src_img_dir):
    """Tự động dò thư mục chứa ảnh khi người dùng truyền thư mục gốc dataset."""
    candidate_dirs = [
        src_img_dir,
        os.path.join(src_img_dir, 'train'),
        os.path.join(src_img_dir, 'images'),
        os.path.join(src_img_dir, 'images', 'train'),
    ]
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')

    for candidate in candidate_dirs:
        if not os.path.isdir(candidate):
            continue
        has_images = any(
            f.lower().endswith(image_extensions)
            for f in os.listdir(candidate)
            if os.path.isfile(os.path.join(candidate, f))
        )
        if has_images:
            return candidate

    return src_img_dir


def auto_label_and_split(
    src_img_dir,
    dest_dataset_dir,
    fresh_count,
    rotten_count,
    train_ratio=0.8,
    rotten_start=1116,
    rotten_end=2223,
    allow_overwrite_existing_labels=False,
):
    # Bảo vệ dữ liệu đã gán nhãn sẵn: mặc định không ghi đè dataset có label tồn tại.
    existing_labels_root = os.path.join(dest_dataset_dir, 'labels')
    if not allow_overwrite_existing_labels and os.path.isdir(existing_labels_root):
        existing_label_files = [
            f for f in os.listdir(existing_labels_root)
            if os.path.isfile(os.path.join(existing_labels_root, f)) and f.lower().endswith('.txt')
        ]
        train_labels_dir = os.path.join(existing_labels_root, 'train')
        val_labels_dir = os.path.join(existing_labels_root, 'val')
        for split_dir in [train_labels_dir, val_labels_dir]:
            if os.path.isdir(split_dir):
                existing_label_files.extend([
                    f for f in os.listdir(split_dir)
                    if os.path.isfile(os.path.join(split_dir, f)) and f.lower().endswith('.txt')
                ])

        if len(existing_label_files) > 0:
            print(
                f"[ERROR] Phát hiện dataset đã có nhãn ở: {os.path.abspath(dest_dataset_dir)}. "
                "Dừng để tránh ghi đè. Hãy đổi --dest-dataset-dir hoặc thêm --allow-overwrite-existing-labels."
            )
            return

    # Tạo các thư mục đích cho YOLO
    for split in ['train', 'val']:
        os.makedirs(os.path.join(dest_dataset_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(dest_dataset_dir, 'labels', split), exist_ok=True)
        
    if not os.path.exists(src_img_dir):
        print(f"[ERROR] Thư mục chứa ảnh gốc không tồn tại: {src_img_dir}")
        return

    # Cho phép truyền thư mục gốc dataset_apple, script sẽ tự tìm thư mục con có ảnh.
    resolved_src_img_dir = _resolve_source_image_dir(src_img_dir)
    if os.path.abspath(resolved_src_img_dir) != os.path.abspath(src_img_dir):
        print(f"[INFO] Tự động dùng thư mục ảnh: {resolved_src_img_dir}")

    # Lấy danh sách ảnh
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
    all_images = [f for f in os.listdir(resolved_src_img_dir) if f.lower().endswith(image_extensions)]
    total_images = len(all_images)
    
    if total_images == 0:
        print(f"[WARNING] Không tìm thấy ảnh nào trong thư mục: {src_img_dir}")
        return
        
    print(f"Tìm thấy {total_images} ảnh gốc. Bắt đầu xử lý...")

    # Khởi tạo bộ phân tích truyền thống để lấy thuật toán phân đoạn
    analyzer = FruitAnalyzer()
    
    # Sắp xếp theo tên để quá trình split train/val ổn định trước khi shuffle.
    all_images.sort()

    # Gán class theo số thứ tự trong tên file:
    # rotten_start <= index <= rotten_end => rotten_apple (class 1), ngược lại fresh_apple (class 0)
    class_map_by_name = {}
    parse_failed_count = 0
    for img_name in all_images:
        image_index = _extract_image_index(img_name)
        if image_index is None:
            class_map_by_name[img_name] = 0
            parse_failed_count += 1
            continue

        class_map_by_name[img_name] = 1 if rotten_start <= image_index <= rotten_end else 0

    # Trộn ngẫu nhiên danh sách để chia train/val
    random.seed(42)
    random.shuffle(all_images)
    
    # Chia tỉ lệ train/val
    split_idx = int(total_images * train_ratio)
    train_images = all_images[:split_idx]
    val_images = all_images[split_idx:]
    
    splits = {
        'train': train_images,
        'val': val_images
    }
    
    success_count = 0
    skipped_count = 0
    fresh_labeled_count = 0
    rotten_labeled_count = 0

    for split_name, img_list in splits.items():
        print(f"\n--- Đang xử lý tập dữ liệu: {split_name.upper()} ({len(img_list)} ảnh) ---")
        
        for idx, img_name in enumerate(img_list):
            src_img_path = os.path.join(resolved_src_img_dir, img_name)
            
            # Đọc ảnh
            img = cv2.imread(src_img_path)
            if img is None:
                print(f"[WARNING] Không thể đọc ảnh: {src_img_path}")
                continue
                
            h, w = img.shape[:2]
            
            # Sử dụng thuật toán _segment_apple để tách nền quả táo
            # Mặc định là không có depth_frame cho ảnh tĩnh
            apple_mask, hull, yolo_info = analyzer._segment_apple(img)
            
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
                
                # Class 0: fresh_apple, Class 1: rotten_apple
                class_id = class_map_by_name[img_name]
                
                # Ghi vào file label dạng YOLO: class_id center_x center_y width height
                with open(label_file_path, 'w', encoding='utf-8') as lf:
                    lf.write(f"{class_id} {x_center:.6f} {y_center:.6f} {x_width:.6f} {y_height:.6f}\n")
                
                success_count += 1
                if class_id == 0:
                    fresh_labeled_count += 1
                else:
                    rotten_labeled_count += 1
            else:
                # Nếu không nhận diện được quả táo (ảnh nền hoặc không phát hiện bằng HSV)
                # Ta tạo file label rỗng (YOLO coi đây là background image để giảm false positive)
                open(label_file_path, 'w').close()
                skipped_count += 1
                
            if (idx + 1) % 50 == 0 or (idx + 1) == len(img_list):
                print(f" Đã xử lý {idx + 1}/{len(img_list)} ảnh...")

    print(f"\n[HOÀN THÀNH] Đã xử lý tổng cộng {total_images} ảnh:")
    print(f" - Thành công (tạo nhãn táo): {success_count} ảnh")
    print(f"   + fresh_apple: {fresh_labeled_count} ảnh")
    print(f"   + rotten_apple: {rotten_labeled_count} ảnh")
    if parse_failed_count > 0:
        print(
            f" - Cảnh báo: {parse_failed_count} ảnh không tách được số thứ tự từ tên file, mặc định gán fresh_apple."
        )
    print(f" - Bỏ qua/Tạo nhãn rỗng (background): {skipped_count} ảnh")
    print(f" - Dữ liệu YOLO được lưu tại: {os.path.abspath(dest_dataset_dir)}")
    
    # Tạo file dataset.yaml cho YOLOv8
    yaml_path = os.path.join(dest_dataset_dir, 'dataset.yaml')
    yaml_content = f"""path: {os.path.abspath(dest_dataset_dir)} # Đường dẫn tuyệt đối tới dataset
train: images/train
val: images/val

names:
  0: fresh_apple
  1: rotten_apple
"""
    with open(yaml_path, 'w', encoding='utf-8') as yf:
        yf.write(yaml_content)
    print(f" - Đã tạo file cấu hình YOLO: {os.path.abspath(yaml_path)}")


def parse_args():
    parser = argparse.ArgumentParser(
        description='Auto label dataset táo thành YOLOv8 với 2 class fresh/rotten.'
    )
    parser.add_argument(
        '--src-img-dir',
        default=os.path.join('dataset', 'dataset_apple'),
        help='Thư mục ảnh nguồn.',
    )
    parser.add_argument(
        '--dest-dataset-dir',
        default=os.path.join('dataset', 'dataset_apple', 'yolo_dataset_index_1116_2223'),
        help='Thư mục đầu ra YOLO dataset.',
    )
    parser.add_argument(
        '--fresh-count',
        type=int,
        default=2000,
        help='Số ảnh đầu tiên (sau khi sort tên) thuộc class fresh_apple.',
    )
    parser.add_argument(
        '--rotten-count',
        type=int,
        default=1000,
        help='Số ảnh còn lại thuộc class rotten_apple.',
    )
    parser.add_argument(
        '--train-ratio',
        type=float,
        default=0.8,
        help='Tỉ lệ train (0.0 - 1.0). Mặc định 0.8.',
    )
    parser.add_argument(
        '--rotten-start',
        type=int,
        default=1116,
        help='Chỉ số ảnh bắt đầu thuộc rotten_apple (bao gồm).',
    )
    parser.add_argument(
        '--rotten-end',
        type=int,
        default=2223,
        help='Chỉ số ảnh kết thúc thuộc rotten_apple (bao gồm).',
    )
    parser.add_argument(
        '--allow-overwrite-existing-labels',
        action='store_true',
        help='Cho phép ghi đè dataset đích nếu đã có file nhãn. Mặc định: không ghi đè.',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if not (0.0 < args.train_ratio < 1.0):
        print('[ERROR] train_ratio phải nằm trong khoảng (0.0, 1.0).')
        sys.exit(1)
    if args.rotten_start > args.rotten_end:
        print('[ERROR] rotten_start phải <= rotten_end.')
        sys.exit(1)

    auto_label_and_split(
        src_img_dir=args.src_img_dir,
        dest_dataset_dir=args.dest_dataset_dir,
        fresh_count=args.fresh_count,
        rotten_count=args.rotten_count,
        train_ratio=args.train_ratio,
        rotten_start=args.rotten_start,
        rotten_end=args.rotten_end,
        allow_overwrite_existing_labels=args.allow_overwrite_existing_labels,
    )

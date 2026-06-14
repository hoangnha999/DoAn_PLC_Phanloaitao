import os
import random
import shutil
import sys

# Đổi encoding để console không bị lỗi với tiếng Việt
sys.stdout.reconfigure(encoding='utf-8')

# ================= CẤU HÌNH =================
IMAGE_DIR = r"D:\DOAN_PLC_Phanloaitao\dataset\dataset_apple\Image"
LABEL_DIR = r"D:\DOAN_PLC_Phanloaitao\dataset\dataset_apple\Label"
OUTPUT_DIR = r"D:\DOAN_PLC_Phanloaitao\yolo_dataset"
SPLIT_RATIO = 0.8  # 80% train, 20% val
# ============================================

def main():
    if not os.path.exists(IMAGE_DIR) or not os.path.exists(LABEL_DIR):
        print(f"[LỖI] Không tìm thấy thư mục Image hoặc Label")
        return

    print("[INFO] BẮT ĐẦU CHIA DATASET (80/20)...")

    # 1. Tạo cấu trúc thư mục chuẩn YOLO
    train_images_dir = os.path.join(OUTPUT_DIR, 'images', 'train')
    val_images_dir = os.path.join(OUTPUT_DIR, 'images', 'val')
    train_labels_dir = os.path.join(OUTPUT_DIR, 'labels', 'train')
    val_labels_dir = os.path.join(OUTPUT_DIR, 'labels', 'val')

    for d in [train_images_dir, val_images_dir, train_labels_dir, val_labels_dir]:
        os.makedirs(d, exist_ok=True)
        print(f"[OK] Đã tạo/kiểm tra thư mục: {d}")

    # 2. Quét danh sách file
    valid_extensions = ('.jpg', '.jpeg', '.png')
    all_images = os.listdir(IMAGE_DIR)
    all_labels = os.listdir(LABEL_DIR)
    
    images = [f for f in all_images if f.lower().endswith(valid_extensions)]
    
    # 3. Ghép cặp ảnh và nhãn
    valid_pairs = []
    for img in images:
        base_name = os.path.splitext(img)[0]
        txt_file = base_name + '.txt'
        if txt_file in all_labels:
            valid_pairs.append((img, txt_file))

    print(f"\n[OK] Tìm thấy {len(valid_pairs)} cặp (Ảnh + Nhãn) hợp lệ trên tổng số {len(images)} ảnh.")
    
    if len(valid_pairs) == 0:
        print("[LỖI] Không có dữ liệu để chia. Vui lòng kiểm tra lại đường dẫn.")
        return

    # 4. Xáo trộn danh sách ngẫu nhiên
    random.seed(42)
    random.shuffle(valid_pairs)

    # 5. Cắt danh sách theo tỉ lệ
    train_size = int(len(valid_pairs) * SPLIT_RATIO)
    train_pairs = valid_pairs[:train_size]
    val_pairs = valid_pairs[train_size:]

    print(f"\n[INFO] Sẽ chia thành:\n  - Train: {len(train_pairs)} file\n  - Val:   {len(val_pairs)} file")

    # Hàm copy file
    def copy_files(pairs, dest_img_dir, dest_lbl_dir):
        count = 0
        for img, txt in pairs:
            shutil.copy(os.path.join(IMAGE_DIR, img), os.path.join(dest_img_dir, img))
            shutil.copy(os.path.join(LABEL_DIR, txt), os.path.join(dest_lbl_dir, txt))
            count += 1
            if count % 100 == 0:
                print(f"  ... đã copy {count} file")

    # 6. Thực hiện copy
    print("\n[INFO] Đang copy dữ liệu vào tập Train...")
    copy_files(train_pairs, train_images_dir, train_labels_dir)

    print("[INFO] Đang copy dữ liệu vào tập Val...")
    copy_files(val_pairs, val_images_dir, val_labels_dir)

    # 7. Tạo file dataset.yaml chuẩn
    yaml_content = f"""path: /content/drive/MyDrive/yolo_dataset
train: images/train
val: images/val

names:
  0: apple
"""

    yaml_path = os.path.join(OUTPUT_DIR, 'dataset.yaml')
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    print(f"\n[OK] Đã tạo file cấu hình chuẩn tại: {yaml_path}")
    print("\n[HOÀN TẤT] Dữ liệu của bạn đã sẵn sàng.")
    print(f"--> Thư mục kết quả nằm ở: {OUTPUT_DIR}")
    print("--> Hãy upload cả thư mục 'yolo_dataset' này lên Drive nhé!")

if __name__ == "__main__":
    main()

import os
import sys

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


def _find_project_root():
    """Tìm thư mục gốc của project (DOAN_PLC_Phanloaitao) một cách chắc chắn."""
    # Cách 1: Từ vị trí file hiện tại (analyzer_modules -> Processing -> project root)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    root_from_file = os.path.normpath(os.path.join(this_dir, "..", ".."))

    # Cách 2: Đường dẫn tuyệt đối cố định (backup)
    hardcoded_root = r"D:\DOAN_PLC_Phanloaitao"

    # Ưu tiên cách 1, fallback sang cách 2
    if os.path.isdir(os.path.join(root_from_file, "giaodien")):
        return root_from_file
    if os.path.isdir(os.path.join(hardcoded_root, "giaodien")):
        return hardcoded_root
    return root_from_file


def initialize_yolo_runtime(analyzer):
    """Khởi tạo trạng thái YOLO, tìm model và load nếu khả dụng."""
    analyzer.yolo_model = None
    analyzer.yolo_model_path = None
    analyzer.use_yolo = False
    analyzer.yolo_status = "OFF"
    analyzer.yolo_reason = "not initialized"

    if YOLO_AVAILABLE:
        env_model = os.getenv("APPLE_YOLO_MODEL", "").strip()
        project_root = _find_project_root()
        this_dir = os.path.dirname(os.path.abspath(__file__))

        potential_paths = [
            # --- Đường dẫn chính xác nhất (ưu tiên cao nhất) ---
            os.path.join(project_root, "giaodien", "best.pt"),
            # Đường dẫn tuyệt đối cố định (backup chắc chắn)
            r"D:\DOAN_PLC_Phanloaitao\giaodien\best.pt",
            # --- Đường dẫn tương đối từ file hiện tại ---
            os.path.join(this_dir, "..", "best.pt"),
            os.path.join(this_dir, "..", "..", "giaodien", "best.pt"),
            # --- Đường dẫn training runs ---
            os.path.join(project_root, "runs", "detect", "apple_yolo26", "weights", "best.pt"),
            os.path.join(project_root, "runs", "detect", "apple_yolov8", "weights", "best.pt"),
            # --- Đường dẫn relative từ CWD (fallback) ---
            "best.pt",
            "giaodien/best.pt",
        ]
        if env_model:
            potential_paths.insert(0, env_model)

        # Loại bỏ trùng lặp nhưng giữ thứ tự
        seen = set()
        unique_paths = []
        for p in potential_paths:
            norm = os.path.normpath(os.path.abspath(p))
            if norm not in seen:
                seen.add(norm)
                unique_paths.append(p)

        print(f"[ANALYZER] Project root: {project_root}")
        print(f"[ANALYZER] Tim kiem model trong {len(unique_paths)} duong dan...")

        checked_paths = []
        for path in unique_paths:
            abs_path = os.path.normpath(os.path.abspath(path))
            checked_paths.append(abs_path)
            exists = os.path.isfile(abs_path)
            print(f"[ANALYZER]   {'[V]' if exists else '[X]'} {abs_path}")
            if exists:
                try:
                    analyzer.yolo_model = YOLO(abs_path)
                    analyzer.yolo_model_path = abs_path
                    analyzer.use_yolo = True
                    analyzer.yolo_status = "ON"
                    analyzer.yolo_reason = f"loaded: {abs_path}"
                    print(f"[ANALYZER] >>> Da tai thanh cong mo hinh YOLO tu: {abs_path}")
                    break
                except Exception as e:
                    analyzer.yolo_status = "OFF"
                    analyzer.yolo_reason = f"load error: {e}"
                    print(f"[ANALYZER] !!! Loi khi load model tai {abs_path}: {e}")

        if not analyzer.use_yolo:
            if analyzer.yolo_reason == "not initialized":
                analyzer.yolo_reason = f"no model file found (checked {len(checked_paths)} paths)"
            print(
                "[ANALYZER] YOLO available nhung chua thay model train. "
                f"Da kiem tra {len(checked_paths)} duong dan."
            )
            for cp in checked_paths:
                print(f"[ANALYZER]   - {cp}")
            print("[ANALYZER] Dat APPLE_YOLO_MODEL hoac de file giaodien/best.pt")
    else:
        analyzer.yolo_status = "OFF"
        analyzer.yolo_reason = "ultralytics not installed"
        print("[ANALYZER] Thu vien 'ultralytics' chua cai dat. Chay o che do OpenCV HSV truyen thong.")


def run_yolo_inference(analyzer, frame):
    """Chạy YOLO theo mode track/predict với cơ chế fallback an toàn."""
    if analyzer.yolo_model is None:
        raise RuntimeError("YOLO model is not initialized")

    if analyzer.YOLO_ENABLE_TRACKING:
        try:
            tracked = analyzer.yolo_model.track(
                frame,
                conf=analyzer.YOLO_PREDICT_CONF,
                verbose=False,
                persist=analyzer.YOLO_TRACK_PERSIST,
                tracker=analyzer.YOLO_TRACKER_NAME,
            )[0]
            return tracked, "track", ""
        except Exception as e:
            try:
                predicted = analyzer.yolo_model.predict(frame, conf=analyzer.YOLO_PREDICT_CONF, verbose=False)[0]
                return predicted, "predict_fallback", str(e)
            except Exception:
                raise

    predicted = analyzer.yolo_model.predict(frame, conf=analyzer.YOLO_PREDICT_CONF, verbose=False)[0]
    return predicted, "predict", ""

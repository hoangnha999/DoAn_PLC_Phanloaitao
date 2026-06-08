import os

try:
    from ultralytics import YOLO

    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


def initialize_yolo_runtime(analyzer):
    """Khởi tạo trạng thái YOLO, tìm model và load nếu khả dụng."""
    analyzer.yolo_model = None
    analyzer.yolo_model_path = None
    analyzer.use_yolo = False
    analyzer.yolo_status = "OFF"
    analyzer.yolo_reason = "not initialized"

    if YOLO_AVAILABLE:
        env_model = os.getenv("APPLE_YOLO_MODEL", "").strip()
        potential_paths = [
            os.path.join(os.path.dirname(__file__), "..", "best.pt"),
            os.path.join(os.path.dirname(__file__), "..", "..", "giaodien", "best.pt"),
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "runs",
                "detect",
                "apple_yolo26",
                "weights",
                "best.pt",
            ),
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "runs",
                "detect",
                "apple_yolov8",
                "weights",
                "best.pt",
            ),
            "runs/detect/apple_yolo26/weights/best.pt",
            "runs/detect/apple_yolov8/weights/best.pt",
            "best.pt",
            "giaodien/best.pt",
        ]
        if env_model:
            potential_paths.insert(0, env_model)

        checked_paths = []
        for path in potential_paths:
            abs_path = os.path.abspath(path)
            checked_paths.append(abs_path)
            if os.path.isfile(abs_path):
                try:
                    analyzer.yolo_model = YOLO(abs_path)
                    analyzer.yolo_model_path = abs_path
                    analyzer.use_yolo = True
                    analyzer.yolo_status = "ON"
                    analyzer.yolo_reason = f"loaded: {abs_path}"
                    print(f"[ANALYZER] Da tai thanh cong mo hinh YOLO tu: {abs_path}")
                    break
                except Exception as e:
                    analyzer.yolo_status = "OFF"
                    analyzer.yolo_reason = f"load error: {e}"
                    print(f"[ANALYZER] Warning: Loi khi load model tai {abs_path}: {e}")

        if not analyzer.use_yolo:
            if analyzer.yolo_reason == "not initialized":
                analyzer.yolo_reason = f"no model file found (checked {len(checked_paths)} paths)"
            print(
                "[ANALYZER] YOLO available nhung chua thay model train. "
                "Dat APPLE_YOLO_MODEL hoac de file giaodien/best.pt"
            )
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

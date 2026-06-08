import json
import os
import tempfile
from copy import deepcopy

DEFAULT_CONFIG = {
    "analyzer": {
        "ripeness": {
            "good_thresh": 85,
            "medium_thresh": 70
        },
        "shape": {
            "good_thresh": 0.88,
            "medium_thresh": 0.78
        },
        "size": {
            "large_mm": 80,
            "medium_mm": 60,
            "pixel_to_mm": 0.28,
            "depth_reference_mm": 600.0,
            "enable_depth_size_compensation": True,
            "size_calibration_gain": 2.8
        },
        "hsv": {
            "red1_lower": [0, 65, 40],
            "red1_upper": [15, 255, 255],
            "red2_lower": [160, 65, 40],
            "red2_upper": [180, 255, 255],
            "yellow_lower": [17, 75, 40],
            "yellow_upper": [32, 255, 255],
            "green_lower": [35, 40, 30],
            "green_upper": [90, 255, 255]
        },
        "segmentation": {
            "min_apple_area_ratio": 0.012,
            "defect_dark_thresh": 35,
            "defect_bad_ratio": 20.0,
            "defect_medium_ratio": 10.0,
            "roi_width_ratio": 0.4,
            "roi_height_ratio": 0.6
        },
        "yolo": {
            "conf_thresh": 0.35,
            "predict_conf": 0.05,
            "min_bbox_area_ratio": 0.007,
            "enable_tracking": True,
            "tracker_name": "bytetrack.yaml",
            "track_persist": True
        },
        "blur": {
            "threshold": 100.0,
            "auto_sharpen": True,
            "sharpen_strength": 1.5
        }
    },
    "runtime": {
        "default_camera_mode": "Astra Pro SDK (RGB)",
        "astra_rgb_port_mode": "Tự động (ưu tiên USB: cổng 1 -> 2 -> 0)",
        "require_depth_for_astra": False,
        "capture_frames_required": 10,
        "capture_wait_timeout_s": 6.0,
        "decision_min_quality_score": 0.45,
        "decision_margin_delta": 0.10,
        "decision_min_valid_frames": 6,
        "single_fruit_station_mode": True,
        "track_min_frames": 3,
        "track_stability_min": 0.60,
        "analysis_interval_ms": 100,
        "plc_poll_ms": 200,
        "plc_fault_threshold": 3,
        "vision_fault_threshold": 3,
        "plc_ip": "192.168.0.1",
        "plc_rack": 0,
        "plc_slot": 1,
        "smooth_frames": 10,
        "orchard": "NHA_VUON_A",
        "lot": "",
        "decision_rule_table": {
            "score_grade1": 3,
            "score_grade2": 2,
            "score_grade3": 1,
            "min_grade1": 8,
            "min_grade2": 5
        }
    }
}


def _deep_merge(base, override):
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override

    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _config_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "system_config.json")


def load_runtime_config():
    path = _config_path()
    cfg = deepcopy(DEFAULT_CONFIG)
    if not os.path.isfile(path):
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        return _deep_merge(cfg, user_cfg)
    except Exception as e:
        print(f"[CONFIG] Warning: cannot read config at {path}: {e}")
        return cfg


def save_runtime_config(partial_cfg):
    path = _config_path()
    current_cfg = load_runtime_config()
    merged_cfg = _deep_merge(current_cfg, partial_cfg or {})

    try:
        cfg_dir = os.path.dirname(path)
        os.makedirs(cfg_dir, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix="system_config_", suffix=".json.tmp", dir=cfg_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(merged_cfg, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Lưu thêm bản backup để phục hồi nhanh khi cần.
            if os.path.isfile(path):
                backup_path = f"{path}.bak"
                try:
                    with open(path, "r", encoding="utf-8") as src, open(backup_path, "w", encoding="utf-8") as dst:
                        dst.write(src.read())
                except Exception:
                    pass

            # Atomic replace đảm bảo không tạo file nửa chừng khi mất điện.
            os.replace(tmp_path, path)
        finally:
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return True, path
    except Exception as e:
        return False, str(e)

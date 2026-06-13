import cv2
import numpy as np
import threading
import time
import os

try:
    from pygrabber.dshow_graph import FilterGraph
    PYGRABBER_AVAILABLE = True
except Exception:
    FilterGraph = None
    PYGRABBER_AVAILABLE = False

try:
    from openni import openni2
    OPENNI2_PY_AVAILABLE = True
except Exception:
    openni2 = None
    OPENNI2_PY_AVAILABLE = False

class CameraManager:
    """Module quản lý luồng dữ liệu từ Camera (OpenCV/File/Astra Pro)"""
    
    def __init__(self, on_frame_callback, on_error_callback=None, on_log_callback=None):
        self.on_frame_callback = on_frame_callback
        self.on_error_callback = on_error_callback
        self.on_log_callback = on_log_callback
        
        self.cap = None
        self.depth_cap = None
        self.depth_mode = "none"  # none|opencv_openni|openni2_python
        self._oni_device = None
        self._oni_depth_stream = None
        self._cam_running = False
        self._cam_thread = None
        self._cap_lock = threading.Lock()
        
        # File/Single Image Specific
        self.is_single_image = False
        self.is_video_file = False
        self.single_image_frame = None
        
        # Astra Pro Specific (dùng OpenCV đơn giản)
        self.is_astra_mode = False
        self.depth_available = False
        self.last_depth_distance_m = None
        self.last_depth_distance_mm = None
        self.depth_status = "depth not initialized"
        self.last_depth_error = ""
        self.require_depth_for_astra = False
        self._depth_focus_norm = None
        self._depth_none_count = 0  # Đếm số frame liên tiếp không có mẫu depth hợp lệ

        # Source metadata cho cơ chế auto-recover stream.
        self._source_mode = "none"          # none|camera|video_file|single_image|astra
        self._source_path = ""
        self._source_index = None
        self._source_backend = cv2.CAP_ANY

    @staticmethod
    def _is_virtual_camera_name(name):
        """Heuristic lọc camera ảo để chỉ giữ camera phần cứng cắm thật."""
        n = str(name or "").lower()
        virtual_keywords = [
            "virtual",
            "obs",
            "xsplit",
            "manycam",
            "snap camera",
            "vcam",
            "droidcam",
            "epoccam",
            "ip camera adapter",
            "ndi",
            "screen",
            "capture",
        ]
        return any(k in n for k in virtual_keywords)

    @staticmethod
    def _is_astra_camera_name(name):
        """Nhận diện tên thiết bị có khả năng là Astra/Orbbec."""
        n = str(name or "").lower()
        astra_keywords = ["astra", "orbbec"]
        return any(k in n for k in astra_keywords)

    @staticmethod
    def _enumerate_dshow_device_names():
        """Lấy danh sách tên camera DirectShow theo đúng thứ tự index OpenCV trên Windows."""
        if not PYGRABBER_AVAILABLE:
            return []
        try:
            graph = FilterGraph()
            return list(graph.get_input_devices() or [])
        except Exception:
            return []

    @staticmethod
    def detect_available_cameras(max_test=4):
        """
        Tự động quét và tìm tất cả camera có sẵn trên hệ thống.

        Returns:
            list: Danh sách các index camera khả dụng [(index, name), ...]
        """
        available = []

        # Tắt log OpenCV tạm thời để chặn warning/error spam khi probe.
        try:
            _prev_log = cv2.getLogLevel()
            cv2.setLogLevel(0)  # LOG_LEVEL_SILENT
        except Exception:
            _prev_log = None

        try:
            # Ư u tiên pygrabber (DirectShow) để lấy tên camera thật.
            if PYGRABBER_AVAILABLE:
                try:
                    graph = FilterGraph()
                    device_names = graph.get_input_devices() or []
                    for i, dshow_name in enumerate(device_names):
                        if i >= int(max_test):
                            break
                        if CameraManager._is_virtual_camera_name(dshow_name):
                            continue
                        cap = None
                        try:
                            # Dùng MSMF để tránh FFMPEG/DSHOW warning.
                            cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                            if not cap.isOpened():
                                cap.release()
                                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                            if not cap.isOpened():
                                continue
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                name = f"{dshow_name} ({w}x{h})"
                                available.append((i, name))
                                print(f"[CAM] Tim thay (pygrabber): Cong {i} - {name}")
                        except Exception as e:
                            print(f"[CAM] Cong {i} error (pygrabber probe): {e}")
                        finally:
                            if cap:
                                try:
                                    cap.release()
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"[CAM] pygrabber enumeration failed: {e}")

            # Fallback OpenCV thuần (MSMF → không gây FFMPEG/DShow warning).
            if not available:
                for i in range(int(max_test)):
                    cap = None
                    try:
                        cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                        if not cap.isOpened():
                            try:
                                cap.release()
                            except Exception:
                                pass
                            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                        if cap.isOpened():
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                                name = f"Camera {i} ({w}x{h})"
                                if not CameraManager._is_virtual_camera_name(name):
                                    available.append((i, name))
                                print(f"[CAM] Tim thay: {name}")
                    except Exception as e:
                        print(f"[CAM] Cong {i} error: {e}")
                    finally:
                        if cap:
                            try:
                                cap.release()
                            except Exception:
                                pass
        finally:
            if _prev_log is not None:
                try:
                    cv2.setLogLevel(_prev_log)
                except Exception:
                    pass

        return available

    def probe_astra_connection(self, preferred_indices=None, strict_identity=True):
        """Kiểm tra nhanh khả năng mở RGB của Astra, có xác thực danh tính thiết bị."""
        if preferred_indices is None:
            preferred_indices = [1, 2, 0]

        dshow_names = self._enumerate_dshow_device_names()
        astra_indices = []
        for idx, dev_name in enumerate(dshow_names):
            if self._is_virtual_camera_name(dev_name):
                continue
            if self._is_astra_camera_name(dev_name):
                astra_indices.append(int(idx))

        # Chế độ strict: không xác thực được đúng danh tính thì không được báo "Astra đã kết nối".
        if strict_identity:
            if not dshow_names:
                return {
                    "connected": False,
                    "port": None,
                    "message": "Không xác thực được model camera (thiếu pygrabber/DirectShow enum)",
                }
            if not astra_indices:
                return {
                    "connected": False,
                    "port": None,
                    "message": "Không thấy thiết bị Astra/Orbbec trong danh sách camera",
                }
            candidate_indices = [i for i in preferred_indices if i in astra_indices] + [i for i in astra_indices if i not in preferred_indices]
        else:
            if astra_indices:
                candidate_indices = [i for i in preferred_indices if i in astra_indices] + [i for i in astra_indices if i not in preferred_indices]
            else:
                candidate_indices = list(preferred_indices)

        last_error = ""
        for idx in candidate_indices:
            cap = None
            backend_label = ""
            try:
                cap, backend_used, backend_label = self._open_camera_with_backends(int(idx), prefer_external=True)
                if not cap or not cap.isOpened():
                    last_error = f"cannot open port {idx}"
                    continue

                ok, frame = cap.read()
                if ok and frame is not None:
                    dev_name = dshow_names[idx] if idx < len(dshow_names) else "unknown device"
                    return {
                        "connected": True,
                        "port": int(idx),
                        "message": f"Astra RGB detected on port {idx} ({backend_label}) - {dev_name}",
                    }

                last_error = f"port {idx} opened but no frame"
            except Exception as e:
                last_error = f"port {idx} error: {e}"
            finally:
                try:
                    if cap:
                        cap.release()
                except Exception:
                    pass

        return {
            "connected": False,
            "port": None,
            "message": f"Astra RGB not detected ({last_error or 'no available astra-like port'})",
        }

    def _open_camera_with_backends(self, idx, prefer_external=False):
        """Open camera index with backend fallback order; returns (cap, backend_code, backend_label).
        Dùng MSMF làm primary → tránh FFMPEG/DShow warning và obsensor error.
        Không dùng CAP_ANY để OpenCV không tự động thử obsensor backend gây out-of-range error.
        """
        backend_order = [
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_DSHOW, "DirectShow"),
        ]

        for backend_code, backend_label in backend_order:
            cap = None
            try:
                cap = cv2.VideoCapture(int(idx), backend_code)
                if cap is not None and cap.isOpened():
                    return cap, backend_code, backend_label
            except Exception:
                pass
            finally:
                try:
                    if cap is not None and not cap.isOpened():
                        cap.release()
                except Exception:
                    pass

        return None, cv2.CAP_MSMF, "none"

    def _log(self, msg):
        if self.on_log_callback:
            self.on_log_callback(msg)

    def _error(self, msg):
        if self.on_error_callback:
            self.on_error_callback(msg)

    def set_depth_focus_point(self, x, y, frame_w, frame_h):
        """Cập nhật điểm focus depth theo toạ độ tâm táo trên khung RGB hiện tại."""
        try:
            fw = float(frame_w)
            fh = float(frame_h)
            if fw <= 1.0 or fh <= 1.0:
                return
            nx = float(x) / fw
            ny = float(y) / fh
            nx = float(np.clip(nx, 0.0, 1.0))
            ny = float(np.clip(ny, 0.0, 1.0))
            self._depth_focus_norm = (nx, ny)
        except Exception:
            pass

    def clear_depth_focus_point(self):
        """Xoá focus depth hiện tại khi không còn đối tượng cần đo."""
        self._depth_focus_norm = None

    def is_running(self):
        return self._cam_running

    def start_cv2_camera(self, idx):
        """Mở camera với nhiều phương thức để đảm bảo tương thích"""
        self.stop()
        self.depth_available = False
        self.last_depth_distance_m = None
        self.last_depth_distance_mm = None
        self.depth_status = "depth disabled (cv2 camera mode)"
        self.is_video_file = False
        self._source_mode = "camera"
        self._source_index = idx
        self._source_path = ""
        self._source_backend = cv2.CAP_ANY
        
        # Thử nhiều backend khác nhau (Windows có nhiều API camera)
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_ANY, "Auto")
        ]
        
        for backend, name in backends:
            try:
                self._log(f"🔍 Thử mở camera {idx} bằng {name}...")
                self.cap = cv2.VideoCapture(idx, backend)
                
                if self.cap.isOpened():
                    # Kiểm tra có đọc được frame không
                    ret, test_frame = self.cap.read()
                    if ret and test_frame is not None:
                        self._source_backend = backend
                        self._log(f"✅ Thành công với {name}!")
                        break
                    else:
                        self.cap.release()
                        self.cap = None
                else:
                    self.cap = None
            except Exception as e:
                self._log(f"❌ {name} thất bại: {e}")
                if self.cap:
                    self.cap.release()
                    self.cap = None
        
        if not self.cap or not self.cap.isOpened():
            self._error(f"Không thể mở camera {idx}.\nThử:\n- Kiểm tra camera đã cắm đúng\n- Đóng ứng dụng khác đang dùng camera\n- Thử chọn cổng khác")
            return False
        
        # Cài đặt độ phân giải cơ bản (an toàn, không gây lỗi)
        try:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._log("✅ Camera settings: 640x480")
        except Exception as e:
            self._log(f"⚠️ Không set được độ phân giải camera: {e}")
        
        # ─── Apply Anti-Motion Blur Settings (OPTIONAL) ─────────
        """
        [DISABLED] Áp dụng cài đặt camera CHUYÊN GIẢI QUYẾT MOTION BLUR.
        
        CẢNH BÁO: Hàm này có thể gây lỗi với một số webcam.
        Chỉ bật khi thực sự cần thiết.
        """
        
        # Cài đặt buffer size thấp để giảm lag
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception as e:
            self._log(f"⚠️ Không set được buffer size camera: {e}")
            
        self._cam_running = True
        self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._cam_thread.start()
        return True


    def start_file_mode(self, path, is_video=False):
        self.stop()
        self.depth_available = False
        self.last_depth_distance_m = None
        self.last_depth_distance_mm = None
        self.depth_status = "depth disabled (file mode)"
        self.is_video_file = bool(is_video)
        self._source_path = path
        self._source_index = None
        self._source_backend = cv2.CAP_ANY
        if is_video:
            self._source_mode = "video_file"
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                self._error("Không thể mở file video này!")
                return False
        else:
            self._source_mode = "single_image"
            img = cv2.imread(path)
            if img is None:
                self._error("Không thể mở file ảnh này!")
                return False
            self.single_image_frame = img
            self.is_single_image = True
            
        self._cam_running = True
        self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._cam_thread.start()
        return True

    def start_astra_camera(self, color_idx=None):
        """
        Khởi động Astra Pro ở chế độ RGB (2D).
        """
        self.stop()
        self.is_video_file = False
        self._source_mode = "astra"
        self._source_index = None
        self._source_path = ""
        self._source_backend = cv2.CAP_ANY
        
        try:
            # Xác thực camera Astra theo tên thiết bị để tránh fallback nhầm webcam mặc định.
            dshow_names = self._enumerate_dshow_device_names()
            astra_indices = []
            for idx, dev_name in enumerate(dshow_names):
                if self._is_virtual_camera_name(dev_name):
                    continue
                if self._is_astra_camera_name(dev_name):
                    astra_indices.append(int(idx))

            if dshow_names and not astra_indices:
                self._error(
                    "Không phát hiện thiết bị Astra/Orbbec trong danh sách camera. "
                    "Ứng dụng sẽ không fallback sang webcam mặc định để tránh nhận sai nguồn."
                )
                return False

            # Ưu tiên cổng Astra đã xác thực; nếu không enum được thì fallback theo thứ tự cũ.
            preferred_order = [1, 2, 0]
            if astra_indices:
                if isinstance(color_idx, int) and color_idx in astra_indices:
                    candidate_indices = [color_idx] + [i for i in astra_indices if i != color_idx]
                elif isinstance(color_idx, int) and color_idx >= 0:
                    preferred = astra_indices[0]
                    selected_name = dshow_names[color_idx] if color_idx < len(dshow_names) else "unknown"
                    self._log(
                        f"⚠️ Cổng {color_idx} không phải Astra ({selected_name}). Tự chuyển sang cổng {preferred}."
                    )
                    candidate_indices = [preferred] + [i for i in astra_indices if i != preferred]
                else:
                    candidate_indices = [i for i in preferred_order if i in astra_indices] + [i for i in astra_indices if i not in preferred_order]
            elif isinstance(color_idx, int) and color_idx >= 0:
                candidate_indices = [color_idx] + [i for i in preferred_order if i != color_idx]
            else:
                candidate_indices = preferred_order

            opened_cap = None
            selected_idx = None
            selected_backend = cv2.CAP_ANY
            selected_backend_label = "none"
            for idx in candidate_indices:
                self._log(f"🔍 Astra RGB: thử mở cổng {idx}...")
                trial, backend_used, backend_label = self._open_camera_with_backends(idx, prefer_external=True)
                if trial is not None and trial.isOpened():
                    ok, test_frame = trial.read()
                    if ok and test_frame is not None:
                        opened_cap = trial
                        selected_idx = idx
                        selected_backend = backend_used
                        selected_backend_label = backend_label
                        break
                try:
                    if trial is not None:
                        trial.release()
                except Exception:
                    pass

            self.cap = opened_cap
            self._source_index = selected_idx
            self._source_backend = selected_backend

            if not self.cap or not self.cap.isOpened():
                self._error("Không thể mở RGB Camera của Astra Pro! Kiểm tra:\n1. Kết nối cáp USB\n2. Cổng USB 3.0\n3. Driver camera")
                return False
            
            # Cài đặt độ phân giải RGB
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self._log("✅ RGB Camera settings: 640x480@30fps")
            except Exception as e:
                self._log(f"⚠️ Không set được thông số RGB Astra: {e}")
            
            self.is_astra_mode = True
            # Mặc định FLEX/RGB-only: chỉ khởi tạo depth khi cấu hình yêu cầu bắt buộc.
            if self.require_depth_for_astra:
                self._init_astra_depth_stream()
            else:
                self.depth_available = False
                self.last_depth_distance_m = None
                self.last_depth_distance_mm = None
                self.depth_mode = "none"
                self.depth_status = "rgb-only mode (depth disabled by default)"

            # Chế độ nghiêm ngặt: Astra chỉ được coi là kết nối thành công khi có depth.
            if self.require_depth_for_astra and not self.depth_available:
                depth_reason = self.depth_status or self.last_depth_error or "unknown depth error"
                self._error(
                    "Không thể khởi động Astra Pro Depth. "
                    f"Lý do: {depth_reason}\n"
                    "Ứng dụng sẽ không chạy RGB-only để tránh Z luôn N/A."
                )
                self.is_astra_mode = False
                self._source_mode = "none"
                self._release_cap()
                return False

            self._cam_running = True
            self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
            self._cam_thread.start()
            
            self._log(f"🟢 Astra Pro: RUNNING (RGB) - Cổng {selected_idx} ({selected_backend_label})")
            return True
            
        except Exception as e:
            self._error(f"Lỗi khởi động Astra Pro: {e}")
            return False

    def auto_detect_and_start(self):
        """
        Dò toàn bộ camera, ưu tiên Astra Pro.
        - Nếu pygrabber enum được tên: dùng tên xác thực chính xác.
        - Nếu pygrabber thất bại: vẫn thử start_astra_camera() – nó tự dò cổng 1→2→0.
        - Fallback: webcam thường đầu tiên khả dụng.
        Returns dict: {'success', 'mode', 'port', 'name', 'message'}
        """
        self._log("🔍 [AutoDetect] Đang dò camera, ưu tiên Astra Pro...")

        # Tắt log OpenCV trong suốt quá trình dò – chặn warning FFMPEG + obsensor error.
        try:
            _prev_log = cv2.getLogLevel()
            cv2.setLogLevel(0)
        except Exception:
            _prev_log = None

        def _restore_log():
            if _prev_log is not None:
                try:
                    cv2.setLogLevel(_prev_log)
                except Exception:
                    pass

        try:
            # ── Bước 1: Dò Astra theo tên DirectShow (pygrabber) ──────────────
            dshow_names = self._enumerate_dshow_device_names()
            astra_indices = []
            webcam_indices = []

            for idx, dev_name in enumerate(dshow_names):
                if self._is_virtual_camera_name(dev_name):
                    continue
                if self._is_astra_camera_name(dev_name):
                    astra_indices.append((idx, dev_name))
                else:
                    webcam_indices.append((idx, dev_name))

            # ── Bước 2a: Có tên Astra → thử theo tên xác thực ───────────────
            if astra_indices:
                self._log(f"✅ [AutoDetect] Tìm thấy Astra/Orbbec: {[n for _, n in astra_indices]}")
                preferred = [1, 2, 0]
                ordered = (
                    [p for p in astra_indices if p[0] in preferred]
                    + [p for p in astra_indices if p[0] not in preferred]
                )
                for astra_idx, astra_name in ordered:
                    self._log(f"🔌 [AutoDetect] Thử Astra cổng {astra_idx} ({astra_name})...")
                    ok = self.start_astra_camera(color_idx=astra_idx)
                    if ok:
                        port = int(getattr(self, "_source_index", astra_idx) or astra_idx)
                        self._log(f"🟢 [AutoDetect] Astra Pro kết nối thành công: cổng {port}")
                        _restore_log()
                        return {
                            "success": True,
                            "mode": "astra",
                            "port": port,
                            "name": astra_name,
                            "message": f"Astra Pro RGB: {astra_name} (cổng {port})",
                        }
                self._log("⚠️ [AutoDetect] Tìm thấy Astra nhưng không mở được → fallback webcam")

            else:
                # ── Bước 2b: Không có tên (pygrabber thất bại) → vẫn thử Astra ──────
                # start_astra_camera(None) tự thử cổng 1→2→0 khi không có dshow_names.
                self._log("ℹ️ [AutoDetect] pygrabber không được – thử nhận Astra theo thứ tự 1→2→0...")
                ok = self.start_astra_camera(color_idx=None)
                if ok:
                    port = int(getattr(self, "_source_index", 1) or 1)
                    self._log(f"🟢 [AutoDetect] Astra Pro kết nối (blind): cổng {port}")
                    _restore_log()
                    return {
                        "success": True,
                        "mode": "astra",
                        "port": port,
                        "name": f"Astra Pro (cổng {port})",
                        "message": f"Astra Pro RGB: cổng {port} (blind detect)",
                    }
                self._log("ℹ️ [AutoDetect] Không có Astra, chuyển sang webcam...")

            # ── Bước 3: Fallback webcam thường ───────────────────────────────
            candidates = list(webcam_indices)  # đã có tên từ pygrabber
            if not candidates:
                # Pygrabber không có → quét thủ công với MSMF (không gây FFMPEG warning).
                for i in range(4):  # chỉ 0–3, tránh obsensor error khi vượt số camera thực
                    cap = None
                    try:
                        cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
                        if cap.isOpened():
                            ret, _ = cap.read()
                            if ret:
                                candidates.append((i, f"Camera {i}"))
                    except Exception:
                        pass
                    finally:
                        if cap:
                            try:
                                cap.release()
                            except Exception:
                                pass

            for cam_idx, cam_name in candidates:
                self._log(f"🔌 [AutoDetect] Thử webcam cổng {cam_idx} ({cam_name})...")
                ok = self.start_cv2_camera(cam_idx)
                if ok:
                    self._log(f"🟢 [AutoDetect] Webcam kết nối: cổng {cam_idx}")
                    _restore_log()
                    return {
                        "success": True,
                        "mode": "webcam",
                        "port": cam_idx,
                        "name": cam_name,
                        "message": f"Webcam: {cam_name} (cổng {cam_idx})",
                    }

            _restore_log()
            self._log("❌ [AutoDetect] Không tìm thấy camera nào khả dụng")
            return {
                "success": False,
                "mode": "none",
                "port": None,
                "name": "",
                "message": "Không tìm thấy camera nào (Astra hoặc webcam)",
            }

        except Exception as exc:
            _restore_log()
            self._log(f"❌ [AutoDetect] Lỗi ngoại lệ: {exc}")
            return {
                "success": False,
                "mode": "none",
                "port": None,
                "name": "",
                "message": f"Lỗi dò camera: {exc}",
            }


    def stop(self):
        self._cam_running = False

        # Chờ luồng stream kết thúc trước khi release để tránh race condition read/release.
        if self._cam_thread and self._cam_thread.is_alive():
            self._cam_thread.join(timeout=1.0)
        self._cam_thread = None

        self._release_cap()
        
        self.is_astra_mode = False
        self.depth_available = False
        self.last_depth_distance_m = None
        self.last_depth_distance_mm = None
        self.is_single_image = False
        self.is_video_file = False
        self.single_image_frame = None

    def _release_cap(self):
        """Release VideoCapture an toàn khi có nhiều luồng truy cập."""
        with self._cap_lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
            if self.depth_cap:
                try:
                    self.depth_cap.release()
                except Exception:
                    pass
                self.depth_cap = None

            if self._oni_depth_stream is not None:
                try:
                    self._oni_depth_stream.stop()
                except Exception:
                    pass
                self._oni_depth_stream = None

            if self._oni_device is not None:
                self._oni_device = None

            if OPENNI2_PY_AVAILABLE and openni2 is not None:
                try:
                    if openni2.is_initialized():
                        openni2.unload()
                except Exception:
                    pass

            self.depth_mode = "none"

    def _init_astra_depth_stream(self):
        """Thử khởi tạo luồng depth cho Astra Pro bằng backend OpenNI/OpenNI2."""
        self.depth_available = False
        self.last_depth_distance_m = None
        self.last_depth_distance_mm = None
        self.depth_status = "depth initializing"
        self.last_depth_error = ""

        # Ưu tiên backend Astra chuyên biệt nếu OpenCV build có expose hằng số này.
        backend_candidates = []
        for attr_name, label in [
            ("CAP_OPENNI2_ASTRA", "OpenNI2_ASTRA"),
            ("CAP_OPENNI_ASTRA", "OpenNI_ASTRA"),
            ("CAP_OPENNI2", "OpenNI2"),
            ("CAP_OPENNI", "OpenNI"),
        ]:
            if hasattr(cv2, attr_name):
                backend_candidates.append((int(getattr(cv2, attr_name)), label))

        if not backend_candidates:
            self.depth_status = "OpenCV lacks OpenNI backends"
            self._log("⚠️ Astra Depth: OpenCV không hỗ trợ OpenNI backend, thử OpenNI2 Python fallback...")
            if self._init_openni2_python_stream():
                return
            self.depth_status = "depth unavailable (OpenCV no OpenNI + OpenNI2 fallback failed)"
            return

        open_attempts = []

        # Thử cả dạng constructor 1 tham số và 2 tham số với nhiều index.
        for backend, name in backend_candidates:
            # form 1: VideoCapture(backend)
            open_attempts.append((name, None, lambda b=backend: cv2.VideoCapture(b)))
            # form 2: VideoCapture(index, backend)
            for dev_idx in (0, 1, 2):
                open_attempts.append((name, dev_idx, lambda b=backend, i=dev_idx: cv2.VideoCapture(i, b)))

        for backend_name, dev_idx, cap_factory in open_attempts:
            depth_cap = None
            try:
                depth_cap = cap_factory()
                if not depth_cap or not depth_cap.isOpened():
                    if depth_cap:
                        depth_cap.release()
                    continue

                # Probe một frame depth để đảm bảo stream thực sự usable.
                ok_grab = depth_cap.grab()
                if not ok_grab:
                    depth_cap.release()
                    continue

                ok_depth = False
                try:
                    ok_depth, depth_map = depth_cap.retrieve(None, cv2.CAP_OPENNI_DEPTH_MAP)
                except TypeError:
                    ok_depth, depth_map = depth_cap.retrieve(cv2.CAP_OPENNI_DEPTH_MAP)

                if (not ok_depth) or depth_map is None:
                    depth_cap.release()
                    continue

                with self._cap_lock:
                    self.depth_cap = depth_cap

                self.depth_available = True
                self.depth_mode = "opencv_openni"
                idx_text = "auto" if dev_idx is None else str(dev_idx)
                self.depth_status = f"depth running ({backend_name}, idx={idx_text})"
                self._log(f"✅ Astra Depth: RUNNING ({backend_name}, idx={idx_text})")
                return
            except Exception as e:
                if depth_cap:
                    try:
                        depth_cap.release()
                    except Exception:
                        pass
                idx_text = "auto" if dev_idx is None else str(dev_idx)
                self._log(f"[CAM] Depth init failed ({backend_name}, idx={idx_text}): {e}")

        # Fallback: dùng OpenNI2 Python API trực tiếp (không phụ thuộc OpenCV OpenNI).
        if self._init_openni2_python_stream():
            return

        if self.last_depth_error:
            self.depth_status = f"depth unavailable ({self.last_depth_error})"
        else:
            self.depth_status = "depth unavailable (OpenNI stream open failed)"
        self._log("⚠️ Astra Depth: unavailable (không mở được stream depth OpenNI)")

    def _init_openni2_python_stream(self):
        """Fallback mở luồng depth bằng OpenNI2 Python API."""
        if not OPENNI2_PY_AVAILABLE or openni2 is None:
            self.last_depth_error = "openni python package missing"
            self._log("[CAM] OpenNI2 Python API chưa có (pip install openni)")
            return False

        redist_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "OpenNI2", "Redist")
        )
        if not os.path.isdir(redist_dir):
            # Thử fallback theo root workspace nếu chạy từ vị trí khác.
            redist_dir = os.path.abspath(os.path.join(os.getcwd(), "OpenNI2", "Redist"))

        drivers_dir = os.path.join(redist_dir, "OpenNI2", "Drivers")
        orbbec_dll = os.path.join(drivers_dir, "orbbec.dll")

        if not os.path.isdir(redist_dir):
            self.last_depth_error = f"OpenNI2 Redist not found: {redist_dir}"
            self._log(f"[CAM] {self.last_depth_error}")
            return False
        if not os.path.isdir(drivers_dir):
            self.last_depth_error = f"OpenNI2 Drivers not found: {drivers_dir}"
            self._log(f"[CAM] {self.last_depth_error}")
            return False
        if not os.path.isfile(orbbec_dll):
            self.last_depth_error = f"orbbec.dll missing: {orbbec_dll}"
            self._log(f"[CAM] {self.last_depth_error}")
            return False

        # Trên Windows cần khai báo rõ đường dẫn DLL/Drivers để plugin orbbec được nạp.
        if os.name == "nt":
            try:
                if hasattr(os, "add_dll_directory") and os.path.isdir(redist_dir):
                    os.add_dll_directory(redist_dir)
                if hasattr(os, "add_dll_directory") and os.path.isdir(drivers_dir):
                    os.add_dll_directory(drivers_dir)
            except Exception:
                pass

            if os.path.isdir(redist_dir):
                prev_path = os.environ.get("PATH", "")
                if redist_dir not in prev_path:
                    os.environ["PATH"] = redist_dir + os.pathsep + prev_path
            if os.path.isdir(drivers_dir):
                os.environ["OPENNI2_DRIVERS_PATH"] = drivers_dir

        try:
            if openni2.is_initialized():
                try:
                    openni2.unload()
                except Exception:
                    pass

            if os.path.isdir(redist_dir):
                openni2.initialize(redist_dir)
            else:
                openni2.initialize()

            self._log(f"[CAM] OpenNI2 redist: {redist_dir}")
            self._log(f"[CAM] OpenNI2 drivers: {drivers_dir}")

            dev = openni2.Device.open_any()
            depth_stream = dev.create_depth_stream()

            # Set video mode mặc định để tránh buffer toàn 0 do lỗi config từ thiết bị
            try:
                from openni import openni2 as oni
                video_mode = oni.VideoMode()
                video_mode.fps = 30
                video_mode.resolutionX = 640
                video_mode.resolutionY = 480
                video_mode.pixelFormat = oni.PIXEL_FORMAT_DEPTH_1_MM
                depth_stream.set_video_mode(video_mode)
            except Exception as e:
                self._log(f"[CAM] Không thể set VideoMode, thử chạy default: {e}")

            depth_stream.start()

            # Probe 1 frame depth để chắc stream usable.
            frm = depth_stream.read_frame()
            if frm is None:
                depth_stream.stop()
                return False

            with self._cap_lock:
                self._oni_device = dev
                self._oni_depth_stream = depth_stream

            self.depth_available = True
            self.depth_mode = "openni2_python"
            self.depth_status = "depth running (openni2 python api)"
            self._log("✅ Astra Depth: RUNNING (OpenNI2 Python API)")
            return True
        except Exception as e:
            self.last_depth_error = f"openni2 fallback failed: {e}"
            self._log(f"[CAM] OpenNI2 Python fallback failed: {e}")
            try:
                if OPENNI2_PY_AVAILABLE and openni2 is not None and openni2.is_initialized():
                    openni2.unload()
            except Exception:
                pass
            return False

    def _read_depth_distance_mm(self):
        """Đọc khoảng cách Z tại vùng focus (tâm táo) từ depth map, trả về mm hoặc None."""
        if self.depth_mode == "openni2_python":
            with self._cap_lock:
                dstream = self._oni_depth_stream
            if dstream is None:
                return None
            try:
                frm = dstream.read_frame()
                if frm is None:
                    return None
                w = int(frm.width)
                h = int(frm.height)
                data = frm.get_buffer_as_uint16()
                try:
                    # Chuẩn nhất cho CTypes array của openni2
                    depth_map = np.ndarray((h, w), dtype=np.uint16, buffer=data).copy()
                except Exception:
                    # Fallback
                    depth_map = np.ctypeslib.as_array(data).reshape((h, w))
            except Exception as e:
                self._log(f"[CAM] Lỗi decode depth map: {e}")
                return -1.0
        else:
            with self._cap_lock:
                dcap = self.depth_cap

            if not dcap or not dcap.isOpened():
                return None

            try:
                if not dcap.grab():
                    return None

                try:
                    ok, depth_map = dcap.retrieve(None, cv2.CAP_OPENNI_DEPTH_MAP)
                except TypeError:
                    ok, depth_map = dcap.retrieve(cv2.CAP_OPENNI_DEPTH_MAP)

                if not ok or depth_map is None:
                    return -4.0
                h, w = depth_map.shape[:2]
            except Exception as e:
                self._log(f"[CAM] Lỗi retrieve OpenCV depth: {e}")
                return -5.0

        try:
            if isinstance(self._depth_focus_norm, tuple) and len(self._depth_focus_norm) == 2:
                nx, ny = self._depth_focus_norm
                cx = int(np.clip(round(float(nx) * (w - 1)), 0, w - 1))
                cy = int(np.clip(round(float(ny) * (h - 1)), 0, h - 1))
            else:
                cx, cy = w // 2, h // 2

            # Một số frame depth có lỗ ở tâm; mở rộng ROI theo nhiều mức để giảm N/A giả.
            for half_win in (4, 10, 20, 35):
                x1, x2 = max(0, cx - half_win), min(w, cx + half_win + 1)
                y1, y2 = max(0, cy - half_win), min(h, cy + half_win + 1)

                roi = depth_map[y1:y2, x1:x2]
                if roi.size == 0:
                    continue

                valid = roi[(roi > 80) & (roi < 10000)]
                if valid.size == 0:
                    continue

                return float(np.median(valid))

            # Fallback khi vùng focus bị lỗ depth: lấy percentile gần nhất ở vùng giữa ảnh.
            x1 = max(0, int(w * 0.20))
            x2 = min(w, int(w * 0.80))
            y1 = max(0, int(h * 0.20))
            y2 = min(h, int(h * 0.85))
            roi_mid = depth_map[y1:y2, x1:x2]
            if roi_mid.size > 0:
                valid_mid = roi_mid[(roi_mid > 80) & (roi_mid < 10000)]
                if valid_mid.size > 32:
                    return float(np.percentile(valid_mid, 20))

            # Fallback cuối: quét toàn bộ ảnh nếu vùng giữa bị che khuất / nhiễu
            valid_all = depth_map[(depth_map > 80) & (depth_map < 10000)]
            if valid_all.size > 0:
                return float(np.median(valid_all))

            # Không có mẫu hợp lệ → trả None để stream_loop tự quản lý giá trị cũ.
            # KHÔNG fallback sang last_depth_distance_mm vì sẽ tạo vòng lặp đóng băng Z.
            return -2.0
        except Exception as e:
            self._log(f"[CAM] Lỗi tính median Z: {e}")
            return -3.0

    def _read_depth_distance_m(self):
        """Giữ tương thích ngược: trả về mét dựa trên giá trị mm."""
        z_mm = self._read_depth_distance_mm()
        if z_mm is None:
            return None
        return float(z_mm) / 1000.0

    def _reopen_stream_source(self):
        """Tự phục hồi nguồn stream/camera khi decode lỗi liên tiếp."""
        if self._source_mode in ("single_image", "none"):
            return False

        self._release_cap()

        new_cap = None
        try:
            if self._source_mode in ("camera", "astra"):
                idx = 0 if self._source_index is None else int(self._source_index)
                new_cap = cv2.VideoCapture(idx, self._source_backend)
                if not new_cap or not new_cap.isOpened():
                    return False

                # Giữ cấu hình nhẹ để tránh tăng độ trễ và giảm áp lực decoder.
                try:
                    new_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    new_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    new_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

                # Astra mode: không cho fallback sang camera RGB thường.
                # Chỉ chấp nhận reopen nếu depth stream cũng mở lại được.
                if self._source_mode == "astra":
                    try:
                        self._release_cap()
                    except Exception:
                        pass
                    with self._cap_lock:
                        self.cap = new_cap

                    if self.require_depth_for_astra:
                        self.depth_available = False
                        self._init_astra_depth_stream()
                        if not self.depth_available:
                            self.depth_status = "Astra disconnected (depth stream lost)"
                            try:
                                new_cap.release()
                            except Exception:
                                pass
                            with self._cap_lock:
                                self.cap = None
                            return False
                    else:
                        self.depth_available = False
                        self.last_depth_distance_m = None
                        self.last_depth_distance_mm = None
                        self.depth_mode = "none"
                        self.depth_status = "rgb-only mode (depth disabled by default)"
            elif self._source_mode == "video_file":
                if not self._source_path:
                    return False
                new_cap = cv2.VideoCapture(self._source_path)
                if not new_cap or not new_cap.isOpened():
                    return False
            else:
                return False

            with self._cap_lock:
                # Astra mode đã set cap ở nhánh trên.
                if self._source_mode != "astra":
                    self.cap = new_cap
            self._log("[CAM] Stream auto-recover: reopened source")
            return True
        except Exception as e:
            try:
                if new_cap:
                    new_cap.release()
            except Exception:
                pass
            self._log(f"[CAM] Stream auto-recover failed: {e}")
            return False

    def _stream_loop(self):
        read_failures = 0
        hard_failures = 0

        while self._cam_running:
            if self.is_single_image:
                frame = self.single_image_frame.copy()
                time.sleep(1.0) # Đợi 1 giây cho ảnh tĩnh để giảm tải và hết chớp màn hình
                if self.on_frame_callback and self._cam_running:
                    self.on_frame_callback(frame)
            else:
                with self._cap_lock:
                    cap_ref = self.cap

                if not cap_ref:
                    break

                try:
                    ret, frame = cap_ref.read()
                except cv2.error as e:
                    self._log(f"[CAM] OpenCV read error: {e}")
                    ret, frame = False, None
                except Exception as e:
                    self._log(f"[CAM] Stream read exception: {e}")
                    ret, frame = False, None

                if not ret or frame is None:
                    # Với video file: tránh seek trực tiếp CAP_PROP_POS_FRAMES khi decoder vừa lỗi,
                    # vì một số build ffmpeg có thể văng assertion async_lock.
                    if self.is_video_file and cap_ref:
                        hard_failures += 1
                        if hard_failures <= 3 and self._reopen_stream_source():
                            time.sleep(0.05)
                            continue
                        self._error("Không thể đọc file video ổn định. Vui lòng chọn lại file hoặc đổi định dạng video khác.")
                        self._cam_running = False
                        break

                    # Cho stream/camera vài lần retry trước khi thử recover.
                    read_failures += 1
                    if read_failures <= 10:
                        time.sleep(0.05)
                        continue

                    hard_failures += 1
                    read_failures = 0
                    if hard_failures <= 3 and self._reopen_stream_source():
                        time.sleep(0.1)
                        continue

                    if self._source_mode == "astra":
                        self.depth_available = False
                        if self.require_depth_for_astra:
                            self.depth_status = "Astra disconnected (RGB/depth read failed)"
                            self._error("Astra Pro đã mất kết nối. Vui lòng kiểm tra cáp USB/nguồn và bật lại camera.")
                        else:
                            self.depth_status = "depth unavailable (rgb read retrying)"
                            self._log("⚠️ Astra read lỗi tạm thời, tiếp tục retry giữ camera ON (FLEX mode)")
                            time.sleep(0.2)
                            continue
                    self._log("[CAM] Stream stopped after repeated decode/read failures")
                    self._cam_running = False
                    break

                read_failures = 0
                hard_failures = 0

                depth_info = {
                    "z_distance_mm": self.last_depth_distance_mm,
                    "z_distance_m": self.last_depth_distance_m,
                    "depth_available": bool(self.depth_available),
                    "depth_status": self.depth_status,
                }
                if self.is_astra_mode:
                    z_mm = self._read_depth_distance_mm() if self.depth_available else None
                    if z_mm is not None:
                        # Có mẫu mới hợp lệ: reset stale counter, cập nhật giá trị
                        self._depth_none_count = 0
                        self.last_depth_distance_mm = float(z_mm)
                        self.last_depth_distance_m = float(z_mm) / 1000.0
                        depth_info["z_distance_mm"] = self.last_depth_distance_mm
                        depth_info["z_distance_m"] = self.last_depth_distance_m
                        if self.depth_available:
                            depth_info["depth_status"] = f"{self.depth_status} | sample ok"
                    elif self.depth_available:
                        # Không có mẫu hợp lệ: đếm stale frames
                        self._depth_none_count += 1
                        # Sau ~2 giây (~60 frame) liên tục không có mẫu → xóa giá trị cũ
                        if self._depth_none_count > 60:
                            self.last_depth_distance_mm = None
                            self.last_depth_distance_m = None
                            depth_info["z_distance_mm"] = None
                            depth_info["z_distance_m"] = None
                        depth_info["depth_status"] = f"{self.depth_status} | no valid sample ({self._depth_none_count}f)"

                if self.on_frame_callback and self._cam_running:
                    try:
                        self.on_frame_callback(frame.copy(), depth_info)
                    except TypeError:
                        # Tương thích callback cũ chỉ nhận 1 tham số frame.
                        self.on_frame_callback(frame.copy())
                    except Exception as e:
                        self._log(f"[CAM] Frame callback error: {e}")

        # Đảm bảo giải phóng resource khi vòng lặp kết thúc bất thường.
        self._release_cap()

import cv2
import threading
import time
import numpy as np
import sys
import os

class CameraManager:
    """Module quản lý luồng dữ liệu từ Camera (OpenCV/File/Astra Pro)"""
    
    def __init__(self, on_frame_callback, on_error_callback=None, on_log_callback=None):
        self.on_frame_callback = on_frame_callback
        self.on_error_callback = on_error_callback
        self.on_log_callback = on_log_callback
        
        self.cap = None
        self._cam_running = False
        self._cam_thread = None
        
        # File/Single Image Specific
        self.is_single_image = False
        self.single_image_frame = None
        
        # Astra Pro Specific (dùng OpenCV đơn giản)
        self.is_astra_mode = False

    @staticmethod
    def detect_available_cameras(max_test=5):
        """
        Tự động quét và tìm tất cả camera có sẵn trên hệ thống.
        
        Returns:
            list: Danh sách các index camera khả dụng [(index, name), ...]
        """
        available = []
        
        for i in range(max_test):
            cap = None
            try:
                # Thử mở với CAP_DSHOW trước (nhanh nhất trên Windows)
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                
                if cap.isOpened():
                    # Kiểm tra đọc được frame không
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # Lấy thông tin camera
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        name = f"Camera {i} ({w}x{h})"
                        available.append((i, name))
                        print(f"✅ Tìm thấy: {name}")
                
                cap.release()
                
            except Exception as e:
                print(f"❌ Cổng {i}: {e}")
            finally:
                if cap:
                    cap.release()
        
        return available

    def _log(self, msg):
        if self.on_log_callback:
            self.on_log_callback(msg)

    def _error(self, msg):
        if self.on_error_callback:
            self.on_error_callback(msg)

    def is_running(self):
        return self._cam_running

    def stop(self):
        self._cam_running = False
            
        # Tắt OpenCV
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.is_astra_mode = False
        self.is_single_image = False
        self.single_image_frame = None

    def start_cv2_camera(self, idx):
        """Mở camera với nhiều phương thức để đảm bảo tương thích"""
        self.stop()
        
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
        except:
            pass
        
        # ─── Apply Anti-Motion Blur Settings (OPTIONAL) ─────────
        """
        [DISABLED] Áp dụng cài đặt camera CHUYÊN GIẢI QUYẾT MOTION BLUR.
        
        CẢNH BÁO: Hàm này có thể gây lỗi với một số webcam.
        Chỉ bật khi thực sự cần thiết.
        """
        
        # Cài đặt buffer size thấp để giảm lag
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except:
            pass
            
        self._cam_running = True
        self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._cam_thread.start()
        return True


    def start_file_mode(self, path, is_video=False):
        self.stop()
        if is_video:
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                self._error("Không thể mở file video này!")
                return False
        else:
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

    def start_astra_camera(self, color_idx=1):
        """
        Khởi động Astra Pro qua OpenCV (đơn giản hơn).
        Astra Pro thường xuất hiện như 2 camera:
        - Camera 0/1: RGB camera
        - Camera 1/2: Depth camera (nếu driver hỗ trợ)
        """
        self.stop()
        
        try:
            # Thử mở camera RGB của Astra Pro
            # Astra Pro thường ở cổng USB cao hơn laptop camera
            self.cap = cv2.VideoCapture(color_idx, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                # Thử cổng khác
                self._log(f"⚠️ Không mở được cổng {color_idx}, thử cổng 0...")
                self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            
            if not self.cap.isOpened():
                self._error("Không thể mở Astra Pro! Kiểm tra:\n1. Cắm đúng cổng USB 3.0\n2. Driver đã cài đặt\n3. Thử chọn 'Camera máy tính' hoặc 'Webcam rời'")
                return False
            
            # Cài đặt độ phân giải cơ bản
            try:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.cap.set(cv2.CAP_PROP_FPS, 30)
                self._log("✅ Astra settings: 640x480@30fps")
            except:
                pass
            
            self.is_astra_mode = True
            self._cam_running = True
            self._cam_thread = threading.Thread(target=self._stream_loop, daemon=True)
            self._cam_thread.start()
            
            self._log(f"🟢 Astra Pro: RUNNING (RGB Camera - Cổng {color_idx})")
            return True
            
        except Exception as e:
            self._error(f"Lỗi khởi động Astra Pro: {e}")
            return False
    
    def _stream_loop(self):
        while self._cam_running:
            if self.is_single_image:
                frame = self.single_image_frame.copy()
                time.sleep(1.0) # Đợi 1 giây cho ảnh tĩnh để giảm tải và hết chớp màn hình
            else:
                ret, frame = self.cap.read()
                if not ret:
                    # Nếu là video thì lặp lại (Loop video)
                    if self.cap and self.cap.get(cv2.CAP_PROP_FRAME_COUNT) > 1:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    break
            
            if self.on_frame_callback and self._cam_running:
                self.on_frame_callback(frame.copy())

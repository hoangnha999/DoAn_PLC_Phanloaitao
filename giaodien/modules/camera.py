import cv2
import threading
import time
import numpy as np

class CameraManager:
    """Module quản lý luồng dữ liệu từ Camera (OpenCV/Astra/File)"""
    
    def __init__(self, on_frame_callback, on_error_callback=None, on_log_callback=None):
        self.on_frame_callback = on_frame_callback
        self.on_error_callback = on_error_callback
        self.on_log_callback = on_log_callback
        
        self.cap = None
        self._cam_running = False
        self._cam_thread = None
        
        # Astra Specific
        self.astra_dev = None
        self.astra_depth_stream = None
        self.last_depth_map = None
        
        # File/Single Image Specific
        self.is_single_image = False
        self.single_image_frame = None

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
        
        # Tắt Astra
        if self.astra_dev:
            try:
                if self.astra_depth_stream: 
                    self.astra_depth_stream.stop()
                from openni import openni2
                openni2.unload()
                self.astra_dev = None
                self.astra_depth_stream = None
            except: 
                pass
            
        # Tắt OpenCV
        if self.cap:
            self.cap.release()
            self.cap = None
            
        self.is_single_image = False
        self.single_image_frame = None

    def start_cv2_camera(self, idx):
        self.stop()
        self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self._error(f"Không thể mở camera {idx}.")
            return False
            
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
                # Đối với camera thường hoặc file, raw_depth = None
                self.on_frame_callback(frame.copy(), is_astra=False, depth_colormap=None, raw_depth=None)

    def start_astra_camera(self, color_idx_preference):
        self.stop()
        try:
            from openni import openni2
            openni2.initialize() 
            self.astra_dev = openni2.Device.open_any()
            
            self.astra_depth_stream = self.astra_dev.create_depth_stream()
            self.astra_depth_stream.start()
            
            self.cap = None
            scan_order = [color_idx_preference] + [i for i in (1, 2, 0) if i != color_idx_preference]
            
            for i in scan_order:
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    ret, _ = cap.read()
                    if ret:
                        self.cap = cap
                        break
                    else:
                        cap.release()
            
            if self.cap is None:
                self._log("⚠️ Cảnh báo: Không thể tìm thấy RGB Camera. Chỉ chạy Depth.")
                
            self._cam_running = True
            self._cam_thread = threading.Thread(target=self._stream_astra_loop, daemon=True)
            self._cam_thread.start()
            return True
        except ImportError:
            self._error("Chưa cài đặt SDK. Chạy lệnh: pip install openni")
            return False
        except Exception as e:
            self._error(f"Không thể kết nối Camera Astra: {e}")
            return False

    def _stream_astra_loop(self):
        from openni import openni2
        self._log("Đã vào luồng Astra. Đang đồng bộ hóa RGB và Depth...")
        
        while self._cam_running:
            try:
                color_img = None
                if self.cap and self.cap.isOpened():
                    ret, cframe = self.cap.read()
                    if ret:
                        color_img = cframe.copy()
                
                openni2.wait_for_any_stream([self.astra_depth_stream], timeout=1000)
                
                dframe = self.astra_depth_stream.read_frame()
                ddata = np.frombuffer(dframe.get_buffer_as_uint16(), dtype=np.uint16)
                depth_img = ddata.reshape((dframe.height, dframe.width))
                self.last_depth_map = depth_img.copy()
                
                depth_norm = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)
                
                h, w = depth_colormap.shape[:2]
                bar_h, bar_w, margin = 150, 15, 10
                if h > bar_h + 20 and w > bar_w + 60:
                    gradient = np.linspace(255, 0, bar_h, dtype=np.uint8).reshape(-1, 1)
                    gradient = np.repeat(gradient, bar_w, axis=1)
                    colorbar_color = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
                    
                    x1, y1 = w - margin - bar_w, margin
                    depth_colormap[y1:y1+bar_h, x1:x1+bar_w] = colorbar_color
                    
                    cv2.rectangle(depth_colormap, (x1, y1), (x1+bar_w, y1+bar_h), (255, 255, 255), 1)
                    cv2.putText(depth_colormap, "FAR", (x1 - 35, y1 + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    cv2.putText(depth_colormap, "NEAR", (x1 - 42, y1 + bar_h), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                if self.on_frame_callback and self._cam_running:
                    self.on_frame_callback(color_img, is_astra=True, depth_colormap=depth_colormap, raw_depth=depth_img.copy())
            except Exception as e:
                if "OniStatus.ONI_STATUS_TIME_OUT" not in str(e):
                    self._log(f"Astra Error: {e}")
                time.sleep(0.5)

    def show_point_cloud(self, rgb_frame):
        if self.last_depth_map is None:
            self._error("Chưa có dữ liệu Depth Map!")
            return
            
        try:
            import open3d as o3d
            color_rgb = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2RGB)
            depth_img = self.last_depth_map
            
            o3d_color = o3d.geometry.Image(color_rgb)
            o3d_depth = o3d.geometry.Image(depth_img)
            
            rgbd_image = o3d.geometry.RGBDImage.create_from_color_and_depth(
                o3d_color, o3d_depth, depth_scale=1000.0, depth_trunc=3.0, convert_rgb_to_intensity=False)
            
            intrinsics = o3d.camera.PinholeCameraIntrinsic(
                o3d.camera.PinholeCameraIntrinsicParameters.PrimeSenseDefault)
                
            pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd_image, intrinsics)
            pcd.transform([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
            
            o3d.visualization.draw_geometries([pcd], window_name="Astra Pro 3D Point Cloud", width=800, height=600)
        except ImportError:
            self._error("Chưa cài đặt Open3D. Chạy lệnh: pip install open3d")
        except Exception as e:
            self._error(f"Không thể tạo Point Cloud: {e}")

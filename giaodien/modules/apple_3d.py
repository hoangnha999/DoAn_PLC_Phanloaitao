"""
Module phân tích 3D táo từ Astra Pro depth camera
Đánh giá độ tròn, phát hiện lõm, tính toán sphericity
"""

import numpy as np
from scipy.spatial import ConvexHull
from scipy.ndimage import median_filter
import logging

logger = logging.getLogger(__name__)


class Apple3DAnalyzer:
    """
    Phân tích hình dạng 3D của táo từ depth data
    """
    
    def __init__(self):
        # Camera intrinsics Astra Pro (640x480)
        self.fx = 570.0  # Focal length X (pixels)
        self.fy = 570.0  # Focal length Y (pixels)
        self.cx = 320.0  # Principal point X
        self.cy = 240.0  # Principal point Y
        
        # Ngưỡng phân tích tối ưu cho băng chuyền (60cm - 1.2m)
        self.min_depth = 400      # mm (40cm) - Tránh vật thể quá gần
        self.max_depth = 1200     # mm (120cm) - Loại bỏ nền dưới băng chuyền
        self.dent_threshold = 4.0 # mm (Nhạy hơn để bắt vết móp)
        
    def preprocess_depth(self, depth_image):
        """
        Tiền xử lý depth image: lọc noise, fill holes
        
        Args:
            depth_image: np.array (H, W) - depth in mm
            
        Returns:
            filtered_depth: np.array (H, W) - depth đã lọc
        """
        # Median filter để loại bỏ noise
        filtered = median_filter(depth_image, size=5)
        
        # Clip về range hợp lý
        filtered = np.clip(filtered, self.min_depth, self.max_depth)
        
        # Thay thế giá trị 0 (invalid) bằng mean của lân cận
        mask_valid = filtered > 0
        if np.sum(mask_valid) > 0:
            mean_depth = np.mean(filtered[mask_valid])
            filtered[~mask_valid] = mean_depth
        
        return filtered
    
    def depth_to_pointcloud(self, depth_image, mask):
        """
        Chuyển depth image thành point cloud 3D
        
        Args:
            depth_image: np.array (H, W) - depth in mm
            mask: np.array (H, W) - binary mask của táo (255=táo, 0=nền)
        
        Returns:
            points_3d: np.array (N, 3) - [X, Y, Z] coordinates (mm)
            colors: np.array (N, 3) - [R, G, B] màu của từng điểm (optional)
        """
        # Tiền xử lý depth
        depth_filtered = self.preprocess_depth(depth_image)
        
        h, w = depth_image.shape
        points_3d = []
        
        # Downsample mạnh để đạt tốc độ Real-time (mỗi 4 pixels lấy 1)
        # 640x480 / 16 = ~19,200 points (đủ cho Convex Hull chạy nhanh)
        step = 4
        
        for v in range(0, h, step):
            for u in range(0, w, step):
                # Chỉ lấy điểm trong vùng táo
                if mask[v, u] > 0:
                    z = depth_filtered[v, u]  # Depth (mm)
                    
                    if z > self.min_depth and z < self.max_depth:
                        # Công thức pinhole camera model (projection ngược)
                        x = (u - self.cx) * z / self.fx
                        y = (v - self.cy) * z / self.fy
                        points_3d.append([x, y, z])
        
        points_3d = np.array(points_3d)
        
        if len(points_3d) < 100:
            logger.warning(f"Point cloud quá nhỏ: {len(points_3d)} points")
            return np.array([]), None
        
        logger.info(f"Generated point cloud: {len(points_3d)} points")
        return points_3d
    
    def fit_sphere(self, points_3d):
        """
        Fit hình cầu vào point cloud bằng least squares
        
        Args:
            points_3d: np.array (N, 3)
        
        Returns:
            center: np.array (3,) - tâm hình cầu
            radius: float - bán kính (mm)
        """
        if len(points_3d) < 4:
            return np.array([0, 0, 0]), 0.0
        
        # Tìm tâm gần đúng (centroid)
        center_init = np.mean(points_3d, axis=0)
        
        # Tính bán kính trung bình
        distances = np.linalg.norm(points_3d - center_init, axis=1)
        radius = np.mean(distances)
        
        return center_init, radius
    
    def analyze_sphericity(self, points_3d):
        """
        Đánh giá độ tròn của táo (sphericity score)
        
        Args:
            points_3d: np.array (N, 3)
        
        Returns:
            sphericity: float 0-1 (1 = hoàn hảo tròn như quả cầu)
            surface_variance: float (mm) - độ lệch chuẩn bề mặt
            radius: float (mm) - bán kính trung bình
        """
        if len(points_3d) < 10:
            return 0.0, 0.0, 0.0
        
        # Fit hình cầu
        center, radius = self.fit_sphere(points_3d)
        
        # Tính khoảng cách từ mỗi điểm đến tâm
        distances = np.linalg.norm(points_3d - center, axis=1)
        
        # Độ lệch chuẩn (càng nhỏ càng tròn)
        surface_variance = np.std(distances)
        
        # Sphericity score: 1.0 - (độ lệch / bán kính)
        # Ví dụ: variance = 3mm, radius = 40mm → sphericity = 1 - 3/40 = 0.925
        if radius > 0:
            sphericity = max(0.0, 1.0 - (surface_variance / radius))
        else:
            sphericity = 0.0
        
        logger.info(f"Sphericity: {sphericity:.3f}, Variance: {surface_variance:.2f}mm, Radius: {radius:.2f}mm")
        
        return sphericity, surface_variance, radius
    
    def detect_dents(self, points_3d, threshold_mm=None):
        """
        Phát hiện vùng lõm/móp trên bề mặt táo
        
        Args:
            points_3d: np.array (N, 3)
            threshold_mm: float - độ sâu lõm tối thiểu (mm)
        
        Returns:
            dent_count: int - số lượng điểm lõm
            dent_depth_avg: float (mm) - độ sâu lõm trung bình
            dent_depth_max: float (mm) - độ sâu lõm tối đa
            dent_ratio: float 0-1 - tỷ lệ diện tích lõm
        """
        if threshold_mm is None:
            threshold_mm = self.dent_threshold
        
        if len(points_3d) < 10:
            return 0, 0.0, 0.0, 0.0
        
        # Fit hình cầu chuẩn
        center, mean_radius = self.fit_sphere(points_3d)
        
        # Tính khoảng cách thực tế
        distances = np.linalg.norm(points_3d - center, axis=1)
        
        # Tìm điểm lõm vào (khoảng cách < mean_radius - threshold)
        dent_mask = distances < (mean_radius - threshold_mm)
        dent_count = np.sum(dent_mask)
        
        if dent_count > 0:
            # Độ sâu lõm = bán kính chuẩn - khoảng cách thực
            dent_depths = mean_radius - distances[dent_mask]
            dent_depth_avg = np.mean(dent_depths)
            dent_depth_max = np.max(dent_depths)
            dent_ratio = dent_count / len(points_3d)
        else:
            dent_depth_avg = 0.0
            dent_depth_max = 0.0
            dent_ratio = 0.0
        
        logger.info(f"Dents: count={dent_count}, avg_depth={dent_depth_avg:.2f}mm, max_depth={dent_depth_max:.2f}mm, ratio={dent_ratio:.3f}")
        
        return dent_count, dent_depth_avg, dent_depth_max, dent_ratio
    
    def calculate_volume(self, points_3d):
        """
        Ước lượng thể tích táo bằng Convex Hull
        
        Args:
            points_3d: np.array (N, 3)
        
        Returns:
            volume: float (mm³) - thể tích
        """
        if len(points_3d) < 4:
            return 0.0
        
        try:
            hull = ConvexHull(points_3d)
            volume = hull.volume  # mm³
            logger.info(f"Volume: {volume:.2f} mm³ ({volume/1000:.2f} cm³)")
            return volume
        except Exception as e:
            logger.error(f"Cannot calculate volume: {e}")
            return 0.0
    
    def analyze_complete(self, depth_image, mask):
        """
        Phân tích 3D hoàn chỉnh
        
        Args:
            depth_image: np.array (H, W) - depth in mm
            mask: np.array (H, W) - binary mask
        
        Returns:
            result: dict - kết quả phân tích
        """
        # Tạo point cloud
        points_3d = self.depth_to_pointcloud(depth_image, mask)
        
        if len(points_3d) < 10:
            return {
                "success": False,
                "sphericity": 0.0,
                "surface_variance_mm": 0.0,
                "radius_mm": 0.0,
                "dent_count": 0,
                "dent_depth_avg_mm": 0.0,
                "dent_depth_max_mm": 0.0,
                "dent_ratio": 0.0,
                "volume_cm3": 0.0,
                "point_count": 0
            }
        
        # Phân tích độ tròn
        sphericity, surface_variance, radius = self.analyze_sphericity(points_3d)
        
        # Phát hiện lõm
        dent_count, dent_avg, dent_max, dent_ratio = self.detect_dents(points_3d)
        
        # Tính thể tích
        volume_mm3 = self.calculate_volume(points_3d)
        volume_cm3 = volume_mm3 / 1000.0  # Chuyển sang cm³
        
        result = {
            "success": True,
            "sphericity": round(sphericity, 3),
            "surface_variance_mm": round(surface_variance, 2),
            "radius_mm": round(radius, 2),
            "dent_count": int(dent_count),
            "dent_depth_avg_mm": round(dent_avg, 2),
            "dent_depth_max_mm": round(dent_max, 2),
            "dent_ratio": round(dent_ratio, 3),
            "volume_cm3": round(volume_cm3, 2),
            "point_count": len(points_3d),
            "point_cloud": points_3d  # Lưu point cloud để visualization
        }
        
        return result
    
    def grade_by_3d_metrics(self, analysis_result):
        """
        Phân loại dựa trên metrics 3D
        
        Args:
            analysis_result: dict từ analyze_complete()
        
        Returns:
            grade: int (1, 2, 3)
            reason: str
        """
        if not analysis_result["success"]:
            return 3, "Không đủ dữ liệu 3D"
        
        sphericity = analysis_result["sphericity"]
        dent_count = analysis_result["dent_count"]
        dent_depth_max = analysis_result["dent_depth_max_mm"]
        
        # GRADE-1: Hình dạng hoàn hảo
        if sphericity >= 0.90 and dent_count == 0:
            return 1, "Hình cầu hoàn hảo, không lõm"
        
        # GRADE-3: Nhiều lõm hoặc biến dạng nghiêm trọng
        if sphericity < 0.75 or dent_count > 2 or dent_depth_max > 6.0:
            return 3, f"Sphericity={sphericity:.2f}, {dent_count} lõm"
        
        # GRADE-2: Trung bình
        return 2, f"Sphericity={sphericity:.2f}, {dent_count} lõm nhỏ"
    
    def visualize_point_cloud(self, points_3d, colors=None, window_name="Apple 3D Point Cloud"):
        """
        Hiển thị point cloud 3D bằng Open3D
        
        Args:
            points_3d: np.array (N, 3) - XYZ coordinates
            colors: np.array (N, 3) - RGB colors (0-255) hoặc None
            window_name: str - Tên cửa sổ visualization
        """
        if len(points_3d) < 10:
            logger.warning("Point cloud quá nhỏ để hiển thị")
            return
        
        try:
            import open3d as o3d
            
            # Tạo point cloud object
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(points_3d)
            
            # Thêm màu nếu có
            if colors is not None:
                # Normalize về 0-1
                colors_normalized = colors.astype(np.float64) / 255.0
                pcd.colors = o3d.utility.Vector3dVector(colors_normalized)
            else:
                # Màu mặc định: gradient theo chiều cao (Y)
                y_coords = points_3d[:, 1]
                y_min, y_max = y_coords.min(), y_coords.max()
                if y_max > y_min:
                    normalized_y = (y_coords - y_min) / (y_max - y_min)
                    # Gradient từ xanh lá (bottom) -> đỏ (top)
                    colors_gradient = np.zeros((len(points_3d), 3))
                    colors_gradient[:, 0] = normalized_y  # Red channel
                    colors_gradient[:, 1] = 1.0 - normalized_y  # Green channel
                    pcd.colors = o3d.utility.Vector3dVector(colors_gradient)
            
            # Tính normals để bề mặt đẹp hơn
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=10.0, max_nn=30)
            )
            
            # Tạo coordinate frame (trục tọa độ)
            coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
                size=50.0,  # 50mm
                origin=[0, 0, 0]
            )
            
            # Fit sphere để hiển thị
            center, radius = self.fit_sphere(points_3d)
            sphere_mesh = o3d.geometry.TriangleMesh.create_sphere(radius=radius, resolution=20)
            sphere_mesh.translate(center)
            sphere_mesh.paint_uniform_color([0.9, 0.9, 0.1])  # Màu vàng
            sphere_mesh.compute_vertex_normals()
            
            # Visualization settings
            logger.info(f"Hiển thị {len(points_3d)} điểm, Bán kính sphere: {radius:.1f}mm")
            
            # Hiển thị với custom view
            o3d.visualization.draw_geometries(
                [pcd, coord_frame, sphere_mesh],
                window_name=window_name,
                width=1024,
                height=768,
                left=100,
                top=100,
                point_show_normal=False
            )
            
        except ImportError:
            logger.error("Chưa cài Open3D: pip install open3d")
        except Exception as e:
            logger.error(f"Lỗi visualization: {e}")


if __name__ == "__main__":
    # Test module
    logging.basicConfig(level=logging.INFO)
    
    analyzer = Apple3DAnalyzer()
    
    # Tạo depth image giả lập (hình cầu bán kính 40mm)
    h, w = 480, 640
    depth_test = np.zeros((h, w), dtype=np.uint16)
    mask_test = np.zeros((h, w), dtype=np.uint8)
    
    center_u, center_v = 320, 240
    radius_pixels = 80
    base_depth = 600  # mm
    
    for v in range(h):
        for u in range(w):
            dist_sq = (u - center_u)**2 + (v - center_v)**2
            if dist_sq < radius_pixels**2:
                # Tạo hình cầu
                depth_test[v, u] = int(base_depth + np.sqrt(max(0, radius_pixels**2 - dist_sq)))
                mask_test[v, u] = 255
    
    # Phân tích
    result = analyzer.analyze_complete(depth_test, mask_test)
    print("\n=== KẾT QUẢ PHÂN TÍCH 3D ===")
    for key, value in result.items():
        print(f"{key:25s}: {value}")
    
    grade, reason = analyzer.grade_by_3d_metrics(result)
    print(f"\nĐỀ XUẤT HẠNG: Grade-{grade} ({reason})")

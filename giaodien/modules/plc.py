class PLCManager:
    """Module quản lý kết nối và điều khiển PLC S7-1200 qua Snap7."""
    
    # ─── PLC 1214C Control (Data Block DB10 theo sơ đồ của bạn) ───
    PLC_DB_NUMBER = 10
    
    # Tín hiệu phân loại (Khớp 100% với ảnh bạn gửi)
    PLC_GRADE_BYTE = 0 
    PLC_BIT_GRADE1 = 0 # DB10.DBX0.0 (Apple_GOOD)
    PLC_BIT_GRADE2 = 1 # DB10.DBX0.1 (Apple_MEDIUM)
    PLC_BIT_GRADE3 = 2 # DB10.DBX0.2 (Apple_BAD)

    # Nút nhấn (Dời sang 0.3 và 0.4 để tránh trùng)
    PLC_START_BYTE = 0 
    PLC_START_BIT  = 3 # DB10.DBX0.3
    PLC_STOP_BYTE  = 0 
    PLC_STOP_BIT   = 4 # DB10.DBX0.4

    # Địa chỉ Bộ đếm (Dời xuống Byte 2 cho rộng rãi)
    PLC_DB_COUNTER_START = 2   # DB10.DBW2, DB10.DBW4, DB10.DBW6

    def __init__(self):
        self.client = None
        self.connected = False
        self._snap7_lib = None
        
        try:
            import snap7
            import snap7.type
            self._snap7_lib = snap7
            self._s7t = snap7.type
            self.client = snap7.client.Client()
        except ImportError:
            print("[PLC] Warning: python-snap7 library is not installed.")

    def connect(self, ip, rack, slot):
        """Kết nối tới PLC. Nếu lỗi, tự động chẩn đoán chính xác nguyên nhân."""
        if not self._snap7_lib:
            return False, "Chưa cài python-snap7! Chạy: pip install python-snap7"
            
        try:
            self.client.connect(ip, rack, slot)
            self.connected = True
            return True, f"Connected to {ip}"
        except Exception as e:
            self.connected = False
            # Chẩn đoán lỗi chính xác thay vì chỉ báo chung chung
            exact_error = self._diagnose_connection(ip, rack, slot, str(e))
            return False, exact_error

    def _diagnose_connection(self, ip, rack, slot, original_error):
        """Tiến hành ping và check port 102 để báo lỗi chính xác."""
        import socket
        import subprocess
        import platform
        
        # 1. Kiểm tra định dạng IP
        try:
            socket.inet_aton(ip)
        except socket.error:
            return f"ĐỊA CHỈ IP SAI ĐỊNH DẠNG: '{ip}' không hợp lệ. Vui lòng nhập đúng dạng (VD: 192.168.0.1)"
            
        # 2. Kiểm tra Ping (xem máy tính có nhìn thấy IP này trên mạng không)
        param = '-n' if platform.system().lower()=='windows' else '-c'
        # Timeout 1000ms
        command = ['ping', param, '1', '-w', '1000' if platform.system().lower()=='windows' else '1', ip]
        try:
            output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower()=='windows' else 0)
            if output.returncode != 0:
                return f"LỖI PHẦN CỨNG/MẠNG (Ping timeout): Không tìm thấy thiết bị nào ở IP {ip}.\n→ Cáp mạng bị tuột, đứt, PLC chưa bật nguồn, hoặc máy tính của bạn bị sai Subnet/IP tĩnh."
        except Exception:
            pass
            
        # 3. Kiểm tra Port 102 (Cổng S7 Communication)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        result = sock.connect_ex((ip, 102))
        sock.close()
        
        if result != 0:
            return f"SAI THIẾT BỊ HOẶC CHẶN CỔNG (Port 102 closed): Thiết bị {ip} có phản hồi ping, nhưng KHÔNG mở cổng PLC S7.\n→ Thiết bị này không phải là PLC, hoặc bạn bị Tường lửa (Firewall) chặn cổng 102."
            
        # 4. Port mở nhưng Snap7 vẫn lỗi -> Lỗi quyền truy cập PLC
        err_lower = original_error.lower()
        if "refused" in err_lower or "reset" in err_lower or "iso" in err_lower:
            return f"BỊ TỪ CHỐI TRUY CẬP (Connection Refused): PLC đang chặn kết nối ngoài.\n→ 1. Bạn nhập sai Rack={rack} / Slot={slot} (S7-1200 thường là 0/1).\n→ 2. Bạn CHƯA BẬT 'Permit access with PUT/GET' trong TIA Portal."
            
        return f"LỖI GIAO THỨC SNAP7: {original_error}"

    def disconnect(self):
        """Ngắt kết nối."""
        if self.connected and self.client:
            self.client.disconnect()
        self.connected = False

    def write_bit(self, byte_addr, bit_addr, value: bool):
        """Ghi giá trị True/False vào 1 bit của vùng nhớ M."""
        if not self.connected:
            return False
        try:
            data = self.client.read_area(self._s7t.Areas.MK, 0, byte_addr, 1)
            self._snap7_lib.util.set_bool(data, 0, bit_addr, value)
            self.client.write_area(self._s7t.Areas.MK, 0, byte_addr, data)
            return True
        except Exception as e:
            print(f"[PLC] Error writing bit M{byte_addr}.{bit_addr}: {e}")
            return False

    def write_db_bit(self, db_number, byte_addr, bit_addr, value: bool):
        """Ghi giá trị True/False vào 1 bit của khối DB."""
        if not self.connected:
            return False, "Chưa kết nối PLC"
        try:
            data = self.client.read_area(self._s7t.Areas.DB, db_number, byte_addr, 1)
            self._snap7_lib.util.set_bool(data, 0, bit_addr, value)
            self.client.write_area(self._s7t.Areas.DB, db_number, byte_addr, data)
            return True, "Thành công"
        except Exception as e:
            return False, f"Lỗi Snap7/Network khi ghi DB{db_number}.DBX{byte_addr}.{bit_addr}: {e}"

    def read_counters(self):
        """Đọc bộ đếm từ DB1.DBW2, DB1.DBW4, DB1.DBW6."""
        if not self.connected:
            return None
        try:
            # Đọc 6 byte từ DB1 bắt đầu từ offset 2
            data = self.client.read_area(self._s7t.Areas.DB, self.PLC_DB_NUMBER, self.PLC_DB_COUNTER_START, 6)
            grade1 = self._snap7_lib.util.get_int(data, 0)
            grade2 = self._snap7_lib.util.get_int(data, 2)
            grade3 = self._snap7_lib.util.get_int(data, 4)
            return grade1, grade2, grade3
        except Exception as e:
            print(f"[PLC] Error reading counters from DB: {e}")
            return None

    def start_machine(self):
        """Ghi DB1.DBX0.0 = True."""
        return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_START_BYTE, self.PLC_START_BIT, True)

    def stop_machine(self):
        """Ghi DB1.DBX0.1 = True."""
        return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_STOP_BYTE, self.PLC_STOP_BIT, True)

    def set_grade(self, grade):
        """Bật bit phân loại (Gửi tín hiệu đẩy xi lanh)."""
        if not self.connected:
            return False, "Chưa kết nối PLC"

        # 1. Reset
        reset_ok, msg = self.reset_grades()
        if not reset_ok:
            return False, msg

        # 2. Set
        if grade == "Grade-1":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE1, True)
        elif grade == "Grade-2":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE2, True)
        elif grade == "Grade-3":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE3, True)
        return False, f"Hạng không hợp lệ: {grade}"

    def reset_grades(self):
        """Tắt tất cả các bit phân loại trong DB1.DBX0.2 -> DBX0.4."""
        if not self.connected:
            return False, "Chưa kết nối PLC"
        try:
            # Đọc byte 0 của DB1
            data = self.client.read_area(self._s7t.Areas.DB, self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, 1)
            # Tắt 3 bit phân loại
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE1, False)
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE2, False)
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE3, False)
            # Ghi lại vào DB
            self.client.write_area(self._s7t.Areas.DB, self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, data)
            return True, "Thành công"
        except Exception as e:
            return False, f"Lỗi đọc/ghi khi reset: {e}"

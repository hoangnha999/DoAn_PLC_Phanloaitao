class PLCManager:
    """Module quản lý kết nối và điều khiển PLC S7-1200 qua Snap7."""

    # Cờ lớp để chỉ in cảnh báo thiếu snap7 duy nhất 1 lần cho toàn ứng dụng.
    _warned_missing_snap7 = False

    # ─── PLC 1214C Control (Data Block DB10 theo sơ đồ hiện tại) ───
    # Số DB chính để trao đổi dữ liệu phân loại/cảm biến.
    PLC_DB_NUMBER = 10

    # Byte chứa nhóm bit phân loại trong DB10.
    PLC_GRADE_BYTE = 0
    # DB10.DBX0.0 = Grade-1 (Apple_GOOD)
    PLC_BIT_GRADE1 = 0
    # DB10.DBX0.1 = Grade-2 (Apple_MEDIUM)
    PLC_BIT_GRADE2 = 1
    # DB10.DBX0.2 = Grade-3 (Apple_BAD)
    PLC_BIT_GRADE3 = 2

    # DB10.DBX0.3 = tín hiệu trigger camera/chụp ảnh.
    PLC_CAMERA_BIT = 3

    # Bộ đếm đặt từ DB10.DBW2 để không đè lên byte trạng thái ở DB10.DBB0.
    # Sơ đồ đọc: DBW2 (grade1), DBW4 (grade2), DBW6 (grade3).
    PLC_DB_COUNTER_START = 2

    # Số lần retry đọc xác nhận sau khi ghi bit/byte.
    VERIFY_RETRIES = 3

    def __init__(self):
        # Con trỏ client Snap7; sẽ được gán khi import snap7 thành công.
        self.client = None
        # Trạng thái đã kết nối PLC hay chưa.
        self.connected = False
        # Lưu module snap7 để dùng util/set_bool/get_int.
        self._snap7_lib = None

        try:
            # Import thư viện giao tiếp PLC Siemens qua giao thức S7.
            import snap7
            import snap7.type

            # Lưu tham chiếu module để dùng ở các hàm khác.
            self._snap7_lib = snap7
            # Lưu alias vùng nhớ (Areas.DB, Areas.MK, ...).
            self._s7t = snap7.type
            # Tạo client kết nối TCP đến PLC.
            self.client = snap7.client.Client()
        except ImportError:
            # Nếu thiếu thư viện thì chỉ in cảnh báo 1 lần.
            if not PLCManager._warned_missing_snap7:
                print("[PLC] Warning: python-snap7 library is not installed.")
                PLCManager._warned_missing_snap7 = True

    def connect(self, ip, rack, slot):
        """Kết nối tới PLC. Nếu lỗi, tự động chẩn đoán nguyên nhân."""
        # Chặn sớm nếu môi trường chưa cài thư viện snap7.
        if not self._snap7_lib:
            return False, "Chưa cài python-snap7! Chạy: pip install python-snap7"

        try:
            # Gọi connect với bộ tham số chuẩn S7 (ip/rack/slot).
            self.client.connect(ip, rack, slot)
            # Đánh dấu đã kết nối thành công.
            self.connected = True
            return True, f"Connected to {ip}"
        except Exception as e:
            # Kết nối thất bại -> đảm bảo flag trở về False.
            self.connected = False
            # Chạy quy trình chẩn đoán để trả thông báo dễ hiểu cho vận hành.
            exact_error = self._diagnose_connection(ip, rack, slot, str(e))
            return False, exact_error

    def _diagnose_connection(self, ip, rack, slot, original_error):
        """Ping + check port 102 + suy luận lỗi cấu hình để báo nguyên nhân."""
        # Import cục bộ để chỉ tải khi cần chẩn đoán lỗi.
        import socket
        import subprocess
        import platform

        # 1) Kiểm tra cú pháp IP trước khi ping.
        try:
            socket.inet_aton(ip)
        except socket.error:
            return (
                f"ĐỊA CHỈ IP SAI ĐỊNH DẠNG: '{ip}' không hợp lệ. "
                "Vui lòng nhập đúng dạng (VD: 192.168.0.1)"
            )

        # 2) Ping kiểm tra thiết bị có hiện diện trên mạng hay không.
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = [
            "ping",
            param,
            "1",
            "-w",
            "1000" if platform.system().lower() == "windows" else "1",
            ip,
        ]
        try:
            output = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if platform.system().lower() == "windows"
                    else 0
                ),
            )
            # returncode != 0 nghĩa là ping thất bại.
            if output.returncode != 0:
                return (
                    "LỖI PHẦN CỨNG/MẠNG (Ping timeout): "
                    f"Không tìm thấy thiết bị nào ở IP {ip}.\n"
                    "→ Cáp mạng bị tuột, đứt, PLC chưa bật nguồn, "
                    "hoặc máy tính bị sai Subnet/IP tĩnh."
                )
        except Exception:
            # Nếu bản thân lệnh ping lỗi thì bỏ qua và chuyển sang check port.
            pass

        # 3) Check port 102 (S7 communication port).
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Timeout ngắn để không treo UI.
        sock.settimeout(2.0)
        result = sock.connect_ex((ip, 102))
        sock.close()

        # Port đóng -> có thể sai thiết bị hoặc bị firewall chặn.
        if result != 0:
            return (
                "SAI THIẾT BỊ HOẶC CHẶN CỔNG (Port 102 closed): "
                f"Thiết bị {ip} có phản hồi ping, nhưng KHÔNG mở cổng PLC S7.\n"
                "→ Thiết bị này không phải là PLC, hoặc bị Firewall chặn cổng 102."
            )

        # 4) Port mở mà vẫn lỗi -> thường do bị PLC từ chối phiên kết nối.
        err_lower = original_error.lower()
        if "refused" in err_lower or "reset" in err_lower or "iso" in err_lower:
            return (
                "BỊ TỪ CHỐI TRUY CẬP (Connection Refused): PLC đang chặn kết nối ngoài.\n"
                f"→ 1. Bạn nhập sai Rack={rack} / Slot={slot} (S7-1200 thường là 0/1).\n"
                "→ 2. Bạn CHƯA BẬT 'Permit access with PUT/GET' trong TIA Portal."
            )

        # Trường hợp còn lại: trả về lỗi gốc từ Snap7 để kỹ thuật xử lý.
        return f"LỖI GIAO THỨC SNAP7: {original_error}"

    def disconnect(self):
        """Ngắt kết nối PLC và reset cờ trạng thái."""
        # Chỉ gọi disconnect khi đang kết nối và client tồn tại.
        if self.connected and self.client:
            self.client.disconnect()
        # Dù có lỗi ngầm hay không thì luôn hạ cờ connected.
        self.connected = False

    def write_bit(self, byte_addr, bit_addr, value: bool):
        """Ghi True/False vào 1 bit vùng M (Merker)."""
        # Chặn ghi nếu chưa kết nối để tránh exception không cần thiết.
        if not self.connected:
            return False, "Chưa kết nối PLC"
        try:
            # Đọc đúng 1 byte vùng M tại offset byte_addr.
            data = self.client.read_area(self._s7t.Areas.MK, 0, byte_addr, 1)
            # Set bit trong buffer byte cục bộ.
            self._snap7_lib.util.set_bool(data, 0, bit_addr, value)
            # Ghi trả lại nguyên byte đã chỉnh sửa lên PLC.
            self.client.write_area(self._s7t.Areas.MK, 0, byte_addr, data)
            return True, "Thành công"
        except Exception as e:
            # Trả lỗi chi tiết để log/debug.
            return False, f"Lỗi ghi M{byte_addr}.{bit_addr}: {e}"

    def write_db_bit(self, db_number, byte_addr, bit_addr, value: bool):
        """Ghi True/False vào 1 bit của vùng DB."""
        # Chặn ghi khi offline.
        if not self.connected:
            return False, "Chưa kết nối PLC"
        try:
            # Đọc 1 byte tại DBx.DBB(byte_addr).
            data = self.client.read_area(self._s7t.Areas.DB, db_number, byte_addr, 1)
            # Đặt bit mục tiêu trong byte đã đọc.
            self._snap7_lib.util.set_bool(data, 0, bit_addr, value)
            # Ghi byte đã sửa trở lại DB.
            self.client.write_area(self._s7t.Areas.DB, db_number, byte_addr, data)
            return True, "Thành công"
        except Exception as e:
            return False, (
                f"Lỗi Snap7/Network khi ghi DB{db_number}.DBX{byte_addr}.{bit_addr}: {e}"
            )

    def read_counters(self):
        """Đọc 3 bộ đếm từ DB10.DBW2/4/6."""
        # Trả None khi offline để caller biết không có dữ liệu.
        if not self.connected:
            return None
        try:
            # Đọc 6 byte liên tiếp bắt đầu tại offset 2.
            data = self.client.read_area(
                self._s7t.Areas.DB,
                self.PLC_DB_NUMBER,
                self.PLC_DB_COUNTER_START,
                6,
            )
            # Parse DBW2 -> grade1
            grade1 = self._snap7_lib.util.get_int(data, 0)
            # Parse DBW4 -> grade2
            grade2 = self._snap7_lib.util.get_int(data, 2)
            # Parse DBW6 -> grade3
            grade3 = self._snap7_lib.util.get_int(data, 4)
            return grade1, grade2, grade3
        except Exception as e:
            # In log lỗi kỹ thuật, vẫn trả None để app xử lý mềm.
            print(f"[PLC] Error reading counters from DB: {e}")
            return None

    def read_sensor_trigger(self):
        """Đọc bit trigger camera tại DB10.DBX0.3."""
        # Offline -> không có tín hiệu.
        if not self.connected:
            return None
        try:
            # Đọc byte trạng thái DB10.DBB0.
            data = self.client.read_area(
                self._s7t.Areas.DB,
                self.PLC_DB_NUMBER,
                self.PLC_GRADE_BYTE,
                1,
            )
            # Tách đúng bit camera từ byte vừa đọc.
            return self._snap7_lib.util.get_bool(data, 0, self.PLC_CAMERA_BIT)
        except Exception as e:
            print(
                "[PLC] Error reading camera trigger "
                f"DB{self.PLC_DB_NUMBER}.DBX{self.PLC_GRADE_BYTE}.{self.PLC_CAMERA_BIT}: {e}"
            )
            return None

    def _read_grade_bits(self):
        """Đọc trạng thái 3 bit grade trong DB10.DBB0."""
        if not self.connected:
            return None
        try:
            data = self.client.read_area(
                self._s7t.Areas.DB,
                self.PLC_DB_NUMBER,
                self.PLC_GRADE_BYTE,
                1,
            )
            g1 = bool(self._snap7_lib.util.get_bool(data, 0, self.PLC_BIT_GRADE1))
            g2 = bool(self._snap7_lib.util.get_bool(data, 0, self.PLC_BIT_GRADE2))
            g3 = bool(self._snap7_lib.util.get_bool(data, 0, self.PLC_BIT_GRADE3))
            return g1, g2, g3
        except Exception:
            return None

    def _verify_grade_bits(self, expected_tuple):
        """Xác nhận trạng thái bit grade đúng như kỳ vọng sau ghi."""
        import time

        for _ in range(max(1, int(self.VERIFY_RETRIES))):
            current = self._read_grade_bits()
            if current == expected_tuple:
                return True, "Thành công"
            time.sleep(0.02)
        return False, f"Readback mismatch: expected={expected_tuple}, got={current}"

    def set_grade(self, grade):
        """Bật bit phân loại tương ứng (Grade-1/2/3)."""
        # Không cho gửi grade khi chưa có kết nối PLC.
        if not self.connected:
            return False, "Chưa kết nối PLC"

        # Bước 1: reset toàn bộ bit grade để chỉ còn duy nhất 1 bit được bật.
        reset_ok, msg = self.reset_grades()
        if not reset_ok:
            return False, msg

        # Bước 2: bật bit theo grade đầu vào.
        if grade == "Grade-1":
            ok, msg = self.write_db_bit(
                self.PLC_DB_NUMBER,
                self.PLC_GRADE_BYTE,
                self.PLC_BIT_GRADE1,
                True,
            )
            if not ok:
                return False, msg
            return self._verify_grade_bits((True, False, False))
        elif grade == "Grade-2":
            ok, msg = self.write_db_bit(
                self.PLC_DB_NUMBER,
                self.PLC_GRADE_BYTE,
                self.PLC_BIT_GRADE2,
                True,
            )
            if not ok:
                return False, msg
            return self._verify_grade_bits((False, True, False))
        elif grade == "Grade-3":
            ok, msg = self.write_db_bit(
                self.PLC_DB_NUMBER,
                self.PLC_GRADE_BYTE,
                self.PLC_BIT_GRADE3,
                True,
            )
            if not ok:
                return False, msg
            return self._verify_grade_bits((False, False, True))

        # Đầu vào không hợp lệ.
        return False, f"Hạng không hợp lệ: {grade}"

    def reset_grades(self):
        """Tắt các bit phân loại DB10.DBX0.0..DBX0.2."""
        # Chặn thao tác khi offline.
        if not self.connected:
            return False, "Chưa kết nối PLC"
        try:
            # SỬA LỖI RACE CONDITION: Ghi riêng từng bit, không đọc/ghi cả byte 
            # để tránh đè lên trạng thái cảm biến (DB10.DBX0.3) đang thay đổi.
            ok1, _ = self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE1, False)
            ok2, _ = self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE2, False)
            ok3, _ = self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE3, False)
            
            if ok1 and ok2 and ok3:
                return self._verify_grade_bits((False, False, False))
            return False, "Có lỗi khi ghi reset_grades"
        except Exception as e:
            return False, f"Lỗi đọc/ghi khi reset: {e}"

class PLCManager:
    """Module quản lý kết nối và điều khiển PLC S7-1200 qua Snap7."""
    
    # ─── PLC 1214C Control Bits ───
    PLC_START_BYTE = 0 # M0
    PLC_START_BIT  = 0 # .0 -> M0.0
    PLC_STOP_BYTE  = 0 # M0
    PLC_STOP_BIT   = 1 # .1 -> M0.1

    # ─── PLC Tín hiệu phân loại ───
    PLC_GRADE_BYTE = 1 # M1
    PLC_BIT_GOOD   = 0 # .0 -> M1.0
    PLC_BIT_MEDIUM = 1 # .1 -> M1.1
    PLC_BIT_BAD    = 2 # .2 -> M1.2

    # ─── Địa chỉ MW bộ đếm ───
    PLC_MW_GOOD = 10   # MW10

    def __init__(self):
        self.client = None
        self.connected = False
        self._snap7_lib = None
        
        try:
            import snap7
            import snap7.types
            self._snap7_lib = snap7
            self._s7t = snap7.types
            self.client = snap7.client.Client()
        except ImportError:
            print("[PLC] Cảnh báo: Thư viện python-snap7 chưa được cài đặt.")

    def connect(self, ip, rack, slot):
        """Kết nối tới PLC."""
        if not self._snap7_lib:
            return False, "Chưa cài python-snap7! Chạy: pip install python-snap7"
            
        try:
            self.client.connect(ip, rack, slot)
            self.connected = True
            return True, f"Kết nối thành công tới {ip}"
        except Exception as e:
            self.connected = False
            return False, str(e)

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
            print(f"[PLC] Lỗi ghi bit M{byte_addr}.{bit_addr}: {e}")
            return False

    def read_counters(self):
        """Đọc bộ đếm từ MW10, MW12, MW14."""
        if not self.connected:
            return None
        try:
            data = self.client.read_area(self._s7t.Areas.MK, 0, self.PLC_MW_GOOD, 6)
            good = self._snap7_lib.util.get_int(data, 0)
            medium = self._snap7_lib.util.get_int(data, 2)
            bad = self._snap7_lib.util.get_int(data, 4)
            return good, medium, bad
        except Exception as e:
            print(f"[PLC] Lỗi đọc bộ đếm: {e}")
            return None

    def start_machine(self):
        """Ghi M0.0 = True."""
        return self.write_bit(self.PLC_START_BYTE, self.PLC_START_BIT, True)

    def stop_machine(self):
        """Ghi M0.1 = True."""
        return self.write_bit(self.PLC_STOP_BYTE, self.PLC_STOP_BIT, True)

    def set_grade(self, grade):
        """Bật bit phân loại (Gửi tín hiệu đẩy xi lanh)."""
        if not self.connected:
            return False

        # 1. Reset
        self.reset_grades()

        # 2. Set
        if grade == "GOOD":
            return self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_GOOD, True)
        elif grade == "MEDIUM":
            return self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_MEDIUM, True)
        elif grade == "BAD":
            return self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_BAD, True)
        return False

    def reset_grades(self):
        """Tắt tất cả các bit phân loại."""
        if not self.connected:
            return False
        self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_GOOD, False)
        self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_MEDIUM, False)
        self.write_bit(self.PLC_GRADE_BYTE, self.PLC_BIT_BAD, False)
        return True

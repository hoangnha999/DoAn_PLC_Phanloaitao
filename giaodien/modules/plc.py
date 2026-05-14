class PLCManager:
    """Module quản lý kết nối và điều khiển PLC S7-1200 qua Snap7."""
    
    # ─── PLC 1214C Control (Data Block DB1) ───
    PLC_DB_NUMBER = 1
    
    # Nút nhấn (Offset 0.0 - 0.1)
    PLC_START_BYTE = 0 
    PLC_START_BIT  = 0
    PLC_STOP_BYTE  = 0 
    PLC_STOP_BIT   = 1

    # Tín hiệu phân loại (Offset 0.2 - 0.4)
    PLC_GRADE_BYTE = 0 
    PLC_BIT_GRADE1 = 2 
    PLC_BIT_GRADE2 = 3 
    PLC_BIT_GRADE3 = 4 

    # Địa chỉ Bộ đếm (Offset 2, 4, 6 trong DB1)
    PLC_DB_COUNTER_START = 2   # DB1.DBW2, DB1.DBW4, DB1.DBW6

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
        """Kết nối tới PLC."""
        if not self._snap7_lib:
            return False, "Chưa cài python-snap7! Chạy: pip install python-snap7"
            
        try:
            self.client.connect(ip, rack, slot)
            self.connected = True
            return True, f"Connected to {ip}"
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
            print(f"[PLC] Error writing bit M{byte_addr}.{bit_addr}: {e}")
            return False

    def write_db_bit(self, db_number, byte_addr, bit_addr, value: bool):
        """Ghi giá trị True/False vào 1 bit của khối DB."""
        if not self.connected:
            return False
        try:
            data = self.client.read_area(self._s7t.Areas.DB, db_number, byte_addr, 1)
            self._snap7_lib.util.set_bool(data, 0, bit_addr, value)
            self.client.write_area(self._s7t.Areas.DB, db_number, byte_addr, data)
            return True
        except Exception as e:
            print(f"[PLC] Error writing DB{db_number}.DBX{byte_addr}.{bit_addr}: {e}")
            return False

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
            return False

        # 1. Reset
        self.reset_grades()

        # 2. Set
        if grade == "Grade-1":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE1, True)
        elif grade == "Grade-2":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE2, True)
        elif grade == "Grade-3":
            return self.write_db_bit(self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, self.PLC_BIT_GRADE3, True)
        return False

    def reset_grades(self):
        """Tắt tất cả các bit phân loại trong DB1.DBX0.2 -> DBX0.4."""
        if not self.connected:
            return False
        try:
            # Đọc byte 0 của DB1
            data = self.client.read_area(self._s7t.Areas.DB, self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, 1)
            # Tắt 3 bit phân loại
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE1, False)
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE2, False)
            self._snap7_lib.util.set_bool(data, 0, self.PLC_BIT_GRADE3, False)
            # Ghi lại vào DB
            self.client.write_area(self._s7t.Areas.DB, self.PLC_DB_NUMBER, self.PLC_GRADE_BYTE, data)
            return True
        except Exception as e:
            print(f"[PLC] Error resetting grades in DB: {e}")
            return False

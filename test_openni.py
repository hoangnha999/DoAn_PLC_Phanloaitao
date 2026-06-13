import os
import sys

# Thêm openni vào path
try:
    from openni import openni2
except Exception as e:
    print(f"Loi import openni: {e}")
    sys.exit(1)

redist_dir = r"d:\DOAN_PLC_Phanloaitao\OpenNI2\Redist"
drivers_dir = os.path.join(redist_dir, "OpenNI2", "Drivers")

if os.name == "nt":
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(redist_dir)
        os.add_dll_directory(drivers_dir)
    os.environ["OPENNI2_DRIVERS_PATH"] = drivers_dir

print(f"Redist: {redist_dir}")
print(f"Drivers: {drivers_dir}")

try:
    openni2.initialize(redist_dir)
    print("Initialize OK")
except Exception as e:
    print(f"Loi initialize: {e}")
    sys.exit(1)

try:
    dev = openni2.Device.open_any()
    print("Device info:", dev.get_device_info())
    depth_stream = dev.create_depth_stream()
    depth_stream.start()
    frm = depth_stream.read_frame()
    if frm is None:
        print("Frame None")
    else:
        print("Frame doc thanh cong, width:", frm.width, "height:", frm.height)
    depth_stream.stop()
    dev.close()
    openni2.unload()
except Exception as e:
    print(f"Loi device/stream: {e}")

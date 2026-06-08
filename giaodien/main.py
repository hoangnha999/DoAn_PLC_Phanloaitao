import os
# Sửa lỗi 'Assertion fctx->async_lock failed' của FFmpeg trên Windows
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "threads;1"
# Giảm log WARN nhiễu từ backend camera (đặc biệt DSHOW index probing).
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import tkinter as tk
import traceback
from modules.gui_app import FruitClassificationApp

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FruitClassificationApp(root)
        root.mainloop()
    except Exception:
        print("[FATAL] Ung dung thoat do loi startup:")
        traceback.print_exc()
        raise

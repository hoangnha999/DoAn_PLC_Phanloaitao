import os
# Sửa lỗi 'Assertion fctx->async_lock failed' của FFmpeg trên Windows
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "threads;1"

import tkinter as tk
from modules.gui_app import FruitClassificationApp

if __name__ == "__main__":
    root = tk.Tk()
    app = FruitClassificationApp(root)
    root.mainloop()

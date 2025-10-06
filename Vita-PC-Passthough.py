import sys
import cv2
import os
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class CameraApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("PSVita")
        self.setGeometry(100, 100, 896, 504)
        self.resize(896, 504)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: black;")
        self.setWindowIcon(QIcon(resource_path("psvita.ico")))

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.label)

        self.cap = None
        self.current_camera = 0

        self.resolutions = [(896, 504), (960, 544), (480, 272)]
        self.current_res_index = 0

        self.start_camera(0)

        self.upscaling = False
        self.overlay_mode = None
        self.overlays = {
            "vita2000": {"file": "vita.png", "rect": (221, 64, 858, 424)},
            "vita1000": {"file": "vita1.png", "rect": (213, 53, 866, 426)},
            "psp": {"file": "psp.png", "rect": (238, 68, 845, 414)}
        }

        self.current_mic = 0
        self.audio_stream = None
        self.start_audio_loopback(self.current_mic)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def start_camera(self, index):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if self.cap.isOpened():
            w, h = self.resolutions[self.current_res_index]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            print(f"Camera {index} started at {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
        else:
            print(f"Failed to open camera {index}")

    def start_audio_loopback(self, mic_index):
        if self.audio_stream is not None:
            self.audio_stream.close()
            self.audio_stream = None

        def callback(indata, outdata, frames, time, status):
            outdata[:] = indata

        try:
            self.audio_stream = sd.Stream(
                device=(mic_index, None),
                channels=1,
                samplerate=44100,
                dtype='float32',
                callback=callback
            )
            self.audio_stream.start()
        except Exception as e:
            print(f"Audio loopback error: {e}")

    def keyPressEvent(self, event):
        key = event.key()

        if Qt.Key_1 <= key <= Qt.Key_5:
            cam_index = key - Qt.Key_1
            new_cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
            if new_cap.isOpened():
                if self.cap:
                    self.cap.release()
                self.cap = new_cap
                self.current_camera = cam_index
                self.overlay_mode = None
                w, h = self.resolutions[self.current_res_index]
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                print(f"Switched to camera {cam_index} at {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            else:
                print(f"Camera {cam_index} not available")

        elif Qt.Key_6 <= key <= Qt.Key_8:
            mic_index = key - Qt.Key_6
            self.current_mic = mic_index
            self.start_audio_loopback(self.current_mic)
            print(f"Switched to mic {mic_index}")

        elif key == Qt.Key_9:
            if self.overlay_mode is None:
                self.upscaling = not self.upscaling
                print(f"Upscaling {'enabled' if self.upscaling else 'disabled'}")
            else:
                print("Cannot upscale while overlay is active")

        elif key == Qt.Key_0:
            self.toggle_overlay("vita2000")
        elif key == Qt.Key_Minus:
            self.toggle_overlay("vita1000")
        elif key == Qt.Key_Equal:
            self.toggle_overlay("psp")

        elif key == Qt.Key_BracketLeft:  
            self.current_res_index = (self.current_res_index - 1) % len(self.resolutions)
            w, h = self.resolutions[self.current_res_index]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            print(f"Resolution set to {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        elif key == Qt.Key_BracketRight:  
            self.current_res_index = (self.current_res_index + 1) % len(self.resolutions)
            w, h = self.resolutions[self.current_res_index]
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            print(f"Resolution set to {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

        elif key == Qt.Key_F11:  
            if self.isFullScreen():
                self.showNormal()
                print("Exited fullscreen")
            else:
                self.showFullScreen()
                print("Entered fullscreen")

        super().keyPressEvent(event)


    def toggle_overlay(self, mode):
        if self.overlay_mode == mode:
            print(f"Overlay {mode} disabled")
            self.overlay_mode = None
        else:
            self.overlay_mode = mode
            self.upscaling = False
            print(f"Overlay set to {mode}, upscaling disabled")

    def update_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            return

        if self.overlay_mode:
            overlay_conf = self.overlays[self.overlay_mode]
            overlay_img = cv2.imread(resource_path(overlay_conf["file"]), cv2.IMREAD_UNCHANGED)
            if overlay_img is None:
                return

            x1, y1, x2, y2 = overlay_conf["rect"]
            screen_w, screen_h = x2 - x1, y2 - y1
            cam_frame = cv2.resize(frame, (screen_w, screen_h), interpolation=cv2.INTER_LINEAR)

            if overlay_img.shape[2] == 3:
                overlay_img = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2BGRA)

            combined = overlay_img.copy()
            combined[y1:y2, x1:x2, :3] = cam_frame
            rgb_image = cv2.cvtColor(combined, cv2.COLOR_BGRA2RGBA)
        else:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb_image.shape
        qimg = QImage(rgb_image.data, w, h, ch * w,
                      QImage.Format_RGB888 if ch == 3 else QImage.Format_RGBA8888)

        pix = QPixmap.fromImage(qimg).scaled(
            self.label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation if self.upscaling else Qt.FastTransformation
        )
        self.label.setPixmap(pix)

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        if self.audio_stream is not None:
            self.audio_stream.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraApp()
    window.show()
    sys.exit(app.exec_())

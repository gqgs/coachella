import sys
import os

# --- BOOTSTRAP: Set environment variables and relaunch if necessary ---
# This must happen before ANY other imports (even locale) to ensure C-libraries 
# like libmpv and Qt pick up the environment correctly.
if "COACHELLA_BOOTSTRAP" not in os.environ:
    os.environ["LC_NUMERIC"] = "C"
    os.environ["LC_ALL"] = "C"
    os.environ["COACHELLA_BOOTSTRAP"] = "1"
    
    # Also try to fix LD_LIBRARY_PATH if we are in a venv with PySide6
    # This avoids importing PySide6 before the relaunch
    try:
        # Simple heuristic to find PySide6 in venv without importing
        potential_path = None
        for path in sys.path:
            if "site-packages" in path:
                test_path = os.path.join(path, "PySide6", "Qt", "lib")
                if os.path.exists(test_path):
                    potential_path = test_path
                    break
        
        if potential_path:
            current_ld = os.environ.get("LD_LIBRARY_PATH", "")
            if potential_path not in current_ld:
                os.environ["LD_LIBRARY_PATH"] = potential_path + (":" + current_ld if current_ld else "")
    except Exception:
        pass

    os.execv(sys.executable, [sys.executable] + sys.argv)

# If we reached here, we are in the bootstrapped process
import locale
try:
    locale.setlocale(locale.LC_NUMERIC, 'C')
    locale.setlocale(locale.LC_ALL, 'C')
except Exception:
    pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QPixmap, QIcon, QFont, QPalette, QColor
import mpv

STREAM_DATA = [
    {"id": "2NA7XUw51oo", "name": "Main Stage"},
    {"id": "MdUBm8G41ZU", "name": "Outdoor Theatre"},
    {"id": "NlrpPqb0vwo", "name": "Sahara"},
    {"id": "HJVG2Ck3uuk", "name": "Mojave"},
    {"id": "4C5p1tdRv6c", "name": "Gobi"},
    {"id": "OGNPnQViI3g", "name": "Sonora"},
    {"id": "1KANGsDaRvw", "name": "Yuma"}
]

class ClickableLabel(QLabel):
    clicked = Signal(int)
    def __init__(self, index, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

class MpvWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.container = QWidget(self)
        self.container.setStyleSheet("background-color: black;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container)

        wid = int(self.container.winId())
        # We pass log_handler=print to see what's happening if it still fails
        self.player = mpv.MPV(wid=str(wid),
                              vo='gpu',
                              ytdl=True,
                              input_default_bindings=True,
                              input_vo_keyboard=True)
        
    def play(self, url):
        self.player.play(url)

    def toggle_fullscreen(self):
        self.player.fullscreen = not self.player.fullscreen

    def mouseDoubleClickEvent(self, event):
        self.toggle_fullscreen()

class CoachellaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coachella 2026")
        self.setStyleSheet("background-color: black; color: white;")
        self.resize(1280, 720)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(40)

        # Left Column
        left_column = QVBoxLayout()
        left_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.title_label = QLabel("")
        self.title_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: white;")
        self.title_label.setWordWrap(True)
        left_column.addWidget(self.title_label)

        channel_label = QLabel("Coachella")
        channel_label.setFont(QFont("Arial", 14))
        channel_label.setStyleSheet("color: #AAAAAA; margin-top: 10px;")
        left_column.addWidget(channel_label)

        watch_btn = QPushButton("Watch live")
        watch_btn.setFixedSize(120, 40)
        watch_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid white;
                border-radius: 20px;
                color: white;
                font-weight: bold;
                margin-top: 30px;
            }
            QPushButton:hover {
                background-color: white;
                color: black;
            }
        """)
        left_column.addWidget(watch_btn)

        left_column.addStretch()

        # Thumbnails Row
        thumbs_layout = QHBoxLayout()
        thumbs_layout.setSpacing(10)
        for i in range(len(STREAM_DATA)):
            thumb = ClickableLabel(i)
            pixmap = QPixmap(f"assets/thumb_{i}.jpg")
            if pixmap.isNull():
                thumb.setText(STREAM_DATA[i]["name"])
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setFixedSize(120, 68)
                thumb.setStyleSheet("border: 1px solid #333; font-size: 10px;")
            else:
                thumb.setPixmap(pixmap.scaled(120, 68, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                thumb.setFixedSize(120, 68)
            thumb.clicked.connect(self.load_stream)
            thumbs_layout.addWidget(thumb)
        
        left_column.addLayout(thumbs_layout)

        main_layout.addLayout(left_column, 1)

        # Right Column (Video)
        self.video_widget = MpvWidget()
        main_layout.addWidget(self.video_widget, 2)

        # Initial stream
        self.load_stream(2) # Default to Sahara

    def load_stream(self, index):
        data = STREAM_DATA[index]
        self.title_label.setText(f"{data['name']} - Live from Coachella 2026")
        url = f"https://www.youtube.com/watch?v={data['id']}"
        self.video_widget.play(url)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F:
            self.video_widget.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            if self.video_widget.player.fullscreen:
                self.video_widget.player.fullscreen = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoachellaApp()
    window.show()
    sys.exit(app.exec())

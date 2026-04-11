import sys
import os
import locale
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from datetime import timezone, timedelta
    PDT = timezone(timedelta(hours=-7))
else:
    PDT = ZoneInfo("America/Los_Angeles")

# --- BOOTSTRAP: Set environment variables and relaunch if necessary ---
if "COACHELLA_BOOTSTRAP" not in os.environ:
    os.environ["LC_NUMERIC"] = "C"
    os.environ["LC_ALL"] = "C"
    os.environ["COACHELLA_BOOTSTRAP"] = "1"
    
    try:
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
try:
    locale.setlocale(locale.LC_NUMERIC, 'C')
    locale.setlocale(locale.LC_ALL, 'C')
except Exception:
    pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen
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
        self.setFixedSize(140, 80)
        self.setSelected(False)

    def setSelected(self, selected):
        if selected:
            self.setStyleSheet("border: 4px solid white; border-radius: 4px;")
        else:
            self.setStyleSheet("border: 2px solid rgba(255, 255, 255, 50); border-radius: 4px;")

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

class CoachellaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coachella 2026")
        self.resize(1280, 720)

        # Initialize mpv player in its own window
        self.player = mpv.MPV(
            vo='gpu',
            ytdl=True,
            input_default_bindings=True,
            input_vo_keyboard=True
        )

        # Load schedule image
        self.schedule_pixmap = QPixmap("schedule.jpg")
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background: transparent;")
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        
        # Spacer to push thumbnails to bottom
        main_layout.addStretch()

        # Thumbnails Row
        self.thumbs_layout = QHBoxLayout()
        self.thumbs_layout.setSpacing(15)
        self.thumbs_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.thumb_widgets = []
        for i in range(len(STREAM_DATA)):
            thumb = ClickableLabel(i)
            pixmap = QPixmap(f"assets/thumb_{i}.jpg")
            if not pixmap.isNull():
                # Scale slightly smaller than label to fit border
                thumb.setPixmap(pixmap.scaled(132, 72, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                thumb.setText(STREAM_DATA[i]["name"])
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setStyleSheet(thumb.styleSheet() + " color: white; background: rgba(0,0,0,150); font-size: 10px;")
            
            thumb.clicked.connect(self.load_stream)
            self.thumbs_layout.addWidget(thumb)
            self.thumb_widgets.append(thumb)
        
        main_layout.addLayout(self.thumbs_layout)

        # Timer to update timeline every minute
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(60000)

        # Initial stream
        self.load_stream(2) # Default to Sahara

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw background schedule image
        if not self.schedule_pixmap.isNull():
            scaled_pix = self.schedule_pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled_pix.width()) // 2
            y = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)
            
            # --- Timeline Calculation ---
            scale_factor = scaled_pix.height() / 1350.0
            y_offset_in_scaled = y
            y_4pm_scaled = 210 * scale_factor
            y_12am_scaled = 1205 * scale_factor
            pixels_per_hour = (y_12am_scaled - y_4pm_scaled) / 8.0
            
            try:
                now_pdt = datetime.now(PDT)
            except:
                from datetime import timezone, timedelta
                now_pdt = datetime.now(timezone(timedelta(hours=-7)))
            
            hour = now_pdt.hour
            if hour < 4:
                hour += 24
            
            hours_since_4pm = (hour - 16) + (now_pdt.minute / 60.0)
            
            if 0 <= hours_since_4pm <= 10:
                line_y = y_offset_in_scaled + y_4pm_scaled + (hours_since_4pm * pixels_per_hour)
                pen = QPen(QColor(255, 0, 0, 200))
                pen.setWidth(4)
                painter.setPen(pen)
                painter.drawLine(0, int(line_y), self.width(), int(line_y))
                
                # Draw LIVE indicator
                painter.setPen(QColor(255, 0, 0))
                painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                painter.drawText(20, int(line_y) - 10, f"LIVE {now_pdt.strftime('%H:%M')} PDT")

    def load_stream(self, index):
        # Update UI selection
        for i, thumb in enumerate(self.thumb_widgets):
            thumb.setSelected(i == index)
            
        # Play in separate window
        data = STREAM_DATA[index]
        url = f"https://www.youtube.com/watch?v={data['id']}"
        self.player.play(url)
        # Update mpv window title
        self.player.title = f"{data['name']} - Live from Coachella 2026"

    def closeEvent(self, event):
        self.player.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoachellaApp()
    window.show()
    sys.exit(app.exec())

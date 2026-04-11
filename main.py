import sys
import os
import json
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
    except Exception: pass
    os.execv(sys.executable, [sys.executable] + sys.argv)

try:
    locale.setlocale(locale.LC_NUMERIC, 'C')
    locale.setlocale(locale.LC_ALL, 'C')
except Exception: pass

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush
import mpv

PIXELS_PER_HOUR = 150
START_HOUR = 16 # 4 PM
END_HOUR = 25   # 1 AM next day
COLUMN_WIDTH = 180
TIME_COLUMN_WIDTH = 80 # Increased to prevent overflow

class StageHeader(QWidget):
    def __init__(self, stages, parent=None):
        super().__init__(parent)
        self.stages = stages
        self.setFixedHeight(50)
        self.setFixedWidth(TIME_COLUMN_WIDTH + (len(self.stages) * COLUMN_WIDTH))
        self.selected_index = -1

    def setSelected(self, index):
        self.selected_index = index
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Spacer for time column
        painter.fillRect(0, 0, TIME_COLUMN_WIDTH, self.height(), QColor("#121212"))

        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH)
            color = QColor(stage["color"])
            
            # Header Background
            painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), color)
            
            # Selection indicator in header
            if i == self.selected_index:
                painter.setPen(QPen(Qt.GlobalColor.white, 4))
                painter.drawRect(x + 2, 2, COLUMN_WIDTH - 4, self.height() - 4)

            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(QRect(x, 0, COLUMN_WIDTH, self.height()), Qt.AlignmentFlag.AlignCenter, stage["name"])

class ScheduleGrid(QWidget):
    columnClicked = Signal(int)
    
    def __init__(self, schedule_data, stages, parent=None):
        super().__init__(parent)
        self.schedule_data = schedule_data
        self.stages = stages
        self.selected_index = -1
        self.setFixedWidth(TIME_COLUMN_WIDTH + (len(self.stages) * COLUMN_WIDTH))
        self.setFixedHeight((END_HOUR - START_HOUR) * PIXELS_PER_HOUR + 50)
        self.setMouseTracking(True)
        
    def setSelected(self, index):
        self.selected_index = index
        self.update()

    def mouseMoveEvent(self, event):
        # Change cursor to pointing hand if over a stage column
        if event.pos().x() > TIME_COLUMN_WIDTH:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        x = event.pos().x()
        if x > TIME_COLUMN_WIDTH:
            col = (x - TIME_COLUMN_WIDTH) // COLUMN_WIDTH
            if 0 <= col < len(self.stages):
                self.columnClicked.emit(col)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor("#121212"))
        
        # Draw columns
        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH)
            base_color = QColor(stage["color"]).darker(300)
            
            # Highlight selected column
            if i == self.selected_index:
                painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), base_color.lighter(150))
                painter.setPen(QPen(QColor(stage["color"]), 2))
                painter.drawRect(x, 0, COLUMN_WIDTH, self.height())
            else:
                painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), base_color)

        # Draw time labels
        painter.setFont(QFont("Arial", 10))
        for h in range(START_HOUR, END_HOUR + 1):
            y = (h - START_HOUR) * PIXELS_PER_HOUR
            display_h = h if h <= 12 else h - 12
            if h >= 24: display_h = h - 24
            if display_h == 0: display_h = 12
            ampm = "PM" if h < 24 and h >= 12 else "AM"
            time_str = f"{display_h} {ampm}"
            
            painter.setPen(QColor("#AAAAAA"))
            painter.drawText(QRect(5, y - 10, TIME_COLUMN_WIDTH - 15, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, time_str)
            
            # Grid line
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.drawLine(TIME_COLUMN_WIDTH, y, self.width(), y)

        # Draw Artist Boxes
        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH) + 5
            artists = self.schedule_data.get(stage["name"], [])
            for entry in artists:
                try:
                    def to_float_hour(t_str):
                        h, m = map(int, t_str.split(':'))
                        return h + m/60.0
                    
                    s_h = to_float_hour(entry["start"])
                    e_h = to_float_hour(entry.get("end", entry["start"]))
                    
                    y_start = (s_h - START_HOUR) * PIXELS_PER_HOUR
                    y_end = (e_h - START_HOUR) * PIXELS_PER_HOUR
                    
                    rect = QRect(x, int(y_start), COLUMN_WIDTH - 10, int(y_end - y_start))
                    
                    painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(rect, 5, 5)
                    
                    if i == self.selected_index:
                        painter.setPen(QPen(QColor(stage["color"]), 2))
                        painter.drawRoundedRect(rect, 5, 5)

                    painter.setPen(Qt.GlobalColor.black)
                    painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    painter.drawText(rect.adjusted(8, 8, -8, -20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, entry["artist"])
                    
                    painter.setFont(QFont("Arial", 9))
                    painter.drawText(rect.adjusted(8, 0, -8, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, f"{entry['start']}-{entry.get('end', '??')}")
                except Exception: pass


        # --- Draw Timeline ---
        try:
            now_pdt = datetime.now(PDT)
        except:
            from datetime import timezone, timedelta
            now_pdt = datetime.now(timezone(timedelta(hours=-7)))
        
        hour = now_pdt.hour
        if hour < 4: hour += 24
        current_time_float = hour + (now_pdt.minute / 60.0)
        
        if START_HOUR <= current_time_float <= END_HOUR:
            line_y = (current_time_float - START_HOUR) * PIXELS_PER_HOUR
            painter.setPen(QPen(QColor(255, 0, 0), 3))
            painter.drawLine(TIME_COLUMN_WIDTH, int(line_y), self.width(), int(line_y))
            
            # Label - adjusted width and padding to prevent overflow
            label_text = f"LIVE {now_pdt.strftime('%-I:%M %p')}"
            painter.setBrush(QColor(255, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24, 5, 5)
            
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.drawText(QRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24), Qt.AlignmentFlag.AlignCenter, label_text)

class CoachellaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coachella 2026")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #121212; color: white;")

        # Load configuration
        with open("config.json", "r") as f:
            config = json.load(f)
            self.stages = config.get("STAGES", [])

        # Load schedule
        if os.path.exists("schedule.json"):
            with open("schedule.json", "r") as f:
                self.schedule_data = json.load(f)
        else:
            self.schedule_data = {}

        self.player = mpv.MPV(vo='gpu', ytdl=True, input_default_bindings=True, input_vo_keyboard=True)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Fixed Header
        self.header = StageHeader(self.stages)
        main_layout.addWidget(self.header)
        
        # Scrollable Schedule
        self.scroll = QScrollArea()
        self.grid = ScheduleGrid(self.schedule_data, self.stages)
        self.grid.columnClicked.connect(self.load_stream)
        self.scroll.setWidget(self.grid)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none;")
        main_layout.addWidget(self.scroll)

        # Sync header horizontal scrolling with grid
        self.scroll.horizontalScrollBar().valueChanged.connect(self.sync_header)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.grid.update)
        self.timer.start(60000)

        self.load_stream(2) # Default to Sahara

    def sync_header(self, value):
        self.header.move(-value, 0)

    def load_stream(self, index):
        if not (0 <= index < len(self.stages)):
            return
        self.grid.setSelected(index)
        self.header.setSelected(index)
        data = self.stages[index]
        self.player.play(data["url"])
        self.player.title = f"{data['name']} - Coachella 2026"


    def closeEvent(self, event):
        self.player.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoachellaApp()
    window.show()
    sys.exit(app.exec())

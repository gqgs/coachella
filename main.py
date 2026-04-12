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
    QLabel, QScrollArea, QFrame, QStackedWidget, QPushButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush
import mpv
from sabr_bridge import SabrBridge, is_sabr_height, build_sabr_format

PIXELS_PER_HOUR = 150
START_HOUR = 16 # 4 PM
END_HOUR = 25   # 1 AM next day
COLUMN_WIDTH = 180
TIME_COLUMN_WIDTH = 80
MAX_SABR_RECONNECT_ATTEMPTS = 10
SABR_RECONNECT_BASE_DELAY_MS = 1500

class QualityButton(QPushButton):
    def __init__(self, label, height_val, parent=None):
        super().__init__(label, parent)
        self.height_val = height_val
        self.setCheckable(True)
        self.setFixedSize(55, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: #222;
                color: #888;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #333; color: #CCC; }
            QPushButton:checked {
                background: #555;
                color: white;
                border: 1px solid white;
            }
        """)

class DayButton(QPushButton):
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedSize(90, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: #333;
                color: #AAA;
                border: none;
                border-radius: 0;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #444; color: #DDD; }
            QPushButton:checked {
                background: #555;
                color: white;
            }
        """)

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
        painter.fillRect(0, 0, TIME_COLUMN_WIDTH, self.height(), QColor("#121212"))
        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH)
            color = QColor(stage["color"])
            painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), color)
            if i == self.selected_index:
                painter.setPen(QPen(Qt.GlobalColor.white, 4))
                painter.drawRect(x + 2, 2, COLUMN_WIDTH - 4, self.height() - 4)
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(QRect(x, 0, COLUMN_WIDTH, self.height()), Qt.AlignmentFlag.AlignCenter, stage["name"])

class ScheduleGrid(QWidget):
    columnClicked = Signal(int)
    
    def __init__(self, day_name, day_schedule, stages, app_ref, parent=None):
        super().__init__(parent)
        self.day_name = day_name
        self.day_schedule = day_schedule
        self.stages = stages
        self.app_ref = app_ref
        self.selected_index = -1
        self.setFixedWidth(TIME_COLUMN_WIDTH + (len(self.stages) * COLUMN_WIDTH))
        self.setFixedHeight((END_HOUR - START_HOUR) * PIXELS_PER_HOUR + 50)
        self.setMouseTracking(True)
        
    def setSelected(self, index):
        self.selected_index = index
        self.update()

    def mouseMoveEvent(self, event):
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
        painter.fillRect(self.rect(), QColor("#121212"))
        
        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH)
            base_color = QColor(stage["color"]).darker(300)
            if i == self.selected_index:
                painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), base_color.lighter(150))
                painter.setPen(QPen(QColor(stage["color"]), 2))
                painter.drawRect(x, 0, COLUMN_WIDTH, self.height())
            else:
                painter.fillRect(x, 0, COLUMN_WIDTH, self.height(), base_color)

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
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.drawLine(TIME_COLUMN_WIDTH, y, self.width(), y)

        for i, stage in enumerate(self.stages):
            x = TIME_COLUMN_WIDTH + (i * COLUMN_WIDTH) + 5
            artists = self.day_schedule.get(stage["name"], [])
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

        # Timeline logic: Only draw if this tab's day matches the current system day
        try:
            now_pdt = datetime.now(PDT)
        except:
            from datetime import timezone, timedelta
            now_pdt = datetime.now(timezone(timedelta(hours=-7)))
        
        current_day_name = now_pdt.strftime('%A')
        
        if self.day_name.lower() == current_day_name.lower():
            hour = now_pdt.hour
            if hour < 4: hour += 24
            current_time_float = hour + (now_pdt.minute / 60.0)
            
            if START_HOUR <= current_time_float <= END_HOUR:
                line_y = (current_time_float - START_HOUR) * PIXELS_PER_HOUR
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.drawLine(TIME_COLUMN_WIDTH, int(line_y), self.width(), int(line_y))
                
                is_recording = getattr(self.app_ref, "is_recording", False)
                blink_on = getattr(self.app_ref, "blink_on", True)
                if is_recording and blink_on:
                    label_text = "🔴 RECORDING"
                    bg_color = QColor(200, 0, 0)
                else:
                    label_text = f"LIVE {now_pdt.strftime('%-I:%M %p')}"
                    bg_color = QColor(255, 0, 0)
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24, 5, 5)
                painter.setPen(Qt.GlobalColor.white)
                painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
                painter.drawText(QRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24), Qt.AlignmentFlag.AlignCenter, label_text)

class CoachellaApp(QMainWindow):
    sabrPlaybackEnded = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coachella 2026")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #121212; color: white;")

        self.is_recording = False
        self.blink_on = True
        self.current_stage_index = 2 # Sahara default
        self.sabr_reconnect_attempts = 0

        with open("config.json", "r") as f:
            config = json.load(f)
            self.stages = config.get("STAGES", [])

        if os.path.exists("schedule.json"):
            with open("schedule.json", "r") as f:
                self.schedule_data = json.load(f)
        else:
            self.schedule_data = {}

        self.player = mpv.MPV(vo='gpu', ytdl=True, input_default_bindings=True, input_vo_keyboard=True, log_handler=print)
        # Use the bundled yt-dlp build so mpv and the sync scripts resolve YouTube the same way.
        ytdl_name = "yt-dlp_sabr.exe" if sys.platform.startswith("win") else "yt-dlp_sabr"
        self.ytdl_path = os.path.abspath(ytdl_name)
        self.player['script-opts'] = 'ytdl_hook-ytdl_path=' + self.ytdl_path
        self.sabr_bridge = SabrBridge(self.ytdl_path)

        # Use exact string from working manual test: player-client=default,tv (with dash)
        # Also MUST set user-agent for both ytdl and mpv to prevent access errors
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.player['user-agent'] = ua
        self.player['ytdl-raw-options'] = f'ignore-config=,extractor-args="youtube:player-client=default,tv",user-agent="{ua}"'
        self.current_quality_height = None
        self.current_ytdl_format = self.build_ytdl_format(self.current_quality_height)
        self.player['ytdl-format'] = self.current_ytdl_format
        self.sabr_reconnect_timer = QTimer(self)
        self.sabr_reconnect_timer.setSingleShot(True)
        self.sabr_reconnect_timer.timeout.connect(self.retry_sabr_stream)
        self.sabrPlaybackEnded.connect(self.handle_sabr_playback_ended)

        @self.player.event_callback('end-file')
        def on_end_file(event):
            data = event.data
            if data and data.reason in (mpv.MpvEventEndFile.EOF, mpv.MpvEventEndFile.ERROR):
                self.sabrPlaybackEnded.emit()
        self._sabr_end_file_callback = on_end_file

        self.player.register_key_binding('r', self.toggle_recording)
        self.player.register_key_binding('R', self.toggle_recording)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.header = StageHeader(self.stages)
        main_layout.addWidget(self.header)
        
        self.control_bar = QWidget()
        self.control_bar.setFixedSize(self.header.width(), 40)
        control_layout = QHBoxLayout(self.control_bar)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(0)
        control_layout.addSpacing(TIME_COLUMN_WIDTH)

        self.day_group = QButtonGroup(self)
        self.day_group.setExclusive(True)
        self.day_buttons = []

        self.quality_group = QButtonGroup(self)
        self.quality_group.setExclusive(True)
        self.quality_buttons_by_height = {}
        qualities = [("Auto", None), ("4K", 2160), ("1440p", 1440), ("1080p", 1080), ("720p", 720)]

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: #121212; border: none;")
        self.grids = []
        self.scroll_areas = []
        days_order = ["Friday", "Saturday", "Sunday"]
        
        # Determine current day to auto-select tab
        try:
            now_pdt = datetime.now(PDT)
        except:
            from datetime import timezone, timedelta
            now_pdt = datetime.now(timezone(timedelta(hours=-7)))
        current_day_name = now_pdt.strftime('%A')
        
        default_page_index = 0
        
        for day in days_order:
            if day in self.schedule_data:
                page_index = self.stack.count()
                day_btn = DayButton(day)
                day_btn.clicked.connect(lambda checked=False, idx=page_index: self.set_day(idx))
                self.day_group.addButton(day_btn, page_index)
                self.day_buttons.append(day_btn)
                control_layout.addWidget(day_btn)

                scroll = QScrollArea()
                grid = ScheduleGrid(day, self.schedule_data[day], self.stages, self)
                grid.columnClicked.connect(self.load_stream)
                scroll.setWidget(grid)
                scroll.setWidgetResizable(True)
                scroll.setStyleSheet("border: none;")
                scroll.horizontalScrollBar().valueChanged.connect(self.sync_header)
                self.stack.addWidget(scroll)
                self.grids.append(grid)
                self.scroll_areas.append(scroll)
                
                if day.lower() == current_day_name.lower():
                    default_page_index = page_index

        control_layout.addStretch(1)
        for i, (label, h) in enumerate(qualities):
            btn = QualityButton(label, h)
            self.quality_group.addButton(btn)
            if h is None:
                btn.setChecked(True)
            self.quality_buttons_by_height[h] = btn
            btn.clicked.connect(self.on_quality_clicked)
            if i:
                control_layout.addSpacing(5)
            control_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        main_layout.addWidget(self.control_bar)
        main_layout.addWidget(self.stack)
        if self.day_buttons:
            self.set_day(default_page_index)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_all_grids)
        self.timer.start(60000)

        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(500)

        self.load_stream(self.current_stage_index)

    def on_quality_clicked(self):
        btn = self.sender()
        if btn:
            self.change_quality(btn.height_val)

    def set_day(self, index):
        if not (0 <= index < self.stack.count()):
            return
        self.stack.setCurrentIndex(index)
        self.day_buttons[index].setChecked(True)
        self.sync_header(self.scroll_areas[index].horizontalScrollBar().value())

    def build_ytdl_format(self, height):
        if is_sabr_height(height):
            return build_sabr_format(height)
        # mpv can play YouTube HLS directly, but not raw SABR URLs from ytdl_hook.
        if height:
            return f"best[protocol^=m3u8][height<={height}]/best[protocol^=m3u8]/best[height<={height}]/best"
        return "best[protocol^=m3u8]/best"

    def change_quality(self, height):
        fmt = self.build_ytdl_format(height)
        self.current_quality_height = height
        self.current_ytdl_format = fmt
        self.sabr_reconnect_attempts = 0
        self.sabr_reconnect_timer.stop()
        print(f"Changing quality to: {height if height else 'Auto'} (ytdl-format: {fmt})")
        self.player['ytdl-format'] = fmt
        # Reload current stream to apply quality
        self.load_stream(self.current_stage_index)

    def handle_sabr_playback_ended(self):
        if not is_sabr_height(self.current_quality_height) or self.sabr_reconnect_timer.isActive():
            return
        if self.sabr_reconnect_attempts >= MAX_SABR_RECONNECT_ATTEMPTS:
            self.fallback_to_1080_hls("SABR playback ended repeatedly")
            return

        self.sabr_reconnect_attempts += 1
        delay_ms = min(SABR_RECONNECT_BASE_DELAY_MS * self.sabr_reconnect_attempts, 8000)
        print(f"SABR playback ended; reconnecting in {delay_ms / 1000:.1f}s")
        self.sabr_reconnect_timer.start(delay_ms)

    def retry_sabr_stream(self):
        if is_sabr_height(self.current_quality_height):
            self.load_stream(self.current_stage_index, reconnecting=True)

    def fallback_to_1080_hls(self, reason):
        print(f"{reason}; falling back to 1080p HLS")
        self.sabr_reconnect_timer.stop()
        self.sabr_reconnect_attempts = 0
        self.sabr_bridge.stop_all()
        self.current_quality_height = 1080
        self.current_ytdl_format = self.build_ytdl_format(1080)
        self.player['ytdl-format'] = self.current_ytdl_format
        fallback_button = self.quality_buttons_by_height.get(1080)
        if fallback_button:
            fallback_button.setChecked(True)
        self.player.loadfile(
            self.stages[self.current_stage_index]["url"],
            "replace",
            ytdl_format=self.current_ytdl_format,
        )

    def update_all_grids(self):
        for grid in self.grids:
            grid.update()

    def toggle_blink(self):
        if self.is_recording:
            self.blink_on = not self.blink_on
            self.update_all_grids()

    def toggle_recording(self):
        if not self.is_recording:
            stage_name = self.stages[self.current_stage_index]["name"].replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"coachella_{stage_name}_{timestamp}.ts"
            self.player['stream-record'] = filename
            self.is_recording = True
            print(f"Started recording to {filename}")
        else:
            self.player['stream-record'] = ""
            self.is_recording = False
            print("Stopped recording")
        self.update_all_grids()

    def sync_header(self, value):
        self.header.move(-value, 0)
        self.control_bar.move(-value, self.control_bar.y())

    def load_stream(self, index, reconnecting=False):
        if not (0 <= index < len(self.stages)):
            return
        if not reconnecting:
            self.sabr_reconnect_attempts = 0
        self.sabr_reconnect_timer.stop()
        if self.is_recording:
            self.toggle_recording()
        self.current_stage_index = index
        for grid in self.grids:
            grid.setSelected(index)
        self.header.setSelected(index)
        data = self.stages[index]
        if is_sabr_height(self.current_quality_height):
            try:
                bridge_url = self.sabr_bridge.start(data["url"], self.current_quality_height)
                print(f"Starting SABR bridge for {data['name']} at {self.current_quality_height}p: {bridge_url}")
                self.player.loadfile(bridge_url, "replace")
            except Exception as exc:
                self.fallback_to_1080_hls(f"SABR bridge failed: {exc}")
        else:
            self.sabr_bridge.stop_all()
            self.player.loadfile(data["url"], "replace", ytdl_format=self.current_ytdl_format)
        self.player.title = f"{data['name']} - Coachella 2026"

    def closeEvent(self, event):
        self.sabr_bridge.close()
        self.player.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoachellaApp()
    window.show()
    sys.exit(app.exec())

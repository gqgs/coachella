import sys
import os
import json
import locale
import time
import re
from datetime import datetime, timedelta
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
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint, QUrl
from PySide6.QtGui import QPixmap, QFont, QColor, QPainter, QPen, QBrush, QDesktopServices
import mpv
from sabr_bridge import SabrBridge, is_sabr_height, build_sabr_format
from recording_utils import finalize_recording_for_import

PIXELS_PER_HOUR = 150
START_HOUR = 16 # 4 PM
END_HOUR = 25   # 1 AM next day
FESTIVAL_DAY_END_HOURS = {
    "Friday": 25,
    "Saturday": 25,
    "Sunday": 24,
}
COLUMN_WIDTH = 180
TIME_COLUMN_WIDTH = 80
MAX_SABR_RECONNECT_ATTEMPTS = 10
SABR_RECONNECT_BASE_DELAY_MS = 1500
MAX_HLS_RECONNECT_ATTEMPTS = 5
HLS_RECONNECT_BASE_DELAY_MS = 1000
HLS_DEMUXER_LAVF_OPTIONS = "live_start_index=-8,http_persistent=0,seg_max_retry=5"
HLS_STREAM_LAVF_OPTIONS = (
    "reconnect=1,reconnect_streamed=1,reconnect_on_network_error=1,"
    "reconnect_delay_max=5,reconnect_max_retries=10,rw_timeout=15000000"
)
HLS_CACHE_OPTIONS = {
    "cache": "yes",
    "cache-pause": "yes",
    "cache-pause-initial": "no",
    "cache-pause-wait": "2.5",
    "demuxer-readahead-secs": "30",
    "demuxer-max-bytes": "300MiB",
}
DEFAULT_CACHE_OPTIONS = {
    "cache": "auto",
    "cache-pause": "yes",
    "cache-pause-initial": "no",
    "cache-pause-wait": "1",
    "demuxer-readahead-secs": "1",
    "demuxer-max-bytes": "150MiB",
}
PLAYBACK_DIAGNOSTIC_INTERVAL_MS = 1000
PLAYBACK_DIAGNOSTIC_HEARTBEAT_SECONDS = 20
PLAYBACK_LOW_CACHE_SECONDS = 6
PLAYBACK_STARVED_CACHE_SECONDS = 1
HLS_LOW_CACHE_RELOAD_SECONDS = 10
HLS_FORCE_RESUME_AFTER_SECONDS = 4
HLS_FORCE_RESUME_CACHE_SECONDS = 2.5
PLAYBACK_DIAGNOSTIC_PROPERTIES = (
    "demuxer-cache-duration",
    "demuxer-cache-time",
    "cache-buffering-state",
    "paused-for-cache",
    "cache-speed",
    "demuxer-cache-idle",
    "eof-reached",
    "core-idle",
    "idle-active",
    "demuxer-via-network",
    "time-pos",
    "demuxer-cache-state",
)


def schedule_time_to_minutes(time_text):
    hour, minute = map(int, time_text.split(":"))
    return (hour * 60) + minute


def schedule_time_to_float(time_text):
    return schedule_time_to_minutes(time_text) / 60.0


def display_schedule_time(time_text):
    total_minutes = schedule_time_to_minutes(time_text)
    hour = (total_minutes // 60) % 24
    minute = total_minutes % 60
    return f"{hour:02d}:{minute:02d}"


def current_schedule_context(now):
    time_float = now.hour + (now.minute / 60.0)

    if now.hour < 4:
        previous_day = (now - timedelta(days=1)).strftime("%A")
        extended_time = time_float + 24
        day_end = FESTIVAL_DAY_END_HOURS.get(previous_day)
        if day_end is not None and extended_time <= day_end:
            return previous_day, extended_time
        return None, extended_time

    current_day = now.strftime("%A")
    if current_day in FESTIVAL_DAY_END_HOURS:
        return current_day, time_float
    return None, time_float


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
    stageClicked = Signal(int)

    def __init__(self, stages, parent=None):
        super().__init__(parent)
        self.stages = stages
        self.setFixedHeight(50)
        self.setFixedWidth(TIME_COLUMN_WIDTH + (len(self.stages) * COLUMN_WIDTH))
        self.selected_index = -1
        self.setMouseTracking(True)

    def setSelected(self, index):
        self.selected_index = index
        self.update()

    def stageIndexAt(self, point):
        if point.x() <= TIME_COLUMN_WIDTH:
            return -1
        index = (point.x() - TIME_COLUMN_WIDTH) // COLUMN_WIDTH
        if 0 <= index < len(self.stages):
            return index
        return -1

    def mouseMoveEvent(self, event):
        if self.stageIndexAt(event.pos()) >= 0:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.stageIndexAt(event.pos())
        if index >= 0:
            self.stageClicked.emit(index)

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
        self.end_hour = self.schedule_end_hour()
        self.setFixedWidth(TIME_COLUMN_WIDTH + (len(self.stages) * COLUMN_WIDTH))
        self.setFixedHeight((self.end_hour - START_HOUR) * PIXELS_PER_HOUR + 50)
        self.setMouseTracking(True)

    def schedule_end_hour(self):
        latest_minutes = END_HOUR * 60
        for stage_artists in self.day_schedule.values():
            for entry in stage_artists:
                try:
                    latest_minutes = max(latest_minutes, schedule_time_to_minutes(entry.get("end", entry["start"])))
                except Exception:
                    pass
        return max(END_HOUR, (latest_minutes + 59) // 60)
        
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
        for h in range(START_HOUR, self.end_hour + 1):
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
                    s_h = schedule_time_to_float(entry["start"])
                    e_h = schedule_time_to_float(entry.get("end", entry["start"]))
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
                    start_text = display_schedule_time(entry["start"])
                    end_text = display_schedule_time(entry["end"]) if "end" in entry else "??"
                    painter.drawText(rect.adjusted(8, 0, -8, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, f"{start_text}-{end_text}")
                except Exception: pass

        # Timeline logic: Only draw if this tab's day matches the current system day
        try:
            now_pdt = datetime.now(PDT)
        except:
            from datetime import timezone, timedelta
            now_pdt = datetime.now(timezone(timedelta(hours=-7)))
        
        current_day_name, current_time_float = current_schedule_context(now_pdt)
        
        if current_day_name and self.day_name.lower() == current_day_name.lower():
            if START_HOUR <= current_time_float <= self.end_hour:
                line_y = (current_time_float - START_HOUR) * PIXELS_PER_HOUR
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.drawLine(TIME_COLUMN_WIDTH, int(line_y), self.width(), int(line_y))
                
                is_recording = getattr(self.app_ref, "is_recording", False)
                blink_on = getattr(self.app_ref, "blink_on", True)
                if is_recording and blink_on:
                    label_text = "🔴 RECORDING"
                    bg_color = QColor(200, 0, 0)
                    font_size = 6
                else:
                    label_text = f"LIVE {now_pdt.strftime('%-I:%M %p')}"
                    bg_color = QColor(255, 0, 0)
                    font_size = 6
                painter.setBrush(bg_color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24, 5, 5)
                painter.setPen(Qt.GlobalColor.white)
                painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
                painter.drawText(QRect(2, int(line_y) - 12, TIME_COLUMN_WIDTH - 4, 24), Qt.AlignmentFlag.AlignCenter, label_text)

class CoachellaApp(QMainWindow):
    playbackEnded = Signal()
    recordingToggleRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Coachella 2026")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #121212; color: white;")

        self.is_recording = False
        self.blink_on = True
        self.current_stage_index = 2 # Sahara default
        self.sabr_reconnect_attempts = 0
        self.hls_reconnect_attempts = 0
        self.is_closing = False
        self.last_playback_diag_log = 0
        self.last_playback_diag_state = None
        self.low_cache_since = None
        self.last_hls_force_resume = 0
        self.current_recording_file = None

        with open("config.json", "r") as f:
            config = json.load(f)
            self.stages = config.get("STAGES", [])

        if os.path.exists("schedule.json"):
            with open("schedule.json", "r") as f:
                self.schedule_data = json.load(f)
        else:
            self.schedule_data = {}

        self.player = mpv.MPV(
            vo='gpu',
            ytdl=True,
            input_default_bindings=True,
            input_vo_keyboard=True,
            log_handler=self.handle_mpv_log,
            loglevel='warn',
        )
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
        self.hls_reconnect_timer = QTimer(self)
        self.hls_reconnect_timer.setSingleShot(True)
        self.hls_reconnect_timer.timeout.connect(self.retry_hls_stream)
        self.playbackEnded.connect(self.handle_playback_ended)
        self.recordingToggleRequested.connect(self.toggle_recording)

        @self.player.event_callback('end-file')
        def on_end_file(event):
            data = event.data
            if data and data.reason in (mpv.MpvEventEndFile.EOF, mpv.MpvEventEndFile.ERROR):
                self.playbackEnded.emit()
        self._sabr_end_file_callback = on_end_file

        self.player.register_key_binding('r', self.handle_record_key)
        self.player.register_key_binding('R', self.handle_record_key)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.header = StageHeader(self.stages)
        self.header.stageClicked.connect(self.open_stage_in_browser)
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
        current_day_name, _ = current_schedule_context(now_pdt)
        
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
                
                if current_day_name and day.lower() == current_day_name.lower():
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

        self.playback_diag_timer = QTimer(self)
        self.playback_diag_timer.timeout.connect(self.log_playback_diagnostics)
        self.playback_diag_timer.start(PLAYBACK_DIAGNOSTIC_INTERVAL_MS)

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

    def handle_mpv_log(self, level, prefix, text):
        text = text.rstrip()
        if text:
            print(f"[mpv:{level}:{prefix}] {text}")

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
        self.hls_reconnect_attempts = 0
        self.sabr_reconnect_timer.stop()
        self.hls_reconnect_timer.stop()
        print(f"Changing quality to: {height if height else 'Auto'} (ytdl-format: {fmt})")
        self.player['ytdl-format'] = fmt
        # Reload current stream to apply quality
        self.load_stream(self.current_stage_index)

    def handle_playback_ended(self):
        if self.is_closing:
            return
        if is_sabr_height(self.current_quality_height):
            self.handle_sabr_playback_ended()
        else:
            self.handle_hls_playback_ended()

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

    def handle_hls_playback_ended(self):
        if self.hls_reconnect_timer.isActive():
            return
        if self.hls_reconnect_attempts >= MAX_HLS_RECONNECT_ATTEMPTS:
            print("HLS playback ended repeatedly; leaving stream stopped")
            return

        self.hls_reconnect_attempts += 1
        delay_ms = min(HLS_RECONNECT_BASE_DELAY_MS * self.hls_reconnect_attempts, 5000)
        print(f"HLS playback ended; reconnecting in {delay_ms / 1000:.1f}s")
        self.hls_reconnect_timer.start(delay_ms)

    def retry_hls_stream(self):
        if not is_sabr_height(self.current_quality_height):
            self.load_stream(self.current_stage_index, reconnecting=True)

    def use_hls_network_options(self):
        self.player['demuxer-lavf-o'] = HLS_DEMUXER_LAVF_OPTIONS
        self.player['stream-lavf-o'] = HLS_STREAM_LAVF_OPTIONS
        self.apply_player_options(HLS_CACHE_OPTIONS)

    def clear_hls_network_options(self):
        self.player['demuxer-lavf-o'] = ""
        self.player['stream-lavf-o'] = ""
        self.apply_player_options(DEFAULT_CACHE_OPTIONS)

    def apply_player_options(self, options):
        for name, value in options.items():
            self.player[name] = value

    def safe_player_property(self, name):
        try:
            return self.player._get_property(name, decoder=mpv.lazy_decoder)
        except Exception:
            return None

    def log_playback_diagnostics(self, force=False, reason=None):
        if self.is_closing:
            return

        now = time.monotonic()
        values = {name: self.safe_player_property(name) for name in PLAYBACK_DIAGNOSTIC_PROPERTIES}
        cache_seconds = self.as_float(values.get("demuxer-cache-duration"))
        paused_for_cache = bool(values.get("paused-for-cache"))
        buffering_state = self.as_float(values.get("cache-buffering-state"))
        eof_reached = bool(values.get("eof-reached"))
        core_idle = bool(values.get("core-idle"))
        idle_active = bool(values.get("idle-active"))

        if cache_seconds is not None and cache_seconds <= PLAYBACK_LOW_CACHE_SECONDS:
            if self.low_cache_since is None:
                self.low_cache_since = now
        else:
            self.low_cache_since = None
        low_for = None if self.low_cache_since is None else now - self.low_cache_since

        state = "ok"
        if eof_reached:
            state = "eof"
        elif paused_for_cache:
            state = "paused-for-cache"
        elif core_idle or idle_active:
            state = "idle"
        elif cache_seconds is not None and cache_seconds <= PLAYBACK_STARVED_CACHE_SECONDS:
            state = "starved"
        elif cache_seconds is not None and cache_seconds <= PLAYBACK_LOW_CACHE_SECONDS:
            state = "low-cache"
        elif buffering_state not in (None, 100):
            state = "buffering"

        should_log = force
        should_log = should_log or state != self.last_playback_diag_state
        should_log = should_log or state != "ok"
        should_log = should_log or (now - self.last_playback_diag_log) >= PLAYBACK_DIAGNOSTIC_HEARTBEAT_SECONDS
        should_reload_hls = (
            not force
            and not is_sabr_height(self.current_quality_height)
            and not self.hls_reconnect_timer.isActive()
            and self.hls_reconnect_attempts < MAX_HLS_RECONNECT_ATTEMPTS
            and low_for is not None
            and low_for >= HLS_LOW_CACHE_RELOAD_SECONDS
        )
        should_force_resume_hls = (
            not force
            and not is_sabr_height(self.current_quality_height)
            and paused_for_cache
            and cache_seconds is not None
            and cache_seconds >= HLS_FORCE_RESUME_CACHE_SECONDS
            and low_for is not None
            and low_for >= HLS_FORCE_RESUME_AFTER_SECONDS
            and (now - self.last_hls_force_resume) >= HLS_FORCE_RESUME_AFTER_SECONDS
        )
        if should_reload_hls:
            should_log = True
        if should_force_resume_hls:
            should_log = True

        if not should_log:
            return

        self.last_playback_diag_log = now
        self.last_playback_diag_state = state
        quality = self.current_quality_height if self.current_quality_height else "auto"
        mode = "sabr" if is_sabr_height(self.current_quality_height) else "hls"
        stage = self.stages[self.current_stage_index]["name"] if self.stages else "unknown"
        cache_state = self.format_cache_state(values.get("demuxer-cache-state"))
        parts = [
            f"reason={reason or state}",
            f"mode={mode}",
            f"stage={stage}",
            f"quality={quality}",
            f"cache={self.format_seconds(cache_seconds)}",
            f"low_for={self.format_seconds(low_for)}",
            f"cache_time={self.format_seconds(self.as_float(values.get('demuxer-cache-time')))}",
            f"buffering={self.format_number(buffering_state)}",
            f"paused_for_cache={paused_for_cache}",
            f"cache_speed={self.format_number(self.as_float(values.get('cache-speed')))}",
            f"demuxer_idle={bool(values.get('demuxer-cache-idle'))}",
            f"eof={eof_reached}",
            f"core_idle={core_idle}",
            f"idle_active={idle_active}",
            f"network={bool(values.get('demuxer-via-network'))}",
            f"time_pos={self.format_seconds(self.as_float(values.get('time-pos')))}",
            f"hls_reconnects={self.hls_reconnect_attempts}",
            f"sabr_reconnects={self.sabr_reconnect_attempts}",
            f"cache_state={cache_state}",
        ]
        print("[playback-diag] " + " ".join(parts))
        if should_force_resume_hls:
            self.last_hls_force_resume = now
            print(
                "HLS cache-pause stayed active with "
                f"{cache_seconds:.1f}s buffered; forcing playback resume"
            )
            try:
                self.player._set_property("pause", False)
            except Exception as exc:
                print(f"Unable to force HLS playback resume: {exc}")
        if should_reload_hls:
            self.hls_reconnect_attempts += 1
            print(
                "HLS cache stayed low for "
                f"{low_for:.1f}s; reloading stream behind the live edge"
            )
            self.hls_reconnect_timer.start(0)

    def as_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def format_seconds(self, value):
        if value is None:
            return "n/a"
        return f"{value:.2f}s"

    def format_number(self, value):
        if value is None:
            return "n/a"
        return f"{value:.2f}"

    def format_cache_state(self, state):
        if not isinstance(state, dict):
            return "n/a"

        summary = []
        for key in ("eof", "underrun", "idle", "total-bytes", "fw-bytes", "file-cache-bytes"):
            if key in state:
                summary.append(f"{key}={state[key]}")

        ranges = state.get("seekable-ranges")
        if isinstance(ranges, list) and ranges:
            last_range = ranges[-1]
            if isinstance(last_range, dict):
                start = self.format_seconds(self.as_float(last_range.get("start")))
                end = self.format_seconds(self.as_float(last_range.get("end")))
                summary.append(f"ranges={len(ranges)}")
                summary.append(f"last_range={start}-{end}")

        return ",".join(summary) if summary else str(state)[:160]

    def fallback_to_1080_hls(self, reason):
        print(f"{reason}; falling back to 1080p HLS")
        self.sabr_reconnect_timer.stop()
        self.hls_reconnect_timer.stop()
        self.sabr_reconnect_attempts = 0
        self.hls_reconnect_attempts = 0
        self.log_playback_diagnostics(force=True, reason="fallback-to-hls")
        self.sabr_bridge.stop_all()
        self.current_quality_height = 1080
        self.current_ytdl_format = self.build_ytdl_format(1080)
        self.player['ytdl-format'] = self.current_ytdl_format
        self.use_hls_network_options()
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

    def handle_record_key(self, key_state="p-", *_):
        if key_state and key_state[0] not in ("d", "p"):
            return
        self.recordingToggleRequested.emit()

    def current_recording_extension(self):
        if is_sabr_height(self.current_quality_height):
            return "mkv"
        return "ts"

    def current_artist_name(self):
        try:
            now_pdt = datetime.now(PDT)
        except Exception:
            from datetime import timezone, timedelta
            now_pdt = datetime.now(timezone(timedelta(hours=-7)))

        current_day_name, current_time = current_schedule_context(now_pdt)
        if not current_day_name:
            return "Unknown Artist"

        day_schedule = self.schedule_data.get(current_day_name, {})
        stage_name = self.stages[self.current_stage_index]["name"]

        for entry in day_schedule.get(stage_name, []):
            start = self.schedule_time_to_float(entry["start"])
            end = self.schedule_time_to_float(entry.get("end", entry["start"]))
            if start <= current_time < end:
                return entry["artist"]
        return "Unknown Artist"

    def schedule_time_to_float(self, time_text):
        return schedule_time_to_float(time_text)

    def safe_filename_part(self, value):
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value or "Unknown"

    def current_recording_filename(self):
        stage_name = self.safe_filename_part(self.stages[self.current_stage_index]["name"])
        artist_name = self.safe_filename_part(self.current_artist_name())
        now = datetime.now()
        festival_year = now.year
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        extension = self.current_recording_extension()
        return f"Coachella {festival_year} - {stage_name} {artist_name} {timestamp}.{extension}"

    def show_osd_message(self, message, duration_ms=3000):
        try:
            self.player.command("show-text", message, duration_ms)
        except Exception as exc:
            print(f"Unable to show mpv OSD message: {exc}")

    def toggle_recording(self):
        if not self.is_recording:
            filename = self.current_recording_filename()
            self.player['stream-record'] = filename
            self.is_recording = True
            self.current_recording_file = filename
            print(f"Started recording to {filename}")
            self.show_osd_message(f"Recording started: {filename}")
        else:
            filename = self.current_recording_file
            self.player['stream-record'] = ""
            self.is_recording = False
            self.current_recording_file = None
            print("Stopped recording")
            self.show_osd_message("Recording stopped")
            if filename:
                result = finalize_recording_for_import(filename)
                print(result.message)
                if result.success:
                    self.show_osd_message("Recording finalized for import")
                else:
                    self.show_osd_message("Recording finalization failed")
        self.update_all_grids()

    def sync_header(self, value):
        self.header.move(-value, 0)
        self.control_bar.move(-value, self.control_bar.y())

    def open_stage_in_browser(self, index):
        if not (0 <= index < len(self.stages)):
            return
        stage = self.stages[index]
        url = stage.get("url")
        if not url:
            return
        if not QDesktopServices.openUrl(QUrl(url)):
            print(f"Could not open browser for {stage['name']}: {url}")

    def load_stream(self, index, reconnecting=False):
        if not (0 <= index < len(self.stages)):
            return
        if not reconnecting:
            self.sabr_reconnect_attempts = 0
            self.hls_reconnect_attempts = 0
        self.last_playback_diag_state = None
        self.low_cache_since = None
        self.last_hls_force_resume = 0
        self.sabr_reconnect_timer.stop()
        self.hls_reconnect_timer.stop()
        if self.is_recording and not reconnecting:
            self.toggle_recording()
        self.current_stage_index = index
        for grid in self.grids:
            grid.setSelected(index)
        self.header.setSelected(index)
        data = self.stages[index]
        mode = "sabr" if is_sabr_height(self.current_quality_height) else "hls"
        quality = self.current_quality_height if self.current_quality_height else "auto"
        print(
            "[playback-diag] load "
            f"mode={mode} stage={data['name']} quality={quality} reconnecting={reconnecting} "
            f"ytdl_format={self.current_ytdl_format}"
        )
        if is_sabr_height(self.current_quality_height):
            try:
                self.clear_hls_network_options()
                bridge_url = self.sabr_bridge.start(data["url"], self.current_quality_height)
                print(f"Starting SABR bridge for {data['name']} at {self.current_quality_height}p: {bridge_url}")
                self.player.loadfile(bridge_url, "replace")
            except Exception as exc:
                self.fallback_to_1080_hls(f"SABR bridge failed: {exc}")
        else:
            self.sabr_bridge.stop_all()
            self.use_hls_network_options()
            self.player.loadfile(data["url"], "replace", ytdl_format=self.current_ytdl_format)
        self.player.title = f"{data['name']} - Coachella 2026"
        self.log_playback_diagnostics(force=True, reason="load-issued")

    def closeEvent(self, event):
        self.is_closing = True
        self.playback_diag_timer.stop()
        self.sabr_reconnect_timer.stop()
        self.hls_reconnect_timer.stop()
        self.sabr_bridge.close()
        self.player.terminate()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoachellaApp()
    window.show()
    sys.exit(app.exec())

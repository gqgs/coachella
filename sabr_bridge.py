import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HIGH_QUALITY_MIN_HEIGHT = 1440


def is_sabr_height(height):
    return height is not None and height >= HIGH_QUALITY_MIN_HEIGHT


def build_sabr_format(height):
    if height:
        return f"(bv[height<={height}]+ba)[protocol=sabr]"
    return "(bv+ba)[protocol=sabr]"


class SabrBridgeError(RuntimeError):
    pass


class _BridgeHandler(BaseHTTPRequestHandler):
    bridge = None

    def do_GET(self):
        prefix = "/stream/"
        if not self.path.startswith(prefix):
            self.send_error(404)
            return

        session_id = self.path[len(prefix):].split("?", 1)[0]
        session = self.bridge.get_session(session_id)
        if session is None:
            self.send_error(404)
            return

        try:
            self.send_response(200)
            self.send_header("Content-Type", "video/x-matroska")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            session.stream_to(self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            print(f"SABR bridge stream error: {exc}")
        finally:
            self.bridge.stop_session(session_id)

    def log_message(self, fmt, *args):
        return


class SabrBridge:
    def __init__(self, ytdlp_path, ffmpeg_path="ffmpeg"):
        self.ytdlp_path = ytdlp_path
        self.ffmpeg_path = ffmpeg_path
        self.server = None
        self.thread = None
        self.sessions = {}
        self.lock = threading.Lock()

    def start(self, source_url, height):
        self._ensure_server()
        self.stop_all()

        session = SabrSession(source_url, height, self.ytdlp_path, self.ffmpeg_path)
        try:
            session.check_streaming_prerequisites()
        except Exception:
            session.stop()
            raise
        with self.lock:
            self.sessions[session.id] = session
        try:
            session.start_downloader()
        except Exception:
            self.stop_session(session.id)
            raise
        return f"http://127.0.0.1:{self.server.server_port}/stream/{session.id}"

    def get_session(self, session_id):
        with self.lock:
            return self.sessions.get(session_id)

    def stop_all(self):
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            session.stop()

    def stop_session(self, session_id):
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session:
            session.stop()

    def close(self):
        self.stop_all()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

    def _ensure_server(self):
        if self.server:
            return
        _BridgeHandler.bridge = self
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _BridgeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()


class SabrSession:
    def __init__(self, source_url, height, ytdlp_path, ffmpeg_path):
        self.id = uuid.uuid4().hex
        self.source_url = source_url
        self.height = height
        self.ytdlp_path = ytdlp_path
        self.ffmpeg_path = ffmpeg_path
        self.tempdir = Path(tempfile.mkdtemp(prefix=f"coachella-sabr-{self.id}-"))
        self.stop_event = threading.Event()
        self.downloader = None
        self.ffmpeg = None
        self.log_threads = []
        self.writer_threads = []
        self.stream_lock = threading.Lock()

    def start_downloader(self):
        command = [
            self.ytdlp_path,
            "--ignore-config",
            "--keep-fragments",
            "--part",
            "--newline",
            "--no-progress",
            "--paths", f"temp:{self.tempdir}",
            "--paths", f"home:{self.tempdir}",
            "--extractor-args", "youtube:player-client=default,tv",
            "-f", build_sabr_format(self.height),
            "-o", "stream.%(format_id)s.%(ext)s",
            self.source_url,
        ]
        self.downloader = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self.log_threads.append(self._drain_text_output(self.downloader.stdout, "yt-dlp_sabr"))

    def stream_to(self, output):
        if not self.stream_lock.acquire(blocking=False):
            raise SabrBridgeError("SABR session already has an active stream consumer")
        try:
            self.check_streaming_prerequisites()
            video_part, audio_part = self._wait_for_parts()
            video_fifo = self.tempdir / "video.pipe"
            audio_fifo = self.tempdir / "audio.pipe"
            os.mkfifo(video_fifo)
            os.mkfifo(audio_fifo)

            self.writer_threads = [
                threading.Thread(target=self._tail_file_to_fifo, args=(video_part, video_fifo), daemon=True),
                threading.Thread(target=self._tail_file_to_fifo, args=(audio_part, audio_fifo), daemon=True),
            ]
            for thread in self.writer_threads:
                thread.start()

            self.ffmpeg = subprocess.Popen(
                [
                    self.ffmpeg_path,
                    "-hide_banner",
                    "-loglevel", "fatal",
                    "-fflags", "+genpts+nobuffer",
                    "-thread_queue_size", "1024",
                    "-i", str(video_fifo),
                    "-thread_queue_size", "1024",
                    "-i", str(audio_fifo),
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c", "copy",
                    "-f", "matroska",
                    "-flush_packets", "1",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self.log_threads.append(self._drain_binary_output(self.ffmpeg.stderr, "ffmpeg"))

            while not self.stop_event.is_set():
                chunk = self.ffmpeg.stdout.read(64 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                output.flush()
        finally:
            self._stop_ffmpeg()
            self.stream_lock.release()

    def stop(self):
        self.stop_event.set()
        self._stop_ffmpeg()
        self._stop_process(self.downloader)
        for thread in self.writer_threads:
            thread.join(timeout=1)
        for thread in self.log_threads:
            thread.join(timeout=1)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _wait_for_parts(self, timeout=45):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline and not self.stop_event.is_set():
            parts = sorted(self.tempdir.glob("*.sq*.part"))
            audio_parts = [part for part in parts if ".f140." in part.name and part.stat().st_size > 16 * 1024]
            video_parts = [part for part in parts if ".f140." not in part.name and part.stat().st_size > 256 * 1024]
            if audio_parts and video_parts:
                return video_parts[0], audio_parts[0]
            if self.downloader and self.downloader.poll() is not None:
                last_error = f"yt-dlp_sabr exited with code {self.downloader.returncode}"
                break
            time.sleep(0.2)
        raise SabrBridgeError(last_error or "timed out waiting for SABR fragments")

    def check_streaming_prerequisites(self):
        if not hasattr(os, "mkfifo"):
            raise SabrBridgeError("SABR bridge requires POSIX FIFO support")
        if shutil.which(self.ffmpeg_path) is None and not Path(self.ffmpeg_path).exists():
            raise SabrBridgeError("ffmpeg is required to mux SABR video and audio")

    def _tail_file_to_fifo(self, source_path, fifo_path):
        try:
            with open(fifo_path, "wb", buffering=0) as fifo, open(source_path, "rb", buffering=0) as source:
                while not self.stop_event.is_set():
                    chunk = source.read(64 * 1024)
                    if chunk:
                        fifo.write(chunk)
                    else:
                        if self.downloader and self.downloader.poll() is not None:
                            break
                        time.sleep(0.05)
        except (BrokenPipeError, FileNotFoundError, OSError):
            pass

    def _drain_text_output(self, pipe, label):
        def run():
            if pipe is None:
                return
            for line in pipe:
                if line.strip():
                    print(f"[{label}] {line.rstrip()}")
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def _drain_binary_output(self, pipe, label):
        def run():
            if pipe is None:
                return
            for line in iter(pipe.readline, b""):
                text = line.decode("utf-8", "replace").strip()
                if text:
                    print(f"[{label}] {text}")
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def _stop_ffmpeg(self):
        self._stop_process(self.ffmpeg)
        self.ffmpeg = None

    def _stop_process(self, process):
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

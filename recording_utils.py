import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProbeResult:
    is_valid: bool
    reason: str = ""


@dataclass
class FinalizeResult:
    success: bool
    message: str


def probe_import_safe_video(path, ffprobe_path="ffprobe"):
    command = [
        ffprobe_path,
        "-v", "error",
        "-show_entries", "stream=codec_type,width,height",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return ProbeResult(False, result.stderr.strip() or f"ffprobe exited with {result.returncode}")
    if result.stderr.strip():
        return ProbeResult(False, result.stderr.strip())

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return ProbeResult(False, f"ffprobe returned invalid JSON: {exc}")

    for stream in metadata.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if width > 0 and height > 0:
            return ProbeResult(True)
        return ProbeResult(False, f"video output size is invalid: {width}x{height}")

    return ProbeResult(False, "no video stream found")


def finalize_recording_for_import(path, ffmpeg_path="ffmpeg", ffprobe_path="ffprobe"):
    source = Path(path)
    if not source.exists():
        return FinalizeResult(False, f"recording does not exist: {source}")
    if source.stat().st_size == 0:
        return FinalizeResult(False, f"recording is empty: {source}")

    temp_output = source.with_name(f".{source.stem}.remuxing{source.suffix}")
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-y",
        "-err_detect", "ignore_err",
        "-fflags", "+genpts",
        "-i", str(source),
        "-map", "0",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(temp_output),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return FinalizeResult(False, result.stderr.strip() or f"ffmpeg exited with {result.returncode}")

        probe = probe_import_safe_video(temp_output, ffprobe_path=ffprobe_path)
        if not probe.is_valid:
            return FinalizeResult(False, probe.reason)

        os.replace(temp_output, source)
        return FinalizeResult(True, f"recording finalized for import: {source}")
    finally:
        if temp_output.exists():
            temp_output.unlink()

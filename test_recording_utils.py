import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recording_utils import finalize_recording_for_import, probe_import_safe_video


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def ffprobe_json(width, height):
    return json.dumps({
        "streams": [
            {
                "codec_type": "video",
                "width": width,
                "height": height,
            }
        ]
    })


class TestRecordingUtils(unittest.TestCase):
    @patch("recording_utils.subprocess.run")
    def test_probe_accepts_clean_nonzero_video_size(self, run):
        run.return_value = Completed(stdout=ffprobe_json(1920, 1080))

        result = probe_import_safe_video("recording.mkv")

        self.assertTrue(result.is_valid)

    @patch("recording_utils.subprocess.run")
    def test_probe_rejects_zero_video_size(self, run):
        run.return_value = Completed(stdout=ffprobe_json(0, 1080))

        result = probe_import_safe_video("recording.mkv")

        self.assertFalse(result.is_valid)
        self.assertIn("video output size is invalid", result.reason)

    @patch("recording_utils.subprocess.run")
    def test_probe_rejects_decode_errors_even_with_size_metadata(self, run):
        run.return_value = Completed(
            stdout=ffprobe_json(1920, 1080),
            stderr="Failed to read frame header.",
        )

        result = probe_import_safe_video("recording.mkv")

        self.assertFalse(result.is_valid)
        self.assertIn("Failed to read frame header", result.reason)

    @patch("recording_utils.os.replace")
    @patch("recording_utils.probe_import_safe_video")
    @patch("recording_utils.subprocess.run")
    def test_finalize_remuxes_and_replaces_only_valid_output(self, run, probe, replace):
        run.return_value = Completed()
        probe.return_value.is_valid = True
        probe.return_value.reason = ""

        with tempfile.TemporaryDirectory() as tempdir:
            recording = Path(tempdir) / "Coachella 2026 - MOJAVE Artist 20260413_010203.mkv"
            recording.write_bytes(b"not really media")

            result = finalize_recording_for_import(recording)

        self.assertTrue(result.success)
        self.assertTrue(run.called)
        replace.assert_called_once()

    @patch("recording_utils.os.replace")
    @patch("recording_utils.probe_import_safe_video")
    @patch("recording_utils.subprocess.run")
    def test_finalize_does_not_replace_invalid_output_size(self, run, probe, replace):
        run.return_value = Completed()
        probe.return_value.is_valid = False
        probe.return_value.reason = "video output size is invalid: 0x0"

        with tempfile.TemporaryDirectory() as tempdir:
            recording = Path(tempdir) / "recording.mkv"
            recording.write_bytes(b"not really media")

            result = finalize_recording_for_import(recording)

        self.assertFalse(result.success)
        self.assertIn("video output size is invalid", result.message)
        replace.assert_not_called()


if __name__ == "__main__":
    unittest.main()

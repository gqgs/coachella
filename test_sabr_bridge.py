import unittest

from sabr_bridge import build_sabr_format, is_sabr_height


class TestSabrBridge(unittest.TestCase):
    def test_sabr_height_threshold(self):
        self.assertFalse(is_sabr_height(None))
        self.assertFalse(is_sabr_height(720))
        self.assertFalse(is_sabr_height(1080))
        self.assertTrue(is_sabr_height(1440))
        self.assertTrue(is_sabr_height(2160))

    def test_sabr_format_caps_video_height(self):
        self.assertEqual(build_sabr_format(1440), "(bv[height<=1440]+ba)[protocol=sabr]")
        self.assertEqual(build_sabr_format(2160), "(bv[height<=2160]+ba)[protocol=sabr]")


if __name__ == "__main__":
    unittest.main()

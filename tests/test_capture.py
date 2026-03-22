import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.capture import AudioCapture


class TestAudioCapture(unittest.TestCase):
    @patch("src.capture.subprocess.run")
    def test_start_creates_script_and_thread(self, mock_run):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            self.assertTrue(cap.is_recording)
            self.assertIsNotNone(cap._raw_path)
            self.assertIsNotNone(cap._thread)
            self.assertTrue(cap._thread.is_alive())

            # Unblock the thread
            cap.stop()

    @patch("src.capture.os.system")
    @patch("src.capture.subprocess.run")
    def test_stop_kills_and_converts(self, mock_run, mock_system):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            # Create fake raw file
            with open(cap._raw_path, "wb") as f:
                f.write(b"\x00" * 1024)

            output_path = cap.stop()

            mock_system.assert_called_once()  # pkill
            # subprocess.run called twice: once for capture (thread), once for ffmpeg
            self.assertEqual(mock_run.call_count, 2)
            self.assertFalse(cap.is_recording)
            self.assertTrue(output_path.endswith(".wav"))

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        result = cap.stop()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

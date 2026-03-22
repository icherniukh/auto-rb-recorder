import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.capture import AudioCapture


class TestAudioCapture(unittest.TestCase):
    @patch("src.capture.subprocess.Popen")
    def test_start_spawns_audiotee(self, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "audiotee")
            self.assertIn("--flush", args)
            self.assertIn("12345", args)
            self.assertTrue(cap.is_recording)
            cap.stop()

    @patch("src.capture.subprocess.run")
    @patch("src.capture.subprocess.Popen")
    def test_stop_terminates_and_converts(self, mock_popen, mock_run):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            with open(cap._raw_path, "wb") as f:
                f.write(b"\x00" * 1024)

            output_path = cap.stop()

            mock_proc.terminate.assert_called_once()
            mock_run.assert_called_once()
            ffmpeg_args = mock_run.call_args[0][0]
            self.assertEqual(ffmpeg_args[0], "ffmpeg")
            self.assertIn("s16le", ffmpeg_args)
            self.assertFalse(cap.is_recording)
            self.assertTrue(output_path.endswith(".wav"))

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        result = cap.stop()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

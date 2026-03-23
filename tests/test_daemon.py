import unittest
from unittest.mock import patch, MagicMock
from src.daemon import RecorderDaemon
from src.config import Config


class TestRecorderDaemon(unittest.TestCase):
    @patch("src.daemon.AudioCapture")
    @patch("src.daemon.ProcessMonitor")
    def test_start_recording_on_process_detected(self, MockMonitor, MockCapture):
        cfg = Config(output_dir="/tmp/test_output")
        daemon = RecorderDaemon(cfg)

        daemon._on_rekordbox_start(pid=12345)

        MockCapture.assert_called_once_with(
            pid=12345, 
            output_dir="/tmp/test_output", 
            sample_rate=48000,
            silence_threshold_db=-50,
            min_silence_duration=15,
            decay_tail=5,
            export_format='wav'
        )
        MockCapture.return_value.start.assert_called_once()

    @patch("src.daemon.os.path.exists", return_value=True)
    @patch("src.daemon.AudioCapture")
    @patch("src.daemon.ProcessMonitor")
    def test_stop_recording_and_split_on_process_exit(self, MockMonitor, MockCapture, mock_exists):
        cfg = Config(output_dir="/tmp/test_output")
        daemon = RecorderDaemon(cfg)

        mock_capture = MagicMock()
        daemon._capture = mock_capture

        daemon._on_rekordbox_stop()

        mock_capture.stop.assert_called_once()
        self.assertIsNone(daemon._capture)


if __name__ == "__main__":
    unittest.main()

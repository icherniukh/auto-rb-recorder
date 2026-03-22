import os
import struct
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.capture import AudioCapture


class TestAudioCapture(unittest.TestCase):
    @patch("src.capture.ProcessAudioCapture")
    def test_start_opens_wav_and_starts_tap(self, MockPAC):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            MockPAC.assert_called_once()
            MockPAC.return_value.start.assert_called_once()
            self.assertTrue(cap.is_recording)
            self.assertIsNotNone(cap._output_path)
            self.assertTrue(os.path.exists(cap._output_path))
            cap.stop()

    @patch("src.capture.ProcessAudioCapture")
    def test_stop_closes_tap_and_wav(self, MockPAC):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()
            output_path = cap.stop()

            MockPAC.return_value.stop.assert_called_once()
            MockPAC.return_value.close.assert_called_once()
            self.assertFalse(cap.is_recording)
            self.assertTrue(output_path.endswith(".wav"))

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        result = cap.stop()
        self.assertIsNone(result)

    @patch("src.capture.ProcessAudioCapture")
    def test_on_data_writes_to_wav(self, MockPAC):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            # Extract the on_data callback that was passed to ProcessAudioCapture
            _, kwargs = MockPAC.call_args
            on_data = kwargs["on_data"]

            # Simulate receiving audio data: 100 frames of stereo float32 silence
            import numpy as np
            silence = np.zeros(100 * 2, dtype=np.float32)  # 100 frames x 2 channels
            on_data(silence.tobytes(), 100)

            output_path = cap.stop()
            self.assertTrue(os.path.getsize(output_path) > 44)  # > WAV header


if __name__ == "__main__":
    unittest.main()

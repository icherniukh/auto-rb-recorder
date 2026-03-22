import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.capture import AudioCapture


class TestAudioCapture(unittest.TestCase):
    @patch("src.capture.subprocess.Popen")
    def test_start_opens_wav_and_spawns_process(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        mock_popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "AudioCapCLI")
            self.assertIn("--source", args)
            self.assertTrue(cap.is_recording)
            self.assertTrue(os.path.exists(cap._output_path))
            cap.stop()

    @patch("src.capture.subprocess.Popen")
    def test_stop_terminates_process_and_closes_wav(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.stdout.read.return_value = b""
        mock_popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()
            output_path = cap.stop()

            mock_proc.terminate.assert_called_once()
            self.assertFalse(cap.is_recording)
            self.assertTrue(output_path.endswith(".wav"))

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        result = cap.stop()
        self.assertIsNone(result)

    @patch("src.capture.subprocess.Popen")
    def test_reader_writes_audio_to_wav(self, mock_popen):
        import numpy as np

        # Simulate AudioCapCLI outputting 2 chunks then EOF
        audio = np.random.uniform(-0.5, 0.5, size=2048).astype(np.float32)
        audio_bytes = audio.tobytes()
        mock_proc = MagicMock()
        mock_proc.stdout.read.side_effect = [audio_bytes, b""]
        mock_popen.return_value = mock_proc

        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            # Give reader thread time to process
            import time
            time.sleep(0.1)

            output_path = cap.stop()
            self.assertTrue(os.path.getsize(output_path) > 44)  # > WAV header


if __name__ == "__main__":
    unittest.main()

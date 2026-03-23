import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from src.capture import AudioCapture, db_to_rms


class TestAudioCapture(unittest.TestCase):
    def test_db_to_rms(self):
        # -40 dB is ~ 327.68
        rms = db_to_rms(-40.0)
        self.assertTrue(320 < rms < 330)

    @patch("src.capture.threading.Thread")
    @patch("src.capture.subprocess.Popen")
    def test_start_spawns_audiotee_and_thread(self, mock_popen, mock_thread):
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
            
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()

            self.assertTrue(cap.is_recording)
            self.assertEqual(cap.state, "PASSIVE")
            cap.stop()

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        cap.stop()
        self.assertFalse(cap.is_recording)

    def test_calculate_rms(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        # 4 samples of 100
        chunk = b'\x64\x00' * 4
        rms = cap._calculate_rms(chunk)
        self.assertAlmostEqual(rms, 100.0)

    @patch("src.capture.subprocess.Popen")
    @patch("src.capture.subprocess.run")
    def test_transition_passive_to_active(self, mock_run, mock_popen):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000, silence_threshold_db=-50, decay_tail=0)
            
            # Simulate a loud chunk manually without starting threads
            loud_chunk = b'\xFF\x7F' * 10  # very loud!
            
            cap.state = "PASSIVE"
            cap.is_recording = True
            
            rms = cap._calculate_rms(loud_chunk)
            self.assertTrue(rms > cap.rms_threshold)
            
            # mock reader loop logic just for testing state change
            is_silent = rms < cap.rms_threshold
            if cap.state == "PASSIVE" and not is_silent:
                cap.state = "ACTIVE"
                cap._open_new_file()
            
            self.assertEqual(cap.state, "ACTIVE")
            self.assertIsNotNone(cap._raw_file)
            self.assertTrue("rb_session_" in cap._raw_path)
            self.assertTrue("rb_session_" in cap._output_path)
            cap._raw_file.close()

    def test_circular_buffer_limits(self):
        # 0.1s chunk at 48khz 2ch 2byte = 19200 bytes
        # 5 second tail = 50 chunks
        cap = AudioCapture(pid=1, output_dir="/tmp", decay_tail=5.0)
        self.assertEqual(cap.buffer_maxlen, 50)
        self.assertEqual(cap.ring_buffer.maxlen, 50)
        
        # Add 60 chunks, ensure it only keeps 50
        for i in range(60):
            cap.ring_buffer.append(bytes([i % 255]))
            
        self.assertEqual(len(cap.ring_buffer), 50)

    @patch("src.capture.threading.Thread")
    @patch("src.capture.subprocess.Popen")
    def test_mp3_export_format(self, mock_popen, mock_thread):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=1, output_dir=tmpdir, export_format="mp3")
            cap._open_new_file()
            self.assertTrue(cap._output_path.endswith(".mp3"))
            self.assertTrue(cap._raw_path.endswith(".raw"))
            cap._raw_file.close()

if __name__ == "__main__":
    unittest.main()

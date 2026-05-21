import tempfile
import unittest
from unittest.mock import MagicMock

from src.recorder_core import PCMStreamRecorder


class TestPCMStreamRecorder(unittest.TestCase):
    def test_calculate_rms(self):
        recorder = PCMStreamRecorder(output_dir="/tmp", sample_rate=48000)
        chunk = b"\x64\x00" * 4
        rms = recorder._calculate_rms(chunk)
        self.assertAlmostEqual(rms, 100.0)

    def test_transition_passive_to_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = PCMStreamRecorder(
                output_dir=tmpdir,
                sample_rate=48000,
                silence_threshold_db=-50,
                decay_tail=0,
            )

            loud_chunk = b"\xFF\x7F" * 10
            recorder.process_chunk(loud_chunk)

            self.assertEqual(recorder.state, "ACTIVE")
            self.assertIsNotNone(recorder._raw_file)
            self.assertIn("rb_session_", recorder._raw_path)
            self.assertIn("rb_session_", recorder._output_path)
            recorder._raw_file.close()

    def test_circular_buffer_limits(self):
        recorder = PCMStreamRecorder(output_dir="/tmp", decay_tail=5.0)
        self.assertEqual(recorder.buffer_maxlen, 50)
        self.assertEqual(recorder.ring_buffer.maxlen, 50)

        for i in range(60):
            recorder.ring_buffer.append(bytes([i % 255]))

        self.assertEqual(len(recorder.ring_buffer), 50)

    def test_mp3_export_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = PCMStreamRecorder(output_dir=tmpdir, export_format="mp3")
            recorder._open_new_file()
            self.assertTrue(recorder._output_path.endswith(".mp3"))
            self.assertTrue(recorder._raw_path.endswith(".raw"))
            recorder._raw_file.close()

    def test_finalize_exports_active_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = PCMStreamRecorder(output_dir=tmpdir, decay_tail=0)
            recorder.exporter.export_async = MagicMock()

            recorder.process_chunk(b"\xFF\x7F" * 10)
            raw_path = recorder._raw_path
            output_path = recorder._output_path

            recorder.finalize()

            recorder.exporter.export_async.assert_called_once_with(raw_path, output_path)
            self.assertEqual(recorder.state, "PASSIVE")

    def test_last_active_at_updates_on_non_silent_chunk(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = PCMStreamRecorder(
                output_dir=tmpdir,
                sample_rate=48000,
                silence_threshold_db=-50,
                decay_tail=0,
            )

            with patch("src.recorder_core.time.time") as mock_time:
                # Transition PASSIVE -> ACTIVE
                mock_time.return_value = 100.0
                loud_chunk = b"\xFF\x7F" * 10
                recorder.process_chunk(loud_chunk)

                self.assertEqual(recorder.state, "ACTIVE")
                self.assertEqual(recorder.last_active_at, 100.0)

                # Process another loud chunk in ACTIVE state
                mock_time.return_value = 105.0
                recorder.process_chunk(loud_chunk)

                self.assertEqual(recorder.state, "ACTIVE")
                self.assertEqual(recorder.last_active_at, 105.0)

            if recorder._raw_file:
                recorder._raw_file.close()


if __name__ == "__main__":
    unittest.main()

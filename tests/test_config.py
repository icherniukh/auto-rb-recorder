import unittest
import tempfile
import os
from src.config import Config


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = Config()
        self.assertEqual(cfg.sample_rate, 48000)
        self.assertEqual(cfg.silence_threshold_db, -50)
        self.assertEqual(cfg.min_silence_duration, 15)
        self.assertEqual(cfg.decay_tail, 5)
        self.assertEqual(cfg.poll_interval, 2.0)
        self.assertEqual(cfg.process_name, "rekordbox")
        self.assertTrue(cfg.output_dir.endswith("RekordboxRecordings"))

    def test_load_from_toml(self):
        toml_content = (
            '[recording]\n'
            'sample_rate = 44100\n'
            'output_dir = "/tmp/my_sets"\n'
            '\n'
            '[trigger]\n'
            'silence_threshold_db = -40\n'
            'min_silence_duration = 20\n'
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            f.flush()
            cfg = Config.from_file(f.name)

        os.unlink(f.name)
        self.assertEqual(cfg.sample_rate, 44100)
        self.assertEqual(cfg.output_dir, "/tmp/my_sets")
        self.assertEqual(cfg.silence_threshold_db, -40)
        self.assertEqual(cfg.min_silence_duration, 20)
        self.assertEqual(cfg.decay_tail, 5)

if __name__ == "__main__":
    unittest.main()

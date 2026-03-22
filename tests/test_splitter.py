import unittest
from src.splitter import SilenceSplitter


class TestSilenceSplitter(unittest.TestCase):
    def test_parse_silence_detect_output(self):
        ffmpeg_stderr = (
            "[silencedetect @ 0x1] silence_start: 45.230\n"
            "[silencedetect @ 0x1] silence_end: 62.100 | silence_duration: 16.870\n"
            "[silencedetect @ 0x1] silence_start: 3600.500\n"
            "[silencedetect @ 0x1] silence_end: 3620.000 | silence_duration: 19.500\n"
        )
        splitter = SilenceSplitter(silence_threshold_db=-50, min_silence_duration=15)
        segments = splitter.parse_silence_boundaries(ffmpeg_stderr, total_duration=3700.0)

        # Expect 3 segments: [0, 45.23], [62.1, 3600.5], [3620.0, 3700.0]
        self.assertEqual(len(segments), 3)
        self.assertAlmostEqual(segments[0][0], 0.0)
        self.assertAlmostEqual(segments[0][1], 45.23)
        self.assertAlmostEqual(segments[1][0], 62.1)
        self.assertAlmostEqual(segments[1][1], 3600.5)

    def test_filters_short_segments(self):
        ffmpeg_stderr = (
            "[silencedetect @ 0x1] silence_start: 2.0\n"
            "[silencedetect @ 0x1] silence_end: 20.0 | silence_duration: 18.0\n"
        )
        splitter = SilenceSplitter(
            silence_threshold_db=-50, min_silence_duration=15, min_segment_duration=10
        )
        segments = splitter.parse_silence_boundaries(ffmpeg_stderr, total_duration=25.0)

        # [0, 2] is 2s — filtered. [20, 25] is 5s — filtered.
        self.assertEqual(len(segments), 0)

    def test_no_silence_returns_full_file(self):
        splitter = SilenceSplitter(silence_threshold_db=-50, min_silence_duration=15)
        segments = splitter.parse_silence_boundaries("", total_duration=3600.0)

        self.assertEqual(len(segments), 1)
        self.assertAlmostEqual(segments[0][0], 0.0)
        self.assertAlmostEqual(segments[0][1], 3600.0)


if __name__ == "__main__":
    unittest.main()

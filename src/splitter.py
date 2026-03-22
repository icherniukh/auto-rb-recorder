import os
import re
import subprocess
from typing import List, Tuple


class SilenceSplitter:
    def __init__(
        self,
        silence_threshold_db: float = -50,
        min_silence_duration: float = 15,
        min_segment_duration: float = 30,
    ):
        self.silence_threshold_db = silence_threshold_db
        self.min_silence_duration = min_silence_duration
        self.min_segment_duration = min_segment_duration

    def parse_silence_boundaries(
        self, ffmpeg_stderr: str, total_duration: float
    ) -> List[Tuple[float, float]]:
        starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", ffmpeg_stderr)]
        ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", ffmpeg_stderr)]

        if not starts:
            return [(0.0, total_duration)]

        segments: List[Tuple[float, float]] = []
        segments.append((0.0, starts[0]))
        for i, end in enumerate(ends):
            next_start = starts[i + 1] if i + 1 < len(starts) else total_duration
            segments.append((end, next_start))

        return [(s, e) for s, e in segments if (e - s) >= self.min_segment_duration]

    def detect_silence(self, input_path: str) -> str:
        result = subprocess.run(
            [
                "ffmpeg", "-i", input_path,
                "-af", f"silencedetect=noise={self.silence_threshold_db}dB:d={self.min_silence_duration}",
                "-f", "null", "-",
            ],
            capture_output=True, text=True,
        )
        return result.stderr

    def get_duration(self, input_path: str) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True,
        )
        return float(result.stdout.strip())

    def split(self, input_path: str, output_dir: str) -> List[str]:
        stderr = self.detect_silence(input_path)
        duration = self.get_duration(input_path)
        segments = self.parse_silence_boundaries(stderr, duration)

        base = os.path.splitext(os.path.basename(input_path))[0]
        output_files = []

        for i, (start, end) in enumerate(segments, 1):
            out_path = os.path.join(output_dir, f"{base}_set{i:02d}.wav")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", input_path,
                    "-ss", str(start), "-to", str(end),
                    "-c", "copy", out_path,
                ],
                capture_output=True,
            )
            output_files.append(out_path)

        return output_files

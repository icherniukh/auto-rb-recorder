import logging
import os
import subprocess
from datetime import datetime
from typing import Optional

log = logging.getLogger("rb-recorder")


class AudioCapture:
    """Captures audio from Rekordbox using audiotee (Core Audio Taps).

    audiotee outputs s16le PCM to stdout with --flush for immediate writes.
    On stop, converts raw PCM to WAV via ffmpeg.
    """

    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000,
                 source_name: str = "rekordbox"):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.source_name = source_name
        self.is_recording = False
        self._proc: Optional[subprocess.Popen] = None
        self._raw_path: Optional[str] = None
        self._output_path: Optional[str] = None
        self._raw_file = None

    def start(self):
        if self.is_recording:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._raw_path = os.path.join(self.output_dir, f".rb_session_{timestamp}.raw")
        self._output_path = os.path.join(self.output_dir, f"rb_session_{timestamp}.wav")

        self._raw_file = open(self._raw_path, "wb")
        self._proc = subprocess.Popen(
            [
                "audiotee",
                "--include-processes", str(self.pid),
                "--sample-rate", str(self.sample_rate),
                "--stereo",
                "--flush",
            ],
            stdout=self._raw_file,
            stderr=subprocess.DEVNULL,
        )
        self.is_recording = True

    def stop(self) -> Optional[str]:
        if not self.is_recording:
            return None

        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=10)
            self._proc = None

        if self._raw_file:
            self._raw_file.close()
            self._raw_file = None

        # Convert raw s16le PCM to WAV
        if self._raw_path and os.path.exists(self._raw_path):
            raw_size = os.path.getsize(self._raw_path)
            duration = raw_size / (self.sample_rate * 2 * 2)  # s16le stereo
            log.info(f"Raw capture: {raw_size} bytes ({duration:.1f}s)")
            if raw_size > 0:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-f", "s16le", "-ar", str(self.sample_rate), "-ac", "2",
                        "-i", self._raw_path,
                        "-c:a", "pcm_s16le", self._output_path,
                    ],
                    capture_output=True,
                )
            os.unlink(self._raw_path)

        self.is_recording = False
        return self._output_path

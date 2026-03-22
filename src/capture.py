import logging
import os
import subprocess
import tempfile
import threading
from datetime import datetime
from typing import Optional

log = logging.getLogger("rb-recorder")

# Capture script template. exec replaces the shell with timeout+AudioCapCLI
# so that SIGTERM reaches the right process. This approach is required because
# AudioCapCLI only flushes its output buffer when the parent process blocks
# on it (subprocess.run / wait) — non-blocking Popen produces 0 bytes.
_CAPTURE_SCRIPT = """#!/bin/bash
exec timeout {max_duration} AudioCapCLI --source {source} > "{raw_path}" 2>/dev/null
"""


class AudioCapture:
    """Captures audio from a named source using AudioCapCLI.

    Runs a blocking capture in a background thread. On stop, kills the
    capture process and converts the raw float32 PCM to 16-bit WAV via ffmpeg.
    """

    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000,
                 source_name: str = "rekordbox"):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.source_name = source_name
        self.is_recording = False
        self._thread: Optional[threading.Thread] = None
        self._script_path: Optional[str] = None
        self._raw_path: Optional[str] = None
        self._output_path: Optional[str] = None

    def _run_capture(self):
        """Blocking capture — runs in a background thread."""
        subprocess.run([self._script_path])

    def start(self):
        if self.is_recording:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._raw_path = os.path.join(self.output_dir, f".rb_session_{timestamp}.raw")
        self._output_path = os.path.join(self.output_dir, f"rb_session_{timestamp}.wav")

        # Write capture script
        fd, self._script_path = tempfile.mkstemp(suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(_CAPTURE_SCRIPT.format(
                max_duration=86400,
                source=self.source_name,
                raw_path=self._raw_path,
            ))
        os.chmod(self._script_path, 0o755)

        self._thread = threading.Thread(target=self._run_capture, daemon=True)
        self._thread.start()
        self.is_recording = True

    def stop(self) -> Optional[str]:
        if not self.is_recording:
            return None

        # Kill the capture process (timeout + AudioCapCLI via exec)
        os.system(f'pkill -f "timeout 86400 AudioCapCLI --source {self.source_name}"')

        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

        # Clean up script
        if self._script_path and os.path.exists(self._script_path):
            os.unlink(self._script_path)
            self._script_path = None

        # Convert raw float32 PCM to 16-bit WAV
        if self._raw_path and os.path.exists(self._raw_path):
            raw_size = os.path.getsize(self._raw_path)
            log.info(f"Raw capture: {raw_size} bytes ({raw_size / 384000:.1f}s)")
            if raw_size > 0:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-f", "f32le", "-ar", str(self.sample_rate), "-ac", "2",
                        "-i", self._raw_path,
                        "-c:a", "pcm_s16le", self._output_path,
                    ],
                    capture_output=True,
                )
            os.unlink(self._raw_path)

        self.is_recording = False
        return self._output_path

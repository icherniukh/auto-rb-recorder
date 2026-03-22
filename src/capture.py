import os
import subprocess
import threading
import wave
from datetime import datetime
from typing import Optional

import numpy as np

CHUNK_SIZE = 8192  # bytes per read from AudioCapCLI stdout


class AudioCapture:
    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000,
                 source_name: str = "rekordbox"):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.source_name = source_name
        self.is_recording = False
        self._proc: Optional[subprocess.Popen] = None
        self._wav: Optional[wave.Wave_write] = None
        self._output_path: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _reader_loop(self):
        while not self._stop_event.is_set():
            chunk = self._proc.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            samples = np.frombuffer(chunk, dtype=np.float32).copy()
            np.clip(samples, -1.0, 1.0, out=samples)
            int16_samples = (samples * 32767).astype(np.int16)
            self._wav.writeframes(int16_samples.tobytes())

    def start(self):
        if self.is_recording:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = os.path.join(self.output_dir, f"rb_session_{timestamp}.wav")

        self._wav = wave.open(self._output_path, "wb")
        self._wav.setnchannels(2)
        self._wav.setsampwidth(2)  # 16-bit PCM
        self._wav.setframerate(self.sample_rate)

        self._proc = subprocess.Popen(
            ["AudioCapCLI", "--source", self.source_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        self.is_recording = True

    def stop(self) -> Optional[str]:
        if not self.is_recording:
            return None

        self._stop_event.set()

        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=5)
            self._proc = None

        if self._reader_thread:
            self._reader_thread.join(timeout=5)
            self._reader_thread = None

        if self._wav:
            self._wav.close()
            self._wav = None

        self.is_recording = False
        return self._output_path

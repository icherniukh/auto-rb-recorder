import os
import threading
import wave
from datetime import datetime
from typing import Optional

import numpy as np
from proctap import ProcessAudioCapture


class AudioCapture:
    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.is_recording = False
        self._tap: Optional[ProcessAudioCapture] = None
        self._wav: Optional[wave.Wave_write] = None
        self._output_path: Optional[str] = None
        self._lock = threading.Lock()

    def _on_data(self, pcm: bytes, frames: int):
        with self._lock:
            if self._wav:
                samples = np.frombuffer(pcm, dtype=np.float32).copy()
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

        self._tap = ProcessAudioCapture(pid=self.pid, on_data=self._on_data)
        self._tap.start()
        self.is_recording = True

    def stop(self) -> Optional[str]:
        if not self.is_recording:
            return None

        if self._tap:
            self._tap.stop()
            self._tap.close()
            self._tap = None

        with self._lock:
            if self._wav:
                self._wav.close()
                self._wav = None

        self.is_recording = False
        return self._output_path

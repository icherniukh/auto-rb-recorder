import logging
import math
import os
import shutil
import subprocess
import threading
from array import array
from collections import deque
from datetime import datetime
from typing import Optional

log = logging.getLogger("rb-recorder")


def db_to_rms(db: float) -> float:
    # 0 dBFS = 32768 for 16-bit audio
    return 32768.0 * (10.0 ** (db / 20.0))


def _find_executable(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    # macOS LaunchAgents often lack standard interactive PATHs
    for fallback in [f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}"]:
        if os.path.exists(fallback):
            return fallback
    return name



class AudioCapture:
    """Captures audio from Rekordbox using audiotee (Core Audio Taps).

    Performs live chunk-based chunk evaluation for silence to prevent writing
    massive files during long idle periods. Splits continuous sessions into
    separate `.raw` files using a circular buffer to keep the decay tail,
    then automatically converts them to WAV via ffmpeg.
    """

    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000,
                 source_name: str = "rekordbox", silence_threshold_db: float = -50.0,
                 min_silence_duration: float = 15.0, decay_tail: float = 5.0,
                 export_format: str = "wav"):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.source_name = source_name
        self.export_format = export_format.lower()
        self.is_recording = False
        
        # Audio properties and chunking
        self.chunk_duration = 0.1  # 100ms chunks
        self.channels = 2
        self.bytes_per_sample = 2  # s16le
        self.chunk_size = int(self.sample_rate * self.chunk_duration * self.channels * self.bytes_per_sample)
        
        # Silence Detection Settings
        self.rms_threshold = db_to_rms(silence_threshold_db)
        self.silence_chunks_threshold = int(min_silence_duration / self.chunk_duration)
        self.buffer_maxlen = int(decay_tail / self.chunk_duration)
        
        self.state = "PASSIVE"
        self.ring_buffer = deque(maxlen=self.buffer_maxlen)
        self.silence_count = 0
        
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._raw_path: Optional[str] = None
        self._output_path: Optional[str] = None
        self._raw_file = None

    def _open_new_file(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._raw_path = os.path.join(self.output_dir, f".rb_session_{timestamp}.raw")
        self._output_path = os.path.join(self.output_dir, f"rb_session_{timestamp}.{self.export_format}")
        self._raw_file = open(self._raw_path, "wb")
        log.info(f"Opened new recording session: {self._raw_path}")
        
    def _close_current_file(self):
        if self._raw_file:
            self._raw_file.close()
            self._raw_file = None
            
        if self._raw_path and os.path.exists(self._raw_path):
            raw_size = os.path.getsize(self._raw_path)
            duration = raw_size / (self.sample_rate * self.channels * self.bytes_per_sample)
            log.info(f"Raw capture finished: {raw_size} bytes ({duration:.1f}s)")
            
            # Start conversion asynchronously so we don't block the next active session
            if raw_size > 0:
                def convert(raw_p, out_p, sr, fmt):
                    log.info(f"Converting {raw_p} to {out_p}")
                    
                    cmd = [
                        _find_executable("ffmpeg"), "-y",
                        "-f", "s16le", "-ar", str(sr), "-ac", "2",
                        "-i", raw_p
                    ]
                    
                    if fmt == "mp3":
                        cmd.extend(["-c:a", "libmp3lame", "-b:a", "320k", out_p])
                    else:
                        cmd.extend(["-c:a", "pcm_s16le", out_p])
                        
                    subprocess.run(cmd, capture_output=True)
                    os.unlink(raw_p)
                    log.info(f"Finished conversion: {out_p}")
                
                t = threading.Thread(target=convert, args=(self._raw_path, self._output_path, self.sample_rate, self.export_format))
                t.start()
            else:
                os.unlink(self._raw_path)
        
        self._raw_path = None
        self._output_path = None

    def _calculate_rms(self, chunk: bytes) -> float:
        # Array of 16-bit signed integers
        # 'h' is signed short (2 bytes)
        a = array('h', chunk)
        # Using a fast generator for sum of squares
        sum_squares = sum(x * x for x in a)
        if len(a) == 0:
            return 0.0
        return math.sqrt(sum_squares / len(a))

    def _read_loop(self):
        while self.is_recording and self._proc and self._proc.stdout:
            # Read exactly chunk_size bytes
            chunk = self._proc.stdout.read(self.chunk_size)
            if not chunk:
                break
                
            rms = self._calculate_rms(chunk)
            is_silent = rms < self.rms_threshold
            
            if self.state == "PASSIVE":
                self.ring_buffer.append(chunk)
                if not is_silent:
                    log.info(f"Audio detected! Transistioning to ACTIVE. RMS={rms:.1f} > {self.rms_threshold:.1f}")
                    self.state = "ACTIVE"
                    self._open_new_file()
                    # Flush the ring buffer to disk
                    for c in self.ring_buffer:
                        self._raw_file.write(c)
                    self.ring_buffer.clear()
                    self.silence_count = 0
            
            elif self.state == "ACTIVE":
                if self._raw_file:
                    self._raw_file.write(chunk)
                    
                if is_silent:
                    self.silence_count += 1
                    if self.silence_count >= self.silence_chunks_threshold:
                        log.info("Continuous silence detected. Transitioning to PASSIVE.")
                        self._close_current_file()
                        self.state = "PASSIVE"
                else:
                    self.silence_count = 0

    def start(self):
        if self.is_recording:
            return

        self.is_recording = True
        self.state = "PASSIVE"
        self.ring_buffer.clear()
        self.silence_count = 0

        self._proc = subprocess.Popen(
            [
                _find_executable("audiotee"),
                "--include-processes", str(self.pid),
                "--sample-rate", str(self.sample_rate),
                "--stereo",
                "--flush",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def stop(self) -> None:
        if not self.is_recording:
            return

        self.is_recording = True # Keep true during teardown
        
        if self._proc:
            self._proc.terminate()
            self._proc.wait(timeout=10)
            self._proc = None

        self.is_recording = False
        
        if self._reader_thread:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None

        if self.state == "ACTIVE":
            self._close_current_file()
            self.state = "PASSIVE"

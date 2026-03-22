# Rekordbox Auto-Recorder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a macOS daemon that automatically captures Rekordbox's audio output, records continuously while the app is running, and splits into individual set files by silence detection on exit.

**Architecture:** A Python daemon polls for the Rekordbox process. On detection, it uses ProcTap (a Python library wrapping macOS ScreenCaptureKit) to capture app-specific audio via callbacks and writes directly to WAV using Python's `wave` module. On Rekordbox exit, it finalizes the recording and runs FFmpeg silence-based splitting to produce individual set files.

**Tech Stack:** Python 3.12+, proc-tap (ScreenCaptureKit), FFmpeg (post-processing only), macOS 13.0+ LaunchAgent

**Prerequisites:**
- macOS 13.0+ (Ventura — required for ScreenCaptureKit process audio capture)
- `brew install ffmpeg` (post-processing: silence detection + splitting)
- `pip install proc-tap` (audio capture library)
- Screen Recording permission granted on first run (macOS system prompt)

**Key design decisions:**
- ProcTap replaces audiotee — native Python library, no subprocess piping for capture
- Python `wave` module writes WAV directly from PCM callbacks — FFmpeg only needed for post-processing
- "Record everything, split later" approach — no real-time VOX state machine needed
- ProcTap's built-in audio analysis (RMS/peak dB) available for future VOX enhancements

---

## Task 1: Validate Audio Capture Pipeline (PoC)

**Files:**
- Create: `scripts/poc_capture.py`

Validates that ProcTap can isolate and capture Rekordbox audio on macOS before writing any project code.

**Step 1: Install ProcTap**

```bash
pip install proc-tap
```

Run: `proctap --help`
Expected: Help output showing `--pid`, `--name`, `--stdout`, `--list-audio-procs` flags.

**Step 2: List audio processes and verify Rekordbox appears**

Open Rekordbox and play a track, then run:

```bash
proctap --list-audio-procs
```

Expected: Output includes a line with `rekordbox` and its PID.

**Step 3: Test CLI capture piped to FFmpeg**

```bash
RBPID=$(pgrep -x rekordbox)
proctap --pid $RBPID --stdout | timeout 10 ffmpeg -y -f s16le -ar 48000 -ac 2 -i pipe:0 -c:a pcm_s24le /tmp/rb_test_cli.wav || true
```

Run: `ffprobe /tmp/rb_test_cli.wav 2>&1 | grep -E "Duration|Audio"`
Expected: Shows duration ~10s, pcm_s24le codec, 48000 Hz, stereo.

**Step 4: Test Python API capture to WAV**

```python
# scripts/poc_capture.py
"""PoC: Capture Rekordbox audio using ProcTap Python API + wave module."""
import subprocess
import struct
import sys
import time
import wave

from proctap import ProcTap, StreamConfig


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    output = f"poc_capture_{int(time.time())}.wav"

    result = subprocess.run(["pgrep", "-x", "rekordbox"], capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Rekordbox not running")
        sys.exit(1)
    pid = int(result.stdout.strip().split("\n")[0])

    config = StreamConfig()
    config.sample_rate = 48000
    config.channels = 2

    wf = wave.open(output, "wb")
    wf.setnchannels(2)
    wf.setsampwidth(2)  # 16-bit = 2 bytes
    wf.setframerate(48000)

    def on_chunk(pcm: bytes, frames: int):
        wf.writeframes(pcm)

    tap = ProcTap(pid=pid, config=config, on_data=on_chunk)
    tap.start()
    print(f"Capturing {duration}s from Rekordbox (PID {pid})...")
    time.sleep(duration)
    tap.stop()
    tap.close()
    wf.close()
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()
```

Run: `python scripts/poc_capture.py 10`
Expected: Creates a WAV file. Play it back — should match Rekordbox output with no system sounds.

**Step 5: Commit**

```bash
git init
git add scripts/poc_capture.py
git commit -m "feat: PoC validating ProcTap capture from Rekordbox"
```

---

## Task 2: Process Monitor — Detect Rekordbox Lifecycle

**Files:**
- Create: `src/process_monitor.py`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_process_monitor.py`

The process monitor polls for Rekordbox and emits lifecycle events.

**Step 1: Write the failing test**

```python
# tests/test_process_monitor.py
import unittest
from unittest.mock import patch
from src.process_monitor import ProcessMonitor


class TestProcessMonitor(unittest.TestCase):
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_start(self, mock_find):
        mock_find.side_effect = [None, None, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])

    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_stop(self, mock_find):
        mock_find.side_effect = [12345, 12345, None]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345), ("stop",)])

    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_ignores_duplicate_start(self, mock_find):
        mock_find.side_effect = [12345, 12345, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_process_monitor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.process_monitor'`

**Step 3: Write minimal implementation**

```python
# src/process_monitor.py
import subprocess
from typing import Callable, Optional


class ProcessMonitor:
    def __init__(self, process_name: str, poll_interval: float = 2.0):
        self.process_name = process_name
        self.poll_interval = poll_interval
        self.on_start: Callable[[int], None] = lambda pid: None
        self.on_stop: Callable[[], None] = lambda: None
        self._current_pid: Optional[int] = None

    def _find_pid(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.process_name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return int(result.stdout.strip().split("\n")[0])
        except (ValueError, subprocess.SubprocessError):
            pass
        return None

    def poll_once(self):
        pid = self._find_pid()
        was_running = self._current_pid is not None
        is_running = pid is not None

        if is_running and not was_running:
            self._current_pid = pid
            self.on_start(pid)
        elif not is_running and was_running:
            self._current_pid = None
            self.on_stop()
```

**Step 4: Create package init files**

```python
# src/__init__.py
# tests/__init__.py
```

(Both empty.)

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_process_monitor.py -v`
Expected: 3 passed.

**Step 6: Commit**

```bash
git add src/__init__.py src/process_monitor.py tests/__init__.py tests/test_process_monitor.py
git commit -m "feat: process monitor detects Rekordbox start/stop by PID"
```

---

## Task 3: Audio Capture — ProcTap + WAV Writer

**Files:**
- Create: `src/capture.py`
- Test: `tests/test_capture.py`

Uses ProcTap's Python callback API to receive PCM chunks and writes them to a WAV file via the `wave` module. No subprocess piping needed.

**Step 1: Write the failing test**

```python
# tests/test_capture.py
import os
import struct
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call
from src.capture import AudioCapture


class TestAudioCapture(unittest.TestCase):
    @patch("src.capture.ProcTap")
    def test_start_opens_wav_and_starts_tap(self, MockProcTap):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            MockProcTap.assert_called_once()
            MockProcTap.return_value.start.assert_called_once()
            self.assertTrue(cap.is_recording)
            # WAV file should be created
            self.assertIsNotNone(cap._output_path)
            self.assertTrue(os.path.exists(cap._output_path))

            cap.stop()

    @patch("src.capture.ProcTap")
    def test_stop_closes_tap_and_wav(self, MockProcTap):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()
            output_path = cap.stop()

            MockProcTap.return_value.stop.assert_called_once()
            MockProcTap.return_value.close.assert_called_once()
            self.assertFalse(cap.is_recording)
            self.assertTrue(output_path.endswith(".wav"))

    def test_stop_without_start_is_noop(self):
        cap = AudioCapture(pid=12345, output_dir="/tmp", sample_rate=48000)
        result = cap.stop()
        self.assertIsNone(result)

    @patch("src.capture.ProcTap")
    def test_on_data_writes_to_wav(self, MockProcTap):
        with tempfile.TemporaryDirectory() as tmpdir:
            cap = AudioCapture(pid=12345, output_dir=tmpdir, sample_rate=48000)
            cap.start()

            # Extract the on_data callback that was passed to ProcTap
            _, kwargs = MockProcTap.call_args
            on_data = kwargs["on_data"]

            # Simulate receiving audio data (1 frame of stereo 16-bit silence)
            silence = struct.pack("<hh", 0, 0)
            on_data(silence * 100, 100)

            output_path = cap.stop()

            # Verify file has content
            self.assertTrue(os.path.getsize(output_path) > 44)  # > WAV header


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_capture.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/capture.py
import os
import threading
import wave
from datetime import datetime
from typing import Optional

from proctap import ProcTap, StreamConfig


class AudioCapture:
    def __init__(self, pid: int, output_dir: str, sample_rate: int = 48000):
        self.pid = pid
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.is_recording = False
        self._tap: Optional[ProcTap] = None
        self._wav: Optional[wave.Wave_write] = None
        self._output_path: Optional[str] = None
        self._lock = threading.Lock()

    def _on_data(self, pcm: bytes, frames: int):
        with self._lock:
            if self._wav:
                self._wav.writeframes(pcm)

    def start(self):
        if self.is_recording:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._output_path = os.path.join(self.output_dir, f"rb_session_{timestamp}.wav")

        self._wav = wave.open(self._output_path, "wb")
        self._wav.setnchannels(2)
        self._wav.setsampwidth(2)  # 16-bit PCM
        self._wav.setframerate(self.sample_rate)

        config = StreamConfig()
        config.sample_rate = self.sample_rate
        config.channels = 2

        self._tap = ProcTap(pid=self.pid, config=config, on_data=self._on_data)
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_capture.py -v`
Expected: 4 passed.

**Step 5: Commit**

```bash
git add src/capture.py tests/test_capture.py
git commit -m "feat: audio capture using ProcTap callbacks + wave writer"
```

---

## Task 4: Silence Splitter — Post-Session File Splitting

**Files:**
- Create: `src/splitter.py`
- Test: `tests/test_splitter.py`

After a session recording completes, this module uses FFmpeg's `silencedetect` to find silence boundaries and splits the file into individual sets.

**Step 1: Write the failing test**

```python
# tests/test_splitter.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_splitter.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/splitter.py
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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_splitter.py -v`
Expected: 3 passed.

**Step 5: Commit**

```bash
git add src/splitter.py tests/test_splitter.py
git commit -m "feat: silence-based splitter for post-session file splitting"
```

---

## Task 5: Configuration

**Files:**
- Create: `src/config.py`
- Create: `config.default.toml`
- Test: `tests/test_config.py`

Centralizes all tunable parameters with sensible defaults. Uses TOML (stdlib in Python 3.11+).

**Step 1: Write the failing test**

```python
# tests/test_config.py
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# src/config.py
import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class Config:
    # Recording
    sample_rate: int = 48000
    output_dir: str = field(
        default_factory=lambda: os.path.expanduser("~/Music/RekordboxRecordings")
    )

    # Trigger / splitter
    silence_threshold_db: float = -50
    min_silence_duration: float = 15
    min_segment_duration: float = 30
    decay_tail: float = 5

    # Process monitor
    process_name: str = "rekordbox"
    poll_interval: float = 2.0

    @classmethod
    def from_file(cls, path: str) -> "Config":
        with open(path, "rb") as f:
            data = tomllib.load(f)

        cfg = cls()
        rec = data.get("recording", {})
        trig = data.get("trigger", {})
        monitor = data.get("monitor", {})

        if "sample_rate" in rec:
            cfg.sample_rate = rec["sample_rate"]
        if "output_dir" in rec:
            cfg.output_dir = rec["output_dir"]
        if "silence_threshold_db" in trig:
            cfg.silence_threshold_db = trig["silence_threshold_db"]
        if "min_silence_duration" in trig:
            cfg.min_silence_duration = trig["min_silence_duration"]
        if "min_segment_duration" in trig:
            cfg.min_segment_duration = trig["min_segment_duration"]
        if "decay_tail" in trig:
            cfg.decay_tail = trig["decay_tail"]
        if "process_name" in monitor:
            cfg.process_name = monitor["process_name"]
        if "poll_interval" in monitor:
            cfg.poll_interval = monitor["poll_interval"]

        return cfg
```

**Step 4: Write the default config file**

```toml
# config.default.toml — Rekordbox Auto-Recorder defaults
# Copy to ~/.config/rb-recorder/config.toml to customize.

[recording]
sample_rate = 48000
output_dir = "~/Music/RekordboxRecordings"

[trigger]
silence_threshold_db = -50   # dB level below which audio is "silence"
min_silence_duration = 15    # seconds of silence before splitting
min_segment_duration = 30    # discard segments shorter than this
decay_tail = 5               # seconds to keep recording after silence

[monitor]
process_name = "rekordbox"
poll_interval = 2.0          # seconds between process checks
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: 2 passed.

**Step 6: Commit**

```bash
git add src/config.py config.default.toml tests/test_config.py
git commit -m "feat: TOML-based configuration with sensible defaults"
```

---

## Task 6: Main Daemon — Wire Everything Together

**Files:**
- Create: `src/daemon.py`
- Test: `tests/test_daemon.py`

The daemon is the top-level orchestrator: it wires the process monitor, audio capture, and splitter into a single run loop.

**Step 1: Write the failing test**

```python
# tests/test_daemon.py
import unittest
from unittest.mock import patch, MagicMock
from src.daemon import RecorderDaemon
from src.config import Config


class TestRecorderDaemon(unittest.TestCase):
    @patch("src.daemon.SilenceSplitter")
    @patch("src.daemon.AudioCapture")
    @patch("src.daemon.ProcessMonitor")
    def test_start_recording_on_process_detected(self, MockMonitor, MockCapture, MockSplitter):
        cfg = Config(output_dir="/tmp/test_output")
        daemon = RecorderDaemon(cfg)

        daemon._on_rekordbox_start(pid=12345)

        MockCapture.assert_called_once_with(
            pid=12345, output_dir="/tmp/test_output", sample_rate=48000
        )
        MockCapture.return_value.start.assert_called_once()

    @patch("src.daemon.SilenceSplitter")
    @patch("src.daemon.AudioCapture")
    @patch("src.daemon.ProcessMonitor")
    def test_stop_recording_and_split_on_process_exit(self, MockMonitor, MockCapture, MockSplitter):
        cfg = Config(output_dir="/tmp/test_output")
        daemon = RecorderDaemon(cfg)

        mock_capture = MagicMock()
        mock_capture.stop.return_value = "/tmp/test_output/session.wav"
        daemon._capture = mock_capture

        daemon._on_rekordbox_stop()

        mock_capture.stop.assert_called_once()
        MockSplitter.return_value.split.assert_called_once_with(
            "/tmp/test_output/session.wav", "/tmp/test_output"
        )


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daemon.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# src/daemon.py
import logging
import os
import signal
import time
from typing import Optional

from src.capture import AudioCapture
from src.config import Config
from src.process_monitor import ProcessMonitor
from src.splitter import SilenceSplitter

log = logging.getLogger("rb-recorder")


class RecorderDaemon:
    def __init__(self, config: Config):
        self.config = config
        self._capture: Optional[AudioCapture] = None
        self._running = False

        self._monitor = ProcessMonitor(
            config.process_name, poll_interval=config.poll_interval
        )
        self._monitor.on_start = self._on_rekordbox_start
        self._monitor.on_stop = self._on_rekordbox_stop

        self._splitter = SilenceSplitter(
            silence_threshold_db=config.silence_threshold_db,
            min_silence_duration=config.min_silence_duration,
            min_segment_duration=config.min_segment_duration,
        )

    def _on_rekordbox_start(self, pid: int):
        log.info(f"Rekordbox detected (PID {pid}). Starting recording.")
        os.makedirs(self.config.output_dir, exist_ok=True)
        self._capture = AudioCapture(
            pid=pid,
            output_dir=self.config.output_dir,
            sample_rate=self.config.sample_rate,
        )
        self._capture.start()

    def _on_rekordbox_stop(self):
        if not self._capture:
            return
        log.info("Rekordbox closed. Stopping recording.")
        output_path = self._capture.stop()
        self._capture = None

        if output_path and os.path.exists(output_path):
            log.info(f"Splitting session: {output_path}")
            files = self._splitter.split(output_path, self.config.output_dir)
            log.info(f"Created {len(files)} set file(s): {files}")

    def run(self):
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        log.info("Rekordbox Auto-Recorder armed. Waiting for Rekordbox...")

        while self._running:
            self._monitor.poll_once()
            time.sleep(self.config.poll_interval)

    def _handle_shutdown(self, signum, frame):
        log.info("Shutdown signal received.")
        self._running = False
        self._on_rekordbox_stop()
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_daemon.py -v`
Expected: 2 passed.

**Step 5: Commit**

```bash
git add src/daemon.py tests/test_daemon.py
git commit -m "feat: main daemon wiring process monitor, capture, and splitter"
```

---

## Task 7: CLI Entry Point

**Files:**
- Create: `src/__main__.py`

Provides the `python -m src` entry point.

**Step 1: Write the entry point**

```python
# src/__main__.py
import argparse
import logging
import os

from src.config import Config
from src.daemon import RecorderDaemon


def main():
    parser = argparse.ArgumentParser(description="Rekordbox Auto-Recorder")
    parser.add_argument(
        "-c", "--config",
        default=os.path.expanduser("~/.config/rb-recorder/config.toml"),
        help="Path to config file",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if os.path.exists(args.config):
        config = Config.from_file(args.config)
    else:
        config = Config()

    daemon = RecorderDaemon(config)
    daemon.run()


if __name__ == "__main__":
    main()
```

**Step 2: Test manually**

Run: `python -m src --verbose`
Expected: Logs `Rekordbox Auto-Recorder armed. Waiting for Rekordbox...` and polls every 2 seconds. Ctrl+C exits cleanly.

**Step 3: Commit**

```bash
git add src/__main__.py
git commit -m "feat: CLI entry point with config loading and verbose flag"
```

---

## Task 8: macOS LaunchAgent for Auto-Start

**Files:**
- Create: `install/com.rb-recorder.plist`
- Create: `scripts/install.sh`

A LaunchAgent plist ensures the daemon starts at login and stays running.

**Step 1: Write the LaunchAgent plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rb-recorder</string>
    <key>ProgramArguments</key>
    <array>
        <string>__PYTHON_PATH__</string>
        <string>-m</string>
        <string>src</string>
    </array>
    <key>WorkingDirectory</key>
    <string>__INSTALL_DIR__</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/rb-recorder.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/rb-recorder.log</string>
</dict>
</plist>
```

**Step 2: Write the install script**

```bash
#!/usr/bin/env bash
# scripts/install.sh — Install rb-recorder as a macOS LaunchAgent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$SCRIPT_DIR/install/com.rb-recorder.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.rb-recorder.plist"
PYTHON_PATH="$(which python3)"

sed -e "s|__INSTALL_DIR__|$SCRIPT_DIR|g" \
    -e "s|__PYTHON_PATH__|$PYTHON_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed. Daemon will start at login."
echo "  Python: $PYTHON_PATH"
echo "  Logs:   /tmp/rb-recorder.log"
echo "  Uninstall: launchctl unload $PLIST_DST && rm $PLIST_DST"
```

**Step 3: Commit**

```bash
git add install/com.rb-recorder.plist scripts/install.sh
git commit -m "feat: macOS LaunchAgent for auto-start at login"
```

---

## Task 9: Integration Test — Full End-to-End

**Files:**
- Create: `scripts/integration_test.sh`

A manual integration test script that validates the full pipeline with a real Rekordbox session.

**Step 1: Write the integration test script**

```bash
#!/usr/bin/env bash
# scripts/integration_test.sh — Full end-to-end integration test
set -euo pipefail

OUTPUT_DIR="/tmp/rb_recorder_integration_test"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "=== Rekordbox Auto-Recorder Integration Test ==="
echo ""
echo "Prerequisites:"
echo "  1. Rekordbox is NOT running"
echo "  2. pip install proc-tap"
echo "  3. ffmpeg is installed (ffmpeg -version)"
echo "  4. Screen Recording permission granted"
echo ""
read -p "Press Enter to start the daemon..."

python -m src -v 2>&1 | tee "$OUTPUT_DIR/daemon.log" &
DAEMON_PID=$!
echo "Daemon started (PID $DAEMON_PID)"
echo ""

echo "--- Step 1: Open Rekordbox and play a track for ~30 seconds ---"
read -p "Press Enter when done..."

echo "--- Step 2: Stop playback and wait ~20 seconds (silence gap) ---"
read -p "Press Enter after 20 seconds of silence..."

echo "--- Step 3: Play another track for ~30 seconds ---"
read -p "Press Enter when done..."

echo "--- Step 4: Quit Rekordbox ---"
read -p "Press Enter after Rekordbox has fully closed..."

sleep 5
kill $DAEMON_PID 2>/dev/null || true

echo ""
echo "=== Results ==="
ls -lh ~/Music/RekordboxRecordings/ 2>/dev/null || echo "No output files found!"
echo ""
echo "Check the WAV files for:"
echo "  - Two separate set files (split by silence)"
echo "  - Clean audio without system sounds"
echo "  - No missing audio at track starts"
echo "  - Reverb tails preserved at track ends"
```

**Step 2: Commit**

```bash
git add scripts/integration_test.sh
git commit -m "feat: integration test script for manual end-to-end validation"
```

---

## Task Summary

| Task | Component | Dependency | Tests |
|------|-----------|-----------|-------|
| 1 | PoC — Validate ProcTap capture | None (manual) | Manual |
| 2 | Process Monitor | None | 3 unit |
| 3 | Audio Capture (ProcTap + wave) | proc-tap | 4 unit |
| 4 | Silence Splitter | ffmpeg | 3 unit |
| 5 | Configuration | None | 2 unit |
| 6 | Main Daemon | Tasks 2-5 | 2 unit |
| 7 | CLI Entry Point | Task 6 | Manual |
| 8 | LaunchAgent Install | Task 7 | Manual |
| 9 | Integration Test | All | Manual E2E |

**Total: 9 tasks, ~14 unit tests, 1 integration test script**

**Only external dependency for capture:** `pip install proc-tap`
**FFmpeg role reduced to:** post-processing only (silence detection + splitting)

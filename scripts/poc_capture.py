#!/usr/bin/env python3
"""PoC: Capture audio from Rekordbox via ProcTap and write to WAV.

Validates that the ProcTap audio capture pipeline works end-to-end.
Captures float32 PCM from the target process, converts to int16,
and writes a standard WAV file.

Usage:
    python scripts/poc_capture.py [duration_seconds]
"""

import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
from proctap import STANDARD_CHANNELS, STANDARD_SAMPLE_RATE, ProcessAudioCapture


def find_rekordbox_pid() -> int:
    """Find Rekordbox PID via pgrep. Exits if not running."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "rekordbox"],
            capture_output=True,
            text=True,
            check=True,
        )
        pid = int(result.stdout.strip().splitlines()[0])
        return pid
    except (subprocess.CalledProcessError, ValueError, IndexError):
        print("ERROR: Rekordbox is not running.", file=sys.stderr)
        print("Start Rekordbox and try again.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    # Parse optional duration argument
    duration = 10.0
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
            if duration <= 0:
                raise ValueError
        except ValueError:
            print(f"ERROR: Invalid duration: {sys.argv[1]}", file=sys.stderr)
            print("Usage: poc_capture.py [duration_seconds]", file=sys.stderr)
            sys.exit(1)

    # Find Rekordbox
    pid = find_rekordbox_pid()
    print(f"Found Rekordbox (PID {pid})")

    # Prepare output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"poc_capture_{timestamp}.wav")

    # Open WAV file for writing (int16, stereo, 48kHz)
    wf = wave.open(str(output_path), "wb")
    wf.setnchannels(STANDARD_CHANNELS)
    wf.setsampwidth(2)  # 2 bytes for int16
    wf.setframerate(STANDARD_SAMPLE_RATE)

    frames_written = 0

    def on_data(pcm: bytes, frames: int) -> None:
        """Callback: convert float32 PCM to int16 and write to WAV."""
        nonlocal frames_written
        samples = np.frombuffer(pcm, dtype=np.float32)
        # Clip to [-1.0, 1.0] to avoid int16 overflow, then convert
        np.clip(samples, -1.0, 1.0, out=samples)
        int16_samples = (samples * 32767).astype(np.int16)
        wf.writeframes(int16_samples.tobytes())
        frames_written += frames

    # Start capture
    cap = ProcessAudioCapture(pid=pid, on_data=on_data)
    print(f"Capturing {duration}s of audio to {output_path} ...")
    cap.start()

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        cap.stop()
        cap.close()
        wf.close()

    total_seconds = frames_written / STANDARD_SAMPLE_RATE
    print(f"Done. Wrote {frames_written} frames ({total_seconds:.1f}s) to {output_path}")


if __name__ == "__main__":
    main()

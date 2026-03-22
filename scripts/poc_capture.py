#!/usr/bin/env python3
"""PoC: Capture audio from Rekordbox via AudioCapCLI and write to WAV.

Uses Core Audio Taps API (via AudioCapCLI) to capture app-specific audio.

Usage:
    python scripts/poc_capture.py [duration_seconds]
"""

import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK_SIZE = 8192


def check_prerequisites() -> None:
    if not shutil.which("AudioCapCLI"):
        print("ERROR: AudioCapCLI not found in PATH.", file=sys.stderr)
        print("Install: https://github.com/pi0neerpat/AudioCapCLI/releases", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(["pgrep", "-x", "rekordbox"], capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Rekordbox is not running.", file=sys.stderr)
        sys.exit(1)

    # Verify AudioCapCLI can see Rekordbox
    result = subprocess.run(
        ["AudioCapCLI", "--list-sources"],
        capture_output=True, text=True, timeout=5,
    )
    if "rekordbox" not in result.stdout.lower():
        print("ERROR: AudioCapCLI cannot see Rekordbox audio.", file=sys.stderr)
        print("Check System Audio Recording permission.", file=sys.stderr)
        sys.exit(1)
    print("AudioCapCLI: OK (Rekordbox audio source found)")


def main() -> None:
    duration = 10.0
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
            if duration <= 0:
                raise ValueError
        except ValueError:
            print(f"ERROR: Invalid duration: {sys.argv[1]}", file=sys.stderr)
            sys.exit(1)

    check_prerequisites()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"poc_capture_{timestamp}.wav")

    wf = wave.open(str(output_path), "wb")
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)

    proc = subprocess.Popen(
        ["AudioCapCLI", "--source", "rekordbox"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    print(f"Capturing {duration}s of audio to {output_path} ...")
    frames_written = 0
    start_time = time.monotonic()

    try:
        while time.monotonic() - start_time < duration:
            chunk = proc.stdout.read(CHUNK_SIZE)
            if not chunk:
                break
            samples = np.frombuffer(chunk, dtype=np.float32).copy()
            np.clip(samples, -1.0, 1.0, out=samples)
            int16_samples = (samples * 32767).astype(np.int16)
            wf.writeframes(int16_samples.tobytes())
            frames_written += len(int16_samples) // CHANNELS
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        wf.close()

    total_seconds = frames_written / SAMPLE_RATE
    if frames_written == 0:
        print("ERROR: No audio captured.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Done. Wrote {frames_written} frames ({total_seconds:.1f}s) to {output_path}")


if __name__ == "__main__":
    main()

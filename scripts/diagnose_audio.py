#!/usr/bin/env python3
"""Diagnose audio format from ProcTap — logs chunk sizes, byte counts, and format info."""
import subprocess
import sys
import time
from proctap import ProcessAudioCapture, STANDARD_SAMPLE_RATE, STANDARD_CHANNELS

result = subprocess.run(["pgrep", "-x", "rekordbox"], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR: Rekordbox not running"); sys.exit(1)
pid = int(result.stdout.strip().splitlines()[0])
print(f"Rekordbox PID: {pid}")

chunks = []

def on_data(pcm: bytes, frames: int):
    chunks.append((len(pcm), frames))

cap = ProcessAudioCapture(pid=pid, on_data=on_data)
cap.start()
print("Capturing 3 seconds...")
time.sleep(3)
cap.stop()
cap.close()

if not chunks:
    print("ERROR: No audio data received!")
    sys.exit(1)

print(f"\nReceived {len(chunks)} chunks")
print(f"First 5 chunks (bytes, frames):")
for i, (nbytes, nframes) in enumerate(chunks[:5]):
    bytes_per_frame = nbytes / nframes if nframes > 0 else 0
    bytes_per_sample = bytes_per_frame / 2  # assuming stereo
    print(f"  chunk {i}: {nbytes} bytes, {nframes} frames, "
          f"{bytes_per_frame:.1f} bytes/frame, {bytes_per_sample:.1f} bytes/sample")

total_bytes = sum(b for b, _ in chunks)
total_frames = sum(f for _, f in chunks)
bytes_per_frame = total_bytes / total_frames if total_frames else 0
bytes_per_sample = bytes_per_frame / 2

print(f"\nTotals:")
print(f"  {total_bytes} bytes, {total_frames} frames")
print(f"  {bytes_per_frame:.1f} bytes/frame")
print(f"  {bytes_per_sample:.1f} bytes/sample")
print(f"  Expected for float32 stereo: 8.0 bytes/frame, 4.0 bytes/sample")
print(f"  Expected for int16 stereo:   4.0 bytes/frame, 2.0 bytes/sample")

expected_frames_3s = STANDARD_SAMPLE_RATE * 3
print(f"\n  Expected frames for 3s @ {STANDARD_SAMPLE_RATE}Hz: {expected_frames_3s}")
print(f"  Actual frames: {total_frames}")
print(f"  Ratio: {total_frames / expected_frames_3s:.3f}x")

if bytes_per_frame == 8.0:
    print("\n=> Format is float32 stereo (as expected)")
elif bytes_per_frame == 4.0:
    print("\n=> Format is int16 stereo OR float32 mono!")
    print("   If your WAV sounds sped up 2x, the data is likely int16 already")
elif bytes_per_frame == 16.0:
    print("\n=> Format is float64 stereo or float32 quad-channel!")
else:
    print(f"\n=> Unexpected format: {bytes_per_frame} bytes/frame")

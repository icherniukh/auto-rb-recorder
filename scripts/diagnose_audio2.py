#!/usr/bin/env python3
"""Deeper audio format diagnosis — checks actual sample values and byte rates."""
import struct
import subprocess
import sys
import time
from proctap import ProcessAudioCapture

result = subprocess.run(["pgrep", "-x", "rekordbox"], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR: Rekordbox not running"); sys.exit(1)
pid = int(result.stdout.strip().splitlines()[0])

raw_data = bytearray()
timestamps = []

def on_data(pcm: bytes, frames: int):
    raw_data.extend(pcm)
    timestamps.append(time.monotonic())

cap = ProcessAudioCapture(pid=pid, on_data=on_data)
t0 = time.monotonic()
cap.start()
time.sleep(3)
cap.stop()
cap.close()
elapsed = time.monotonic() - t0

if not raw_data:
    print("ERROR: No data"); sys.exit(1)

total = len(raw_data)
print(f"Captured {total} bytes in {elapsed:.2f}s")
print(f"Byte rate: {total / elapsed:.0f} bytes/sec")
print()

# Check what the data looks like as float32
print("=== Interpreting as float32 stereo ===")
bytes_per_sec = total / elapsed
frames_per_sec_f32 = bytes_per_sec / 8  # 4 bytes × 2 channels
print(f"  Implied sample rate: {frames_per_sec_f32:.0f} Hz")
# Peek at first few samples
vals_f32 = struct.unpack_from(f'<{min(20, total//4)}f', raw_data)
print(f"  First 10 values: {[f'{v:.6f}' for v in vals_f32[:10]]}")
all_in_range = all(-1.5 <= v <= 1.5 for v in vals_f32[:100])
print(f"  Values in [-1.5, 1.5]: {all_in_range}")

print()
print("=== Interpreting as int16 stereo ===")
frames_per_sec_i16 = bytes_per_sec / 4  # 2 bytes × 2 channels
print(f"  Implied sample rate: {frames_per_sec_i16:.0f} Hz")
vals_i16 = struct.unpack_from(f'<{min(20, total//2)}h', raw_data)
print(f"  First 10 values: {list(vals_i16[:10])}")

print()
print("=== Interpreting as float32 MONO ===")
frames_per_sec_f32_mono = bytes_per_sec / 4  # 4 bytes × 1 channel
print(f"  Implied sample rate: {frames_per_sec_f32_mono:.0f} Hz")

# Save raw for manual inspection
with open("/tmp/rb_raw_diag.pcm", "wb") as f:
    f.write(raw_data)
print(f"\nRaw data saved to /tmp/rb_raw_diag.pcm ({total} bytes)")
print("Try playing with ffplay:")
print(f"  ffplay -f f32le -ar 48000 -ac 2 /tmp/rb_raw_diag.pcm")
print(f"  ffplay -f f32le -ar 44100 -ac 2 /tmp/rb_raw_diag.pcm")
print(f"  ffplay -f s16le -ar 48000 -ac 2 /tmp/rb_raw_diag.pcm")

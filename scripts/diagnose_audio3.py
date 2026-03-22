#!/usr/bin/env python3
"""Check if captured data actually contains audio or is all silence."""
import subprocess
import sys
import time
import numpy as np
from proctap import ProcessAudioCapture

result = subprocess.run(["pgrep", "-x", "rekordbox"], capture_output=True, text=True)
if result.returncode != 0:
    print("ERROR: Rekordbox not running"); sys.exit(1)
pid = int(result.stdout.strip().splitlines()[0])

chunks_raw = []

def on_data(pcm: bytes, frames: int):
    chunks_raw.append(pcm)

cap = ProcessAudioCapture(pid=pid, on_data=on_data)
cap.start()
print(f"Capturing 5 seconds from Rekordbox PID {pid}...")
print("MAKE SURE A TRACK IS PLAYING LOUD")
time.sleep(5)
cap.stop()
cap.close()

if not chunks_raw:
    print("ERROR: No chunks received"); sys.exit(1)

print(f"\nReceived {len(chunks_raw)} chunks")

# Analyze each chunk
for i, chunk in enumerate(chunks_raw):
    as_f32 = np.frombuffer(chunk, dtype=np.float32)
    as_i16 = np.frombuffer(chunk, dtype=np.int16)

    f32_nonzero = np.count_nonzero(as_f32)
    f32_max = np.max(np.abs(as_f32))
    i16_nonzero = np.count_nonzero(as_i16)
    i16_max = np.max(np.abs(as_i16))

    if i < 5 or i == len(chunks_raw) - 1 or f32_nonzero > 0:
        label = "FIRST" if i < 5 else ("LAST" if i == len(chunks_raw) - 1 else "HAS DATA")
        print(f"  chunk {i:3d} [{label}]: {len(chunk)} bytes | "
              f"f32: {f32_nonzero}/{len(as_f32)} nonzero, max={f32_max:.6f} | "
              f"i16: {i16_nonzero}/{len(as_i16)} nonzero, max={i16_max}")

    # Stop printing after first 5 chunks with data to avoid spam
    if i >= 10 and f32_nonzero > 0:
        remaining_with_data = sum(1 for c in chunks_raw[i+1:] if np.any(np.frombuffer(c, dtype=np.float32)))
        print(f"  ... {remaining_with_data} more chunks with data")
        break

# Full buffer analysis
full = np.frombuffer(b''.join(chunks_raw), dtype=np.float32)
total_nonzero = np.count_nonzero(full)
print(f"\nFull buffer: {len(full)} float32 values, {total_nonzero} nonzero ({100*total_nonzero/len(full):.1f}%)")
print(f"  Range: [{full.min():.6f}, {full.max():.6f}]")
if total_nonzero > 0:
    rms = np.sqrt(np.mean(full ** 2))
    print(f"  RMS level: {rms:.6f} ({20*np.log10(rms+1e-10):.1f} dB)")
else:
    print("  ALL ZEROS — ScreenCaptureKit is NOT getting Rekordbox audio!")
    print("  This is a permission or routing issue, not a format issue.")

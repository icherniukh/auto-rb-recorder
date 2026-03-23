# Rekordbox Auto-Recorder

A macOS daemon that automatically captures a DJ's audio output from Pioneer Rekordbox directly using the Core Audio Taps API.

When Rekordbox launches, recording starts silently. When Rekordbox quits, the recording automatically stops, converts the raw capture into a standard WAV or MP3, and natively isolates the set into a single file by stripping away gigabytes of idle silence before and after the set.

## Architecture & Data Flow

```
Process Monitor ──► Audio Capture ──► Silence State Machine
(pgrep polling)     (audiotee→raw)    (ring buffer memory limit)
       │                  │                    │
       ▼                  ▼                    ▼
  Rekordbox PID    .raw float32 PCM      rb_session_{date}.wav
  start/stop          → WAV/MP3 
```

**Data flow:** `audiotee --include-processes PID` → python chunk stream → circular buffer silence evaluation → `ffmpeg` background conversion to WAV/MP3.

## Features

- **Pioneer Rekordbox Support** — Successfully taps into Rekordbox's custom audio engine, bypassing the usual ScreenCaptureKit restrictions that lead to dead/silent screen recordings.
- **Smart Silence Autodetection** — Live audio is evaluated chunk-by-chunk for volume (RMS). Recording completely pauses during extended silence (e.g. before the club opens), effectively splitting huge, day-long recording sessions into isolated 1-2 hour sets automatically without disk bloat.
- **Background Daemon** — Detects Rekordbox launch and exit via process polling, running silently alongside your setup.
- **WAV & MP3 Export** — High quality natively exported tracks. Defaults to WAV but MP3 320k encoding can be selected.
- **Graceful Termination** — Even if Rekordbox crashes, the isolated ring buffer ensures your mix is completely saved, flushed, and converted successfully.

## Prerequisites

- macOS 14.2+ (Core Audio Taps API requirement)
- `brew install ffmpeg`
- `audiotee` (bundled via submodule or built from source).

## Installation

This project is built and installed using `pyinstaller` to create a compiled app executable, helping bypass macOS dynamic privacy issues regarding Screen Recording permissions.

```bash
# 1. Clone the repository and submodules
git clone --recurse-submodules https://github.com/your-username/auto-rb-recorder.git
cd auto-rb-recorder

# 2. Build the python daemon
uv pip install pyinstaller
bash scripts/build.sh

# 3. Setup the Config
cp config.default.toml ~/.config/rb-recorder/config.toml

# 4. Install the LaunchAgent
bash scripts/install.sh
```

### macOS Permissions
You **must** give the generated `dist/auto-rb-recorder` application **Screen Recording** permissions in `System Settings -> Privacy & Security`. This is required for *any* application to utilize `Core Audio Taps` on macOS 14.2+.

## Configuration

All parameters are tunable via `~/.config/rb-recorder/config.toml`.

```toml
[recording]
sample_rate = 48000
output_dir = "~/Music/auto-rb-recorder"
export_format = "wav"  # allow "wav" or "mp3"

[trigger]
silence_threshold_db = -50
min_silence_duration = 15
decay_tail = 5

[monitor]
process_name = "rekordbox"
poll_interval = 2.0
```

# Rekordbox Auto-Recorder — Agent Instructions

## Overview

A macOS daemon that automatically captures a DJ's audio output from Pioneer Rekordbox. When Rekordbox launches, recording starts silently. When Rekordbox quits, the recording stops, converts to WAV, and splits into individual set files by silence detection.

**Stack:** Python 3.12+ (orchestration), audiotee (Core Audio Taps capture), FFmpeg (encoding + splitting), macOS 14.2+

**Key constraint:** ScreenCaptureKit cannot capture Rekordbox audio (returns all zeros) because Rekordbox uses a custom audio engine. The project uses Core Audio Taps (`AudioHardwareCreateProcessTap`) via `audiotee` instead. See `research-findings.md` for the full technical investigation.

## Architecture

```
Process Monitor ──► Audio Capture ──► Silence Splitter
(pgrep polling)     (audiotee→raw)    (ffmpeg silencedetect)
       │                  │                    │
       ▼                  ▼                    ▼
  Rekordbox PID    .raw float32 PCM      _set01.wav, _set02.wav, ...
  start/stop          → WAV via ffmpeg
```

**Data flow:** `audiotee --include-processes PID --flush` → raw s16le PCM file → `ffmpeg -f s16le` → WAV → `ffmpeg silencedetect` → split WAVs

## Working / Verified Features

- **Audio capture from Rekordbox** — audiotee captures at 48kHz stereo via Core Audio Taps. Verified: correct audio, proper levels (-19 dB RMS on music). `--flush` flag required for subprocess compatibility.
- **Process monitor** — detects Rekordbox launch/exit via `pgrep -x`. Includes startup delay (10s) and stop debounce (10s) to handle Rekordbox's multi-process startup cycle.
- **WAV conversion** — raw s16le PCM → 16-bit WAV via ffmpeg. Verified with real recordings.
- **Silence-based splitting** — ffmpeg `silencedetect` parses silence boundaries, splits into individual set files, filters segments shorter than 10s. Verified with synthetic and real audio.
- **TOML configuration** — all parameters tunable via `~/.config/rb-recorder/config.toml`.
- **CLI entry point** — `python -m src -v` with config path and verbose flags.
- **Full lifecycle** — daemon waits → detects Rekordbox → records → Rekordbox quits → stops → converts → splits. Verified E2E.
- **15 unit tests passing** — all modules have test coverage.

## Known Issues / Not Yet Verified

- **Full lifecycle with music + silence gap** — the splitter works on synthetic audio, but a real test with play→silence→play→quit hasn't been completed clean yet (Rekordbox startup cycle caused short captures in testing).
- **LaunchAgent** — `install/com.rb-recorder.plist` and `scripts/install.sh` exist but haven't been tested with actual login-time auto-start.
- **Crash recovery** — if Rekordbox crashes mid-recording, the raw file persists but the WAV conversion + split won't run until the daemon's next cycle. No automatic recovery of orphaned `.raw` files.
- **Long session stability** — not tested with multi-hour DJ sets. Disk space usage is ~184KB/s (660MB/hour).
- **audiotee stability** — the user noted audiotee "is not stable nowadays." No issues observed during short tests but long sessions may reveal problems.
- **Permissions UX** — Screen Recording permission must be granted manually. No guided setup flow.

## Prerequisites

- macOS 14.2+ (Core Audio Taps API)
- `brew install ffmpeg`
- `audiotee` binary at `/usr/local/bin/audiotee` (build from https://github.com/makeusabrew/audiotee — `swift build -c release`)
- Screen Recording permission granted to the terminal app
- Python 3.12+ with venv: `uv venv && uv pip install pytest`

## Running

```bash
source .venv/bin/activate
python -m src -v                    # Run daemon (verbose)
python -m pytest tests/ -v          # Run tests
python scripts/poc_capture.py 10    # PoC: capture 10 seconds
```

## Project Structure

```
src/
  __main__.py        CLI entry point
  daemon.py          Main orchestrator (wires monitor + capture + splitter)
  process_monitor.py Rekordbox lifecycle detection (pgrep + debounce)
  capture.py         audiotee subprocess + ffmpeg WAV conversion
  splitter.py        ffmpeg silencedetect + file splitting
  config.py          TOML configuration with defaults
tests/               15 unit tests (pytest)
scripts/             PoC scripts, diagnostics, install helper
install/             LaunchAgent plist template
docs/plans/          Implementation plan
```

## Issue Tracking

This project uses **bd** (beads) for issue tracking.

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

## Key Decisions & Pitfalls

- **audiotee requires `--flush`** — without it, stdout buffering prevents subprocess pipe reads from getting data.
- **audiotee outputs s16le** (not float32) — conversion must use `-f s16le` not `-f f32le`.
- **AudioCapCLI doesn't work from scripts** — macOS TCC blocks it outside interactive terminals. Don't switch back to it.
- **ProcTap/ScreenCaptureKit returns all zeros for Rekordbox** — Rekordbox uses a custom audio engine that bypasses ScreenCaptureKit's hooks. Don't revisit this path.
- **Rekordbox bundle ID is `com.pioneerdj.rekordboxdj`** (not `com.pioneerdj.rekordbox`).
- **Rekordbox spawns multiple processes during startup** — the process monitor must debounce both start and stop detection.

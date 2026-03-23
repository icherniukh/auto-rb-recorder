# Rekordbox Auto-Recorder — Agent Instructions

## Known Issues / Not Yet Verified

- **Full lifecycle with music + silence gap** — the splitter works on synthetic audio, but a real test with play→silence→play→quit hasn't been completed clean yet (Rekordbox startup cycle caused short captures in testing).
- **LaunchAgent** — `install/com.rb-recorder.plist` and `scripts/install.sh` exist but haven't been tested with actual login-time auto-start.
- **Crash recovery** — if Rekordbox crashes mid-recording, the raw file persists but the WAV conversion + split won't run until the daemon's next cycle. No automatic recovery of orphaned `.raw` files.
- **Long session stability** — not tested with multi-hour DJ sets. Disk space usage is ~184KB/s (660MB/hour).
- **audiotee stability** — the user noted audiotee "is not stable nowadays." No issues observed during short tests but long sessions may reveal problems.
- **Permissions UX** — Screen Recording permission must be granted manually. No guided setup flow.

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

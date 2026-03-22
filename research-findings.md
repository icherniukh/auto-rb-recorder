# Research Findings: Rekordbox Auto-Recorder Technical Validation

This document presents independent research findings that challenge key assumptions in the current spec and propose a revised technical foundation.

---

## 1. The FFmpeg ScreenCaptureKit Command Is Likely Non-Functional

The spec's core capture command:

```bash
ffmpeg -f screencapturekit -i "com.pioneerdj.rekordbox" -capture_audio true -vn -c:a pcm_s24le output_set.wav
```

**Finding:** There is no evidence that FFmpeg exposes a `-f screencapturekit` demuxer that accepts application bundle IDs as input. FFmpeg on macOS uses `-f avfoundation` for media capture, and while Apple's ScreenCaptureKit framework exists at the OS level, FFmpeg does not appear to surface it as a direct input format in any documented release (including FFmpeg 7.0+).

**Impact:** PoC Test 1 would almost certainly fail. The entire audio capture layer needs a different approach.

**References:**
- [FFmpeg Devices Documentation](https://ffmpeg.org/ffmpeg-devices.html)
- [FFmpeg Formats Documentation](https://ffmpeg.org/ffmpeg-formats.html)
- [OBS Studio ScreenCaptureKit PR (obs-studio #6600)](https://github.com/obsproject/obs-studio/pull/6600) — shows ScreenCaptureKit integration requires native code, not an FFmpeg flag

---

## 2. Core Audio Taps API: The Real Solution (macOS 14.2+)

Apple introduced `AudioHardwareCreateProcessTap` in macOS 14.2, providing a first-party API for **process-specific audio capture** — exactly what this project needs.

### How It Works

- Creates a tap on a specific process's audio output by PID
- Audio flows through without disrupting normal playback
- Requires Screen Recording permission (macOS system prompt)
- Outputs raw PCM data that can be piped or encoded

### Existing CLI Tools

Two open-source projects already wrap this API:

- **audiotee** — Rust CLI tool. Captures audio from specific PIDs via `--include-processes`, outputs raw PCM to stdout. Supports configurable sample rates (44100, 48000 Hz, etc.).
- **AudioCapCLI** — Swift CLI tool forked from insidegui/AudioCap. Another wrapper around the same Core Audio Taps API.

### Proposed Capture Pipeline

```bash
audiotee --include-processes $(pgrep rekordbox) --sample-rate 48000 \
  | ffmpeg -f s16le -ar 48000 -ac 2 -i pipe:0 -c:a pcm_s24le output.wav
```

### Trade-off

This bumps the minimum macOS requirement from **12.3+** (current spec) to **14.2+**. Given that macOS 14 Sonoma has been out since late 2023, this is likely acceptable for most users.

**References:**
- [Apple: AudioHardwareCreateProcessTap](https://developer.apple.com/documentation/coreaudio/audiohardwarecreateprocesstap(_:_:))
- [Apple: Capturing system audio with Core Audio taps](https://developer.apple.com/documentation/CoreAudio/capturing-system-audio-with-core-audio-taps)
- [audiotee (GitHub)](https://github.com/makeusabrew/audiotee)
- [AudioCap (GitHub)](https://github.com/insidegui/AudioCap)
- [AudioCapCLI (GitHub)](https://github.com/pi0neerpat/AudioCapCLI)
- [Core Audio Taps API example (Gist)](https://gist.github.com/directmusic/7d653806c24fe5bb8166d12a9f4422de)

---

## 3. MIDI Trigger Assumption Has a Critical Flaw

The spec's hybrid trigger engine relies on intercepting MIDI play/pause signals from Rekordbox. This assumption is broken.

**Finding:** According to Pioneer DJ community forums, **Rekordbox does not broadcast MIDI OUT signals to third-party devices**. MIDI output for LED feedback and state changes is not implemented for non-Pioneer hardware. When a user clicks Play with the mouse or keyboard, no MIDI message is emitted whatsoever.

**Impact on the spec:**
- PoC Test 3 (Hardware-Agnostic MIDI Interception) would fail for mouse/keyboard playback
- The "hardware agnosticism" requirement (Section 2.1) cannot be met via MIDI sniffing
- MIDI interception only works by capturing messages *from the controller to Rekordbox* (input direction), not Rekordbox's state changes (output direction) — and even then, it misses mouse/keyboard-initiated playback entirely

**Conclusion:** MIDI should be dropped as a trigger mechanism entirely unless the scope is narrowed to "controller-only" workflows.

**References:**
- [Pioneer DJ Forums: "MIDI Out on Rekordbox Doesn't do anything"](https://forums.pioneerdj.com/hc/en-us/community/posts/213225766-Midi-Out-on-Rekordbox-Doesnt-do-anything)
- [Rekordbox MIDI Learn Operation Guide (PDF)](https://cdn.rekordbox.com/files/20241203210623/rekordbox7.0.5_midi_learn_operation_guide_EN.pdf)

---

## 4. Audio-Only VOX Triggering Should Be Primary

Given the MIDI limitation above, the audio threshold (VOX) approach — described as a fallback in the current spec — should become the **primary and sole trigger mechanism**.

### Pre-Buffer Technique

The spec correctly identifies the risk of missing quiet intros. The standard mitigation is a **rolling pre-buffer**: continuously buffer the last N seconds of audio in memory, and when the threshold triggers, prepend the buffer to the recording. This is a well-established technique in voice-activated recorders and broadcast systems.

### Suggested Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| Trigger threshold | -50 dB | Level above which recording starts |
| Trigger hold time | 2 sec | Continuous audio above threshold before starting |
| Silence timeout | 15 sec | Silence duration before stopping |
| Decay tail | 5 sec | Extra recording after stop trigger (reverb tails) |
| Pre-buffer | 5 sec | Rolling buffer prepended to capture start |

---

## 5. Alternative Architecture: Record Everything, Split Later

Since Core Audio Taps provides a continuous PCM stream from Rekordbox's process, there's an even simpler architecture that eliminates the state machine entirely:

1. **Always record** while Rekordbox is running — pipe the full audio stream to a WAV/FLAC file
2. **Post-hoc splitting** — use FFmpeg's `silencedetect` filter on the finished file to identify set boundaries and auto-split into individual sessions
3. **Cleanup** — delete silence-only segments, normalize remaining files

```bash
# Post-session: detect silence boundaries and split
ffmpeg -i full_session.wav -af silencedetect=noise=-50dB:d=15 -f null - 2>&1 | grep silencedetect
```

**Pros:** No real-time state machine, no edge cases with quiet intros or false triggers, crash-safe (file is always being written), simpler codebase.

**Cons:** Uses more disk space during recording (silence is recorded), requires a post-processing step, less "instant" — files aren't ready until Rekordbox closes and splitting completes.

---

## Summary: Revised Technical Foundation

| Spec Assumption | Status | Replacement |
|----------------|--------|-------------|
| `ffmpeg -f screencapturekit` captures app audio | Not functional | Core Audio Taps API via `audiotee` or native Swift/Rust wrapper |
| MIDI sniffing detects play/pause | Broken for mouse/keyboard | Audio threshold (VOX) as sole trigger |
| macOS 12.3+ minimum | Needs update | macOS 14.2+ (for Core Audio Taps) |
| Hybrid MIDI + audio trigger | Over-engineered | Pure audio analysis (VOX + pre-buffer) or record-everything approach |
| BlackHole not needed | Correct | Confirmed — Core Audio Taps is the native replacement |

The project is very doable. It just needs a different technical foundation than what's currently specified.

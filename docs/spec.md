# Rekordbox Auto-Recorder: macOS Hybrid Architecture

This specification outlines a macOS-native, low-overhead automatic recording tool for Rekordbox. It completely avoids custom C++/Rust audio engines, kernel extensions, and virtual audio drivers (like BlackHole). Instead, it orchestrates native macOS capabilities and mature CLI tools.

## 1. Core Architecture

The system consists of three primary components:
1. **The Automation Wrapper (Launcher):** A lightweight macOS automation (via Shortcuts or Automator) that launches our background monitor whenever Rekordbox is opened.
2. **The Hybrid Trigger Engine (Node.js/Python/Go):** A background process that listens for both MIDI playback commands (from the XONE:K2 or other controllers) AND audio output levels to intelligently determine when to start/stop recording.
3. **The Recording Backend (`ffmpeg`):** Utilizes `ffmpeg` combined with Apple's modern `ScreenCaptureKit` to pull internal application audio directly from the Rekordbox process with near-zero overhead.

---

## 2. Audio Capture: FFmpeg + ScreenCaptureKit (No BlackHole)

As of macOS 12.3+ (and implemented in FFmpeg 7.0+), Apple's `ScreenCaptureKit` framework allows direct capture of application-specific audio without the need for virtual audio drivers.

*   **How it works:** We tell FFmpeg to record audio originating *only* from the `com.pioneerdj.rekordbox` application bundle.
*   **The Command:** 
    ```bash
    ffmpeg -f screencapturekit -i "com.pioneerdj.rekordbox" -capture_audio true -vn -c:a pcm_s24le output_set.wav
    ```
    *(Note: `-vn` disables video capture, strictly recording the 24-bit PCM audio).*
*   **Zero Impact:** Because this uses native OS hooks, it bypasses the need to change Rekordbox's internal audio routing. Rekordbox still outputs to the Master/Controller as normal.

---

## 3. The Hybrid Trigger Engine (MIDI + Audio Threshold)

Relying *only* on MIDI can fail if the user plays a track via the mouse, and relying *only* on audio thresholds can cut off quiet intro buildups or false-trigger on system sounds. A hybrid approach ensures perfection.

**State Machine Logic:**

1.  **START Condition:** 
    *   **IF** the engine sniffs a MIDI `PLAY` command from the controller **OR** 
    *   **IF** the engine detects continuous audio output from Rekordbox (above -50dB) for > 2 seconds (handled via an audio analysis node or an `ffmpeg` silence filter).
    *   **THEN:** Spawn the `ffmpeg` recording child process.

2.  **STOP Condition (The "Hang Time"):**
    *   **IF** the engine sniffs a MIDI `PAUSE/CUE` command **OR**
    *   **IF** absolute silence is detected from Rekordbox for > 15 seconds.
    *   **THEN:** Do NOT stop immediately. Wait for a configurable decay timer (e.g., 5 seconds) to capture reverb tails.
    *   **FINALLY:** Send a `SIGINT` (Ctrl+C equivalent) to the `ffmpeg` process to safely finalize and write the WAV file headers.

---

## 4. Automation & Auto-Launch

To ensure the user never forgets to start the recording tool, it should be bound to Rekordbox's lifecycle.

**Implementation Option (macOS Shortcuts / Automator):**
1.  **The Trigger:** Use the native macOS **Shortcuts** app's "Automation" tab (or create an Automator "Wrapper App").
2.  **The Event:** Set the trigger to: "When App 'Rekordbox' is Opened".
3.  **The Action:** Execute a shell script: 
    ```bash
    nohup /path/to/our/trigger_engine > /dev/null 2>&1 &
    ```
4.  **Graceful Exit:** The Trigger Engine should periodically check if the `rekordbox.exe` (or macOS equivalent process) is still running. If Rekordbox is closed, the Trigger Engine gracefully kills any active `ffmpeg` recordings and terminates itself.

---

## 5. Development Roadmap

1.  **Phase 1 (Proof of Concept):** Verify `ffmpeg -f screencapturekit` successfully isolates and captures Rekordbox audio on the target Mac without BlackHole.
2.  **Phase 2 (MIDI Wrapper):** Adapt the existing XONE:K2 MIDI project to spawn and kill the `ffmpeg` subprocess using `SIGINT`.
3.  **Phase 3 (Hybrid Logic):** Implement the "Hang Time" delay on stop, and integrate the fallback audio threshold detection.
4.  **Phase 4 (Packaging):** Create the macOS Shortcut/Automator script to bind the engine to the Rekordbox launch event.
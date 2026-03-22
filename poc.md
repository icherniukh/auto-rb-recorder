# Proof of Concept (PoC) Test Plan

To validate the macOS hybrid architecture before full development, the following isolated PoC tests must be executed.

## Test 1: FFmpeg ScreenCaptureKit Audio Isolation
**Goal:** Verify `ffmpeg` can capture Rekordbox's internal audio natively without BlackHole, and test file handling behavior.

*   **Action 1:** Open Rekordbox and play a track.
*   **Action 2:** Run the following command in Terminal:
    ```bash
    ffmpeg -f screencapturekit -i "com.pioneerdj.rekordbox" -capture_audio true -vn -c:a pcm_s24le test_recording.wav
    ```
*   **Expected Result:** FFmpeg begins capturing audio. The output file grows.
*   **Action 3:** Stop playback in Rekordbox. Press `Ctrl+C` (SIGINT) in the Terminal.
*   **Expected Result:** FFmpeg gracefully closes the file. The resulting `test_recording.wav` plays back perfectly without system sounds (e.g., macOS notification pings should not be in the recording).
*   **Action 4 (Crash Test):** Start recording again. Force-quit (`kill -9`) the FFmpeg process (simulating a crash). 
*   **Expected Result:** Check if the resulting WAV file is playable or if the headers are corrupted. (If corrupted, we will need to research auto-repairing WAV headers or streaming to a raw PCM format).

## Test 2: Audio Threshold Detection (VOX)
**Goal:** Determine if we can rely solely on an audio stream for start/stop triggers, bypassing MIDI entirely.

*   **Action:** Pipe the ScreenCaptureKit audio stream into an analysis tool (like `sox` or a simple Python script using `pyaudio` listening to a system loopback).
*   **Test Case A (The Fade-in):** Play a track with a very slow, quiet, ambient intro.
    *   **Expected Result:** Does the threshold trigger early enough, or does it miss the first 10 seconds of the song?
*   **Test Case B (The Breakdown):** Play a track with a long, near-silent breakdown in the middle.
    *   **Expected Result:** Does the system falsely trigger a "STOP" command? We need to determine the maximum required silence duration to prevent false stops.

## Test 3: Hardware-Agnostic MIDI Interception
**Goal:** Verify we can sniff MIDI signals globally from Rekordbox without interfering with the user's controller.

*   **Action:** Connect any standard DJ controller (or use the mouse).
*   **Test Case A:** Use a tool like `MIDI Monitor` (macOS native) or a simple Python `mido` script to listen to all active MIDI buses.
*   **Expected Result:** When clicking "Play" with the mouse, does Rekordbox broadcast a MIDI OUT signal reflecting the state change? 
*   **Test Case B:** When pressing "Play" on the connected hardware controller, can our script intercept the `Note On` / `CC` message *without* blocking it from reaching Rekordbox?

## Test 4: macOS Auto-Launch Hooks
**Goal:** Validate that we can reliably trigger a background script automatically when Rekordbox opens.

*   **Action 1 (Shortcuts App):** Create a macOS Personal Automation. Trigger: "When App 'Rekordbox' is Opened". Action: Run Shell Script `touch /tmp/rekordbox_started.txt`.
*   **Test Case:** Open Rekordbox. 
*   **Expected Result:** Does the file appear in `/tmp` immediately? Is there an annoying macOS notification that pops up every time?
*   **Action 2 (Automator Wrapper):** Create an Automator Application that runs the shell script and then launches Rekordbox.
*   **Test Case:** Launch via the Automator app.
*   **Expected Result:** Does the script run cleanly in the background without keeping a Terminal window open?

## Test 5: Graceful Termination on App Exit
**Goal:** Ensure the background daemon dies when Rekordbox closes.

*   **Action:** Write a simple bash script that loops every 2 seconds, checking `pgrep rekordbox`. If the PID is not found, the script echoes "Rekordbox closed" and exits.
*   **Test Case:** Run the script, open Rekordbox, then Quit Rekordbox.
*   **Expected Result:** The script should successfully detect the closure and terminate itself within 2 seconds.
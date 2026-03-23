# Rekordbox Auto-Recorder: Project Requirements

## 1. Core Objective
Develop a macOS-based utility that automatically records a DJ's master audio output from Pioneer's Rekordbox software. The recording process must start and stop automatically based on the actual playback state of the software, requiring zero manual intervention from the user during a performance.

## 2. Functional Requirements

### 2.1. Playback Detection (Start/Stop Triggers)
*   **Automatic Start:** The system must begin recording audio when a track starts playing in Rekordbox.
*   **Automatic Stop:** The system must stop recording when playback is paused or stopped.
*   **Hardware Agnosticism:** The detection mechanism must work regardless of the specific DJ controller or hardware connected (e.g., must not be hardcoded to a specific Pioneer controller or third-party device).
*   **Mouse/Keyboard Support:** The system must successfully trigger even if the user initiates playback via the computer mouse or keyboard instead of a physical controller.

### 2.2. Audio Capture & Quality
*   **Direct Capture:** The system must capture the internal audio output of the Rekordbox application directly.
*   **Zero Routing Configuration:** The user must not be required to install third-party virtual audio cables (like BlackHole) or manually re-route macOS system audio.
*   **High Fidelity:** The recording must be saved in a lossless, high-quality format (e.g., 24-bit WAV or high-bitrate FLAC/ALAC) to ensure professional audio standards.
*   **Zero Interference:** The recording process must not introduce audio latency, dropouts, or affect the performance of Rekordbox in any way.

### 2.3. Edge Case Handling (The "Hang Time" & "Pre-roll")
*   **Reverb/Echo Tails:** When playback stops, the recording must not cut off instantly. It must continue for a configurable duration (e.g., 5 seconds) to capture natural decay, reverb tails, or echo FX.
*   **Instant Start Capture:** The system must ensure the very first transient (e.g., the attack of the first kick drum) is captured without clipping or missing milliseconds of audio due to boot-up delays.

### 2.4. Automation & Lifecycle Management
*   **Auto-Launch:** The recording utility must automatically launch and "arm" itself in the background whenever the user opens the Rekordbox application.
*   **Auto-Termination:** When the user closes Rekordbox, the utility must safely finalize any active recordings, save the files, and gracefully terminate itself to free up system resources.
*   **Crash Recovery:** If Rekordbox crashes unexpectedly, the utility must successfully save the recording up to the point of the crash without corrupting the audio file.

## 3. Non-Functional Requirements
*   **OS Environment:** macOS (Targeting modern versions, 12.3+).
*   **User Interface:** The tool should run silently in the background (headless or menu-bar only) with minimal to no UI required for daily operation.
*   **Resource Efficiency:** The background daemon must consume negligible CPU and RAM while waiting for playback to start.
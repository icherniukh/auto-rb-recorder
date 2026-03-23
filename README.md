# auto-rb-recorder

A macOS background daemon that automatically records your Pioneer Rekordbox DJ sets. It monitors when Rekordbox is running and intercepts the main audio output directly from the system.

## How it works

When you open Pioneer Rekordbox, the recorder wakes up and hooks into the audio stream. As long as you are actively playing music, it saves the audio to your disk.

It evaluates the audio stream live:
- **Silence Stripping:** If Rekordbox is open but not playing audio for an extended period, recording pauses to save disk space.
- **Mix Splitting:** Continuous silence breaks your sessions into separate audio files.
- **Auto Export:** When you close Rekordbox, the recorder exports the raw audio chunks into `.wav` or `.mp3` files in your `~/Music/auto-rb-recorder` folder.

## Installation

The recommended installation method is via Homebrew:

```bash
brew tap icherniukh/tap
brew install auto-rb-recorder
```

To run the daemon automatically in the background at log in:
```bash
brew services start auto-rb-recorder
```

## Permissions (macOS 14+)

In order to capture your system's audio output, macOS requires explicit consent.

The first time you open Rekordbox after installing, a system dialog will request **Screen Recording** permissions for `auto-rb-recorder`.

To approve it:
1. When the dialog appears, click **Open System Settings**.
2. Toggle the switch ON for `auto-rb-recorder` (or navigate to `/opt/homebrew/bin/auto-rb-recorder` to add it manually).
3. If missed, open **System Settings -> Privacy & Security -> Screen Recording** to toggle it manually.

## Configuration

You can customize the silence detection thresholds and the output directory by editing `~/.config/rb-recorder/config.toml`:

```toml
[recording]
sample_rate = 48000
output_dir = "~/Music/auto-rb-recorder"
export_format = "wav"  # allow "wav" or "mp3"

[trigger]
silence_threshold_db = -50
min_silence_duration = 15
```

## Compiling from Source

If you want to build the executable manually on your system:
```bash
git clone --recurse-submodules https://github.com/icherniukh/auto-rb-recorder.git
cd auto-rb-recorder
uv pip install pyinstaller
bash scripts/build.sh
```

Official releases are packaged as a `universal2` macOS executable, signed with an Apple Developer Application ID, notarized by Apple via `xcrun notarytool`, and uploaded automatically via GitHub Actions.

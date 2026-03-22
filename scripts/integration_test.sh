#!/usr/bin/env bash
# scripts/integration_test.sh — Full end-to-end integration test
set -euo pipefail

OUTPUT_DIR="/tmp/rb_recorder_integration_test"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

echo "=== Rekordbox Auto-Recorder Integration Test ==="
echo ""
echo "Prerequisites:"
echo "  1. Rekordbox is NOT running"
echo "  2. pip install proc-tap"
echo "  3. ffmpeg is installed (ffmpeg -version)"
echo "  4. Screen Recording permission granted"
echo ""
read -p "Press Enter to start the daemon..."

python -m src -v 2>&1 | tee "$OUTPUT_DIR/daemon.log" &
DAEMON_PID=$!
echo "Daemon started (PID $DAEMON_PID)"
echo ""

echo "--- Step 1: Open Rekordbox and play a track for ~30 seconds ---"
read -p "Press Enter when done..."

echo "--- Step 2: Stop playback and wait ~20 seconds (silence gap) ---"
read -p "Press Enter after 20 seconds of silence..."

echo "--- Step 3: Play another track for ~30 seconds ---"
read -p "Press Enter when done..."

echo "--- Step 4: Quit Rekordbox ---"
read -p "Press Enter after Rekordbox has fully closed..."

sleep 5
kill $DAEMON_PID 2>/dev/null || true

echo ""
echo "=== Results ==="
ls -lh ~/Music/RekordboxRecordings/ 2>/dev/null || echo "No output files found!"
echo ""
echo "Check the WAV files for:"
echo "  - Two separate set files (split by silence)"
echo "  - Clean audio without system sounds"
echo "  - No missing audio at track starts"
echo "  - Reverb tails preserved at track ends"

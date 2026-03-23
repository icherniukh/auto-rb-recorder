#!/usr/bin/env bash
# scripts/install.sh — Install rb-recorder as a macOS LaunchAgent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$SCRIPT_DIR/install/com.rb-recorder.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.rb-recorder.plist"

EXEC_PATH="$SCRIPT_DIR/dist/auto-rb-recorder"
if [ ! -f "$EXEC_PATH" ]; then
    echo "Executable not found at $EXEC_PATH. Please run scripts/build.sh first."
    exit 1
fi

sed -e "s|__INSTALL_DIR__|$SCRIPT_DIR|g" \
    -e "s|__EXEC_PATH__|$EXEC_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed. Daemon will start at login."
echo "  Executable: $EXEC_PATH"
echo "  Logs:       /tmp/rb-recorder.log"
echo "  Uninstall:  launchctl unload $PLIST_DST && rm $PLIST_DST"

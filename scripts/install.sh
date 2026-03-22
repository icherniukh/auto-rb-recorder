#!/usr/bin/env bash
# scripts/install.sh — Install rb-recorder as a macOS LaunchAgent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$SCRIPT_DIR/install/com.rb-recorder.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.rb-recorder.plist"
PYTHON_PATH="$(which python3)"

sed -e "s|__INSTALL_DIR__|$SCRIPT_DIR|g" \
    -e "s|__PYTHON_PATH__|$PYTHON_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "Installed. Daemon will start at login."
echo "  Python: $PYTHON_PATH"
echo "  Logs:   /tmp/rb-recorder.log"
echo "  Uninstall: launchctl unload $PLIST_DST && rm $PLIST_DST"

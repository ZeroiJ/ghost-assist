#!/usr/bin/env bash
# Ghost Assistant — Start daemon + overlay
# Run this to launch Ghost

GHOST_DIR="$(cd "$(dirname "$0")" && pwd)"
GHOST_URL="http://localhost:7777"
GHOST_CLASS="ghost-assistant"

echo "[Ghost] Starting daemon..."

# Activate venv and start FastAPI daemon in background
source "$GHOST_DIR/.venv/bin/activate"
cd "$GHOST_DIR"

# Kill existing daemon if running
pkill -f "uvicorn daemon:app" 2>/dev/null
sleep 0.5

# Start daemon
python -m uvicorn daemon:app --host 127.0.0.1 --port 7777 --log-level info &
DAEMON_PID=$!
echo "[Ghost] Daemon PID: $DAEMON_PID"

# Wait for daemon to be ready
echo "[Ghost] Waiting for daemon..."
for i in $(seq 1 30); do
    if curl -s --max-time 1 "$GHOST_URL/status" > /dev/null 2>&1; then
        echo "[Ghost] Daemon ready!"
        break
    fi
    sleep 0.5
done

# Check if daemon actually started
if ! curl -s --max-time 1 "$GHOST_URL/status" > /dev/null 2>&1; then
    echo "[Ghost] ERROR: Daemon failed to start!"
    exit 1
fi

# Launch Chrome Beta overlay
echo "[Ghost] Launching overlay..."
google-chrome-beta \
    --app="$GHOST_URL" \
    --class="$GHOST_CLASS" \
    --disable-background-timer-throttling \
    --no-first-run \
    --user-data-dir="$HOME/.config/ghost-chrome" &

echo "[Ghost] Ready! Use Super+G to toggle, Super+Shift+H to force trigger."
echo "[Ghost] Daemon running at $GHOST_URL"

# Wait for daemon process
wait $DAEMON_PID

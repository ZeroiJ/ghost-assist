#!/usr/bin/env bash
# Ghost Assistant — Emergency Erase
# Called by Super+Shift+Q — kills everything, clears traces, < 1 second
# USE THIS IF SOMEONE LOOKS AT YOUR SCREEN OR ASKS ABOUT THE OVERLAY

GHOST_DIR="$(cd "$(dirname "$0")" && pwd)"

# Kill the Chrome overlay window immediately
hyprctl dispatch closewindow class:ghost-assistant 2>/dev/null &

# Kill the daemon
pkill -9 -f "uvicorn daemon:app" 2>/dev/null &

# Kill audio capture
pkill -9 -f "pw-record.*ghost" 2>/dev/null &

# Clear screenshots
rm -rf "$GHOST_DIR/screenshots/"*.png 2>/dev/null &

# Clear any temp audio files
rm -f "$GHOST_DIR/"*.raw "$GHOST_DIR/"*.wav 2>/dev/null &

# Wait for all background kills to finish
wait

# Notify (silent, low urgency, auto-dismiss)
notify-send -u low -t 1500 "Ghost" "Erased." 2>/dev/null

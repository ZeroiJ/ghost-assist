#!/usr/bin/env bash
# Ghost Assistant — Toggle overlay show/hide
# Called by Super+G keybind and Waybar click

GHOST_CLASS="ghost-assistant"
GHOST_URL="http://localhost:7777"

# Check if a ghost-assistant window exists
if hyprctl clients -j | grep -q "\"class\": \"$GHOST_CLASS\""; then
    # Window exists — check if it's in special workspace (hidden)
    ADDR=$(hyprctl clients -j | python3 -c "
import json, sys
clients = json.load(sys.stdin)
for c in clients:
    if c.get('class') == '$GHOST_CLASS':
        ws = c.get('workspace', {})
        addr = c.get('address', '')
        ws_name = ws.get('name', '')
        if ws_name.startswith('special'):
            # Hidden — move to current workspace
            print(f'dispatch movetoworkspace e+0,address:{addr}')
        else:
            # Visible — move to special workspace to hide
            print(f'dispatch movetoworkspacesilent special:ghost,address:{addr}')
        break
")
    if [ -n "$ADDR" ]; then
        hyprctl "$ADDR"
    fi
else
    # No window — check if daemon is running, then launch Chrome
    if curl -s --max-time 1 "$GHOST_URL/status" > /dev/null 2>&1; then
        google-chrome-beta \
            --app="$GHOST_URL" \
            --class="$GHOST_CLASS" \
            --disable-background-timer-throttling \
            --no-first-run \
            --user-data-dir="$HOME/.config/ghost-chrome" &
    else
        notify-send "Ghost" "Daemon not running. Start with: ~/ghost-assit/GHOST/start.sh" -u normal
    fi
fi

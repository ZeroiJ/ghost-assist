#!/usr/bin/env bash
# Ghost Assistant — Apply window rules to existing overlay

# Try multiple times with increasing delays
for i in 1 2 3 4 5; do
    ADDR=$(hyprctl clients -j 2>/dev/null | python3 -c "
import json, sys
clients = json.load(sys.stdin)
for c in clients:
    if c.get('title') == 'Ghost' and c.get('floating') == True:
        print(c.get('address'))
" 2>/dev/null)
    
    if [ -n "$ADDR" ]; then
        hyprctl dispatch resizewindowpixel exact 350 450,address:$ADDR 2>/dev/null
        break
    else
        sleep $i
    fi
done

#!/usr/bin/env bash
# Ghost Assistant — Force trigger (generate answer NOW)
# Called by Super+Shift+H keybind

curl -s -X POST http://localhost:7777/trigger > /dev/null 2>&1

# Exit silently — the overlay will update via SSE

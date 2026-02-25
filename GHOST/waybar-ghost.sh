#!/usr/bin/env bash
# Ghost Assistant — Waybar Module Status Script
# Polls /status every 2s (via Waybar interval), outputs Waybar JSON
# Shows ghost state as colored icon with tooltip

STATUS=$(curl -s --max-time 2 http://127.0.0.1:7777/status 2>/dev/null)

if [ -z "$STATUS" ] || [ "$STATUS" = "" ]; then
    # Daemon not running
    echo '{"text": "󰊠", "class": "off", "tooltip": "Ghost: offline"}'
    exit 0
fi

STATE=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state','error'))" 2>/dev/null)
ANSWERS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('answers_count',0))" 2>/dev/null)
TRANSCRIPT=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_length',0))" 2>/dev/null)

case "$STATE" in
    passive)
        echo "{\"text\": \"󰊠\", \"class\": \"passive\", \"tooltip\": \"Ghost: listening\\nAnswers: ${ANSWERS}\\nTranscript: ${TRANSCRIPT} chars\"}"
        ;;
    generating)
        echo "{\"text\": \"󰊠\", \"class\": \"generating\", \"tooltip\": \"Ghost: generating answer...\"}"
        ;;
    answering)
        echo "{\"text\": \"󰊠\", \"class\": \"answering\", \"tooltip\": \"Ghost: answer ready\\nAnswers: ${ANSWERS}\"}"
        ;;
    cooldown)
        echo "{\"text\": \"󰊠\", \"class\": \"cooldown\", \"tooltip\": \"Ghost: cooldown\\nAnswers: ${ANSWERS}\"}"
        ;;
    error)
        echo "{\"text\": \"󰊠\", \"class\": \"error\", \"tooltip\": \"Ghost: error\"}"
        ;;
    *)
        echo "{\"text\": \"󰊠\", \"class\": \"passive\", \"tooltip\": \"Ghost: ${STATE}\"}"
        ;;
esac

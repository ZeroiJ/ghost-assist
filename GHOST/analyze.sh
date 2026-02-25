#!/usr/bin/env bash
# Ghost Assistant — On-Demand Screen Analysis
# Called by Super+Shift+A — captures current screen and sends to Gemini Vision
# Works even when the overlay is hidden

curl -s -X POST http://127.0.0.1:7777/analyze-screen > /dev/null 2>&1 &

notify-send -u low -t 1500 "Ghost" "Analyzing screen..." 2>/dev/null

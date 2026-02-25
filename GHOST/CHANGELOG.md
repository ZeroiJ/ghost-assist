# Changelog

All notable changes to Ghost Assistant will be documented in this file.

---

## [Unreleased]

### Known Issues
- **Chrome Wayland transparency:** Chrome `--app` mode does not support true transparency on Wayland. Window rule opacity is set but not visually applied. Consider GTK4 Layer Shell for Phase 16.

---

## [0.14.0] — 2026-02-26

### Window Rules Fix (Phase 15)

- **Fixed Hyprland 0.53.3 syntax:** Window rules now use `float on`, `pin on` (was missing "on")
- **Immediate float:** Window now floats from launch (no half-screen flash)
- **Match by class:** Rules match `chrome-localhost__-Default` (Chrome's actual class)
- **No more Waybar errors:** Correct syntax doesn't break Waybar
- **Click-through:** JavaScript sets `pointer-events: none` on overlay (except input/buttons)
- **Simplified toggle.sh:** Removed manual hyprctl dispatch workaround

### What works now:
- Super+G opens floating 350x450 window in top-right
- Window stays pinned on all workspaces
- Clicks pass through to editor below
- Input field and buttons remain interactive — 2026-02-25

### Transparent HUD & Window Rules Fix (Phase 13-14)

- **Auto-trigger tuned:** Disabled by default, increased silence threshold (4s), cooldown (30s), energy threshold (0.03)
- **Keyword matching improved:** Requires 2+ keyword matches, minimum 8-word transcript length
- **Added `/toggle-auto-trigger` endpoint** in daemon for enabling/disabling auto-trigger
- **Overlay transparency:** Added rgba backgrounds in CSS for semi-transparent effect (limited by Chrome Wayland support)
- **Click-through mode:** Added `pointer-events: none` in CSS, click-through toggle button in overlay
- **Smaller overlay:** Resized to 350×450px for less intrusive display
- **Window rules removed:** Removed broken window rules from `ghost.conf` (Hyprland syntax issues)
- **Manual float/pin:** `toggle.sh` now uses `hyprctl dispatch` commands for float/pin/resize after Chrome launches

---

## [0.12.0] — 2026-02-25

### systemd Service (Phase 12)

- Added `ghost-daemon.service` — systemd user unit (`~/.config/systemd/user/`)
- `Type=simple`, `Restart=always`, `RestartSec=3`
- Depends on `graphical-session.target` and `pipewire.service`
- Resource limits: `MemoryMax=1G`, `CPUQuota=50%`
- Updated `start.sh` to prefer systemd when available, fallback to direct launch
- `start.sh` now checks if overlay is already running before launching a duplicate

---

## [0.11.0] — 2026-02-25

### Waybar Module (Phase 11)

- Added `waybar-ghost.sh` — polls `/status` every 2s, outputs Waybar-compatible JSON
- Added `custom/ghost` module to `~/.config/waybar/config.jsonc` (leftmost in `modules-right`)
- Status colors: green (listening), yellow pulsing (generating), blue (answering), dim (cooldown/off), red (error)
- Click: toggle overlay (`toggle.sh`), Right-click: analyze screen (`analyze.sh`)
- Tooltip shows state, answer count, and transcript length
- CSS styling added to `~/.config/waybar/style.css`

---

## [0.10.0] — 2026-02-25

### Multi-Model Fallback with Rate Tracking (Phase 10)

- Added `rate_tracker.py` — tracks Gemini API calls per minute/day (free tier: ~15 RPM, 1500 RPD)
- Tracks error counts per model, backs off after 3+ errors in 5 minutes
- Persists rate data to `limits.json` (survives daemon restart)
- `get_best_model()` returns best available model based on current limits
- `generate_answer()` in daemon now uses rate tracker to pick best model
- Tries models in priority order: Gemini -> Ollama
- `/status` endpoint includes `rate_limits` summary

---

## [0.9.0] — 2026-02-25

### Session History (Phase 9)

- Answers saved to `history/` as JSON files: `{id, answer, timestamp, source, ai}`
- Rolling history — keeps last 50 answers (pruned on each save)
- Added `GET /history?limit=20` endpoint for recent answers
- History loaded from disk on daemon startup (persists across restarts)
- History sent to overlay on SSE reconnect

---

## [0.8.0] — 2026-02-25

### Custom User Context Hot-Reload (Phase 8)

- Added `context.txt` — plain text file for resume, target role, tech stack, company info
- Loaded by `config.py` at startup, injected into system prompt
- Added `POST /reload-context` endpoint — hot-reload without daemon restart
- Updates both `gemini_client` and `ollama_client` module-level context in-place
- `/status` now includes `user_context_length`

---

## [0.7.0] — 2026-02-25

### On-Demand Screen Analysis (Phase 7)

- Added `get_vision_answer_stream()` in `gemini_client.py` — sends PIL Image directly to Gemini Vision
- Vision prompt: "Look at this screen. Identify the question/problem. Give the complete answer."
- Added `POST /analyze-screen` endpoint — takes screenshot via grim, sends to Gemini Vision, streams response
- Added `analyze.sh` + `Super+Shift+A` keybind in `ghost.conf`
- Overlay: camera icon button + `Ctrl+Enter` shortcut to trigger screen analysis
- Yellow pulsing animation while analysis is in progress
- SCREEN source label on analysis answer cards

---

## [0.6.0] — 2026-02-25

### Emergency Erase (Phase 6)

- Added `erase.sh` — kills uvicorn, Chrome overlay, clears screenshots + temp audio, sends notification
- Added `Super+Shift+Q` keybind (`Super+Shift+E` was taken by Email)
- Entire erase runs in under 1 second

---

## [0.5.0] — 2026-02-25

### Teleprompter Prompt Rewrite (Phase 5)

- Rewrote `SYSTEM_PROMPT` in `config.py` to teleprompter style
- Answers are now "exact words to say" — not suggestions, not explanations
- 1-3 sentences max for verbal answers, code snippets for coding questions
- `USER_CONTEXT` loaded from `context.txt` and injected into prompt via `{user_context}` placeholder

---

## [0.4.0] — 2026-02-25

### Streaming Responses (Phase 4)

- `gemini_client.py`: switched to `generate_content_stream()` with `asyncio.to_thread()` wrapper
- `ollama_client.py`: switched to `stream: true` with NDJSON parsing
- SSE events: `answer-start`, `answer-chunk`, `answer-done` for real-time token delivery
- Overlay: incremental rendering with blinking cursor during generation
- Answer cards build up token-by-token as AI generates

---

## [0.3.0] — 2026-02-25

### Project Restructure

- Moved all source files from repo root (`~/ghost-assit/`) into `GHOST/` subfolder
- Updated all paths, imports, and scripts to reference new location
- `.gitignore` updated for `GHOST/` subfolder structure

---

## [0.2.0] — 2026-02-25

### Hyprland Integration (Phase 3)

- Added `ghost.conf` — window rules for `ghost-assistant` class: `float`, `pin`, `no_screen_share`, `no_blur`, `no_anim`, `no_shadow`
- Positioned top-right (75% x, 10% y), 400x600px
- Added `toggle.sh` (Super+G), `trigger.sh` (Super+Shift+H), `start.sh`
- Sourced `ghost.conf` as last line of `~/.config/hypr/hyprland.conf`

### Overlay UI (Phase 2)

- `static/index.html` — overlay layout with answer display, status bar, manual input
- `static/style.css` — dark monochrome theme matching Omarchy aesthetic
- `static/app.js` — SSE listener with auto-reconnect, markdown rendering, manual question submission

---

## [0.1.0] — 2026-02-25

### Initial MVP Release (Phases 0-1)

First working build of Ghost — invisible AI interview assistant for Arch Linux (Omarchy / Hyprland / Wayland).

**Backend**
- `config.py` — central configuration (thresholds, API keys, prompts, paths)
- `detector.py` — silence detection (2.5s threshold) + keyword matching + 15s cooldown
- `whisper_worker.py` — PipeWire audio capture via `pw-record` -> faster-whisper `tiny.en` -> rolling 2-minute transcript buffer
- `ocr_worker.py` — `grim` screenshots every 10s -> Tesseract OCR -> rolling 5-snapshot screen text buffer
- `gemini_client.py` — Gemini Flash 2.0 API client (primary, using `google-genai` SDK)
- `ollama_client.py` — Ollama `llava:7b` local fallback client (offline mode)
- `daemon.py` — FastAPI server on `localhost:7777` with endpoints: `/`, `/status`, `/trigger`, `/ask`, `/stream`

**Project Setup**
- Python venv with all dependencies (fastapi, uvicorn, faster-whisper, google-genai, pytesseract, Pillow, httpx)
- `.env` with Gemini API key + config
- PipeWire virtual sink (`ghost_sink`) for combined mic + system audio capture
- `.gitignore`, `.env.example`, PRD, Implementation Plan

### Architecture Decisions
- **AI routing:** Gemini primary, Ollama fallback on failure or `OFFLINE_MODE=true`
- **Audio:** PipeWire virtual sink captures both mic and system audio
- **Window stealth:** Hyprland `no_screen_share` — native Wayland, invisible to screen sharing
- **Model:** `gemini-2.5-flash` (switched from `gemini-2.0-flash` after quota exhaustion)
- **Python env:** venv in project dir, not system-wide

---

*Format follows [Keep a Changelog](https://keepachangelog.com/).*

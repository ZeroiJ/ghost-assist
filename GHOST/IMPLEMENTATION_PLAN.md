# Ghost Assistant — Implementation Plan

## Decisions

| Decision | Choice |
|----------|--------|
| Project directory | `~/ghost-assit/` (develop here, systemd points here) |
| Python environment | venv inside project (`.venv/`) |
| AI primary | Gemini Flash 2.0 API |
| AI fallback | Ollama `llava:7b` (local, offline) |
| Keybind: toggle overlay | `Super+G` |
| Keybind: force trigger | `Super+Shift+H` |
| Approach | MVP first, then Waybar + systemd |

---

## System State (pre-build)

| Component | Status |
|-----------|--------|
| Arch Linux + Hyprland + Wayland | Running |
| PipeWire | Running (PulseAudio compat active) |
| Python 3.14 | Installed |
| grim | Installed |
| Chrome Beta | Installed |
| Ollama | Installed (server not running, need to pull llava:7b) |
| tesseract | **NOT installed** |
| python-pip | **NOT installed** (using venv instead) |
| All Python packages | **NOT installed** |

### Keybind Conflict Resolved

`Super+Shift+G` is already bound to Signal in `~/.config/hypr/bindings.conf`.
Ghost force-trigger moved to `Super+Shift+H`. Toggle remains `Super+G` (was free).

---

## File Structure (MVP)

```
~/ghost-assit/
├── GHOST_ASSISTANT_PRD_v2.md    # PRD (existing)
├── IMPLEMENTATION_PLAN.md       # this file
├── .env                         # GEMINI_API_KEY, OFFLINE_MODE
├── .venv/                       # Python virtual environment
├── config.py                    # Central configuration + constants
├── daemon.py                    # FastAPI backend (all endpoints + SSE + worker orchestration)
├── whisper_worker.py            # PipeWire audio capture -> faster-whisper -> rolling transcript buffer
├── detector.py                  # Silence detection + keyword matching + cooldown
├── gemini_client.py             # Gemini Flash 2.0 API client
├── ollama_client.py             # Ollama llava:7b fallback client
├── ocr_worker.py                # grim screenshot every 10s -> Tesseract OCR -> screen text buffer
├── toggle.sh                    # Show/hide Chrome overlay (called by keybind + waybar)
├── trigger.sh                   # POST to /trigger (force active mode)
├── start.sh                     # Launch daemon + Chrome overlay
├── static/
│   ├── index.html               # Overlay UI
│   ├── style.css                # Dark monochrome theme
│   └── app.js                   # SSE listener + manual input + keyboard shortcuts
└── screenshots/                 # Rolling buffer (last 5, auto-cleared)

~/.config/hypr/
└── ghost.conf                   # Window rules + keybinds (sourced last in hyprland.conf)
```

---

## Phase 0 — Environment Setup

- [ ] Install system packages: `tesseract`, `tesseract-data-eng`
- [ ] Create Python venv in `~/ghost-assit/.venv/`
- [ ] Install Python packages: `fastapi`, `uvicorn`, `faster-whisper`, `google-generativeai`, `python-dotenv`, `pytesseract`, `Pillow`, `websockets`, `httpx`
- [ ] Create `.env` with `GEMINI_API_KEY` placeholder and `OFFLINE_MODE=false`
- [ ] Create `screenshots/` directory
- [ ] Start Ollama server and pull `llava:7b` model
- [ ] Verify PipeWire is capturing audio correctly

**Validation:** `source .venv/bin/activate && python -c "import fastapi, faster_whisper, google.generativeai; print('OK')"`

---

## Phase 1 — Backend Core

### 1.1 `config.py` — Central Configuration

- [ ] Load `.env` via python-dotenv
- [ ] Constants: `SILENCE_THRESHOLD=2.5`, `COOLDOWN_DURATION=15`, `SCREENSHOT_INTERVAL=10`
- [ ] Question keyword list
- [ ] Paths: screenshots dir, audio temp file
- [ ] Gemini/Ollama config
- [ ] Server config: host, port (7777)

### 1.2 `detector.py` — Question Detection

- [ ] `should_trigger(transcript, silence_duration) -> bool`
- [ ] Silence check: `silence_duration >= SILENCE_THRESHOLD`
- [ ] Keyword check: last sentence contains question keyword
- [ ] Cooldown tracking: 15s after each trigger
- [ ] Both conditions must be true for auto-trigger

### 1.3 `whisper_worker.py` — Audio Capture + Transcription

- [ ] Set up PipeWire virtual combined sink (mic + system audio)
- [ ] Launch `pw-record` as subprocess capturing from combined source
- [ ] Feed audio chunks to faster-whisper (`tiny.en` model)
- [ ] Maintain rolling 2-minute transcript buffer (deque)
- [ ] Track silence duration from audio energy levels
- [ ] Run as async background task
- [ ] Expose `get_transcript()` and `get_silence_duration()`

### 1.4 `ocr_worker.py` — Screen Capture + OCR

- [ ] Run `grim` every 10 seconds to capture screenshot
- [ ] Run Tesseract OCR on each screenshot
- [ ] Maintain rolling buffer of last 5 screen text snapshots
- [ ] Auto-delete old screenshots (keep only 5)
- [ ] Run as async background task
- [ ] Expose `get_screen_text()` returning combined text from buffer

### 1.5 `gemini_client.py` — Primary AI

- [ ] Accept transcript + screen text as input
- [ ] Use interview-context prompt from PRD (section 11)
- [ ] Call Gemini Flash 2.0 API
- [ ] Return formatted answer (question detected + answer + tip)
- [ ] Handle rate limits (15 RPM free tier) and errors gracefully
- [ ] `async def get_answer(transcript, screen_text) -> str`

### 1.6 `ollama_client.py` — Fallback AI

- [ ] Same interface as gemini_client
- [ ] Call local Ollama `llava:7b` model
- [ ] Used when Gemini fails or `OFFLINE_MODE=true`
- [ ] `async def get_answer(transcript, screen_text) -> str`

### 1.7 `daemon.py` — FastAPI Application

- [ ] `GET /` — serves overlay UI (static files)
- [ ] `GET /status` — returns JSON: `{state, transcript_length, last_trigger_time}`
- [ ] `POST /trigger` — force generate answer from current context
- [ ] `POST /ask` — manual question from overlay input
- [ ] `GET /stream` — SSE endpoint pushing answers + status updates to overlay
- [ ] On startup: launch whisper_worker, ocr_worker as background tasks
- [ ] Auto-trigger loop: check detector every 0.5s, fire if conditions met
- [ ] AI routing: try Gemini first, fall back to Ollama on failure
- [ ] State machine: `passive` -> `generating` -> `answering` -> `passive`

**Validation:** `curl localhost:7777/status` returns JSON. `curl -X POST localhost:7777/trigger` generates an answer.

---

## Phase 2 — Overlay UI

### 2.1 `static/index.html`

- [ ] Minimal dark overlay layout
- [ ] Answer display area (scrollable, supports markdown-ish formatting)
- [ ] Status indicator bar (passive / generating / cooldown)
- [ ] Manual text input at bottom
- [ ] Answer history (scroll up to see previous)

### 2.2 `static/style.css`

- [ ] Dark monochrome theme matching Omarchy aesthetic
- [ ] Background: `#0a0a0a` with slight transparency
- [ ] Text: `#e0e0e0`, accent: `#4a9eff`
- [ ] Status colors: green (listening), yellow (generating), red (error)
- [ ] Monospace font for code snippets
- [ ] Compact layout for 400x600px window
- [ ] Smooth fade-in for new answers

### 2.3 `static/app.js`

- [ ] SSE connection to `/stream` — auto-reconnect on disconnect
- [ ] Render answers as they arrive (append to history)
- [ ] Manual question: Enter to send via `POST /ask`
- [ ] Escape to clear current input
- [ ] Auto-scroll to latest answer
- [ ] Status dot updates from SSE events

**Validation:** Open `localhost:7777` in browser. Send manual question via input. Answer appears.

---

## Phase 3 — Hyprland Integration

### 3.1 `~/.config/hypr/ghost.conf`

- [ ] Window rules for class `ghost-assistant`:
  - `float` — above tiling layout
  - `pin` — visible on all workspaces
  - `move 75% 10%` — top-right corner
  - `size 400 600` — fixed dimensions
  - `noblur`, `noanim`, `noshadow` — clean rendering
  - **`noscreenshare`** — invisible to Zoom/Meet/Teams (THE KEY RULE)
- [ ] Keybind `Super+G` — toggle overlay show/hide (calls `toggle.sh`)
- [ ] Keybind `Super+Shift+H` — force trigger (calls `trigger.sh`)

### 3.2 `toggle.sh`

- [ ] Check if Chrome `ghost-assistant` window exists via `hyprctl clients`
- [ ] If exists: toggle visibility with `hyprctl dispatch togglespecialworkspace`
- [ ] If not exists: launch Chrome Beta with `--app=http://localhost:7777 --class=ghost-assistant`

### 3.3 `trigger.sh`

- [ ] `curl -s -X POST http://localhost:7777/trigger`
- [ ] Simple, called by keybind

### 3.4 `start.sh`

- [ ] Activate venv
- [ ] Start FastAPI daemon (uvicorn)
- [ ] Wait for server ready
- [ ] Launch Chrome Beta overlay
- [ ] Set up PipeWire virtual sink if not already active

### 3.5 Source ghost.conf

- [ ] Add `source = ~/.config/hypr/ghost.conf` as LAST line in `~/.config/hypr/hyprland.conf`
- [ ] Highest priority — won't be overwritten by Omarchy updates

**Critical Validation:**
1. Open Google Meet / Zoom
2. Start screen share
3. Verify Ghost overlay is **NOT** visible in the shared screen
4. Verify keybinds work and don't leak to the call application

---

## Phase 4 — Waybar Module (Post-MVP)

- [ ] Add `custom/ghost` module to `modules-right` in `~/.config/waybar/config.jsonc`
- [ ] Module script: polls `/status` every 2s, outputs Waybar JSON
- [ ] Status dot: green (listening), yellow (generating), red (error/offline)
- [ ] Click handler: calls `toggle.sh`
- [ ] Style in `~/.config/waybar/style.css`

---

## Phase 5 — systemd Service (Post-MVP)

- [ ] Write `ghost.service` systemd user unit
- [ ] `systemctl --user enable ghost`
- [ ] Auto-start daemon on login
- [ ] `Restart=always` for crash recovery
- [ ] PipeWire virtual sink setup in `ExecStartPre`

---

## Phase 6 — Tuning (Post-MVP)

- [ ] Tune silence threshold (default 2.5s)
- [ ] Tune cooldown duration (default 15s)
- [ ] Expand keyword list for domain-specific interviews
- [ ] Adjust screenshot interval (5s for coding interviews)
- [ ] Tune Gemini prompt based on real answer quality
- [ ] Test Gemini -> Ollama fallback on network drop

---

## Build Order (MVP)

| Step | File(s) | Depends On |
|------|---------|------------|
| 1 | Environment setup (packages, venv) | Nothing |
| 2 | `config.py` | Step 1 |
| 3 | `detector.py` | Step 2 |
| 4 | `whisper_worker.py` | Step 2 |
| 5 | `ocr_worker.py` | Step 2 |
| 6 | `gemini_client.py` + `ollama_client.py` | Step 2 |
| 7 | `daemon.py` | Steps 3-6 |
| 8 | `static/` (index.html, style.css, app.js) | Step 7 |
| 9 | `ghost.conf` + `toggle.sh` + `trigger.sh` + `start.sh` | Steps 7-8 |
| 10 | Source ghost.conf in hyprland.conf | Step 9 |
| 11 | End-to-end test | All above |

---

## Resource Budget (MVP, passive mode)

| Component | CPU | RAM |
|-----------|-----|-----|
| FastAPI daemon (idle) | ~0.1% | ~50MB |
| faster-whisper tiny.en | ~8-15% | ~200MB |
| Tesseract OCR (every 10s) | ~2% burst | ~50MB |
| Silence + keyword detector | ~0.1% | ~5MB |
| grim screenshot loop | ~0.5% burst | negligible |
| Chrome Beta overlay (hidden) | ~1-2% | ~150MB |
| **Total (passive)** | **~12-20%** | **~455MB** |

Your system: Ryzen 5 5600H (12 threads) + 15GB RAM. Comfortable.

---

*Next step: say "go" and I'll start building from Phase 0.*

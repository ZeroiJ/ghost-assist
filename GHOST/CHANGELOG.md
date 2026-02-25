# Changelog

All notable changes to Ghost Assistant will be documented in this file.

---

## [0.1.0] — 2026-02-25

### Initial MVP Release

First working build of Ghost — invisible AI interview assistant for Arch Linux (Omarchy / Hyprland / Wayland).

### Added

**Backend**
- `config.py` — central configuration (thresholds, API keys, prompts, paths)
- `detector.py` — silence detection (2.5s threshold) + keyword matching + 15s cooldown
- `whisper_worker.py` — PipeWire audio capture via `pw-record` -> faster-whisper `tiny.en` -> rolling 2-minute transcript buffer
- `ocr_worker.py` — `grim` screenshots every 10s -> Tesseract OCR -> rolling 5-snapshot screen text buffer
- `gemini_client.py` — Gemini Flash 2.0 API client (primary, using `google-genai` SDK)
- `ollama_client.py` — Ollama `llava:7b` local fallback client (offline mode)
- `daemon.py` — FastAPI server on `localhost:7777` with endpoints:
  - `GET /` — serves overlay UI
  - `GET /status` — JSON status for Waybar
  - `POST /trigger` — force generate answer (keybind)
  - `POST /ask` — manual question from overlay input
  - `GET /stream` — SSE endpoint for real-time updates

**Frontend**
- `static/index.html` — overlay layout with answer display, status bar, manual input
- `static/style.css` — dark monochrome theme matching Omarchy aesthetic
- `static/app.js` — SSE listener, auto-scroll, manual question submission, keyboard shortcuts

**Hyprland Integration**
- `~/.config/hypr/ghost.conf` — window rules for `ghost-assistant` class:
  - `float` + `pin` — floats above tiling, visible on all workspaces
  - `no_screen_share` — invisible to Zoom/Meet/Teams via xdg-desktop-portal
  - `no_blur`, `no_anim`, `no_shadow` — clean rendering
  - Positioned top-right (75% x, 10% y), 400x600px
- `toggle.sh` — Super+G toggles overlay show/hide
- `trigger.sh` — Super+Shift+H forces AI answer generation
- `start.sh` — launches daemon + Chrome Beta overlay

**Project Setup**
- `.gitignore` — excludes `.venv/`, `.env`, `screenshots/`, `__pycache__/`
- `.env.example` — template for API keys and config
- `GHOST_ASSISTANT_PRD_v2.md` — full product requirements document
- `IMPLEMENTATION_PLAN.md` — phased build plan with checklists
- Python venv with all dependencies (fastapi, uvicorn, faster-whisper, google-genai, pytesseract, Pillow, httpx)

### Architecture Decisions
- **Keybinds:** Super+G (toggle) and Super+Shift+H (trigger) — avoids conflict with existing Super+Shift+G (Signal)
- **Python env:** venv in project dir, not system-wide
- **AI routing:** Gemini first, Ollama fallback on failure or `OFFLINE_MODE=true`
- **Window rule syntax:** uses Hyprland 0.53+ named rule format (`windowrule { ... }`)
- **Audio:** PipeWire virtual sink (`ghost_sink`) for combined mic + system audio capture

### Not Yet Implemented
- Waybar custom module (status dot indicator)
- systemd user service (auto-start on login)
- Tuning phase (threshold adjustments, prompt refinement)

---

*Format follows [Keep a Changelog](https://keepachangelog.com/).*

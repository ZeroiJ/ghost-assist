# Ghost Assistant — Implementation Plan

## Decisions

| Decision | Choice |
|----------|--------|
| Project directory | `~/ghost-assit/GHOST/` (restructured from root) |
| Python environment | venv inside project (`GHOST/.venv/`) |
| AI primary | Gemini Flash 2.0 API |
| AI fallback | Ollama `llava:7b` (local, offline) |
| Keybind: toggle overlay | `Super+G` |
| Keybind: force trigger | `Super+Shift+H` |
| Keybind: emergency erase | `Super+Shift+Q` |
| Keybind: analyze screen | `Super+Shift+A` |
| Approach | MVP first, then enhancements inspired by Cheating Daddy |
| Reference project | `~/ghost-assit/cheating-daddy/` (Electron/JS, Windows/Mac) |

---

## Current State (2026-02-26)

| Component | Status |
|-----------|--------|
| Arch Linux + Hyprland + Wayland | Running |
| PipeWire | Running (ghost_sink virtual sink active) |
| Python 3.14 | Installed |
| grim + tesseract | Installed |
| Chrome Beta | Installed |
| Ollama | Installed |
| Python venv + all packages | Installed in `GHOST/.venv/` |
| `.env` with Gemini API key | Configured |
| Daemon | Running (or via systemd) |
| Auto-trigger | Disabled by default |
| Overlay transparency | Partial (Chrome Wayland limitation) |
| Window rules | Removed (toggle.sh workaround) |

---

## File Structure

```
~/ghost-assit/
├── GHOST/                          # Main project
│   ├── .venv/                      # Python virtual environment
│   ├── .env                        # GEMINI_API_KEY, OFFLINE_MODE
│   ├── config.py                   # Central configuration + constants
│   ├── daemon.py                   # FastAPI backend (endpoints + SSE + workers)
│   ├── whisper_worker.py           # PipeWire audio -> faster-whisper -> transcript
│   ├── detector.py                 # Silence + keyword detection + cooldown
│   ├── gemini_client.py            # Gemini Flash 2.0 API client
│   ├── ollama_client.py            # Ollama fallback client
│   ├── ocr_worker.py               # grim screenshots -> Tesseract OCR
│   ├── rate_tracker.py             # Rate limit tracking + model rotation
│   ├── toggle.sh                   # Show/hide overlay (Super+G)
│   ├── trigger.sh                  # Force trigger (Super+Shift+H)
│   ├── erase.sh                    # Emergency erase (Super+Shift+Q)
│   ├── analyze.sh                  # Analyze screen (Super+Shift+A)
│   ├── start.sh                    # Launch daemon + Chrome overlay
│   ├── static/
│   │   ├── index.html              # Overlay UI
│   │   ├── style.css               # Dark monochrome theme
│   │   └── app.js                  # SSE listener + input + shortcuts
│   ├── screenshots/                # Rolling buffer (auto-cleared)
│   ├── history/                    # Persistent answer history (JSON files)
│   ├── CHANGELOG.md
│   ├── IMPLEMENTATION_PLAN.md      # This file
│   ├── GHOST_ASSISTANT_PRD_v2.md
│   └── .env.example
│
├── cheating-daddy/                 # Reference project (read-only)
│   └── (Electron/JS AI interview assistant for Win/Mac)
│
├── .gitignore
└── .git/

~/.config/hypr/
└── ghost.conf                      # Window rules + keybinds (sourced last)
```

---

## Phase 0 — Environment Setup [COMPLETED]

- [x] Install system packages: `tesseract`, `tesseract-data-eng`
- [x] Create Python venv in `GHOST/.venv/`
- [x] Install Python packages: `fastapi`, `uvicorn`, `faster-whisper`, `google-genai`, `python-dotenv`, `pytesseract`, `Pillow`, `websockets`, `httpx`
- [x] Create `.env` with `GEMINI_API_KEY` and `OFFLINE_MODE=false`
- [x] Create `screenshots/` directory
- [x] Verify PipeWire is capturing audio (ghost_sink active)

---

## Phase 1 — Backend Core [COMPLETED]

- [x] `config.py` — 105 lines, loads .env, all constants, keyword list, prompts, GhostState class
- [x] `detector.py` — 90 lines, silence + keyword detection, cooldown tracking
- [x] `whisper_worker.py` — 251 lines, PipeWire virtual sink, pw-record, faster-whisper tiny.en, rolling 2-min buffer
- [x] `ocr_worker.py` — 135 lines, grim screenshots every 10s, Tesseract OCR, rolling 5-snapshot buffer
- [x] `gemini_client.py` — 63 lines, Gemini Flash 2.0 via google-genai SDK
- [x] `ollama_client.py` — 68 lines, Ollama llava:7b fallback via httpx
- [x] `daemon.py` — 270 lines, FastAPI with 5 endpoints, SSE, auto-trigger loop, AI routing

---

## Phase 2 — Overlay UI [COMPLETED]

- [x] `static/index.html` — 48 lines, overlay layout with answer area + input
- [x] `static/style.css` — 307 lines, dark monochrome theme, status colors, animations
- [x] `static/app.js` — 208 lines, SSE with auto-reconnect, markdown rendering, manual input

---

## Phase 3 — Hyprland Integration [COMPLETED]

- [x] `ghost.conf` — window rules (float, pin, no_screen_share) + keybinds
- [x] `toggle.sh` — smart toggle via hyprctl + special workspace
- [x] `trigger.sh` — curl POST to /trigger
- [x] `start.sh` — launch daemon + Chrome overlay
- [x] Sourced in `hyprland.conf` as last line

---

## Phase 4 — Streaming Responses [COMPLETED]

*Inspired by: Cheating Daddy streams all AI responses token-by-token.*
*Current Ghost behavior: waits for full response, then displays all at once.*

### 4.1 `gemini_client.py` — Streaming Support

- [ ] Switch from `generate_content()` to `generate_content_stream()`
- [ ] Yield chunks as they arrive via async generator
- [ ] `async def get_answer_stream(transcript, screen_text) -> AsyncGenerator[str]`

### 4.2 `ollama_client.py` — Streaming Support

- [ ] Switch Ollama API call to `stream: true`
- [ ] Parse NDJSON response line by line
- [ ] `async def get_answer_stream(transcript, screen_text) -> AsyncGenerator[str]`

### 4.3 `daemon.py` — Stream-Aware Answer Generation

- [ ] SSE sends `event: answer-start` when generation begins
- [ ] SSE sends `event: answer-chunk` with each token/chunk as it arrives
- [ ] SSE sends `event: answer-done` when complete
- [ ] Keep existing `event: answer` for backward compat (full response)

### 4.4 `static/app.js` — Incremental Rendering

- [ ] Handle `answer-start`: create new answer card, show cursor/typing indicator
- [ ] Handle `answer-chunk`: append text to current card, auto-scroll
- [ ] Handle `answer-done`: finalize card, remove typing indicator
- [ ] Markdown rendering on each chunk (or on done)

**Validation:** Trigger an answer, see tokens appear one-by-one in the overlay.

---

## Phase 5 — Teleprompter Prompt Rewrite [COMPLETED]

*Inspired by: Cheating Daddy prompts instruct AI to give "exact words to say" — not suggestions, not explanations, but the actual words as if reading from a teleprompter.*

### 5.1 `config.py` — New Prompt Template

- [ ] Rewrite `SYSTEM_PROMPT` to teleprompter style:
  - Give exact words to say, not suggestions
  - 1-3 sentences max for verbal answers
  - Code snippets when coding question detected
  - No preamble, no "you could say..."
- [ ] Add `USER_CONTEXT` config (resume summary, job role, tech stack)
- [ ] Load user context from `.env` or `context.txt` file
- [ ] Inject user context into prompt

### 5.2 Multiple Prompt Profiles (stretch)

- [ ] `interview` profile (default) — technical interview answers
- [ ] `behavioral` profile — STAR method behavioral answers
- [ ] `coding` profile — code-first with explanation
- [ ] Profile selectable via `POST /profile` endpoint or config

**Validation:** Trigger answer, verify response reads like something you'd say out loud.

---

## Phase 6 — Emergency Erase [COMPLETED]

*Inspired by: Cheating Daddy's Ctrl+Shift+E — instantly hides window, closes AI session, clears all data.*

### 6.1 `erase.sh` — Emergency Kill Script

- [x] Kill uvicorn daemon process
- [x] Kill Chrome ghost-assistant window
- [x] Clear screenshots directory
- [x] Clear any temp audio files
- [x] Send desktop notification: "Ghost erased"
- [x] Entire script runs in < 1 second

### 6.2 `ghost.conf` — Emergency Keybind

- [x] Add `Super+Shift+Q` keybind -> `erase.sh` (Q instead of E — E was taken by Email)
- [x] Verified no conflict with existing bindings

**Validation:** Press Super+Shift+Q during a call. Ghost disappears instantly, no traces.

---

## Phase 7 — On-Demand Screen Analysis [COMPLETED]

*Inspired by: Cheating Daddy's manual screenshot + Gemini Vision analysis.*
*Current Ghost behavior: auto-OCR every 10s, but no on-demand "what's on screen?" feature.*

### 7.1 `gemini_client.py` — Vision Streaming

- [x] `get_vision_answer_stream(image_path)` — sends PIL Image to Gemini with vision prompt
- [x] Vision prompt: "Look at this screen. Identify the question/problem. Give the complete answer."
- [x] Sends screenshot as image (not OCR text) for better accuracy
- [x] Streams response via async generator

### 7.2 `daemon.py` — Screen Analysis Endpoint

- [x] `POST /analyze-screen` — takes screenshot NOW via grim, sends to Gemini Vision
- [x] `generate_vision_answer()` — streams chunks via SSE (answer-start/chunk/done)
- [x] Cleans up analysis screenshot after completion
- [x] Returns 503 in offline mode

### 7.3 `analyze.sh` + Keybind

- [x] `analyze.sh` — curl POST to /analyze-screen + notification
- [x] `Super+Shift+A` keybind added to `ghost.conf`
- [x] Works even when overlay is hidden

### 7.4 Overlay UI

- [x] "Analyze Screen" button (camera icon) in footer
- [x] `Ctrl+Enter` keyboard shortcut (global + input-focused)
- [x] Yellow pulsing animation while analyzing
- [x] SCREEN source label in answer cards

**Validation:** Open a LeetCode problem, press Super+Shift+A, get a solution based on what's on screen.

---

## Phase 8 — Custom User Context [COMPLETED]

*Inspired by: Cheating Daddy lets users paste resume + job description into prompt context.*

### 8.1 `context.txt` — User Context File

- [x] Plain text file in project root
- [x] User pastes: resume summary, target role, tech stack, company info
- [x] Loaded by `config.py` at startup
- [x] Injected into system prompt as additional context

### 8.2 `daemon.py` — Context Reload

- [x] `POST /reload-context` — hot-reload context.txt without restart
- [x] Updates both gemini_client and ollama_client module-level USER_CONTEXT
- [x] Returns context preview and length in response
- [x] `/status` now includes `user_context_length`

**Validation:** Add "I'm interviewing for Senior Backend at Google, Python/Go stack" to context.txt. POST /reload-context. Answers become role-specific.

---

## Phase 9 — Session History [COMPLETED]

*Inspired by: Cheating Daddy saves full conversation history with replay.*

### 9.1 Answer Persistence

- [x] Save each answer to `history/` as JSON: `{id, answer, timestamp, source, ai}`
- [x] Rolling history — keep last 50 answers (pruned on each save)
- [x] `GET /history?limit=20` endpoint returns recent answers
- [x] Load history from `history/` on daemon startup (persists across restarts)
- [x] History loaded into answers list and sent to overlay on SSE reconnect

### 9.2 Overlay History View

- [x] Scroll up in overlay to see previous answers (already implemented)
- [x] Answers persist across daemon restarts (loaded from history/)

---

## Phase 10 — Multi-Model Fallback with Rate Tracking [COMPLETED]

*Inspired by: Cheating Daddy rotates between 4 Groq models + Gemini models with daily limits.*

### 10.1 `rate_tracker.py` — Rate Limit Tracking

- [x] Track Gemini API calls per minute and per day (free tier: ~15 RPM, 1500 RPD)
- [x] Track error counts per model (back off after 3+ errors in 5 min)
- [x] Persist rate data to `limits.json` (survives daemon restart)
- [x] `get_best_model()` — returns best available model based on current limits
- [x] `summary()` — returns rate status for all models

### 10.2 `daemon.py` — Smart Model Rotation

- [x] `generate_answer()` now uses rate tracker to pick best model
- [x] Tries models in priority order: gemini -> ollama
- [x] Records successful calls and errors for future decisions
- [x] `/status` endpoint includes `rate_limits` summary
- [x] Logs which model served each answer

---

## Phase 11 — Waybar Module [COMPLETED]

- [x] `waybar-ghost.sh` — polls `/status` every 2s, outputs Waybar JSON with state classes
- [x] Added `custom/ghost` module to `~/.config/waybar/config.jsonc` (leftmost in modules-right)
- [x] Status colors: green (passive/listening), yellow pulsing (generating), blue (answering), dim (cooldown/off), red (error)
- [x] Click: toggle overlay (`toggle.sh`), Right-click: analyze screen (`analyze.sh`)
- [x] Tooltip shows state + answer count + transcript length
- [x] CSS styling added to `~/.config/waybar/style.css`
- [x] Waybar restarted to apply changes

---

## Phase 12 — systemd Service [COMPLETED]

- [x] `ghost-daemon.service` — systemd user unit in `~/.config/systemd/user/`
- [x] `Type=simple`, `Restart=always`, `RestartSec=3`
- [x] Depends on `graphical-session.target` and `pipewire.service`
- [x] Resource limits: `MemoryMax=1G`, `CPUQuota=50%`
- [x] `start.sh` updated to prefer systemd when available, fallback to direct
- [x] `start.sh` now checks if overlay is already running before launching
- [x] Enable with: `systemctl --user enable ghost-daemon`
- [x] Start with: `systemctl --user start ghost-daemon`
- [x] Logs via: `journalctl --user -u ghost-daemon -f`

---

## Phase 13 — Tuning [COMPLETED]

**Summary of fixes applied:**
- Auto-trigger disabled by default (`AUTO_TRIGGER_ENABLED=false` in config)
- Silence threshold: 2.5s → 4.0s
- Energy threshold: 0.01 → 0.03 (rejects more ambient noise)
- Cooldown: 15s → 30s
- Added `MIN_TRANSCRIPT_WORDS=8` (short fragments rejected)
- Added `REQUIRED_KEYWORD_MATCHES=2` (need 2+ keywords)
- Loop interval: 0.5s → 1.0s
- Added `POST /toggle-auto-trigger` endpoint

---

## Phase 14 — Transparent HUD Overlay [COMPLETED WITH LIMITATIONS]

**Goal:** Transform Ghost from an opaque floating window into a semi-transparent HUD.

### What Worked
- [x] CSS transparency: rgba backgrounds applied
- [x] Click-through: pointer-events logic added to app.js
- [x] Smaller overlay: 350×450px
- [x] Manual float/pin workaround in toggle.sh

### What Didn't Work
- **Chrome Wayland transparency**: Chrome `--app` mode does NOT support true transparency on Wayland. The rgba CSS makes it *slightly* translucent but not fully transparent.
- **Window rules**: Hyprland 0.53.3 syntax for `windowrule` caused Waybar errors. Removed window rules entirely from ghost.conf.
- **Manual workaround**: toggle.sh now uses `hyprctl dispatch` to float/pin/resize after Chrome launches.

### Files Modified
- `GHOST/static/style.css` — transparent backgrounds (rgba)
- `GHOST/static/app.js` — click-through logic (pointer-events)
- `GHOST/toggle.sh` — hyprctl dispatch commands for float/pin/resize
- `~/.config/hypr/ghost.conf` — window rules removed (syntax errors)

---

## Phase 15 — Fix Window Rules [COMPLETED]

### What was done:
- Fixed Hyprland 0.53.3 window rule syntax (use `float on`, `pin on`, etc.)
- Window rules now apply immediately on Chrome launch (no half-screen flash)
- Match by `class: chrome-localhost__-Default` (Chrome's actual class for app mode)
- Window floats, pins, sizes to 350x450, positions at 80% 8% automatically
- Removed manual hyprctl dispatch workaround from toggle.sh
- Waybar no longer breaks (correct syntax)
- Click-through logic in app.js (pointer-events: none on #ghost-app)

### Opacity note:
- Window rule `opacity 0.2 0.2` is set but Chrome Wayland doesn't support transparency well
- The window appears but isn't visually transparent (Chrome limitation)
- CSS rgba backgrounds provide partial transparency effect

### Files Modified:
- `~/.config/hypr/ghost.conf` — fixed window rules syntax
- `GHOST/toggle.sh` — removed manual dispatch workaround

---

## Phase 16 — GTK4 Layer Shell (Future)

### 15.1 Fix Hyprland Window Rules

**Problem:** Window rules in `ghost.conf` caused Waybar errors due to Hyprland 0.53.3 syntax issues.

**Options:**
- **A**: Fix window rule syntax (cleaner, works at login)
- **B**: Keep manual workaround in toggle.sh (current state, works but less robust)

**Question for user:** Should I try fixing the window rules syntax, or is the toggle.sh workaround sufficient?

### 15.2 Auto-Trigger Sensitivity UI

**Problem:** Auto-trigger is disabled by default. Users need a way to enable it and tune sensitivity without editing config.py.

**Implementation:**
- [ ] Add toggle button in overlay footer to enable/disable auto-trigger
- [ ] Add sensitivity slider (low/medium/high) in overlay settings
- [ ] `POST /set-sensitivity` endpoint accepts `low|medium|high`
- [ ] Updates detector.py thresholds at runtime

**Sensitivity presets:**
| Preset | Silence (s) | Energy | Cooldown (s) | Keywords |
|--------|-------------|--------|-------------|----------|
| Low    | 6.0         | 0.05   | 60          | 3        |
| Medium | 4.0         | 0.03   | 30          | 2        |
| High   | 2.5         | 0.01   | 15          | 1        |

---

## Phase 16 — Question Detection (Optional)

**Problem:** Currently triggers on any audio containing keywords, even statements.

**Improvement:**
- Detect question intonation patterns
- Look for "how do I...", "what is...", "why does...", "can you..." patterns
- Add `QUESTION_PATTERNS` config with regex list
- Only trigger if keywords AND question pattern detected

**Question for user:** Is this important, or is the current keyword+cooldown approach good enough?

---

## Phase 17 — GTK4 Layer Shell (Future)

**Problem:** Chrome Wayland transparency limitation.

**Solution:** Rewrite overlay as native GTK4 application using Layer Shell protocol.

**Pros:**
- True transparency (40%, 60%, 80% opacity options)
- Native Wayland, no browser dependency
- Lower memory usage
- Click-through built-in

**Cons:**
- Significant rewrite (new frontend, new backend routing)
- New dependencies: gtk4, pygtk, gobject
- More complex window management

**Question for user:** Is true transparency important enough to warrant this rewrite?

---

## Phase 18 — Hotword Detection (Future)

**Problem:** Keyword-in-audio has high false positive rate.

**Solution:** UsePorcupine or Precise for real wake-word detection ("Hey Ghost").

**Pros:**
- Much lower false positive rate
- Runs locally (privacy)
- True hands-free activation

**Cons:**
- Additional dependency
- Must train/customize wake word
- More CPU usage

---

## Phase 19+ — Backlog

- [ ] History search (find past answers by keyword)
- [ ] Audio visualizer (show mic levels)
- [ ] Multiple context profiles (interview/behavioral/coding)
- [ ] Calendar integration for auto-prep

---

## Build Order (Updated)

| Priority | Phase | Description | Status |
|----------|-------|-------------|--------|
| 1 | Phase 13 | Tuning | ✅ Complete |
| 2 | Phase 14 | Transparent HUD | ⚠️ Complete (limitations) |
| 3 | Phase 15 | Window rules + Auto-trigger UI | Pending |
| 4 | Phase 16 | Question detection | Optional |
| 5 | Phase 17 | GTK4 Layer Shell | Future |
| 6 | Phase 18 | Hotword detection | Future |
| 7 | Phase 19+ | Backlog items | Future |

---

*Phases 13-14 complete. Next: Phase 15 (Window rules + Auto-trigger UI)*

---

## Resource Budget (passive mode)

| Component | CPU | RAM |
|-----------|-----|-----|
| FastAPI daemon (idle) | ~0.1% | ~50MB |
| faster-whisper tiny.en | ~8-15% | ~200MB |
| Tesseract OCR (every 10s) | ~2% burst | ~50MB |
| Silence + keyword detector | ~0.1% | ~5MB |
| grim screenshot loop | ~0.5% burst | negligible |
| Chrome Beta overlay (hidden) | ~1-2% | ~150MB |
| **Total (passive)** | **~12-20%** | **~455MB** |

System: Ryzen 5 5600H (12 threads) + 15GB RAM. Comfortable.

---

## Reference: Cheating Daddy Insights

Key architectural differences worth noting:
- **Audio:** Streams raw PCM to Gemini 2.5 Flash Native Audio API (no local Whisper needed). Ghost uses local Whisper — more private but higher CPU.
- **Question detection:** Relies entirely on Gemini's turn detection + speaker diarization. Ghost uses explicit silence + keyword rules — more predictable but less natural.
- **Multi-provider:** Cloud WebSocket, BYOK (Gemini+Groq), Local (Ollama+Whisper). Ghost is simpler: Gemini primary, Ollama fallback.
- **Stealth:** Electron `setContentProtection(true)` + click-through mode. Ghost uses Hyprland `no_screen_share` — native and more reliable on Wayland.
- **UI:** Lit web components with 9 themes. Ghost uses vanilla HTML/CSS/JS — lighter, faster.

---

*Phases 13-14 complete. Next: Phase 15 (Window rules + Auto-trigger UI)*

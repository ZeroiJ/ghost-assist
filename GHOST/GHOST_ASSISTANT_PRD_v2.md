# 👻 Ghost — Invisible AI Interview Assistant
### Product Requirements Document v2.0

---

## 1. Overview

**Ghost** is a locally-running, screen-share-invisible AI assistant built specifically for Arch Linux (Hyprland + Wayland). It passively listens and watches during interviews or meetings, silently building context, and automatically delivers sharp AI-generated answers when it detects a technical question being asked — without ever being visible to the other person on the call.

---

## 2. Goals

- **Invisible** — completely excluded from screen share via Hyprland/Wayland window rules. More bulletproof than Cluely on Mac because it's enforced at the Wayland compositor level
- **Passive by default** — runs silently in the background, never interrupting
- **Automatic intelligence** — detects questions via silence + keyword detection, triggers answers without you doing anything
- **Manual override always available** — `Super+Shift+G` forces a trigger anytime
- **Privacy-first** — local transcription via Whisper + local OCR via Tesseract, Gemini only called when answer is needed
- **Lightweight** — minimal resource footprint during passive mode so your machine stays responsive during the interview
- **Tiling-safe** — floats above Hyprland's tiling layout without disturbing it

---

## 3. Non-Goals

- Not a real-time voice assistant (no wake word, no always-on AI calls)
- Not a standalone app with its own window manager
- Not cross-platform (Arch Linux + Hyprland only, intentionally)
- Not storing any conversation data beyond the current session
- Not hiding from local process managers like Mission Center (unnecessary — only you can see those)

---

## 4. User Persona

**Primary:** A developer or technical professional on Arch Linux (Omarchy) who frequently does technical interviews, pair programming sessions, or online meetings and wants AI assistance that is completely invisible to the other party and requires zero manual interaction during the interview.

---

## 5. Core Features

### 5.1 Passive Mode (always running)
- Continuously captures **both audio channels** (system audio + mic) via PipeWire — no VirtualCable or VoiceMeeter needed, PipeWire handles this natively
- Transcribes speech locally using **faster-whisper** (`tiny.en` model) — stays on device
- Keeps a **rolling 2-minute transcript buffer** in memory
- Takes a **screenshot every 10 seconds** via `grim`
- Runs **Tesseract OCR** on each screenshot to extract screen text (code, slides, problem statements)
- Keeps last 5 screen text snapshots as rolling context buffer
- Zero UI shown, zero network calls — completely silent

### 5.2 Auto-Trigger (Option 4 — Silence + Keyword Detection)
The core intelligence layer. After every transcription chunk, the detector checks two conditions simultaneously:

**Condition 1 — Silence:** Audio has been silent for ≥ 2.5 seconds (interviewer finished speaking)

**Condition 2 — Question keywords:** Last transcribed sentence contains any of:
`how, why, what, explain, implement, design, tell me, can you, walk me, describe, difference between, when would, have you, do you`

**Both conditions must be true** to auto-trigger. If only one is true, Ghost keeps listening.

**Cooldown:** After each auto-trigger, a **15 second cooldown** prevents repeated firing for the same question. During cooldown, listening and buffering continues normally.

### 5.3 Active Mode (manual override)
- Triggered anytime by `Super+Shift+G` — even during cooldown
- Grabs current transcript buffer + latest screen text
- Sends to **Gemini Flash 2.0 API** with interview-context prompt
- Answer appears in Ghost overlay instantly
- User can type manual follow-up questions if needed

### 5.4 Ghost Overlay
- A **Chrome Beta** window launched in `--app=` mode (no browser chrome, no tabs, no URL bar)
- Served by the local FastAPI daemon at `localhost:7777`
- **Floats above Hyprland tiling layout** — does not split or tile with other windows
- Positioned top-right corner (75% x, 10% y), 400x600px fixed size
- **Pinned across all workspaces** — follows you everywhere
- **Excluded from xdg-desktop-portal-hyprland screencasting** — invisible to Zoom, Meet, Teams
- Toggled show/hide with `Super+G` and Waybar click

### 5.5 Waybar Module
- Minimal status indicator on the **right side** of Waybar
- Status dot: 🟢 listening/active, 🟡 generating answer, 🔴 error/offline
- Click to toggle overlay on/off
- Matches Omarchy's minimal monochrome aesthetic

---

## 6. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **OS / WM** | Arch Linux + Hyprland 0.53 + Wayland | Native screen protection via xdg-portal, stricter than Mac/Windows |
| **Backend** | Python 3.12 + FastAPI + Uvicorn | Lightweight async server, easy Gemini integration |
| **Transcription** | faster-whisper (`tiny.en` model) | Local, private, low CPU footprint (~8-15%) |
| **Audio capture** | PipeWire + `pw-record` | Already running on Omarchy, captures both channels natively, no VoiceMeeter needed |
| **Screen capture** | `grim` | Wayland-native screenshot tool |
| **OCR** | Tesseract (`tesseract-data-eng`) | Extracts text from screenshots locally — reads code, slides, problem statements |
| **Question detection** | Silence detector + keyword matcher | Hybrid Option 4 — accurate, lightweight, no extra AI calls |
| **AI (active)** | Google Gemini Flash 2.0 API | Fast, multimodal, free tier sufficient (15 RPM, 1M tokens/day) |
| **AI (local fallback)** | Ollama + `llava:7b` | Offline fallback, runs on RTX 3050 Mobile (4GB VRAM) |
| **Frontend** | HTML + CSS + Vanilla JS | Served by FastAPI, rendered in Chrome Beta app mode |
| **Browser** | Chrome Beta (`google-chrome-beta`) | `--app=` mode for clean overlay, `--class=` for Hyprland rules |
| **Bar** | Waybar | Custom module, right side, status dot + toggle |
| **Keybinds** | Hyprland `ghost.conf` | Sourced last, highest priority, not overwritten by Omarchy updates |
| **Service** | systemd user service | Auto-start daemon on login, auto-restart on crash |

---

## 7. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PASSIVE LAYER                           │
│                                                             │
│  PipeWire ──► pw-record ──► faster-whisper                  │
│  (mic + system audio)            │                          │
│                           transcript buffer                  │
│                           (rolling 2 mins)                  │
│                                  │                          │
│  grim (every 10s) ──► tesseract OCR ──► screen text buffer  │
│                                  │     (last 5 snapshots)   │
│                                  │                          │
│                    ┌─────────────▼──────────────┐           │
│                    │  SILENCE + KEYWORD DETECTOR │           │
│                    │                            │           │
│                    │  silence ≥ 2.5s            │           │
│                    │       AND                  │           │
│                    │  question keyword in        │           │
│                    │  last sentence?             │           │
│                    │       │                    │           │
│                    │  YES ─► auto trigger        │           │
│                    │  NO  ─► keep listening      │           │
│                    │       │                    │           │
│                    │  15s cooldown after trigger │           │
│                    └─────────────┬──────────────┘           │
└──────────────────────────────────│──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     FastAPI DAEMON (:7777)   │
                    │                             │
                    │  GET  /        ← overlay UI │
                    │  GET  /status  ← waybar     │
                    │  POST /ask     ← manual q   │
                    │  POST /trigger ← keybind    │
                    └──────────────┬──────────────┘
                                   │
                         ┌─────────┴──────────┐
                         ▼                    ▼
                  Gemini Flash 2.0       Ollama llava:7b
                  (primary, online)      (fallback, offline)
                         │
                         ▼
          ┌──────────────────────────────────┐
          │        GHOST OVERLAY              │
          │  Chrome Beta --app mode           │
          │  float · pin · noscreenshare      │
          │  top-right corner, all workspaces │
          │  invisible to Zoom/Meet/Teams     │
          └──────────────────────────────────┘
```

---

## 8. Invisibility Mechanism

### How Cluely does it (Mac/Windows)
Uses a native OS window flag to exclude the window from the screen capture API. App-level solution.

### How Ghost does it (Arch/Hyprland/Wayland)
Uses Wayland's compositor-level security model. `xdg-desktop-portal-hyprland` is the ONLY pipeline through which Zoom, Meet, and Teams can capture your screen on Wayland. Our window rule tells the portal to skip our window entirely. **The interviewer's app has zero ability to work around this** — it's enforced at the compositor, not the app level.

```ini
# ~/.config/hypr/ghost.conf
windowrulev2 = float, class:^(ghost-assistant)$
windowrulev2 = pin, class:^(ghost-assistant)$
windowrulev2 = move 75% 10%, class:^(ghost-assistant)$
windowrulev2 = size 400 600, class:^(ghost-assistant)$
windowrulev2 = noblur, class:^(ghost-assistant)$
windowrulev2 = noanim, class:^(ghost-assistant)$
windowrulev2 = noshadow, class:^(ghost-assistant)$
windowrulev2 = noscreenshare, class:^(ghost-assistant)$  # THE KEY LINE
```

Chrome Beta is launched with `--class=ghost-assistant` so Hyprland applies these rules:

```bash
google-chrome-beta --app=http://localhost:7777 \
  --class=ghost-assistant \
  --disable-background-timer-throttling \
  --no-first-run
```

### What about Mission Center / htop?
Ghost WILL appear in Mission Center and htop — but that's completely fine. Those tools are local, only visible to you. The interviewer cannot see your process list. This is a non-issue.

### What about Hyprland keybinds being detected?
Hyprland intercepts keybinds at the compositor level — the application running (Zoom, Meet, etc.) never sees the keypress at all. Zero chance of detection.

---

## 9. Audio Setup (No VoiceMeeter Needed)

On Windows you'd need VirtualCable + VoiceMeeter to merge mic and system audio. On Arch with PipeWire this is native:

```bash
# Create virtual combined sink
pactl load-module module-null-sink \
  sink_name=ghost_sink \
  sink_properties=device.description=GhostSink

# Loopback system audio into it
pactl load-module module-loopback source=ghost_sink.monitor

# Record from combined source
pw-record --target=ghost_sink.monitor ghost_audio.raw
```

PipeWire is already running on your system (verify: `pactl info | grep "Server Name"` → should show PulseAudio on PipeWire).

---

## 10. Silence + Keyword Detector Logic

```python
import time

SILENCE_THRESHOLD = 2.5       # seconds
COOLDOWN_DURATION = 15        # seconds
last_trigger_time = 0

QUESTION_KEYWORDS = [
    'how', 'why', 'what', 'explain', 'implement',
    'design', 'tell me', 'can you', 'walk me',
    'describe', 'difference between', 'when would',
    'have you', 'do you', 'could you', 'would you'
]

def should_trigger(transcript: str, silence_duration: float) -> bool:
    global last_trigger_time

    # Check cooldown
    if time.time() - last_trigger_time < COOLDOWN_DURATION:
        return False

    # Condition 1: silence
    if silence_duration < SILENCE_THRESHOLD:
        return False

    # Condition 2: question keyword in last sentence
    last_sentence = transcript.strip().split('.')[-1].lower()
    has_keyword = any(kw in last_sentence for kw in QUESTION_KEYWORDS)

    if has_keyword:
        last_trigger_time = time.time()
        return True

    return False
```

---

## 11. Gemini Prompt Design

```
You are a hidden AI assistant helping during a technical interview.
The user cannot type long messages — give concise, directly usable answers.

CONTEXT:
- Last 2 minutes of conversation transcript:
  {transcript}

- Current screen content (OCR extracted):
  {screen_text}

Based on the conversation and screen content, what is the most likely 
technical question being asked of the user right now, and what is the 
best answer they should give?

Format your response exactly like this:
**Question detected:** <what you think was asked>
**Answer:** <direct, confident, complete answer>
**Tip:** <one quick extra tip if relevant, otherwise omit this line>

Keep the answer concise but complete. If it's a coding question, 
include a short code snippet.
```

---

## 12. File Structure

```
~/.local/share/ghost/
├── daemon.py                 # FastAPI backend + audio/screenshot loops
├── whisper_worker.py         # faster-whisper transcription thread
├── detector.py               # silence + keyword detection logic
├── gemini_client.py          # Gemini Flash 2.0 API calls
├── ollama_client.py          # Ollama llava:7b fallback
├── ocr_worker.py             # grim + tesseract OCR loop
├── toggle.sh                 # called by Super+G and Waybar click
├── trigger.sh                # called by Super+Shift+G (force active mode)
├── static/
│   ├── index.html            # overlay UI
│   ├── style.css             # minimal dark styling
│   └── app.js                # SSE listener + manual input
├── screenshots/              # rolling buffer — 5 latest (auto cleared)
└── ghost.service             # systemd user service

~/.config/hypr/
└── ghost.conf                # window rules + keybinds (sourced in hyprland.conf)

~/.config/waybar/
├── config.jsonc              # ghost module added to right modules
└── style.css                 # ghost dot indicator styles
```

---

## 13. Keybinds

| Shortcut | Action |
|---|---|
| `Super + G` | Toggle Ghost overlay show/hide |
| `Super + Shift + G` | Force active mode — generate answer NOW |

Both added to `~/.config/hypr/ghost.conf` which is sourced at the end of Hyprland config — highest priority, not overwritten by Omarchy updates.

---

## 14. Resource Budget

| Component | CPU | RAM | GPU |
|---|---|---|---|
| FastAPI daemon (idle) | ~0.1% | ~50MB | 0 |
| faster-whisper tiny.en | ~8-15% | ~200MB | 0 (CPU) |
| Tesseract OCR (every 10s) | ~2% burst | ~50MB | 0 |
| Silence + keyword detector | ~0.1% | ~5MB | 0 |
| grim screenshot loop | ~0.5% burst | negligible | 0 |
| Chrome Beta overlay (hidden) | ~1-2% | ~150MB | minimal |
| Gemini call (on trigger only) | ~0% | 0 | 0 |
| Ollama llava:7b (if fallback) | ~20% | ~4GB VRAM | ~3.5GB |
| **Total (passive, no Ollama)** | **~12-20%** | **~455MB** | **0** |

Ryzen 5 5600H + 15GB RAM handles this comfortably during an interview.

---

## 15. Implementation Roadmap

### Phase 0 — Environment Setup (Day 1)
- [ ] Install system packages: `grim`, `tesseract`, `tesseract-data-eng`, `python`, `python-pip`
- [ ] Install Python packages: `fastapi`, `uvicorn`, `faster-whisper`, `google-generativeai`, `python-dotenv`, `pytesseract`, `Pillow`
- [ ] Pull Ollama model: `ollama pull llava:7b`
- [ ] Set up Gemini API key in `~/.config/ghost/.env`
- [ ] Set up PipeWire virtual sink for combined audio capture
- [ ] Verify Chrome Beta launches correctly with `--app=` and `--class=ghost-assistant`
- [ ] Verify `grim` takes screenshots correctly

### Phase 1 — Backend Daemon (Day 1-2)
- [ ] `daemon.py` — FastAPI app with `/`, `/status`, `/ask`, `/trigger` endpoints + SSE stream
- [ ] `whisper_worker.py` — PipeWire capture thread → faster-whisper → rolling transcript buffer
- [ ] `ocr_worker.py` — grim every 10s → tesseract → screen text buffer (last 5)
- [ ] `detector.py` — silence detection + keyword matching + cooldown logic
- [ ] `gemini_client.py` — sends transcript + screen text to Gemini Flash 2.0
- [ ] `ollama_client.py` — fallback client, auto-switches when offline
- [ ] Test all endpoints with `curl`
- [ ] Test auto-trigger fires correctly on question detection
- [ ] Test cooldown prevents double-firing

### Phase 2 — Overlay UI (Day 2-3)
- [ ] `index.html` — clean dark overlay matching Omarchy's monochrome aesthetic
- [ ] SSE connection to daemon — answer appears automatically when triggered
- [ ] Manual text input for follow-up questions
- [ ] Status indicator (passive / generating / cooldown)
- [ ] Answer history — scroll up to see previous answers
- [ ] Escape to clear current answer, Enter to send manual question

### Phase 3 — Hyprland Integration (Day 3)
- [ ] `ghost.conf` — all window rules for `ghost-assistant` class
- [ ] `ghost.conf` — `Super+G` and `Super+Shift+G` keybinds
- [ ] `toggle.sh` — checks if Chrome window exists, shows/hides it
- [ ] `trigger.sh` — POSTs to `/trigger` endpoint
- [ ] Add `source = ~/.config/hypr/ghost.conf` to Hyprland config
- [ ] Verify window floats above tiling layout correctly
- [ ] Verify window is pinned across all workspaces
- [ ] **Critical test:** open screen share in Meet → verify Ghost window NOT captured

### Phase 4 — Waybar Module (Day 3-4)
- [ ] Add `custom/ghost` module to `~/.config/waybar/config.jsonc` right modules
- [ ] Module script: polls `/status` every 2s, outputs Waybar JSON
- [ ] Click handler calls `toggle.sh`
- [ ] Style dot indicator in `style.css` — green/yellow/red, matches Omarchy theme
- [ ] Test all three status states visually

### Phase 5 — systemd Service (Day 4)
- [ ] Write `~/.local/share/ghost/ghost.service` user unit
- [ ] `systemctl --user enable ghost`
- [ ] `systemctl --user start ghost`
- [ ] Test auto-start on login
- [ ] Test daemon auto-restarts on crash (`Restart=always`)
- [ ] Test PipeWire virtual sink persists across restarts

### Phase 6 — Tuning + Real Interview Test (Day 5)
- [ ] Tune silence threshold (2.5s default — adjust if too sensitive/slow)
- [ ] Tune cooldown duration (15s default — adjust based on interview pace)
- [ ] Tune keyword list — add domain-specific terms (e.g. "complexity", "optimize", "approach")
- [ ] Tune screenshot interval (try 5s for coding interviews)
- [ ] Test full flow: join Meet → share screen → verify Ghost invisible → auto-trigger on question
- [ ] Test Gemini → Ollama fallback when network drops
- [ ] Adjust Gemini prompt based on real answer quality

---

## 16. Installation Commands (Summary)

```bash
# System packages
sudo pacman -S grim tesseract tesseract-data-eng python python-pip

# Python packages
pip install fastapi uvicorn faster-whisper google-generativeai \
            python-dotenv pytesseract Pillow

# Ollama model
ollama pull llava:7b

# PipeWire audio setup
pactl load-module module-null-sink sink_name=ghost_sink \
  sink_properties=device.description=GhostSink
pactl load-module module-loopback source=ghost_sink.monitor

# Enable Ghost service
systemctl --user enable --now ghost.service
```

---

## 17. Privacy Notes

| Data | Where it goes |
|---|---|
| Audio (passive) | Stays on device — processed by local faster-whisper |
| Screenshots (passive) | Stays on device — stored in `/tmp/ghost/`, cleared on reboot |
| OCR text (passive) | Stays on device — held in memory only |
| Transcript + screen text (on trigger) | Sent to Google Gemini Flash 2.0 API |
| Nothing | Stored permanently anywhere |

> **Full offline mode:** Disable Gemini and use Ollama-only. Everything stays local. Response quality lower but 100% private. Toggle via `~/.config/ghost/.env` → `OFFLINE_MODE=true`

---

## 18. Visibility Summary

| Where | Visible? | Notes |
|---|---|---|
| Screen share (Meet/Zoom/Teams) | ❌ No | Excluded via xdg-portal + Hyprland window rule |
| Interviewer's screen | ❌ No | They only see what screen share sends |
| Waybar | ✅ Yes | Only you can see your own Waybar |
| Mission Center / htop | ✅ Yes | Local only — interviewer cannot see your processes |
| Hyprland keybind presses | ❌ No | Intercepted at compositor level, apps never see it |
| Alt-tab / window switcher | ❌ No | `pin` + `float` removes it from switcher |

---

*Ghost v0.2 — built for Arch, built to be invisible, built to win interviews.*

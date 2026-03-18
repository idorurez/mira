# Mira Session Status — 2026-03-17

## What's Working

- **Streaming voice pipeline**: wake word (OpenWakeWord "hey_jarvis") → STT (Vosk) → Claude (OpenClaw gateway, streamed) → TTS (Kokoro af_river, sentence-chunked) → Live2D avatar
- **Streaming response**: Gateway deltas stream token-by-token. TTS starts on first complete sentence while Claude generates the rest. Perceived latency = time-to-first-sentence instead of full-response wait
- **Avatar rendering**: Live2D Hiyori model in Chromium kiosk mode at 60fps. Dramatic expressions with head angle changes on wake (surprised), thinking (eyes up-right, head tilt), talking (mouth animation during TTS)
- **OpenClaw node**: systemd service (`piichan.service`) auto-starts on boot. Gateway bridge in main.py connects separately for voice loop
- **Self-trigger prevention**: mic muted during TTS, skip OWW prediction while muted, audio queue drain, 2s cooldown, single-word transcript filter
- **Voice selection**: English = Kokoro `af_river` (calm, mature), Japanese = VOICEVOX 冥鳴ひまり style_id=14
- **Text mode**: `--simulate --no-mic` for testing gateway + TTS without mic. Streams tokens to terminal in real-time

## Current Issues

### 1. Gateway TTFT (Critical)
- Time-to-first-token: 4.5-10s+ and degrading per message in a session
- Root cause: agent/session configuration on gateway side
- The `mira` agent must be properly configured on gateway with system prompt (personality)
- Personality must be in system prompt (cacheable), NOT injected in user messages
- Session key is `agent:mira:main` — agent name must match exactly
- **Fix**: Configure `mira` agent on gateway with `data/personality.md` as system prompt in SOUL.md

### 2. Mic Signal-to-Noise Ratio (Critical)
- USB PnP Sound Device (hw:2,0) picks up speech at ~0.20 RMS, ambient noise at ~0.15 RMS
- Very low SNR makes STT unreliable — speech barely distinguishable from noise
- Wake word scores hover around 0.3-0.5 (threshold set to 0.3 to compensate)
- **Fix**: ReSpeaker USB mic array with DSP (on order)

### 3. STT Accuracy (High)
- Medium Vosk model (`vosk-model-en-us-0.22-lgraph`, 205MB) still produces poor transcripts
- Root cause is low mic SNR, not model quality
- Large Vosk model (1.8GB) caused OOM reboot (4GB+ RAM)
- **Fix**: Better mic hardware first, then consider Whisper.cpp

### 4. Self-Trigger Residual (Low)
- Mostly fixed with software workarounds
- ReSpeaker with hardware AEC will eliminate this entirely

## Architecture

```
[USB Mic] → OpenWakeWord → Vosk STT → OpenClaw Gateway → Claude API
                                                              ↓ (streaming deltas)
[USB Speaker] ← Kokoro TTS ←──── sentence queue ←──── GatewayBridge
                    ↓ (sentence 1 plays while sentence 2 generates)
[HDMI Display] ← Chromium ← FaceServer (ws:18793 + http:8080) ← Live2D
```

### Streaming Flow (New)

```
Claude generates: "Same thing. Text or voice, it all comes through."
                   ^^^^^^^^^^^^^^^^
                   Sentence 1 detected at "."
                   → pushed to TTS queue immediately
                   → TTS starts speaking while Claude generates rest
                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                      Sentence 2 arrives, queued for TTS
                                      → plays right after sentence 1 finishes
```

## Key Config (config.yaml)

```yaml
voice:
  engine: auto
  kokoro_voice: af_river
  speaker_id: 14        # VOICEVOX 冥鳴ひまり
  volume: 0.3

voice_input:
  wake_word: hey_jarvis
  wake_word_threshold: 0.3
  vosk_model_path: ./models/vosk-model-en-us-0.22-lgraph
  silence_threshold: 0.20
  silence_duration: 1.0
  max_record_seconds: 7.0

audio:
  input_device: 0       # USB PnP Sound Device (mic only)
  output_device: 1      # USB PnP Audio Device (speaker)

can:
  interface: mock
```

## Gateway Agent Configuration

**Critical for performance.** The Pi node sends `sessionKey: "agent:mira:main"`.

The gateway must have:
1. An agent named `mira` (exact match)
2. Personality/system prompt from `data/personality.md` configured in the agent's `SOUL.md`
3. System prompt must NOT be injected in user messages (kills prompt caching, adds 5-10s TTFT)

Without this, TTFT degrades from ~1-2s to 5-10s+ per message.

## Key Files Modified This Session

| File | Changes |
|------|---------|
| `src/main.py` | Streaming TTS pipeline, sentence-chunked voice output, TTFT timing, removed personality injection |
| `src/node.py` | Streaming deltas via `on_delta` callback, removed client-side personality injection, session key `agent:mira:main` |
| `src/voice.py` | `speak_streamed()` — consumes sentence queue for back-to-back TTS |
| `ui/live2d_test.html` | More dramatic expressions with head angle changes |
| `docs/GATEWAY_SETUP.md` | Agent name matching requirement, system prompt vs user message caching |

## Hardware

### On Order
- **ReSpeaker USB Mic Array** with DSP — hardware AEC, better SNR, directional pickup

### Current
- Raspberry Pi 5 (8GB)
- Generic USB PnP mic + USB PnP speaker (separate devices)
- WaveShare 2-CH CAN HAT (unused, mock mode)
- HDMI display for Live2D avatar

## Launch Commands

```bash
# Chromium kiosk (from SSH)
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  chromium --password-store=basic --no-first-run \
  --disable-session-crashed-bubble --kiosk --disk-cache-size=0 \
  http://localhost:8080/live2d_test.html 2>/dev/null &

# Main voice loop
cd /home/piichan/mira
PYTHONUNBUFFERED=1 nohup ./venv/bin/python -m src.main > /tmp/mira.log 2>&1 &

# Text mode (for testing gateway without mic)
cd /home/piichan/mira
PYTHONUNBUFFERED=1 ./venv/bin/python -m src.main --simulate --no-mic

# Monitor logs
tail -f /tmp/mira.log

# Kill everything
pkill -f "src.main"; pkill chromium; fuser -k 8080/tcp 18793/tcp
```

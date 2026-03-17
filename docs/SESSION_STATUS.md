# Mira Session Status — 2026-03-16

## What's Working

- **Full voice pipeline**: wake word (OpenWakeWord "hey_jarvis") → STT (Vosk) → Claude (OpenClaw gateway) → TTS (Kokoro af_river) → Live2D avatar
- **Personality injection**: `data/personality.md` is prepended to every gateway message. Claude responds in character — short, composed, no filler
- **Avatar rendering**: Live2D Hiyori model in Chromium kiosk mode at 60fps. Expression changes on wake (surprised), thinking (waiting for Claude), talking (mouth animation during TTS)
- **OpenClaw node**: systemd service (`piichan.service`) auto-starts on boot. Gateway bridge in main.py connects separately for voice loop
- **Self-trigger prevention**: mic muted during TTS, skip OWW prediction while muted, audio queue drain, 3.5s cooldown, single-word transcript filter
- **Voice selection**: English = Kokoro `af_river` (calm, mature), Japanese = VOICEVOX 冥鳴ひまり style_id=14

## Current Issues

### 1. Mic Signal-to-Noise Ratio (Critical)
- USB PnP Sound Device (hw:2,0) picks up speech at ~0.20 RMS, ambient noise at ~0.15 RMS
- Very low SNR makes STT unreliable — speech is barely distinguishable from noise
- Wake word scores hover around 0.3-0.5 (threshold set to 0.3 to compensate)
- **Fix**: Better mic, directional mic, or hardware gain adjustment

### 2. STT Accuracy (High)
- Medium Vosk model (`vosk-model-en-us-0.22-lgraph`, 205MB) still produces poor transcripts
- "what time is it" → "the", "can you hear me" → "songs on"
- Root cause is low mic SNR, not model quality
- Large Vosk model (1.8GB) was better but caused OOM reboot (4GB+ RAM usage)
- **Consider**: Whisper.cpp for better accuracy, or fix mic first

### 3. TTS Audio Output (Medium)
- `voice.speak()` returns `True` but audio sometimes not heard
- Output device is USB PnP Audio Device (hw:3,0), device index 1
- Direct tests (`sd.play` on device 1) work, but during voice loop it's inconsistent
- May be a timing/device contention issue with mic on same USB hub

### 4. Self-Trigger Residual (Low)
- Mostly fixed but still occasionally triggers after TTS on louder responses
- Current mitigation: mute during TTS + 3.5s cooldown + queue drain + single-word filter
- Could still improve with longer cooldown or hardware mic/speaker isolation

### 5. Gateway Latency (Medium)
- Claude response time: 4-8 seconds via OpenClaw gateway
- TTS synthesis: 3-7 seconds on Pi CPU (scales with response length)
- Total round trip: 8-15 seconds from end of speech to hearing response
- Personality payload (~1KB) sent with every message adds some overhead

## Architecture

```
[USB Mic] → OpenWakeWord → Vosk STT → OpenClaw Gateway → Claude
                                                              ↓
[USB Speaker] ← Kokoro TTS ← main.py ← WebSocket ← Claude response
                                  ↓
[HDMI Display] ← Chromium ← FaceServer (ws:18793 + http:8080) ← Live2D
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

## Key Files Modified This Session

| File | Changes |
|------|---------|
| `src/main.py` | Voice loop timing, mute-during-TTS, gateway personality, no local LLM fallback |
| `src/voice_input.py` | Mute flag, audio queue drain, RMS/ww debug logging, single-word filter |
| `src/voice.py` | Chime generator (unused — causes self-trigger), load all VVM files |
| `src/node.py` | Personality injection into gateway messages |
| `src/face.py` | Listening expression → surprised |
| `src/can_reader.py` | Skip DBC loading in mock mode |
| `data/personality.md` | Rewritten for cyberpunk avatar (mature, composed, voice-first) |

## Hardware Recommendations

### Priority 1: Better Microphone
The single biggest improvement. Current USB mic has terrible SNR.

- **ReSpeaker 2-Mic Pi HAT** (~$10) — sits on GPIO, has onboard ADC, designed for voice assistants. Built-in AEC (acoustic echo cancellation) which would eliminate the self-trigger problem
- **ReSpeaker 4-Mic Array** (~$30) — beamforming for directional pickup, better noise rejection. Also has AEC
- **Seeed Studio USB Mic Array** (~$40) — 4-mic array with onboard DSP, works via USB. Best option if you don't want to use GPIO

### Priority 2: Dedicated Speaker (Separate from Mic)
Physical separation between mic and speaker reduces acoustic feedback (self-triggering).

- **3.5mm speaker via USB DAC** — keep mic and speaker on separate USB devices
- **I2S DAC + amplifier HAT** (e.g., HiFiBerry, Adafruit I2S) — frees up USB, better audio quality, no driver issues

### Priority 3: NVMe Drive
Current SD card is fine for the medium Vosk model. NVMe would help if you want:

- **Large Vosk model** (1.8GB) — faster loading, but still 4GB RAM issue
- **Whisper.cpp models** — base/small models run on Pi 5, need fast disk for loading
- **General responsiveness** — faster pip installs, model loading, log writes

Recommended: **Pimoroni NVMe Base** or **Geekworm X1001** — both sit under the Pi 5

### Priority 4: Coral USB Accelerator (~$30)
- Offloads wake word detection to dedicated TPU
- Frees CPU for STT/TTS
- OpenWakeWord supports Coral acceleration

### Optional: USB Sound Card with Echo Cancellation
- **Jabra Speak 410/510** — all-in-one speakerphone with hardware AEC, great mic array
- Eliminates self-trigger problem entirely at the hardware level
- One USB device replaces both current mic and speaker

## Launch Commands

```bash
# Chromium kiosk (from SSH)
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  chromium --password-store=basic --no-first-run \
  --disable-session-crashed-bubble --kiosk --disk-cache-size=0 \
  http://localhost:8080/live2d_test.html 2>/dev/null &

# Main voice loop
cd /home/piichan/mira
PYTHONUNBUFFERED=1 nohup /home/piichan/mira/venv/bin/python -m src.main > /tmp/mira.log 2>&1 &

# Monitor logs
tail -f /tmp/mira.log

# Kill everything
pkill -f "src.main"; pkill chromium; fuser -k 8080/tcp 18793/tcp
```

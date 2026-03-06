# Pii-chan Product Specification

## Vision

Pii-chan is your AI copilot in the car — an OpenClaw node with a face, voice, and awareness of your vehicle. Not a novelty chatbot, but your actual assistant that happens to live in your car.

## Core Value Proposition

**"OpenClaw, but in your car, with car superpowers."**

Everything you can do with OpenClaw (calendar, messages, reminders, web search, memory) plus:
- Awareness of vehicle state (speed, battery, doors, climate)
- Ability to control vehicle systems (climate, eventually more)
- A persistent presence with personality
- Hands-free interaction while driving

---

## MVP Scope

### Must Have (Day One)

**1. OpenClaw Node**
- Connects to existing OpenClaw gateway
- Full access to all OpenClaw capabilities
- Works via WiFi hotspot or Bluetooth PAN

**2. Greeting & Presence**
- Greets you when you enter the car
- Visual presence on dedicated display
- Can be toggled visible/hidden based on mood

**3. Voice Interaction**
- Wake word activation ("Hey Pii-chan" or configurable)
- Natural conversation via Claude
- Variable voice (can tune TTS voice/style)
- Can be muted when desired

**4. Personality**
- Tunable personality via prompt/config
- Consistent character across sessions
- Remembers conversation context

**5. Car Data Awareness (Read Only)**
- Reads vehicle state via CAN bus
- Knows: engine status, speed, gear, battery, doors
- Can reference car state in conversation
- "How's my battery?" → actual answer

**6. State Memory**
- Remembers actions it has taken
- Supports "undo" / "nevermind" / "change that back"
- Doesn't forget what it just did

### Cut from MVP

- **Multi-user**: Same personality for everyone (for now)
- **CAN Write / Climate Control**: Architecture supports it, but requires sniffing first
- **Always-listening**: Start with wake word only
- **4G connectivity**: Start with hotspot, upgrade path available

---

## User Experience

### Daily Flow

1. **Get in car** → Pi auto-boots from 12V power
2. **Phone connects** → AA/CarPlay to head unit (separate)
3. **Pii-chan wakes** → Connects via phone WiFi hotspot
4. **Greeting** → "Good morning! You've got two meetings today and traffic looks light."
5. **Drive** → Pii-chan visible on dedicated screen, responds to wake word
6. **Interaction** → "Hey Pii-chan, remind me to call mom when I get home"
7. **Arrive** → "See you later!"

### Interaction Modes

| Mode | Display | Voice | Wake Word |
|------|---------|-------|-----------|
| **Active** | Visible, animated | On | Listening |
| **Quiet** | Visible, calm | Muted | Listening |
| **Hidden** | Off | Muted | Listening |
| **Sleep** | Off | Off | Off |

User can switch modes via voice: "Pii-chan, go quiet" / "Pii-chan, hide" / "Pii-chan, wake up"

### Personality Tuning

Personality defined in config file (`personality.md` or YAML):

```yaml
personality:
  name: "Pii-chan"
  style: "helpful, slightly playful, concise"
  voice: "warm, feminine"  # or masculine, neutral, robotic, etc.
  greeting_style: "casual"
  verbosity: "low"  # low, medium, high
  japanese_mode: false  # toggle for Japanese responses/voice
```

Users can adjust via conversation: "Pii-chan, be more formal" → updates config

---

## Architecture

### Hardware (MVP)

| Component | Purpose | Required |
|-----------|---------|----------|
| Raspberry Pi 5 8GB | Compute | ✓ |
| Waveshare 2-CH CAN HAT | CAN bus read | ✓ |
| HyperPixel 4.0 (or similar) | Display | ✓ |
| USB Microphone | Voice input | ✓ |
| MAX98357A + Speaker | Voice output | ✓ |
| 12V→5V 5A Converter | Power | ✓ |
| Waveshare SIM7600 4G HAT | Dedicated 4G | Optional (upgrade) |

**Estimated cost:** ~$200 (without 4G) / ~$270 (with 4G)

### Software Stack

```
┌─────────────────────────────────────────────────────────┐
│                      Pii-chan                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Voice In    │  │ Voice Out   │  │ Display         │  │
│  │ (Whisper)   │  │ (TTS)       │  │ (Face/Presence) │  │
│  └──────┬──────┘  └──────▲──────┘  └────────▲────────┘  │
│         │                │                   │          │
│         └────────────────┼───────────────────┘          │
│                          │                              │
│              ┌───────────┴───────────┐                  │
│              │   OpenClaw Node       │                  │
│              │   (Gateway Client)    │                  │
│              └───────────┬───────────┘                  │
│                          │                              │
│              ┌───────────┴───────────┐                  │
│              │   CAN Interface       │                  │
│              │   (Read vehicle state)│                  │
│              └───────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
                           │
                    WiFi / 4G
                           │
                           ▼
              ┌───────────────────────┐
              │   OpenClaw Gateway    │
              │   (Your server)       │
              │   - Claude API        │
              │   - Memory            │
              │   - All integrations  │
              └───────────────────────┘
```

### Connectivity Priority

1. WiFi (phone hotspot or known networks)
2. Bluetooth PAN (if WiFi unavailable)
3. 4G HAT (if installed and others unavailable)

### CAN Integration

**MVP (Read Only):**
- Engine state, RPM
- Vehicle speed
- Gear position
- Battery SOC
- Door status
- Fuel level

**Future (Write - requires sniffing):**
- Climate control (temp, fan, mode, zones)
- Possibly: seat heaters, lights, locks

---

## Connectivity Strategy

### MVP: Phone WiFi Hotspot

**Flow:**
1. User enables WiFi hotspot on phone
2. Pi auto-connects to known hotspot SSID
3. OpenClaw node connects to gateway

**Friction:** Manual hotspot toggle each drive

**Mitigation:**
- Test Bluetooth PAN (might auto-connect)
- iOS Shortcut: "When CarPlay connects → enable hotspot"
- Android: Bluetooth auto-hotspot if supported by device

### Future: Dedicated 4G

**When to upgrade:**
- Tired of hotspot toggle
- Want Pii-chan to work without phone
- ~$10-15/mo acceptable

**Hardware:** Waveshare SIM7600 or Sixfab 4G HAT

---

## Phase 2 (Post-MVP)

### Climate Control
- Sniff Sienna/4Runner HVAC CAN messages
- Implement climate_set commands
- "Pii-chan, set rear to feet only"
- "I'm cold" → raises temp intelligently

### Always-Listening Mode
- Continuous speech detection
- Lower latency responses
- Optional (some prefer wake word)

### Multi-User
- Recognize who's driving (voice? phone presence?)
- Different personalities/preferences per user
- Kid-friendly mode

### Visual Enhancements
- Animated face/expressions
- Mood based on context (sleepy on highway, alert in traffic)
- Weather/time awareness in display

### Smart Integrations
- "Almost home" → prep house (lights, thermostat)
- Trip summaries in memory
- Proactive alerts based on calendar + traffic

---

## Success Metrics

### MVP Success
- [ ] Boots reliably when car starts
- [ ] Connects to gateway within 30 seconds
- [ ] Voice interaction works while driving (noise handling)
- [ ] Correctly reads and reports car state
- [ ] Personality feels consistent and tunable
- [ ] Daily driver for 2 weeks without wanting to turn it off

### Phase 2 Success
- [ ] Climate control works via voice
- [ ] Family doesn't find it annoying
- [ ] Used for more than car stuff (calendar, reminders, etc.)

---

## Open Questions

1. **Wake word engine:** Porcupine? Snowboy? Something else?
2. **TTS voice:** ElevenLabs? Local (Piper)? VOICEVOX for Japanese?
3. **Display framework:** Web-based (Electron)? Native (Qt)? Simple pygame?
4. **Face design:** Anime style? Abstract? Minimal?

---

## Timeline (Rough)

| Phase | Focus | Duration |
|-------|-------|----------|
| **0** | Hardware acquisition | 1 week |
| **1** | OpenClaw node + voice I/O working | 2 weeks |
| **2** | Display + personality | 1 week |
| **3** | CAN read integration | 1 week |
| **4** | Polish + daily driver test | 2 weeks |
| **---** | **MVP Complete** | ~7 weeks |
| **5** | CAN sniffing (HVAC) | 2-4 weeks |
| **6** | Climate control | 2 weeks |

---

*Last updated: 2025-03-06*

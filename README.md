# 🐣 ピーちゃん (Pii-chan)

An AI car companion that lives in your vehicle, understands your driving, and provides natural Japanese commentary.

## Overview

Pii-chan reads CAN bus data from your car, understands the context of your driving session, and speaks naturally using a local LLM + Japanese TTS. She's not a soundboard — she thinks and responds based on what's happening.

## Features

- **Real-time CAN monitoring** — Speed, RPM, gear, doors, lights, etc.
- **Natural conversation** — LLM-generated responses, not canned audio
- **Session memory** — Remembers today's drive and past trips
- **Japanese TTS** — VOICEVOX for natural Japanese speech
- **Personality** — Kind, helpful, slightly clumsy AI spirit

## Quick Start (Desktop Prototype)

```bash
# Clone and setup
cd pii-chan
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# Download a model (Qwen 2.5 1.5B recommended)
# See docs/MODEL_SETUP.md

# Run with simulated CAN data
python src/main.py --simulate

# Run the simulator UI (mock driving)
python src/simulator.py
```

## Project Structure

```
pii-chan/
├── src/
│   ├── main.py              # Main entry point
│   ├── can_reader.py        # CAN bus interface (real + mock)
│   ├── brain.py             # LLM integration + context building
│   ├── voice.py             # VOICEVOX TTS wrapper
│   ├── display.py           # Face/UI rendering
│   ├── memory.py            # Session + history storage
│   ├── simulator.py         # Desktop driving simulator
│   └── config.py            # Configuration
├── data/
│   ├── toyota_sienna.dbc    # CAN database (message definitions)
│   ├── personality.md       # Pii-chan's personality prompt
│   └── sessions.db          # SQLite history (created at runtime)
├── assets/
│   └── faces/               # Face expression images
├── tests/
│   └── test_brain.py        # Unit tests
├── requirements.txt
└── README.md
```

## Hardware (Future)

For actual car deployment:
- Raspberry Pi 5 8GB
- Waveshare 2-CH CAN HAT
- HyperPixel 4.0 display
- MAX98357A I2S amp + speaker
- 12V→5V power supply

## Configuration

Copy `config.example.yaml` to `config.yaml` and adjust:

```yaml
llm:
  model_path: ./models/qwen2.5-1.5b-instruct-q4_k_m.gguf
  context_size: 4096

voice:
  engine: voicevox  # or 'mock' for testing
  speaker_id: 1     # VOICEVOX character

can:
  interface: mock   # or 'socketcan' for real hardware
  channel: can0
```

## License

MIT — Do what you want, but please share cool improvements!

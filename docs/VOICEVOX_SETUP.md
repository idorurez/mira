# VOICEVOX Setup

VOICEVOX is a free, open-source Japanese text-to-speech engine with cute anime-style voices. Perfect for Pii-chan!

## Installation

### macOS / Windows

1. Download from: https://voicevox.hiroshiba.jp/
2. Install and run VOICEVOX
3. It starts a local server on port 50021

### Linux (including Raspberry Pi)

```bash
# Download VOICEVOX Core
# Check https://github.com/VOICEVOX/voicevox_core for latest release

# For x86_64:
wget https://github.com/VOICEVOX/voicevox_core/releases/download/0.15.0/voicevox_core-linux-x64-cpu-0.15.0.zip

# For Raspberry Pi (ARM):
wget https://github.com/VOICEVOX/voicevox_core/releases/download/0.15.0/voicevox_core-linux-arm64-cpu-0.15.0.zip

# Unzip and run
unzip voicevox_core-*.zip
cd voicevox_core-*
./run --host 0.0.0.0 --port 50021
```

### Docker

```bash
docker run -p 50021:50021 voicevox/voicevox_engine:cpu-latest
```

## Available Voices

| ID | Character | Style |
|----|-----------|-------|
| 0 | 四国めたん | あまあま (sweet) |
| 1 | ずんだもん | あまあま (sweet) |
| 2 | 四国めたん | ノーマル |
| 3 | **ずんだもん** | **ノーマル** ← Recommended for Pii-chan |
| 8 | 春日部つむぎ | ノーマル |
| 10 | 雨晴はう | ノーマル |
| 14 | 冥鳴ひまり | ノーマル |

**Recommended for Pii-chan:** Speaker ID `3` (ずんだもん ノーマル) - cute but clear.

## Testing

```bash
# Check if VOICEVOX is running
curl http://localhost:50021/speakers

# Generate test audio
curl -X POST "http://localhost:50021/audio_query?text=ピピッ！こんにちは！&speaker=3" \
  -H "Content-Type: application/json" > query.json

curl -X POST "http://localhost:50021/synthesis?speaker=3" \
  -H "Content-Type: application/json" \
  -d @query.json > test.wav

# Play it
aplay test.wav  # Linux
afplay test.wav  # macOS
```

## Configuration

In `config.yaml`:

```yaml
voice:
  engine: voicevox
  voicevox_url: http://localhost:50021
  speaker_id: 3  # ずんだもん
  speed: 1.1     # Slightly faster
```

## Troubleshooting

### VOICEVOX not responding
- Check if the process is running
- Verify port 50021 is not blocked
- Try `curl http://localhost:50021/speakers`

### Audio not playing
- Check `sounddevice` is installed: `pip install sounddevice`
- On Linux, ensure ALSA or PulseAudio is working
- Try: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### No voice in car (Raspberry Pi)
- Connect speaker to 3.5mm jack or I2S DAC
- Test with: `speaker-test -c 2 -t wav`

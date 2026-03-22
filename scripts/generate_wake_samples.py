#!/usr/bin/env python3
"""
Generate synthetic wake word samples for "miraku" using Kokoro TTS.

Produces varied audio clips by:
- Using multiple Kokoro voices
- Varying speed (0.8x - 1.3x)
- Adding the wake word in different contexts (isolated, in phrases)

Output: WAV files at 16kHz mono, ready for openWakeWord training.

Usage:
    python scripts/generate_wake_samples.py --output ./training/positive --count 500
    python scripts/generate_wake_samples.py --output ./training/negative --negative --count 200
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# Kokoro voices — mix of English and Japanese-capable voices for variety
VOICES = [
    # English voices (will pronounce "miraku" phonetically)
    "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore",
    "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck",
    # British voices
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    # Japanese voices
    "jf_alpha", "jf_gongitsune", "jf_nezumi", "jf_tebukuro",
    "jm_kumo",
]

# Positive samples: variations of "miraku"
POSITIVE_PHRASES = [
    # Japanese pronunciation
    "ミラク",
    "ミラク、",
    # Romanized for English voices
    "miraku",
    "meeraku",
    "mee rah koo",
    # In context (short phrases containing the wake word)
    "hey miraku",
    "ミラク、聞いて",
    "ミラク、教えて",
    "ok miraku",
]

# Negative samples: similar-sounding words that should NOT trigger
NEGATIVE_PHRASES = [
    # Similar phonetics
    "miracle", "miraculous", "mirror", "mural",
    "morocco", "meraki", "maracas", "mikado",
    "karaoke", "teriyaki", "sudoku", "haiku",
    # Common speech fragments
    "hello", "hey there", "excuse me", "thank you",
    "good morning", "good night", "see you later",
    "turn left", "turn right", "slow down", "speed up",
    "what time is it", "how far", "are we there yet",
    # Japanese common words
    "ありがとう", "おはよう", "すみません",
    "そうですね", "なるほど", "大丈夫",
]

# Speed variations for diversity
SPEEDS = [0.8, 0.9, 1.0, 1.05, 1.1, 1.2, 1.3]


def generate_samples(output_dir: str, count: int, negative: bool = False):
    """Generate wake word samples using Kokoro TTS."""
    from kokoro_onnx import Kokoro

    model_path = "./models/kokoro/kokoro-v1.0.onnx"
    voices_path = "./models/kokoro/voices-v1.0.bin"

    if not Path(model_path).exists() or not Path(voices_path).exists():
        print(f"Error: Kokoro model not found at {model_path}")
        print("Download from: https://huggingface.co/hexgrad/Kokoro-82M")
        sys.exit(1)

    print("Loading Kokoro TTS...")
    kokoro = Kokoro(model_path, voices_path)

    os.makedirs(output_dir, exist_ok=True)
    phrases = NEGATIVE_PHRASES if negative else POSITIVE_PHRASES
    label = "negative" if negative else "positive"

    print(f"Generating {count} {label} samples...")
    generated = 0
    errors = 0

    while generated < count:
        # Pick random voice, phrase, and speed
        voice = VOICES[generated % len(VOICES)]
        phrase = phrases[generated % len(phrases)]
        speed = SPEEDS[generated % len(SPEEDS)]

        # Japanese voices for Japanese text, English voices for English
        is_japanese_text = any('\u3000' <= c <= '\u9fff' for c in phrase)
        is_japanese_voice = voice.startswith("j")

        # Skip mismatched language/voice combos
        if is_japanese_text and not is_japanese_voice:
            # Use romanized version for English voices
            phrase = phrases[0] if not negative else phrase
            if is_japanese_text:
                generated += 1
                continue

        try:
            samples, sr = kokoro.create(phrase, voice=voice, speed=speed)

            # Convert to 16kHz mono int16 (openWakeWord format)
            if sr != 16000:
                n_out = int(len(samples) * 16000 / sr)
                x_in = np.linspace(0, 1, len(samples), endpoint=False)
                x_out = np.linspace(0, 1, n_out, endpoint=False)
                samples = np.interp(x_out, x_in, samples)
                sr = 16000

            # Normalize
            peak = np.max(np.abs(samples))
            if peak > 0:
                samples = samples / peak * 0.9

            filename = f"{label}_{generated:05d}_{voice}_{speed:.1f}.wav"
            filepath = os.path.join(output_dir, filename)
            sf.write(filepath, samples.astype(np.float32), sr)
            generated += 1

            if generated % 50 == 0:
                print(f"  {generated}/{count} generated...")

        except Exception as e:
            errors += 1
            if errors > 20:
                print(f"Too many errors ({errors}), stopping.")
                break
            generated += 1  # Skip this combo
            continue

    print(f"Done! Generated {generated} {label} samples in {output_dir}")
    if errors:
        print(f"  ({errors} errors skipped)")


def main():
    parser = argparse.ArgumentParser(description="Generate wake word training samples")
    parser.add_argument("--output", "-o", default="./training/positive",
                        help="Output directory for WAV files")
    parser.add_argument("--count", "-n", type=int, default=500,
                        help="Number of samples to generate")
    parser.add_argument("--negative", action="store_true",
                        help="Generate negative (non-wake-word) samples instead")
    args = parser.parse_args()

    generate_samples(args.output, args.count, args.negative)


if __name__ == "__main__":
    main()

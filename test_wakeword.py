import sounddevice as sd
import numpy as np
from openwakeword.model import Model

# List devices
print("Audio devices:")
print(sd.query_devices())

# Find USB mic
devices = sd.query_devices()
usb_idx = None
for i, d in enumerate(devices):
    if 'USB' in d['name'] and d['max_input_channels'] > 0:
        usb_idx = i
        print(f"\nUsing: {d['name']}")
        break

# Load model
model = Model()
print("Wake words:", list(model.models.keys()))

RATE = 16000
CHUNK = 1280

print("\nListening... say 'hey jarvis' (Ctrl+C to stop)")

def callback(indata, frames, time, status):
    audio = (indata[:, 0] * 32767).astype(np.int16)
    prediction = model.predict(audio)
    for ww, score in prediction.items():
        if score > 0.5:
            print(f"🎤 {ww}: {score:.2f}")

with sd.InputStream(device=usb_idx, channels=1, samplerate=RATE, 
                    blocksize=CHUNK, callback=callback):
    try:
        while True:
            sd.sleep(100)
    except KeyboardInterrupt:
        print("\nStopped")

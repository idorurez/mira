"""
Voice Output - VOICEVOX TTS integration
"""
import io
import wave
import threading
from typing import Optional
from dataclasses import dataclass

try:
    import requests
    import numpy as np
    import sounddevice as sd
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

@dataclass
class VoiceConfig:
    engine: str = "mock"  # "voicevox" or "mock"
    voicevox_url: str = "http://localhost:50021"
    speaker_id: int = 1
    speed: float = 1.1
    pitch: float = 0.0
    intonation: float = 1.0
    volume: float = 1.0

class Voice:
    """
    Text-to-speech using VOICEVOX or mock output.
    
    VOICEVOX must be running locally. Download from:
    https://voicevox.hiroshiba.jp/
    
    Popular speaker IDs:
    - 0: 四国めたん (あまあま)
    - 1: ずんだもん (あまあま)  
    - 2: 四国めたん (ノーマル)
    - 3: ずんだもん (ノーマル)
    - 8: 春日部つむぎ
    - 10: 雨晴はう
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._speaking = False
        self._lock = threading.Lock()
        
    def is_available(self) -> bool:
        """Check if VOICEVOX is running."""
        if self.config.engine == "mock":
            return True
            
        if not VOICE_AVAILABLE:
            return False
            
        try:
            r = requests.get(f"{self.config.voicevox_url}/speakers", timeout=2)
            return r.status_code == 200
        except:
            return False
            
    def get_speakers(self) -> list:
        """Get list of available VOICEVOX speakers."""
        if self.config.engine == "mock" or not VOICE_AVAILABLE:
            return []
            
        try:
            r = requests.get(f"{self.config.voicevox_url}/speakers", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return []
        
    def speak(self, text: str, blocking: bool = True) -> bool:
        """
        Speak the given text.
        
        Args:
            text: Japanese text to speak
            blocking: If True, wait for speech to complete
            
        Returns:
            True if speech started/completed successfully
        """
        if self.config.engine == "mock":
            return self._mock_speak(text, blocking)
        else:
            return self._voicevox_speak(text, blocking)
            
    def _mock_speak(self, text: str, blocking: bool) -> bool:
        """Mock speech output (just prints)."""
        print(f"🔊 ピーちゃん: 「{text}」")
        return True
        
    def _voicevox_speak(self, text: str, blocking: bool) -> bool:
        """Speak using VOICEVOX."""
        if not VOICE_AVAILABLE:
            print(f"[Voice unavailable] {text}")
            return False
            
        if blocking:
            return self._voicevox_speak_sync(text)
        else:
            thread = threading.Thread(
                target=self._voicevox_speak_sync, 
                args=(text,),
                daemon=True
            )
            thread.start()
            return True
            
    def _voicevox_speak_sync(self, text: str) -> bool:
        """Synchronous VOICEVOX speech."""
        with self._lock:
            if self._speaking:
                return False
            self._speaking = True
            
        try:
            # Step 1: Get audio query
            params = {
                "text": text,
                "speaker": self.config.speaker_id
            }
            r = requests.post(
                f"{self.config.voicevox_url}/audio_query",
                params=params,
                timeout=10
            )
            if r.status_code != 200:
                return False
                
            query = r.json()
            
            # Apply config
            query["speedScale"] = self.config.speed
            query["pitchScale"] = self.config.pitch
            query["intonationScale"] = self.config.intonation
            query["volumeScale"] = self.config.volume
            
            # Step 2: Synthesize
            r = requests.post(
                f"{self.config.voicevox_url}/synthesis",
                params={"speaker": self.config.speaker_id},
                json=query,
                timeout=30
            )
            if r.status_code != 200:
                return False
                
            # Step 3: Play audio
            audio_data = r.content
            self._play_wav(audio_data)
            
            return True
            
        except Exception as e:
            print(f"VOICEVOX error: {e}")
            return False
            
        finally:
            self._speaking = False
            
    def _play_wav(self, wav_data: bytes):
        """Play WAV audio data."""
        with io.BytesIO(wav_data) as f:
            with wave.open(f, 'rb') as wav:
                sample_rate = wav.getframerate()
                n_channels = wav.getnchannels()
                n_frames = wav.getnframes()
                
                audio = wav.readframes(n_frames)
                audio_array = np.frombuffer(audio, dtype=np.int16)
                
                if n_channels == 2:
                    audio_array = audio_array.reshape(-1, 2)
                    
        sd.play(audio_array, sample_rate)
        sd.wait()
        
    def stop(self):
        """Stop current speech (if playing)."""
        try:
            sd.stop()
        except:
            pass
        self._speaking = False
        
    @property
    def is_speaking(self) -> bool:
        return self._speaking


class MockVoice(Voice):
    """Voice that just prints - for testing without VOICEVOX."""
    
    def __init__(self):
        super().__init__(VoiceConfig(engine="mock"))
        
    def speak(self, text: str, blocking: bool = True) -> bool:
        print(f"🔊 ピーちゃん: 「{text}」")
        return True

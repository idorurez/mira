#!/usr/bin/env python3
"""
ピーちゃん (Pii-chan) - Main Entry Point

Usage:
    python -m src.main              # Run with real CAN (requires hardware)
    python -m src.main --simulate   # Run with simulated CAN data
    python -m src.main --simulator  # Run interactive driving simulator
"""

import argparse
import time
import signal
import sys
from pathlib import Path

from .config import Config
from .can_reader import CANReader, CarState
from .brain import PiiBrain
from .voice import Voice, VoiceConfig
from .memory import SessionMemory

# Global for clean shutdown
running = True

def signal_handler(sig, frame):
    global running
    print("\n👋 Shutting down Pii-chan...")
    running = False

def main():
    global running
    
    parser = argparse.ArgumentParser(description="🐣 ピーちゃん - AI Car Companion")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--simulate", action="store_true", help="Use simulated CAN data")
    parser.add_argument("--simulator", action="store_true", help="Run interactive simulator")
    parser.add_argument("--no-voice", action="store_true", help="Disable voice output")
    parser.add_argument("--no-model", action="store_true", help="Use rule-based responses (no LLM)")
    args = parser.parse_args()
    
    # Load config
    config = Config.load(args.config)
    
    # Interactive simulator mode
    if args.simulator:
        from .simulator import DrivingSimulator
        sim = DrivingSimulator(config)
        sim.start()
        return
    
    print("=" * 50)
    print("🐣 ピーちゃん (Pii-chan) v0.1.0")
    print("=" * 50)
    print()
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize components
    print("Initializing components...")
    
    # CAN reader
    interface = "mock" if args.simulate else config.can.interface
    can = CANReader(
        interface=interface,
        channel=config.can.channel,
        dbc_path=config.can.dbc_path
    )
    print(f"  ✓ CAN interface: {interface}")
    
    # Voice
    if args.no_voice:
        voice = Voice(VoiceConfig(engine="mock"))
        print("  ✓ Voice: disabled (mock)")
    else:
        voice = Voice(VoiceConfig(
            engine=config.voice.engine,
            voicevox_url=config.voice.voicevox_url,
            speaker_id=config.voice.speaker_id,
            speed=config.voice.speed
        ))
        if voice.is_available():
            print(f"  ✓ Voice: {config.voice.engine}")
        else:
            print(f"  ⚠ Voice: VOICEVOX not available, using mock")
            voice = Voice(VoiceConfig(engine="mock"))
    
    # Brain
    model_path = None if args.no_model else config.llm.model_path
    if model_path and not Path(model_path).exists():
        print(f"  ⚠ Model not found: {model_path}")
        print("    Run without --no-model or download a model first")
        model_path = None
        
    brain = PiiBrain(
        model_path=model_path,
        personality_path=config.brain.personality_path,
        context_size=config.llm.context_size,
        max_tokens=config.llm.max_tokens,
        temperature=config.llm.temperature
    )
    print(f"  ✓ Brain: {'LLM' if model_path else 'rule-based'}")
    
    # Memory
    memory = SessionMemory(config.db_path)
    brain.set_memory(memory)
    print(f"  ✓ Memory: {config.db_path}")
    
    # Connect brain to CAN events
    can.add_callback(brain.on_can_event)
    
    print()
    print("Starting Pii-chan...")
    print("(Press Ctrl+C to stop)")
    print()
    
    # Start session
    brain.start_session()
    can.start()
    
    # Greeting
    greeting = "ピピッ！起動完了！よろしくね〜"
    voice.speak(greeting)
    
    # Main loop
    last_think = 0
    think_interval = config.brain.think_interval
    
    try:
        while running:
            now = time.time()
            
            # Think periodically
            if now - last_think >= think_interval:
                response = brain.think(
                    can.state,
                    cooldown=config.brain.speech_cooldown
                )
                
                if response:
                    voice.speak(response)
                    
                    # Log to memory
                    if brain.current_session:
                        memory.log_speech(
                            response,
                            brain.current_session.session_id
                        )
                        
                last_think = now
                
            time.sleep(0.1)
            
    finally:
        # Cleanup
        print("\nStopping...")
        brain.end_session()
        can.stop()
        
        # Goodbye
        voice.speak("またね〜！")
        
        print("👋 Goodbye!")


if __name__ == "__main__":
    main()

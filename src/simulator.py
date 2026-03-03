"""
Desktop Driving Simulator - Test Pii-chan without a car
"""
import time
import threading
from typing import Optional

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from .can_reader import CANReader, CarState, Gear
from .brain import PiiBrain
from .voice import Voice, VoiceConfig
from .memory import SessionMemory
from .config import Config

class DrivingSimulator:
    """
    Interactive driving simulator for testing Pii-chan.
    
    Controls:
    - SPACE: Toggle engine
    - P/R/N/D: Change gear
    - UP/DOWN: Accelerate/Brake
    - LEFT/RIGHT: Turn
    - O: Open/close door
    - ESC: Quit
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        
        # Components
        self.can = CANReader(interface="mock")
        self.brain = PiiBrain(
            model_path=self.config.llm.model_path if hasattr(self.config, 'llm') else None,
            personality_path=self.config.brain.personality_path if hasattr(self.config, 'brain') else "./data/personality.md"
        )
        self.voice = Voice(VoiceConfig(engine="mock"))
        self.memory = SessionMemory(self.config.db_path if hasattr(self.config, 'db_path') else "./data/sessions.db")
        
        # Connect brain to memory and CAN
        self.brain.set_memory(self.memory)
        self.can.add_callback(self.brain.on_can_event)
        
        # Simulation state
        self.running = False
        self.speed_target = 0.0
        
        # PyGame
        self.screen = None
        self.clock = None
        self.font = None
        
    def start(self):
        """Start the simulator."""
        if not PYGAME_AVAILABLE:
            print("pygame not installed - running in text mode")
            self._run_text_mode()
            return
            
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("🐣 ピーちゃん Simulator")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 32)
        
        # Start session
        self.brain.start_session()
        self.can.start()
        self.running = True
        
        # Start thinking thread
        think_thread = threading.Thread(target=self._think_loop, daemon=True)
        think_thread.start()
        
        try:
            self._run_pygame()
        finally:
            self.running = False
            self.brain.end_session()
            self.can.stop()
            pygame.quit()
            
    def _run_pygame(self):
        """Main PyGame loop."""
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                    
            # Update simulation
            self._update_simulation()
            
            # Draw
            self._draw()
            
            self.clock.tick(30)
            
    def _handle_key(self, key):
        """Handle keyboard input."""
        state = self.can.state
        
        if key == pygame.K_ESCAPE:
            self.running = False
            
        elif key == pygame.K_SPACE:
            # Toggle engine
            self.can.mock_set_engine(not state.engine_running)
            
        elif key == pygame.K_p:
            self.can.mock_set_gear(Gear.PARK)
            self.speed_target = 0
            
        elif key == pygame.K_r:
            self.can.mock_set_gear(Gear.REVERSE)
            
        elif key == pygame.K_n:
            self.can.mock_set_gear(Gear.NEUTRAL)
            
        elif key == pygame.K_d:
            self.can.mock_set_gear(Gear.DRIVE)
            
        elif key == pygame.K_UP:
            if state.engine_running and state.gear in (Gear.DRIVE, Gear.REVERSE):
                self.speed_target = min(self.speed_target + 10, 120)
                
        elif key == pygame.K_DOWN:
            self.speed_target = max(self.speed_target - 20, 0)
            if self.speed_target == 0:
                self.can.mock_set_brake(True, 80)
            else:
                self.can.mock_set_brake(False)
                
        elif key == pygame.K_o:
            # Toggle driver door
            self.can.mock_set_doors(fl=not state.door_fl_open)
            
        elif key == pygame.K_f:
            # Force Pii-chan to say something
            response = self.brain.force_response(state)
            self.voice.speak(response)
            
    def _update_simulation(self):
        """Update simulated car state."""
        state = self.can.state
        
        # Gradually change speed
        if state.engine_running:
            diff = self.speed_target - state.speed_kmh
            if abs(diff) > 0.5:
                new_speed = state.speed_kmh + (diff * 0.1)
                self.can.mock_set_speed(max(0, new_speed))
                
                # Update RPM based on speed
                rpm = 800 + (state.speed_kmh * 30)
                self.can.mock_set_engine(True, rpm)
        else:
            if state.speed_kmh > 0:
                self.can.mock_set_speed(state.speed_kmh * 0.95)
                
    def _think_loop(self):
        """Background thread for Pii-chan to think."""
        while self.running:
            time.sleep(3)  # Think every 3 seconds
            
            response = self.brain.think(
                self.can.state,
                cooldown=self.config.brain.speech_cooldown if hasattr(self.config, 'brain') else 30.0
            )
            
            if response:
                self.voice.speak(response)
                
    def _draw(self):
        """Draw the simulator UI."""
        state = self.can.state
        
        # Background
        self.screen.fill((30, 30, 40))
        
        # Title
        self._draw_text("🐣 ピーちゃん Driving Simulator", 20, 20, (255, 255, 255))
        
        # Car state
        y = 80
        gear_names = {Gear.PARK: "P", Gear.REVERSE: "R", Gear.NEUTRAL: "N", 
                      Gear.DRIVE: "D", Gear.BRAKE: "B"}
        
        self._draw_text(f"Engine: {'ON' if state.engine_running else 'OFF'}", 20, y, 
                       (100, 255, 100) if state.engine_running else (255, 100, 100))
        y += 30
        
        self._draw_text(f"Gear: {gear_names.get(state.gear, '?')}", 20, y, (255, 255, 255))
        y += 30
        
        self._draw_text(f"Speed: {state.speed_kmh:.0f} km/h", 20, y, (255, 255, 255))
        y += 30
        
        self._draw_text(f"RPM: {state.engine_rpm:.0f}", 20, y, (200, 200, 200))
        y += 30
        
        self._draw_text(f"Brake: {'ON' if state.brake_pressed else 'OFF'}", 20, y,
                       (255, 100, 100) if state.brake_pressed else (100, 100, 100))
        y += 30
        
        self._draw_text(f"Door: {'OPEN' if state.any_door_open else 'Closed'}", 20, y,
                       (255, 200, 100) if state.any_door_open else (100, 100, 100))
        y += 50
        
        # Controls help
        self._draw_text("Controls:", 20, y, (150, 150, 150))
        y += 25
        controls = [
            "SPACE - Engine On/Off",
            "P/R/N/D - Gear",
            "UP/DOWN - Speed",
            "O - Door",
            "F - Force Pii-chan to speak",
            "ESC - Quit"
        ]
        for ctrl in controls:
            self._draw_text(ctrl, 30, y, (120, 120, 120))
            y += 22
            
        # Last speech
        y = 450
        self._draw_text("Last speech:", 20, y, (150, 150, 150))
        y += 25
        if self.brain.last_speech_text:
            self._draw_text(f"「{self.brain.last_speech_text}」", 30, y, (100, 200, 255))
        else:
            self._draw_text("(waiting...)", 30, y, (80, 80, 80))
            
        # Recent events
        x = 400
        y = 80
        self._draw_text("Recent Events:", x, y, (150, 150, 150))
        y += 25
        for event in self.brain.recent_events[-8:]:
            self._draw_text(f"• {event.description}", x + 10, y, (180, 180, 180))
            y += 22
            
        pygame.display.flip()
        
    def _draw_text(self, text: str, x: int, y: int, color):
        """Draw text to screen."""
        # Handle Japanese text - need a font that supports it
        try:
            surface = self.font.render(text, True, color)
            self.screen.blit(surface, (x, y))
        except:
            # Fallback for characters font doesn't support
            ascii_text = text.encode('ascii', 'replace').decode('ascii')
            surface = self.font.render(ascii_text, True, color)
            self.screen.blit(surface, (x, y))
            
    def _run_text_mode(self):
        """Run in text-only mode without pygame."""
        print("=" * 50)
        print("🐣 ピーちゃん Text Mode Simulator")
        print("=" * 50)
        print("\nCommands:")
        print("  engine  - Toggle engine")
        print("  gear X  - Set gear (p/r/n/d)")
        print("  speed X - Set speed")
        print("  door    - Toggle door")
        print("  talk    - Force Pii-chan to speak")
        print("  state   - Show current state")
        print("  quit    - Exit")
        print()
        
        self.brain.start_session()
        self.can.start()
        self.running = True
        
        # Start thinking thread
        think_thread = threading.Thread(target=self._think_loop, daemon=True)
        think_thread.start()
        
        try:
            while self.running:
                try:
                    cmd = input("> ").strip().lower()
                except EOFError:
                    break
                    
                if cmd == "quit" or cmd == "q":
                    break
                elif cmd == "engine":
                    self.can.mock_set_engine(not self.can.state.engine_running)
                    print(f"Engine: {'ON' if self.can.state.engine_running else 'OFF'}")
                elif cmd.startswith("gear "):
                    g = cmd.split()[1]
                    gears = {"p": Gear.PARK, "r": Gear.REVERSE, "n": Gear.NEUTRAL, "d": Gear.DRIVE}
                    if g in gears:
                        self.can.mock_set_gear(gears[g])
                        print(f"Gear: {g.upper()}")
                elif cmd.startswith("speed "):
                    try:
                        spd = float(cmd.split()[1])
                        self.can.mock_set_speed(spd)
                        print(f"Speed: {spd} km/h")
                    except:
                        print("Invalid speed")
                elif cmd == "door":
                    self.can.mock_set_doors(fl=not self.can.state.door_fl_open)
                    print(f"Door: {'OPEN' if self.can.state.door_fl_open else 'Closed'}")
                elif cmd == "talk":
                    response = self.brain.force_response(self.can.state)
                    self.voice.speak(response)
                elif cmd == "state":
                    s = self.can.state
                    print(f"  Engine: {s.engine_running}, Gear: {s.gear.name}")
                    print(f"  Speed: {s.speed_kmh} km/h, RPM: {s.engine_rpm}")
                    print(f"  Door: {s.any_door_open}")
                elif cmd:
                    print("Unknown command. Type 'quit' to exit.")
                    
        finally:
            self.running = False
            self.brain.end_session()
            self.can.stop()


def main():
    """Run the simulator."""
    import sys
    
    config = Config.load("config.yaml")
    sim = DrivingSimulator(config)
    
    print("Starting ピーちゃん simulator...")
    print("(Make sure VOICEVOX is running if you want voice output)")
    print()
    
    sim.start()


if __name__ == "__main__":
    main()

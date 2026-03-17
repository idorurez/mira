"""
CAN Bus Reader - Handles real CAN interface and mock simulation
"""
import time
import random
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
from enum import Enum
import threading

try:
    import can
    import cantools
    CAN_AVAILABLE = True
except ImportError:
    CAN_AVAILABLE = False

class Gear(Enum):
    PARK = 0
    REVERSE = 1
    NEUTRAL = 2
    DRIVE = 3
    BRAKE = 4  # B mode for hybrids

@dataclass
class CarState:
    """Current state of the vehicle from CAN data."""
    timestamp: float = 0.0
    
    # Motion
    speed_kmh: float = 0.0
    wheel_speed_fl: float = 0.0
    wheel_speed_fr: float = 0.0
    wheel_speed_rl: float = 0.0
    wheel_speed_rr: float = 0.0
    
    # Engine/Powertrain
    engine_rpm: float = 0.0
    engine_running: bool = False
    engine_temp_c: float = 20.0
    gear: Gear = Gear.PARK
    gas_pedal: float = 0.0
    gas_released: bool = True
    
    # Braking
    brake_pressure: float = 0.0
    brake_pressed: bool = False
    
    # Steering
    steering_angle: float = 0.0
    steering_rate: float = 0.0
    
    # Hybrid specific
    battery_soc: float = 80.0
    ev_mode: int = 0  # 0=Normal, 1=EV, 2=ECO, 3=Power
    charging: bool = False
    
    # Lights/Signals
    turn_signal: int = 0  # 0=None, 1=Left, 2=Right
    high_beams: bool = False
    hazards: bool = False
    
    # Body
    door_fl_open: bool = False
    door_fr_open: bool = False
    door_rl_open: bool = False
    door_rr_open: bool = False
    seatbelt_driver: bool = True
    
    # Fuel
    fuel_level_pct: float = 75.0
    fuel_low: bool = False
    
    # Safety systems
    bsm_left: bool = False
    bsm_right: bool = False
    
    # Cruise
    cruise_active: bool = False
    cruise_set_speed: float = 0.0
    
    # Derived
    any_door_open: bool = field(init=False)
    
    def __post_init__(self):
        self.any_door_open = any([
            self.door_fl_open, self.door_fr_open,
            self.door_rl_open, self.door_rr_open
        ])
    
    def update_derived(self):
        """Update derived fields after state changes."""
        self.any_door_open = any([
            self.door_fl_open, self.door_fr_open,
            self.door_rl_open, self.door_rr_open
        ])

class CANReader:
    """
    CAN bus reader with support for real hardware and simulation.
    """
    
    def __init__(self, interface: str = "mock", channel: str = "can0", 
                 dbc_path: Optional[str] = None):
        self.interface = interface
        self.channel = channel
        self.state = CarState()
        self.callbacks: List[Callable[[CarState, str], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Load DBC if provided
        self.db = None
        if dbc_path and Path(dbc_path).exists() and interface != "mock":
            if CAN_AVAILABLE:
                self.db = cantools.database.load_file(dbc_path)
        
        # For mock mode
        self._mock_scenario: Optional[Callable] = None
        
    def add_callback(self, callback: Callable[[CarState, str], None]):
        """Add a callback for state changes. callback(state, event_name)"""
        self.callbacks.append(callback)
        
    def _notify(self, event: str):
        """Notify all callbacks of a state change."""
        self.state.update_derived()
        for cb in self.callbacks:
            try:
                cb(self.state, event)
            except Exception as e:
                print(f"Callback error: {e}")
    
    def start(self):
        """Start reading CAN data."""
        self._running = True
        if self.interface == "mock":
            self._thread = threading.Thread(target=self._mock_loop, daemon=True)
        elif self.interface == "socketcan":
            self._thread = threading.Thread(target=self._can_loop, daemon=True)
        else:
            raise ValueError(f"Unknown interface: {self.interface}")
        self._thread.start()
        
    def stop(self):
        """Stop reading CAN data."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            
    def set_mock_scenario(self, scenario: Callable[["CANReader"], None]):
        """Set a mock scenario function for testing."""
        self._mock_scenario = scenario
            
    def _can_loop(self):
        """Read from actual CAN interface."""
        if not CAN_AVAILABLE:
            raise RuntimeError("python-can not installed")
            
        bus = can.interface.Bus(channel=self.channel, bustype='socketcan')
        
        while self._running:
            msg = bus.recv(timeout=1.0)
            if msg and self.db:
                try:
                    decoded = self.db.decode_message(msg.arbitration_id, msg.data)
                    self._update_state_from_can(msg.arbitration_id, decoded)
                except Exception:
                    pass  # Unknown message
                    
        bus.shutdown()
        
    def _update_state_from_can(self, msg_id: int, data: Dict[str, Any]):
        """Update car state from decoded CAN message."""
        old_state = CarState(**self.state.__dict__)
        self.state.timestamp = time.time()
        
        # Map CAN messages to state
        if msg_id == 180:  # SPEED
            self.state.speed_kmh = data.get('SPEED', self.state.speed_kmh)
        elif msg_id == 170:  # WHEEL_SPEEDS
            self.state.wheel_speed_fl = data.get('WHEEL_SPEED_FL', self.state.wheel_speed_fl)
            self.state.wheel_speed_fr = data.get('WHEEL_SPEED_FR', self.state.wheel_speed_fr)
            self.state.wheel_speed_rl = data.get('WHEEL_SPEED_RL', self.state.wheel_speed_rl)
            self.state.wheel_speed_rr = data.get('WHEEL_SPEED_RR', self.state.wheel_speed_rr)
        elif msg_id == 295:  # GEAR_PACKET
            gear_val = data.get('GEAR', 0)
            self.state.gear = Gear(min(gear_val, 4))
        elif msg_id == 800:  # ENGINE_STATUS
            self.state.engine_rpm = data.get('ENGINE_RPM', self.state.engine_rpm)
            self.state.engine_running = data.get('ENGINE_RUNNING', False)
        elif msg_id == 513:  # GAS_PEDAL
            self.state.gas_pedal = data.get('GAS_PEDAL', self.state.gas_pedal)
            self.state.gas_released = data.get('GAS_RELEASED', True)
        elif msg_id == 166:  # BRAKE_MODULE
            self.state.brake_pressure = data.get('BRAKE_PRESSURE', self.state.brake_pressure)
            self.state.brake_pressed = data.get('BRAKE_PRESSED', False)
        elif msg_id == 37:  # STEER_ANGLE_SENSOR
            self.state.steering_angle = data.get('STEER_ANGLE', self.state.steering_angle)
            self.state.steering_rate = data.get('STEER_RATE', self.state.steering_rate)
        elif msg_id == 764:  # HYBRID_STATUS
            self.state.battery_soc = data.get('BATTERY_SOC', self.state.battery_soc)
            self.state.ev_mode = data.get('EV_MODE', self.state.ev_mode)
            self.state.charging = data.get('CHARGING', False)
        elif msg_id == 466:  # LIGHT_STALK
            self.state.turn_signal = data.get('TURN_SIGNALS', 0)
            self.state.high_beams = data.get('HIGH_BEAMS', False)
        elif msg_id == 467:  # BODY_CONTROL
            self.state.door_fl_open = data.get('DOOR_OPEN_FL', False)
            self.state.door_fr_open = data.get('DOOR_OPEN_FR', False)
            self.state.door_rl_open = data.get('DOOR_OPEN_RL', False)
            self.state.door_rr_open = data.get('DOOR_OPEN_RR', False)
            self.state.seatbelt_driver = data.get('SEATBELT_DRIVER', True)
        elif msg_id == 552:  # ENGINE_TEMP
            self.state.engine_temp_c = data.get('ENGINE_TEMP', self.state.engine_temp_c)
        elif msg_id == 1042:  # FUEL_STATUS
            self.state.fuel_level_pct = data.get('FUEL_LEVEL', self.state.fuel_level_pct)
            self.state.fuel_low = data.get('FUEL_LOW_WARNING', False)
        elif msg_id == 1014:  # BSM_STATUS
            self.state.bsm_left = data.get('BSM_LEFT', False)
            self.state.bsm_right = data.get('BSM_RIGHT', False)
            
        # Detect events
        self._detect_events(old_state)
        
    def _detect_events(self, old_state: CarState):
        """Detect state change events."""
        s = self.state
        o = old_state
        
        # Gear changes
        if s.gear != o.gear:
            self._notify(f"gear_change_{s.gear.name.lower()}")
            
        # Engine state
        if s.engine_running and not o.engine_running:
            self._notify("engine_start")
        elif not s.engine_running and o.engine_running:
            self._notify("engine_stop")
            
        # Speed events
        if s.speed_kmh > 0 and o.speed_kmh == 0:
            self._notify("start_moving")
        elif s.speed_kmh == 0 and o.speed_kmh > 0:
            self._notify("stopped")
        if s.speed_kmh > 100 and o.speed_kmh <= 100:
            self._notify("high_speed")
            
        # Door events
        if s.any_door_open and not o.any_door_open:
            self._notify("door_opened")
        elif not s.any_door_open and o.any_door_open:
            self._notify("door_closed")
            
        # Braking
        if s.brake_pressed and not o.brake_pressed:
            if s.brake_pressure > 100:
                self._notify("hard_brake")
                
        # BSM warnings
        if s.bsm_left and not o.bsm_left:
            self._notify("bsm_left")
        if s.bsm_right and not o.bsm_right:
            self._notify("bsm_right")
            
        # Fuel
        if s.fuel_low and not o.fuel_low:
            self._notify("fuel_low")
            
    def _mock_loop(self):
        """Generate mock CAN data for testing."""
        # Start with engine off, parked
        self.state = CarState(timestamp=time.time())
        
        if self._mock_scenario:
            # Run custom scenario
            self._mock_scenario(self)
        else:
            # Default: just idle
            while self._running:
                self.state.timestamp = time.time()
                time.sleep(0.1)
                
    # Mock state setters for simulation
    def mock_set_gear(self, gear: Gear):
        old = CarState(**{k: v for k, v in self.state.__dict__.items() if k != 'any_door_open'})
        self.state.gear = gear
        self.state.timestamp = time.time()
        self._detect_events(old)
        
    def mock_set_speed(self, speed_kmh: float):
        old = CarState(**{k: v for k, v in self.state.__dict__.items() if k != 'any_door_open'})
        self.state.speed_kmh = speed_kmh
        self.state.timestamp = time.time()
        self._detect_events(old)
        
    def mock_set_engine(self, running: bool, rpm: float = 800):
        old = CarState(**{k: v for k, v in self.state.__dict__.items() if k != 'any_door_open'})
        self.state.engine_running = running
        self.state.engine_rpm = rpm if running else 0
        self.state.timestamp = time.time()
        self._detect_events(old)
        
    def mock_set_brake(self, pressed: bool, pressure: float = 50):
        old = CarState(**{k: v for k, v in self.state.__dict__.items() if k != 'any_door_open'})
        self.state.brake_pressed = pressed
        self.state.brake_pressure = pressure if pressed else 0
        self.state.timestamp = time.time()
        self._detect_events(old)
        
    def mock_set_doors(self, fl=False, fr=False, rl=False, rr=False):
        old = CarState(**{k: v for k, v in self.state.__dict__.items() if k != 'any_door_open'})
        self.state.door_fl_open = fl
        self.state.door_fr_open = fr
        self.state.door_rl_open = rl
        self.state.door_rr_open = rr
        self.state.timestamp = time.time()
        self._detect_events(old)

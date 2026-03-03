"""
Session Memory - Stores driving history and events
"""
import sqlite3
import json
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid

@dataclass
class DrivingSession:
    """A single driving session."""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    total_distance_km: float = 0.0
    max_speed_kmh: float = 0.0
    notes: str = ""

@dataclass  
class SessionEvent:
    """An event within a session."""
    event_id: str
    session_id: str
    timestamp: float
    event_type: str
    data: Dict[str, Any]

class SessionMemory:
    """
    SQLite-based memory for driving sessions and events.
    """
    
    def __init__(self, db_path: str = "./data/sessions.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time REAL NOT NULL,
                end_time REAL,
                total_distance_km REAL DEFAULT 0,
                max_speed_kmh REAL DEFAULT 0,
                notes TEXT DEFAULT ''
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT DEFAULT '{}',
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Speech log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS speech_log (
                speech_id TEXT PRIMARY KEY,
                session_id TEXT,
                timestamp REAL NOT NULL,
                text TEXT NOT NULL,
                context TEXT DEFAULT ''
            )
        """)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_time ON sessions(start_time)")
        
        conn.commit()
        conn.close()
        
    def start_session(self) -> DrivingSession:
        """Start a new driving session."""
        session = DrivingSession(
            session_id=str(uuid.uuid4()),
            start_time=time.time()
        )
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (session_id, start_time) VALUES (?, ?)",
            (session.session_id, session.start_time)
        )
        conn.commit()
        conn.close()
        
        return session
        
    def end_session(self, session_id: str, 
                    total_distance_km: float = 0, 
                    max_speed_kmh: float = 0,
                    notes: str = ""):
        """End a driving session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sessions 
            SET end_time = ?, total_distance_km = ?, max_speed_kmh = ?, notes = ?
            WHERE session_id = ?
        """, (time.time(), total_distance_km, max_speed_kmh, notes, session_id))
        conn.commit()
        conn.close()
        
    def log_event(self, session_id: str, event_type: str, data: Dict[str, Any]):
        """Log an event in the current session."""
        event_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO events (event_id, session_id, timestamp, event_type, data) VALUES (?, ?, ?, ?, ?)",
            (event_id, session_id, time.time(), event_type, json.dumps(data))
        )
        conn.commit()
        conn.close()
        
    def log_speech(self, text: str, session_id: Optional[str] = None, context: str = ""):
        """Log a speech utterance."""
        speech_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO speech_log (speech_id, session_id, timestamp, text, context) VALUES (?, ?, ?, ?, ?)",
            (speech_id, session_id, time.time(), text, context)
        )
        conn.commit()
        conn.close()
        
    def get_session(self, session_id: str) -> Optional[DrivingSession]:
        """Get a session by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return DrivingSession(
                session_id=row[0],
                start_time=row[1],
                end_time=row[2],
                total_distance_km=row[3] or 0,
                max_speed_kmh=row[4] or 0,
                notes=row[5] or ""
            )
        return None
        
    def get_recent_sessions(self, limit: int = 5) -> List[DrivingSession]:
        """Get recent completed sessions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE end_time IS NOT NULL 
            ORDER BY start_time DESC 
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            DrivingSession(
                session_id=row[0],
                start_time=row[1],
                end_time=row[2],
                total_distance_km=row[3] or 0,
                max_speed_kmh=row[4] or 0,
                notes=row[5] or ""
            )
            for row in rows
        ]
        
    def get_session_events(self, session_id: str) -> List[SessionEvent]:
        """Get all events for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [
            SessionEvent(
                event_id=row[0],
                session_id=row[1],
                timestamp=row[2],
                event_type=row[3],
                data=json.loads(row[4]) if row[4] else {}
            )
            for row in rows
        ]
        
    def get_last_session(self) -> Optional[DrivingSession]:
        """Get the most recent completed session."""
        sessions = self.get_recent_sessions(1)
        return sessions[0] if sessions else None
        
    def get_time_since_last_drive(self) -> Optional[float]:
        """Get seconds since last drive ended."""
        last = self.get_last_session()
        if last and last.end_time:
            return time.time() - last.end_time
        return None
        
    def get_stats(self) -> Dict[str, Any]:
        """Get overall driving statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total sessions
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE end_time IS NOT NULL")
        total_sessions = cursor.fetchone()[0]
        
        # Total distance
        cursor.execute("SELECT SUM(total_distance_km) FROM sessions")
        total_distance = cursor.fetchone()[0] or 0
        
        # Total time
        cursor.execute("""
            SELECT SUM(end_time - start_time) FROM sessions 
            WHERE end_time IS NOT NULL
        """)
        total_time_seconds = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_sessions": total_sessions,
            "total_distance_km": total_distance,
            "total_time_hours": total_time_seconds / 3600,
        }

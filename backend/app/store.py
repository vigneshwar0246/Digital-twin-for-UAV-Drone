import json, sqlite3
from pathlib import Path
from threading import RLock
from .schemas import Telemetry, TwinAssessment
from .states import EngineState

class TelemetryStore:
    SCHEMA_VERSION = 3

    def __init__(self, path: Path):
        self.path = path; self._lock = RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > self.SCHEMA_VERSION:
                raise RuntimeError(f"database schema version {version} is newer than supported version {self.SCHEMA_VERSION}")
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS telemetry (id INTEGER PRIMARY KEY, engine_id TEXT NOT NULL, mission_id TEXT NOT NULL, timestamp TEXT NOT NULL, telemetry_json TEXT NOT NULL, assessment_json TEXT NOT NULL)")
            columns={row[1] for row in db.execute("PRAGMA table_info(telemetry)")}
            if "state_json" not in columns:
                db.execute("ALTER TABLE telemetry ADD COLUMN state_json TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS ix_telemetry_engine_time ON telemetry(engine_id, timestamp DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_telemetry_mission_time ON telemetry(mission_id, timestamp)")
            db.execute("CREATE TABLE IF NOT EXISTS simulation_missions (mission_id TEXT PRIMARY KEY, engine_id TEXT NOT NULL, start_time TEXT NOT NULL, seed INTEGER NOT NULL, configuration_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS simulation_snapshots (mission_id TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, FOREIGN KEY(mission_id) REFERENCES simulation_missions(mission_id))")
            db.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")

    def _connect(self):
        db=sqlite3.connect(self.path, timeout=10); db.row_factory=sqlite3.Row; return db

    def ready(self) -> bool:
        with self._connect() as db:
            return db.execute("SELECT 1").fetchone()[0] == 1

    def add(self, telemetry: Telemetry, assessment: TwinAssessment, state: EngineState | None = None):
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO telemetry(engine_id,mission_id,timestamp,telemetry_json,assessment_json,state_json) VALUES(?,?,?,?,?,?)",
                (telemetry.engine_id, telemetry.mission_id, telemetry.timestamp.isoformat(), telemetry.model_dump_json(), assessment.model_dump_json(), state.model_dump_json() if state else None))

    def history(self, engine_id: str, limit: int):
        if not 1 <= limit <= 10000:
            raise ValueError("history limit must be between 1 and 10000")
        with self._connect() as db:
            rows=db.execute("SELECT telemetry_json,assessment_json,state_json FROM telemetry WHERE engine_id=? ORDER BY timestamp DESC,id DESC LIMIT ?",(engine_id,limit)).fetchall()
        return [{"telemetry":json.loads(r["telemetry_json"]),"assessment":json.loads(r["assessment_json"]),
                 **({"state":json.loads(r["state_json"])} if r["state_json"] else {})} for r in reversed(rows)]

    def latest(self, engine_id: str):
        rows=self.history(engine_id,1); return rows[0] if rows else None

    def clear_engine(self,engine_id:str):
        """Clear only an ephemeral demo engine stream before a new run."""
        with self._lock, self._connect() as db:
            db.execute("DELETE FROM telemetry WHERE engine_id=?",(engine_id,))

    def simulation_snapshot(self,mission_id:str):
        with self._connect() as db:
            row=db.execute("SELECT snapshot_json FROM simulation_snapshots WHERE mission_id=?",(mission_id,)).fetchone()
        return json.loads(row["snapshot_json"]) if row else None

    def check_simulation_identity(self,mission_id:str,configuration:dict):
        existing=self.simulation_config(mission_id)
        if existing is not None and existing!=configuration:
            raise ValueError("mission ID already belongs to a different simulation configuration")

    def save_simulation(self,mission_id:str,engine_id:str,start_time:str,seed:int,configuration:dict,snapshot:dict|None=None):
        with self._lock,self._connect() as db:
            existing=db.execute("SELECT configuration_json FROM simulation_missions WHERE mission_id=?",(mission_id,)).fetchone()
            if existing is not None and json.loads(existing["configuration_json"])!=configuration:
                raise ValueError("mission ID already belongs to a different simulation configuration")
            db.execute("INSERT OR IGNORE INTO simulation_missions(mission_id,engine_id,start_time,seed,configuration_json) VALUES(?,?,?,?,?)",
                (mission_id,engine_id,start_time,seed,json.dumps(configuration)))
            if snapshot is not None:
                db.execute("INSERT OR IGNORE INTO simulation_snapshots(mission_id,snapshot_json) VALUES(?,?)",
                    (mission_id,json.dumps(snapshot)))

    def simulation_config(self,mission_id:str):
        with self._connect() as db:
            row=db.execute("SELECT configuration_json FROM simulation_missions WHERE mission_id=?",(mission_id,)).fetchone()
        return json.loads(row["configuration_json"]) if row else None

    def simulations(self,limit:int=100):
        if not 1 <= limit <= 500: raise ValueError("simulation list limit must be between 1 and 500")
        with self._connect() as db:
            rows=db.execute("SELECT mission_id,engine_id,start_time,seed,configuration_json FROM simulation_missions ORDER BY start_time DESC,mission_id DESC LIMIT ?",(limit,)).fetchall()
        return [{"mission_id":row["mission_id"],"engine_id":row["engine_id"],"start_time":row["start_time"],"seed":row["seed"],
            "profile":json.loads(row["configuration_json"]).get("profile"),"source":"simulated_mission"} for row in rows]

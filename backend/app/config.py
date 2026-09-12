from dataclasses import dataclass, field
from pathlib import Path
import os
from .adapters.base import AdapterMode

BACKEND_DIR = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    title: str = "MALE UAV Aero-Engine Digital Twin"
    version: str = "1.0.0"
    database_path: Path = Path(os.getenv("DIGITAL_TWIN_DB", BACKEND_DIR / "runtime" / "digital_twin.db"))
    replay_data_path: Path = Path(os.getenv("DIGITAL_TWIN_DATA", BACKEND_DIR / "dataset" / "data" / "aero_engine_full.csv"))
    metrics_path: Path = BACKEND_DIR / "model_evaluation" / "outputs" / "reports" / "metrics_summary.json"
    max_history_rows: int = int(os.getenv("DIGITAL_TWIN_HISTORY_LIMIT", "1000"))
    adapter_mode: AdapterMode = AdapterMode(os.getenv("DIGITAL_TWIN_ADAPTER", "SIMULATOR").upper())
    can_mapping_path: Path = Path(os.getenv("DIGITAL_TWIN_CAN_MAPPING", BACKEND_DIR / "app" / "adapters" / "sample_synthetic_can.json"))
    socketcan_channel: str = os.getenv("DIGITAL_TWIN_SOCKETCAN_CHANNEL", "can0")
    environment: str = field(default_factory=lambda: os.getenv("DIGITAL_TWIN_ENV", "development").lower())
    token_lifetime_minutes: int = field(default_factory=lambda: int(os.getenv("DIGITAL_TWIN_TOKEN_MINUTES", "30")))
    requests_per_minute: int = field(default_factory=lambda: int(os.getenv("DIGITAL_TWIN_RATE_LIMIT", "120")))
    token_secret: str | None = field(default_factory=lambda: os.getenv("DIGITAL_TWIN_TOKEN_SECRET"))
    demo_mode: bool = field(default_factory=lambda: os.getenv("DIGITAL_TWIN_DEMO_MODE", "false").lower() in {"1","true","yes"})
    demo_mission_id: str = field(default_factory=lambda: os.getenv("DIGITAL_TWIN_DEMO_MISSION", "MISSION_0110"))

    def __post_init__(self):
        if self.environment not in {"development","production"}: raise ValueError("DIGITAL_TWIN_ENV must be development or production")
        if self.environment=="production" and (not self.token_secret or len(self.token_secret)<32): raise ValueError("production requires DIGITAL_TWIN_TOKEN_SECRET with at least 32 characters")
        if self.token_lifetime_minutes < 1: raise ValueError("DIGITAL_TWIN_TOKEN_MINUTES must be positive")
        if self.requests_per_minute < 1: raise ValueError("DIGITAL_TWIN_RATE_LIMIT must be positive")

settings = Settings()

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine_id: str = Field(min_length=1, max_length=64)
    mission_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mission_phase: str = Field(default="unknown", max_length=64)
    rpm: float = Field(ge=0, le=3200)
    cylinder_head_temp_1_c: float = Field(ge=-45, le=270)
    cylinder_head_temp_2_c: float = Field(ge=-45, le=270)
    cylinder_head_temp_3_c: float = Field(ge=-45, le=270)
    cylinder_head_temp_4_c: float = Field(ge=-45, le=270)
    exhaust_gas_temp_1_c: float = Field(ge=-45, le=950)
    exhaust_gas_temp_2_c: float = Field(ge=-45, le=950)
    exhaust_gas_temp_3_c: float = Field(ge=-45, le=950)
    exhaust_gas_temp_4_c: float = Field(ge=-45, le=950)
    oil_temperature_c: float = Field(ge=-45, le=155)
    oil_pressure_kpa: float = Field(ge=0, le=700)
    fuel_flow_lph: float = Field(ge=0, le=75)
    vibration_rms: float = Field(ge=0, le=25)
    alternator_voltage: float = Field(ge=0, le=32)
    alternator_state: Literal["ONLINE", "OFFLINE", "DEGRADED", "UNKNOWN"] | None = None
    battery_voltage: float = Field(ge=18, le=30)
    battery_current_a: float | None = Field(default=None, ge=-300, le=300)
    injection_timing_deg: float = Field(ge=5, le=35)
    engine_load_percent: float = Field(ge=0, le=110)
    throttle_percent: float = Field(ge=0, le=100)
    altitude_m: float = Field(ge=0, le=8000)
    ambient_temperature_c: float = Field(ge=-45, le=50)
    ambient_pressure_kpa: float | None = Field(default=None, ge=35, le=105)
    humidity_percent: float | None = Field(default=None, ge=0, le=100)

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

class Alert(BaseModel):
    code: str
    severity: Literal["advisory", "warning", "critical"]
    message: str
    evidence: dict[str, float | str]

class TwinAssessment(BaseModel):
    engine_id: str
    mission_id: str
    timestamp: datetime
    health_index: float
    rul_hours: float
    anomaly_score: float
    predicted_fault: str
    confidence: float
    maintenance_advisory: str
    alerts: list[Alert]
    method: str = "explainable physics-informed prototype rules"
    ml_inference: dict = Field(default_factory=lambda: {"status": "disabled"})

class MissionProfile(str, Enum):
    HIGH_ALTITUDE="HIGH_ALTITUDE"; ENDURANCE="ENDURANCE"; HOT_WEATHER="HOT_WEATHER"
    RAPID_THROTTLE="RAPID_THROTTLE"; NORMAL_CRUISE="NORMAL_CRUISE"

class DegradationScenario(str, Enum):
    NONE="NONE"; COOLING_DEGRADATION="COOLING_DEGRADATION"; INJECTOR_DEGRADATION="INJECTOR_DEGRADATION"
    LUBRICATION_DEGRADATION="LUBRICATION_DEGRADATION"; SENSOR_DRIFT="SENSOR_DRIFT"
    COMBUSTION_INSTABILITY="COMBUSTION_INSTABILITY"; VIBRATION_ANOMALY="VIBRATION_ANOMALY"

class SimulationRequest(BaseModel):
    profile: MissionProfile
    duration_minutes: int = Field(default=30, ge=1, le=240)
    interval_seconds: int = Field(default=5, ge=1, le=60)
    engine_id: str = Field(default="SIM_ENGINE_001", min_length=1, max_length=64)
    mission_id: str | None = Field(default=None,min_length=1,max_length=64)
    start_time: datetime | None = None
    degradation_scenario: DegradationScenario = DegradationScenario.NONE
    degradation_severity: float = Field(default=.65,ge=0,le=1)
    seed: int = 26054

    @field_validator("profile","degradation_scenario",mode="before")
    @classmethod
    def normalize_enum(cls,value): return value.upper() if isinstance(value,str) else value

    @field_validator("start_time")
    @classmethod
    def simulation_start_timezone(cls,value):
        if value is not None and value.tzinfo is None: raise ValueError("start_time must include a timezone")
        return value

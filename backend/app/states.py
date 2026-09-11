from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class QualityFlag(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    STALE = "STALE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    SENSOR_FAULT = "SENSOR_FAULT"
    SUSPECT = "SUSPECT"

class ParameterState(BaseModel):
    value: float | str | bool | None
    unit: str
    quality: QualityFlag
    reason: str | None = None

class TelemetryState(BaseModel):
    observed_at: datetime
    parameters: dict[str, ParameterState]
    accepted_parameters: list[str] = Field(default_factory=list)
    rejected_parameters: list[str] = Field(default_factory=list)

class EnvironmentState(BaseModel):
    altitude_m: float | None = None
    ambient_temperature_c: float | None = None
    density_ratio: float | None = None
    air_density_proxy: float | None = None
    ambient_pressure_kpa: float | None = None
    humidity_percent: float | None = None

class PhysicsState(BaseModel):
    cht_mean_c: float | None = None
    egt_mean_c: float | None = None
    cht_spread_c: float | None = None
    egt_spread_c: float | None = None
    estimated_fuel_flow_lph: float | None = None
    thermal_load_index: float | None = None
    lubrication_health_indicator: float | None = None
    combustion_health_indicator: float | None = None
    vibration_health_indicator: float | None = None
    electrical_health_indicator: float | None = None
    overall_engine_health_index: float | None = None
    model_version: str | None = None
    assumption_classification: str | None = None

class EnginePerformanceState(BaseModel):
    rpm: float | None = None
    load_percent: float | None = None
    throttle_percent: float | None = None
    fuel_flow_lph: float | None = None
    fuel_flow_residual_lph: float | None = None
    injection_timing_residual_deg: float | None = None
    engine_efficiency_percent: float | None = None

class SubsystemHealth(BaseModel):
    health_score: float
    confidence: float
    evidence_signals: dict[str, float | int | str]
    reason: str
    severity: str
    uncertainty: str

class HealthState(BaseModel):
    overall_index: float
    subsystem_indices: dict[str, float]
    subsystem_assessments: dict[str, SubsystemHealth] = Field(default_factory=dict)
    fusion_version: str | None = None
    method: str = "prototype engineering health calculation"

class DegradationState(BaseModel):
    cumulative_damage_index: float
    health_slope_per_hour: float | None = None
    samples_observed: int = 0
    trend: str = "insufficient_data"

class FaultHypothesis(BaseModel):
    fault: str
    score: float
    evidence: dict[str, float | str]

class FaultDiagnostic(BaseModel):
    fault_code: str
    fault_name: str
    severity: str
    probability: float | None = None
    engineering_score: float
    score_kind: str
    health_impact: float
    evidence: dict
    affected_subsystems: list[str]
    recommended_action: str
    first_detected: datetime
    last_detected: datetime
    diagnostic_version: str
    uncertainty: str

class FaultState(BaseModel):
    anomaly_score: float
    primary_fault: str
    hypotheses: list[FaultHypothesis] = Field(default_factory=list)
    diagnostics: list[FaultDiagnostic] = Field(default_factory=list)
    supported_diagnostic_categories: list[str] = Field(default_factory=list)

class PredictionState(BaseModel):
    rul_hours: float
    lower_bound_hours: float
    upper_bound_hours: float
    maintenance_advisory: str
    method: str = "engineering proxy; not a validated RUL model"
    data_sufficiency: str = "prototype_only"

class MissionState(BaseModel):
    mission_id: str
    phase: str
    sample_count: int
    first_observed_at: datetime
    last_observed_at: datetime

class EngineState(BaseModel):
    engine_id: str
    synchronized_at: datetime
    synchronized: bool
    telemetry: TelemetryState
    environment: EnvironmentState
    physics: PhysicsState
    performance: EnginePerformanceState
    health: HealthState
    degradation: DegradationState
    faults: FaultState
    mission: MissionState
    prediction: PredictionState
    alerts: list[dict]
    threshold_config_version: str
    threshold_classification: str = "engineering hypothesis / prototype threshold"
    manufacturer_approved: bool = False

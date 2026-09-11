"""Central configuration for the educational engine simulation.

All limits and coefficients below are configurable engineering assumptions. They
are not official specifications from DRDO or any engine manufacturer.
"""
from dataclasses import dataclass
from pathlib import Path

SEED = 26054
PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
REPORTS_DIR = PACKAGE_DIR / "reports"
GRAPHS_DIR = PACKAGE_DIR / "graphs"

FAULT_CLASSES = (
    "Healthy", "Spark_Plug_Misfire", "Fuel_Injector_Degradation",
    "Lubrication_System_Degradation", "Cooling_System_Degradation",
    "Bearing_Wear", "Combustion_Instability", "Sensor_Drift",
    "Alternator_Degradation",
)
SEVERITIES = ("None", "Low", "Medium", "High")
PHASES = (
    "engine_start", "warm_up", "takeoff", "climb", "cruise",
    "endurance_cruise", "rapid_throttle_transition", "descent", "landing", "shutdown",
)

REQUIRED_COLUMNS = (
    "timestamp", "mission_id", "engine_id", "time_seconds", "mission_phase",
    "operating_hours", "cycle_count", "altitude_m", "ambient_temperature_c",
    "ambient_pressure_kpa", "humidity_percent", "airspeed_kmh", "throttle_percent",
    "engine_load_percent", "rpm", "manifold_pressure_kpa", "fuel_flow_lph",
    "air_fuel_ratio", "cylinder_head_temp_1_c", "cylinder_head_temp_2_c",
    "cylinder_head_temp_3_c", "cylinder_head_temp_4_c", "exhaust_gas_temp_1_c",
    "exhaust_gas_temp_2_c", "exhaust_gas_temp_3_c", "exhaust_gas_temp_4_c",
    "oil_temperature_c", "oil_pressure_kpa", "vibration_rms", "alternator_voltage",
    "battery_voltage", "injection_timing_deg", "engine_efficiency_percent",
    "fault_type", "fault_severity", "anomaly_label", "health_index", "rul_hours",
    "mission_reliability_percent", "mission_outcome",
)

# Inclusive physical plausibility bounds used by generation and validation.
BOUNDS = {
    "altitude_m": (0, 8000), "ambient_temperature_c": (-45, 50),
    "ambient_pressure_kpa": (35, 105), "humidity_percent": (5, 100),
    "airspeed_kmh": (0, 260), "throttle_percent": (0, 100),
    "engine_load_percent": (0, 110), "rpm": (0, 3200),
    "manifold_pressure_kpa": (20, 180), "fuel_flow_lph": (0, 75),
    "air_fuel_ratio": (9, 18), "cylinder_head_temp_1_c": (-45, 270),
    "cylinder_head_temp_2_c": (-45, 270), "cylinder_head_temp_3_c": (-45, 270),
    "cylinder_head_temp_4_c": (-45, 270), "exhaust_gas_temp_1_c": (-45, 950),
    "exhaust_gas_temp_2_c": (-45, 950), "exhaust_gas_temp_3_c": (-45, 950),
    "exhaust_gas_temp_4_c": (-45, 950), "oil_temperature_c": (-45, 155),
    "oil_pressure_kpa": (0, 700), "vibration_rms": (0, 25),
    "alternator_voltage": (0, 32), "battery_voltage": (18, 30),
    "injection_timing_deg": (5, 35), "engine_efficiency_percent": (0, 100),
    "health_index": (0, 100), "rul_hours": (0, 2500),
    "mission_reliability_percent": (0, 100),
}

@dataclass(frozen=True)
class DatasetConfig:
    rows: int = 100_000
    missions: int = 120
    sampling_interval_seconds: float = 5.0
    engines: int = 12
    seed: int = SEED
    min_fault_samples: int = 500

DEFAULT_CONFIG = DatasetConfig()

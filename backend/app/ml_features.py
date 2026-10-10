"""Versioned feature contract shared by offline training and live inference."""

SCHEMA_VERSION = "live-telemetry-v1"
NUMERIC_FEATURES = [
    "altitude_m", "ambient_temperature_c", "throttle_percent", "engine_load_percent",
    "rpm", "fuel_flow_lph", *[f"cylinder_head_temp_{i}_c" for i in range(1, 5)],
    *[f"exhaust_gas_temp_{i}_c" for i in range(1, 5)], "oil_temperature_c",
    "oil_pressure_kpa", "vibration_rms", "alternator_voltage", "battery_voltage",
    "injection_timing_deg",
]
FEATURES = ["mission_phase", *NUMERIC_FEATURES]

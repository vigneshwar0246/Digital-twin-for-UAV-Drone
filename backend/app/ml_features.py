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

# Causal features for the separate synthetic-scenario research model. They
# are calculated from current and earlier samples of the same mission.
SCENARIO_CURRENT_FEATURES = [
    "cht_spread_c", "egt_spread_c", "cht_mean_c", "egt_mean_c",
    "cht_upper_pair_spread_c", "cht_lower_pair_spread_c",
]
SCENARIO_TEMPORAL_FEATURES = [
    f"{name}_{suffix}"
    for name in ("rpm", "vibration_rms", "cht_mean_c", "egt_mean_c")
    for suffix in ("delta", "rolling_std_7", "rolling_std_21")
] + ["cht_spread_c_rolling_mean_21", "egt_spread_c_rolling_mean_21", "cht_rise_rate_c_per_s"]
SCENARIO_FEATURES = FEATURES + SCENARIO_CURRENT_FEATURES + SCENARIO_TEMPORAL_FEATURES

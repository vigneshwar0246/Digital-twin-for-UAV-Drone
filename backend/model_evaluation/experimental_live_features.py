"""Research-only causal feature state for the controlled live experiment."""
from collections import deque
from math import isfinite
import numpy as np

from backend.app.ml_features import FEATURES, NUMERIC_FEATURES


class TelemetryState:
    def __init__(self, max_age_seconds=30):
        self.max_age_seconds = max_age_seconds
        self.reset()

    def reset(self):
        self.mission_id = None
        self.last_time = None
        self.history = {x: deque(maxlen=21) for x in
                        ("rpm", "vibration_rms", "cht_mean_c", "egt_mean_c", "cht_spread_c", "egt_spread_c",
                         "cht_load_residual_c", "oil_temperature_c")}
        self.previous = {}

    def push(self, mission_id, time_seconds, telemetry, now_seconds=None):
        if not mission_id or not isfinite(float(time_seconds)):
            raise ValueError("mission identifier and finite timestamp required")
        if now_seconds is not None and (not isfinite(float(now_seconds)) or
                                        now_seconds - time_seconds > self.max_age_seconds or
                                        time_seconds > now_seconds):
            raise ValueError("stale or future telemetry")
        if self.mission_id != mission_id:
            if time_seconds != 0:
                raise ValueError("mid-mission history unavailable")
            self.reset()
            self.mission_id = mission_id
        if self.last_time is not None and time_seconds <= self.last_time:
            raise ValueError("duplicate or out-of-order telemetry")
        if telemetry.get("mission_phase") is None:
            raise ValueError("mission phase unavailable")
        data = {"mission_phase": telemetry["mission_phase"]}
        for key in NUMERIC_FEATURES:
            value = telemetry.get(key)
            if value is None or not isfinite(float(value)):
                raise ValueError(f"missing or invalid telemetry: {key}")
            data[key] = float(value)
        cht = sorted(data[f"cylinder_head_temp_{i}_c"] for i in range(1, 5))
        egt = [data[f"exhaust_gas_temp_{i}_c"] for i in range(1, 5)]
        data.update(cht_spread_c=cht[-1] - cht[0], egt_spread_c=max(egt) - min(egt),
                    cht_mean_c=float(np.mean(cht)), egt_mean_c=float(np.mean(egt)),
                    cht_upper_pair_spread_c=cht[3] - cht[1],
                    cht_lower_pair_spread_c=cht[2] - cht[0])
        data["cht_load_residual_c"] = (data["cht_mean_c"] - data["ambient_temperature_c"]
            - 1.25 * data["engine_load_percent"] - .0014 * data["altitude_m"])
        data["cht_egt_gap_c"] = data["cht_mean_c"] - data["egt_mean_c"]
        data["cht_peak_over_median_c"] = cht[3] - float(np.median(cht))
        for col in ("rpm", "vibration_rms", "cht_mean_c", "egt_mean_c"):
            data[f"{col}_delta"] = data[col] - self.previous[col] if col in self.previous else 0.
            self.history[col].append(data[col])
            for window in (7, 21):
                values = list(self.history[col])[-window:]
                data[f"{col}_rolling_std_{window}"] = float(np.std(values, ddof=1)) if len(values) >= 2 else 0.
        for col in ("cht_spread_c", "egt_spread_c"):
            self.history[col].append(data[col])
            data[f"{col}_rolling_mean_21"] = float(np.mean(self.history[col]))
        dt = time_seconds - self.last_time if self.last_time is not None else 1.
        data["cht_rise_rate_c_per_s"] = data["cht_mean_c_delta"] / dt
        for col in ("cht_load_residual_c", "oil_temperature_c"):
            data[f"{col}_delta"] = data[col] - self.previous[col] if col in self.previous else 0.
            self.history[col].append(data[col])
            data[f"{col}_rolling_mean_21"] = float(np.mean(self.history[col]))
        self.previous = {x: data[x] for x in self.history}
        self.last_time = time_seconds
        return data

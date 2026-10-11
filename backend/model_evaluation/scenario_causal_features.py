"""Version-two causal features for synthetic sensor-freeze recognition."""
from collections import deque
import numpy as np

from backend.app.ml_features import SCENARIO_FEATURES
from .controlled_live_experiments import matrix as base_matrix
from .experimental_live_features import TelemetryState

EXTRA_FEATURES = [
    "cht1_delta_c", "cht1_rolling_std_7", "cht1_peer_std_ratio_7",
]
FEATURES_V2 = SCENARIO_FEATURES + EXTRA_FEATURES
COMBUSTION_FEATURES = [
    "egt_even_odd_gap_c", "egt_even_odd_gap_rolling_std_7",
    "egt_even_odd_gap_abs_mean_7",
]
FEATURES_V3 = FEATURES_V2 + COMBUSTION_FEATURES


def matrix(frame, features=FEATURES_V2):
    """Current/past cylinder-one variation relative to the peer cylinders."""
    if features != FEATURES_V2:
        raise ValueError("synthetic scenario feature contract differs")
    result = base_matrix(frame, SCENARIO_FEATURES)
    peers = [f"cylinder_head_temp_{i}_c" for i in (2, 3, 4)]
    result["cht_peer_mean_c"] = result[peers].mean(axis=1)
    group = result.groupby("mission_id", sort=False)
    result["cht1_delta_c"] = group["cylinder_head_temp_1_c"].diff().fillna(0)
    result["cht1_rolling_std_7"] = (group["cylinder_head_temp_1_c"].rolling(7, min_periods=2)
                                     .std().reset_index(level=0, drop=True).fillna(0))
    peer_std = (group["cht_peer_mean_c"].rolling(7, min_periods=2)
                .std().reset_index(level=0, drop=True).fillna(0))
    result["cht1_peer_std_ratio_7"] = result["cht1_rolling_std_7"] / (peer_std + .1)
    return result


class ScenarioTelemetryState(TelemetryState):
    """Online counterpart; all windows reset at each mission boundary."""

    def reset(self):
        super().reset()
        self.cht1_history = deque(maxlen=7)
        self.peer_history = deque(maxlen=7)

    def push(self, mission_id, time_seconds, telemetry, now_seconds=None):
        data = super().push(mission_id, time_seconds, telemetry, now_seconds)
        current = data["cylinder_head_temp_1_c"]
        peer = float(np.mean([data[f"cylinder_head_temp_{i}_c"] for i in (2, 3, 4)]))
        data["cht1_delta_c"] = current - self.cht1_history[-1] if self.cht1_history else 0.
        self.cht1_history.append(current)
        self.peer_history.append(peer)
        cht_std = float(np.std(self.cht1_history, ddof=1)) if len(self.cht1_history) >= 2 else 0.
        peer_std = float(np.std(self.peer_history, ddof=1)) if len(self.peer_history) >= 2 else 0.
        data["cht1_rolling_std_7"] = cht_std
        data["cht1_peer_std_ratio_7"] = cht_std / (peer_std + .1)
        return data


def matrix_with_combustion(frame, features=FEATURES_V3):
    """Add a causal paired-cylinder EGT oscillation signature."""
    if features != FEATURES_V3:
        raise ValueError("synthetic scenario feature contract differs")
    result = matrix(frame, FEATURES_V2)
    result["egt_even_odd_gap_c"] = (
        result["exhaust_gas_temp_1_c"] + result["exhaust_gas_temp_3_c"]
        - result["exhaust_gas_temp_2_c"] - result["exhaust_gas_temp_4_c"]
    ) / 2
    group = result.groupby("mission_id", sort=False)
    result["egt_even_odd_gap_rolling_std_7"] = (
        group["egt_even_odd_gap_c"].rolling(7, min_periods=2)
        .std().reset_index(level=0, drop=True).fillna(0)
    )
    result["egt_even_odd_gap_abs_mean_7"] = (
        result["egt_even_odd_gap_c"].abs().groupby(result["mission_id"], sort=False)
        .rolling(7, min_periods=1).mean().reset_index(level=0, drop=True)
    )
    return result


class CombustionTelemetryState(ScenarioTelemetryState):
    def reset(self):
        super().reset()
        self.egt_gap_history = deque(maxlen=7)

    def push(self, mission_id, time_seconds, telemetry, now_seconds=None):
        data = super().push(mission_id, time_seconds, telemetry, now_seconds)
        gap = (data["exhaust_gas_temp_1_c"] + data["exhaust_gas_temp_3_c"]
               - data["exhaust_gas_temp_2_c"] - data["exhaust_gas_temp_4_c"]) / 2
        self.egt_gap_history.append(gap)
        data["egt_even_odd_gap_c"] = gap
        data["egt_even_odd_gap_rolling_std_7"] = (
            float(np.std(self.egt_gap_history, ddof=1)) if len(self.egt_gap_history) >= 2 else 0.
        )
        data["egt_even_odd_gap_abs_mean_7"] = float(np.mean(np.abs(self.egt_gap_history)))
        return data

"""Offline/streaming parity and fail-closed behavior for research features."""
import numpy as np
import pytest

from backend.model_evaluation.controlled_live_experiments import (COOLING_CURRENT,
    COOLING_TEMPORAL, CURRENT, FEATURES, TEMPORAL, load, matrix)
from backend.model_evaluation.experimental_live_features import TelemetryState


def sample():
    splits = load()
    frame = splits.fit.sort_values(["mission_id", "time_seconds"])
    missions = frame.mission_id.drop_duplicates().iloc[:2]
    return frame[frame.mission_id.isin(missions)]


def test_offline_streaming_feature_parity():
    raw = sample()
    features = FEATURES + CURRENT + TEMPORAL + COOLING_CURRENT + COOLING_TEMPORAL
    offline = matrix(raw, features)
    state = TelemetryState()
    for index, row in raw.iterrows():
        online = state.push(row.mission_id, row.time_seconds, row.to_dict())
        for feature in features:
            if feature == "mission_phase":
                assert online[feature] == offline.loc[index, feature]
            else:
                assert np.isclose(online[feature], offline.loc[index, feature], rtol=1e-8, atol=1e-8)


def test_bad_telemetry_and_mission_reset():
    row = sample().iloc[0].to_dict()
    with pytest.raises(ValueError, match="missing"):
        TelemetryState().push("mission", 0, {k: v for k, v in row.items() if k != "rpm"})
    with pytest.raises(ValueError, match="invalid"):
        TelemetryState().push("mission", 0, {**row, "rpm": float("nan")})
    with pytest.raises(ValueError, match="stale"):
        TelemetryState().push("mission", 0, row, now_seconds=31)
    with pytest.raises(ValueError, match="mid-mission"):
        TelemetryState().push("mission", 10, row)
    state = TelemetryState()
    state.push("mission", 0, row)
    with pytest.raises(ValueError, match="out-of-order"):
        state.push("mission", 0, row)
    state.push("next", 0, row)
    assert state.mission_id == "next"
    assert len(state.history["rpm"]) == 1

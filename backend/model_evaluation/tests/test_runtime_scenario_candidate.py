"""Synthetic scenario labels and online feature parity, independent of fitting."""
import numpy as np
import pytest

from backend.app.schemas import DegradationScenario, MissionProfile
from backend.model_evaluation.experimental_live_features import TelemetryState
from backend.model_evaluation.runtime_scenario_candidate import (
    FEATURE_COLUMNS, mission_frame, matrix, run,
)
from backend.model_evaluation.scenario_causal_features import (
    FEATURES_V2, FEATURES_V3, CombustionTelemetryState, ScenarioTelemetryState,
    matrix as scenario_matrix, matrix_with_combustion,
)


def test_scenario_truth_and_online_features_match_offline():
    raw = mission_frame(991, MissionProfile.FULL_MISSION, DegradationScenario.MISFIRE)
    assert set(raw.fault_type) == {"NONE", "MISFIRE"}
    assert raw.loc[raw.time_seconds < 120, "fault_type"].eq("NONE").all()
    offline = matrix(raw, FEATURE_COLUMNS)
    streaming = TelemetryState()
    for index, row in raw.iterrows():
        online = streaming.push(row.mission_id, row.time_seconds, row.to_dict())
        for feature in FEATURE_COLUMNS:
            if feature == "mission_phase":
                assert online[feature] == offline.loc[index, feature]
            else:
                assert np.isclose(online[feature], offline.loc[index, feature], rtol=1e-8, atol=1e-8)


def test_training_refuses_to_replace_an_existing_output(tmp_path):
    with pytest.raises(FileExistsError, match="output already exists"):
        run(tmp_path)


def test_severity_variants_have_distinct_mission_histories():
    low = mission_frame(992, MissionProfile.NORMAL_CRUISE, DegradationScenario.COOLING_DEGRADATION, .2)
    high = mission_frame(992, MissionProfile.NORMAL_CRUISE, DegradationScenario.COOLING_DEGRADATION, .8)
    assert low.mission_id.iloc[0] != high.mission_id.iloc[0]
    assert low.severity_level.eq(.2).all()
    assert high.severity_level.eq(.8).all()


def test_sensor_history_features_match_streaming_inference():
    raw = mission_frame(993, MissionProfile.FULL_MISSION, DegradationScenario.SENSOR_FREEZE, .2)
    offline = scenario_matrix(raw)
    streaming = ScenarioTelemetryState()
    for index, row in raw.iterrows():
        online = streaming.push(row.mission_id, row.time_seconds, row.to_dict())
        for feature in FEATURES_V2:
            if feature == "mission_phase":
                assert online[feature] == offline.loc[index, feature]
            else:
                assert np.isclose(online[feature], offline.loc[index, feature], rtol=1e-8, atol=1e-8)


def test_combustion_features_match_streaming_inference():
    raw = mission_frame(994, MissionProfile.RAPID_THROTTLE, DegradationScenario.COMBUSTION_INSTABILITY, .2)
    offline = matrix_with_combustion(raw)
    streaming = CombustionTelemetryState()
    for index, row in raw.iterrows():
        online = streaming.push(row.mission_id, row.time_seconds, row.to_dict())
        for feature in FEATURES_V3:
            if feature == "mission_phase":
                assert online[feature] == offline.loc[index, feature]
            else:
                assert np.isclose(online[feature], offline.loc[index, feature], rtol=1e-8, atol=1e-8)

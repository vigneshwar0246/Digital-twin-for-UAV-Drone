import pandas as pd
from backend.model_evaluation.evaluation_protocol import build_evaluation_splits

def fixture_frame():
    rows=[]; faults=["Healthy","Fault_A","Fault_B"]
    for engine in range(9):
        for mission in range(5):
            for t in range(3):
                rows.append({"engine_id":f"E{engine}","mission_id":f"E{engine}M{mission}","timestamp":f"2026-01-{mission+1:02d}T00:00:0{t}Z","time_seconds":t,
                    "mission_phase":"cruise" if mission%2 else "climb","altitude_m":1000+engine*10,"ambient_temperature_c":20,"throttle_percent":50,"fault_type":faults[(engine+mission)%3]})
    return pd.DataFrame(rows)

def test_engine_and_mission_leakage_are_absent():
    s=build_evaluation_splits(fixture_frame())
    # Default three-engine held-outs leave three training engines in this fixture.
    assert all(s.manifest["engine_disjoint"].values())
    assert s.manifest["mission_disjoint"]
    assert set(s.fit.engine_id).isdisjoint(s.validation.engine_id)
    assert set(s.fit.engine_id).isdisjoint(s.challenge.engine_id)
    assert set(s.validation.engine_id).isdisjoint(s.challenge.engine_id)

def test_time_forward_uses_later_missions_without_mission_overlap():
    s=build_evaluation_splits(fixture_frame())
    assert set(s.fit.mission_id).isdisjoint(s.time_forward.mission_id)
    for engine in set(s.fit.engine_id):
        assert s.fit[s.fit.engine_id==engine].timestamp.max()<s.time_forward[s.time_forward.engine_id==engine].timestamp.min()

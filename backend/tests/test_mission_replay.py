from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.tests.api_auth import authenticate

MISSION={"profile":"NORMAL_CRUISE","duration_minutes":1,"interval_seconds":5,"engine_id":"REPLAY_ENGINE",
    "mission_id":"DETERMINISTIC_REPLAY","start_time":"2026-09-11T12:00:00Z","degradation_scenario":"COOLING_DEGRADATION",
    "degradation_severity":0.8,"seed":991}

def create_stored_mission(client):
    response=client.post("/api/v1/simulations",json=MISSION)
    assert response.status_code==200

def test_replay_pause_resume_speed_advance_and_seek():
    with TestClient(app) as client:
        authenticate(client)
        create_stored_mission(client)
        created=client.post("/api/v1/replays",json={"mission_id":"DETERMINISTIC_REPLAY","engine_id":"REPLAY_ENGINE","speed":2}).json()
        replay_id=created["replay_id"]
        assert created["position"]==0 and created["total_samples"]==12
        paused=client.post(f"/api/v1/replays/{replay_id}/pause").json(); assert paused["paused"]
        blocked=client.post(f"/api/v1/replays/{replay_id}/advance",json={"virtual_seconds":5}).json()
        assert blocked["processed"]==0 and blocked["status"]["position"]==0
        client.post(f"/api/v1/replays/{replay_id}/resume")
        advanced=client.post(f"/api/v1/replays/{replay_id}/advance",json={"virtual_seconds":5}).json()
        assert advanced["processed"]==2
        frame=advanced["frames"][0]
        assert {"telemetry","assessment","state"}<=set(frame)
        assert {"health","faults","degradation","prediction","environment"}<=set(frame["state"])
        sought=client.post(f"/api/v1/replays/{replay_id}/seek",json={"time_seconds":10}).json()
        assert sought["position"]==2 and datetime.fromisoformat(sought["current_time"].replace("Z","+00:00"))==datetime(2026,9,11,12,0,5,tzinfo=timezone.utc)

def test_time_range_filters_replay_deterministically():
    with TestClient(app) as client:
        authenticate(client)
        create_stored_mission(client)
        request={"mission_id":"DETERMINISTIC_REPLAY","start_time":"2026-09-11T12:00:10Z","end_time":"2026-09-11T12:00:30Z","speed":1}
        first=client.post("/api/v1/replays",json=request).json(); second=client.post("/api/v1/replays",json=request).json()
        assert first["total_samples"]==second["total_samples"]==5
        assert first["start_time"]==second["start_time"] and first["end_time"]==second["end_time"]
        assert datetime.fromisoformat(first["start_time"].replace("Z","+00:00"))==datetime(2026,9,11,12,0,10,tzinfo=timezone.utc)
        assert datetime.fromisoformat(first["end_time"].replace("Z","+00:00"))==datetime(2026,9,11,12,0,30,tzinfo=timezone.utc)

def test_post_flight_report_contains_required_analysis_and_is_repeatable():
    with TestClient(app) as client:
        authenticate(client)
        create_stored_mission(client)
        one=client.get("/api/v1/missions/DETERMINISTIC_REPLAY/report").json()
        two=client.get("/api/v1/missions/DETERMINISTIC_REPLAY/report").json()
        required={"mission_summary","maximum_cht_c","maximum_egt_c","minimum_oil_pressure_kpa","maximum_vibration_rms",
            "fuel_usage_liters","time_spent_abnormal_seconds","fault_events","health_trend","degradation_trend",
            "maintenance_recommendations","environment_conditions","rul_proxy","deterministic_replay"}
        assert required<=set(one)
        assert one==two
        assert one["mission_summary"]["mission_id"]=="DETERMINISTIC_REPLAY"
        assert one["fuel_usage_liters"]>0 and one["maximum_cht_c"]>0
        assert one["rul_proxy"]["method"]=="engineering proxy; not a validated RUL model"
        assert one["deterministic_replay"] is True

def test_replay_report_endpoint_completes_partially_processed_session():
    with TestClient(app) as client:
        authenticate(client)
        create_stored_mission(client)
        replay_id=client.post("/api/v1/replays",json={"mission_id":"DETERMINISTIC_REPLAY","speed":1}).json()["replay_id"]
        client.post(f"/api/v1/replays/{replay_id}/advance",json={"virtual_seconds":5})
        report=client.get(f"/api/v1/replays/{replay_id}/report")
        assert report.status_code==200 and report.json()["mission_summary"]["samples"]==12
        assert client.get(f"/api/v1/replays/{replay_id}").json()["completed"] is True

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.tests.api_auth import authenticate

SAMPLE={"engine_id":"ENGINE_TEST","mission_id":"MISSION_TEST","timestamp":"2026-09-11T10:00:00Z","mission_phase":"cruise","rpm":2200,"cylinder_head_temp_1_c":160,"cylinder_head_temp_2_c":162,"cylinder_head_temp_3_c":164,"cylinder_head_temp_4_c":163,"exhaust_gas_temp_1_c":600,"exhaust_gas_temp_2_c":602,"exhaust_gas_temp_3_c":604,"exhaust_gas_temp_4_c":603,"oil_temperature_c":95,"oil_pressure_kpa":380,"fuel_flow_lph":27,"vibration_rms":2.5,"alternator_voltage":28.1,"battery_voltage":25.1,"injection_timing_deg":22,"engine_load_percent":65,"throttle_percent":67,"altitude_m":5200,"ambient_temperature_c":-10}

def test_health_ingest_and_history():
    with TestClient(app) as c:
        assert c.get("/api/v1/health").json()["status"]=="ok"
        authenticate(c)
        response=c.post("/api/v1/telemetry",json=SAMPLE)
        assert response.status_code==201 and response.json()["predicted_fault"]=="Healthy"
        assert c.get("/api/v1/engines/ENGINE_TEST/latest").status_code==200

def test_invalid_sensor_rejected():
    bad={**SAMPLE,"rpm":9000}
    with TestClient(app) as c:
        authenticate(c)
        assert c.post("/api/v1/telemetry",json=bad).status_code==422
        missing={k:v for k,v in SAMPLE.items() if k!="rpm"}
        assert c.post("/api/v1/telemetry",json=missing).status_code==422

def test_fault_alert_and_simulation():
    bad={**SAMPLE,"oil_pressure_kpa":70}
    with TestClient(app) as c:
        authenticate(c)
        result=c.post("/api/v1/telemetry",json=bad).json()
        assert result["predicted_fault"]=="Lubrication_System_Degradation"
        state=c.get("/api/v1/engines/ENGINE_TEST/state")
        assert state.status_code==200
        assert state.json()["threshold_classification"]=="engineering hypothesis / prototype threshold"
        history=c.get("/api/v1/engines/ENGINE_TEST/history").json()
        assert "state" in history[-1]
        sim=c.post("/api/v1/simulations",json={"profile":"endurance","duration_minutes":1,"interval_seconds":10})
        assert sim.status_code==200 and sim.json()["sample_count"]==6

def test_model_report_never_hides_failed_release_status():
    with TestClient(app) as c:
        authenticate(c)
        report=c.get("/api/v1/model/report")
        assert report.status_code==200
        body=report.json()
        assert body["MODEL_STATUS"]=="NOT_VALIDATED"
        assert body["RELEASE_READINESS"]=="NOT_RELEASE_READY"
        assert body["release_gate_passed"] is False
        assert body["release_gate"]["split_integrity_passed"] is True

def test_adapter_health_is_exposed_without_requiring_hardware():
    with TestClient(app) as c:
        authenticate(c)
        response=c.get("/api/v1/adapters/health")
        assert response.status_code==200
        body=response.json()
        assert body["mode"]=="SIMULATOR" and body["connected"] is True
        assert {"last_message","messages_received","messages_dropped","sequence_errors","stale_messages"}<=set(body)

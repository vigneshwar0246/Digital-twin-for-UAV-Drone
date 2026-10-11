from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas import DegradationScenario, MissionProfile, SimulationRequest
from backend.app.simulation import build_mission
from backend.tests.api_auth import authenticate

START=datetime(2026,9,11,12,0,tzinfo=timezone.utc)
def request(profile=MissionProfile.NORMAL_CRUISE,scenario=DegradationScenario.NONE,seed=123):
    return SimulationRequest(profile=profile,degradation_scenario=scenario,degradation_severity=.8,duration_minutes=1,
        interval_seconds=5,engine_id="SIM_TEST_ENGINE",mission_id=f"SIM_{profile.value}_{scenario.value}",start_time=START,seed=seed)

@pytest.mark.parametrize("profile",list(MissionProfile))
def test_every_mission_profile_has_complete_metadata_and_signals(profile):
    mission=build_mission(request(profile=profile))
    assert mission.mission_id and mission.engine_id and mission.start_time==START and mission.duration_seconds==60
    assert len(mission.altitude_profile)==len(mission.ambient_temperature_profile)==len(mission.throttle_profile)==len(mission.rpm_profile)==12
    assert mission.environment_parameters["humidity_available"] is True
    sample=mission.telemetry[-1]
    assert sample.rpm>=0 and sample.fuel_flow_lph>=0 and sample.vibration_rms>=0
    assert sample.ambient_pressure_kpa is not None and sample.humidity_percent is not None
    assert sample.alternator_state in {"ONLINE","OFFLINE"} and sample.injection_timing_deg is not None

@pytest.mark.parametrize("scenario",[x for x in DegradationScenario if x!=DegradationScenario.NONE])
def test_every_degradation_scenario_is_reproducible(scenario):
    first=build_mission(request(scenario=scenario,seed=77))
    second=build_mission(request(scenario=scenario,seed=77))
    assert first.model_dump(mode="json")==second.model_dump(mode="json")
    assert first.degradation_scenario==scenario and first.seed==77

def test_degradation_scenarios_change_relevant_terminal_signals():
    healthy=build_mission(request()).telemetry[-1]
    cooling=build_mission(request(scenario=DegradationScenario.COOLING_DEGRADATION)).telemetry[-1]
    injector=build_mission(request(scenario=DegradationScenario.INJECTOR_DEGRADATION)).telemetry[-1]
    lubrication=build_mission(request(scenario=DegradationScenario.LUBRICATION_DEGRADATION)).telemetry[-1]
    drift=build_mission(request(scenario=DegradationScenario.SENSOR_DRIFT)).telemetry[-1]
    vibration=build_mission(request(scenario=DegradationScenario.VIBRATION_ANOMALY)).telemetry[-1]
    misfire=build_mission(request(scenario=DegradationScenario.MISFIRE)).telemetry[-1]
    alternator=build_mission(request(scenario=DegradationScenario.ALTERNATOR_DEGRADATION)).telemetry[-1]
    frozen=build_mission(request(scenario=DegradationScenario.SENSOR_FREEZE)).telemetry
    assert cooling.cylinder_head_temp_2_c>healthy.cylinder_head_temp_2_c
    assert injector.fuel_flow_lph<healthy.fuel_flow_lph
    assert lubrication.oil_pressure_kpa<healthy.oil_pressure_kpa
    assert drift.cylinder_head_temp_1_c>healthy.cylinder_head_temp_1_c
    assert vibration.vibration_rms>healthy.vibration_rms
    assert misfire.exhaust_gas_temp_1_c<healthy.exhaust_gas_temp_1_c
    assert alternator.alternator_voltage<healthy.alternator_voltage
    assert frozen[-1].cylinder_head_temp_1_c==frozen[-2].cylinder_head_temp_1_c

def test_simulation_uses_shared_ingestion_and_stores_replay_configuration():
    payload=request(scenario=DegradationScenario.COOLING_DEGRADATION).model_dump(mode="json")
    with TestClient(app) as client:
        authenticate(client)
        response=client.post("/api/v1/simulations?persist=true",json=payload)
        assert response.status_code==200
        body=response.json(); assert body["sample_count"]==12 and body["persisted_telemetry"] is True
        state=client.get("/api/v1/engines/SIM_TEST_ENGINE/state").json()
        assert state["mission"]["sample_count"]==12
        stored=client.get(f"/api/v1/simulations/{body['mission_id']}/configuration")
        assert stored.status_code==200 and stored.json()["seed"]==123
        replay=client.post(f"/api/v1/simulations/{body['mission_id']}/replay")
        assert replay.status_code==200
        replay_body=replay.json()
        assert replay_body["telemetry"]==body["telemetry"]
        assert replay_body["seed"]==body["seed"] and replay_body["start_time"]==body["start_time"]

def test_legacy_lowercase_profile_input_remains_supported():
    assert SimulationRequest(profile="endurance").profile==MissionProfile.ENDURANCE

def test_full_mission_has_phase_progression_and_explicit_synthetic_truth():
    mission=build_mission(request(profile=MissionProfile.FULL_MISSION,scenario=DegradationScenario.COOLING_DEGRADATION))
    phases=[item.mission_phase for item in mission.telemetry]
    assert phases==[item.phase for item in mission.scenario_truth]
    assert phases[0]=="ENGINE_START" and phases[-1]=="SHUTDOWN"
    assert {"WARM_UP","GROUND","TAKEOFF","CLIMB","CRUISE","DESCENT","LANDING"}<=set(phases)
    assert mission.generator_version=="mission-simulator-v2"
    assert mission.fault_onset_seconds==next(x.time_seconds for x in mission.scenario_truth if x.fault_active)
    assert all(not x.fault_active for x in mission.scenario_truth if x.time_seconds<mission.fault_onset_seconds)
    assert mission.scenario_truth[-1].progression==.8
    assert mission.telemetry[-1].throttle_percent==0
    assert mission.telemetry[-1].fuel_flow_lph==0
    assert build_mission(request(profile=MissionProfile.FULL_MISSION,scenario=DegradationScenario.COOLING_DEGRADATION)).model_dump(mode="json")==mission.model_dump(mode="json")

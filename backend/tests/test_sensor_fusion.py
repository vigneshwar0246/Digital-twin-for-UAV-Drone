from datetime import datetime, timedelta, timezone
from backend.app.core import DigitalTwinCore
from backend.app.schemas import Telemetry

BASE={"engine_id":"FUSION_ENGINE","mission_id":"FUSION_MISSION","timestamp":datetime(2026,9,11,10,0,tzinfo=timezone.utc),"mission_phase":"cruise","rpm":2200,"cylinder_head_temp_1_c":160,"cylinder_head_temp_2_c":162,"cylinder_head_temp_3_c":164,"cylinder_head_temp_4_c":163,"exhaust_gas_temp_1_c":600,"exhaust_gas_temp_2_c":602,"exhaust_gas_temp_3_c":604,"exhaust_gas_temp_4_c":603,"oil_temperature_c":95,"oil_pressure_kpa":380,"fuel_flow_lph":27,"vibration_rms":2.5,"alternator_voltage":28.1,"battery_voltage":25.1,"injection_timing_deg":22,"engine_load_percent":65,"throttle_percent":67,"altitude_m":5200,"ambient_temperature_c":-10}

def sample(**changes): return Telemetry(**{**BASE,**changes})

def assessments(state): return state.health.subsystem_assessments

def test_all_required_subsystems_return_uncertainty_and_evidence():
    _,state=DigitalTwinCore().synchronize(sample())
    expected={"THERMAL_HEALTH","LUBRICATION_HEALTH","COMBUSTION_HEALTH","FUEL_SYSTEM_HEALTH","VIBRATION_HEALTH","ELECTRICAL_HEALTH","SENSOR_HEALTH"}
    assert set(assessments(state))==expected
    for item in assessments(state).values():
        assert 0<=item.health_score<=100 and 0<=item.confidence<=1
        assert item.reason and item.severity in {"NORMAL","ADVISORY","WARNING","CRITICAL"}
        assert item.uncertainty in {"low","medium","high"}
        assert isinstance(item.evidence_signals,dict)

def test_correlated_overheating_signals_reduce_thermal_health():
    normal=assessments(DigitalTwinCore().synchronize(sample())[1])["THERMAL_HEALTH"]
    hot=assessments(DigitalTwinCore().synchronize(sample(ambient_temperature_c=45,rpm=2800,engine_load_percent=100,
        cylinder_head_temp_1_c=250,cylinder_head_temp_2_c=252,cylinder_head_temp_3_c=251,cylinder_head_temp_4_c=253,
        exhaust_gas_temp_1_c=850,exhaust_gas_temp_2_c=852,exhaust_gas_temp_3_c=851,exhaust_gas_temp_4_c=853))[1])["THERMAL_HEALTH"]
    assert hot.health_score<normal.health_score
    assert {"cht_context_residual_c","egt_context_residual_c","rpm","load_proxy_percent"}<=set(hot.evidence_signals)

def test_lubrication_fuses_pressure_temperature_rpm_and_load():
    core=DigitalTwinCore(); normal=assessments(core.synchronize(sample())[1])["LUBRICATION_HEALTH"]
    degraded=assessments(DigitalTwinCore().synchronize(sample(oil_pressure_kpa=90,oil_temperature_c=145,rpm=2700,engine_load_percent=95))[1])["LUBRICATION_HEALTH"]
    assert degraded.health_score<normal.health_score
    assert "pressure_residual_kpa" in degraded.evidence_signals

def test_fuel_system_uses_correlated_residual_timing_and_egt_inputs():
    normal=assessments(DigitalTwinCore().synchronize(sample())[1])["FUEL_SYSTEM_HEALTH"]
    degraded=assessments(DigitalTwinCore().synchronize(sample(fuel_flow_lph=5,injection_timing_deg=34,
        exhaust_gas_temp_1_c=500,exhaust_gas_temp_2_c=700,exhaust_gas_temp_3_c=705,exhaust_gas_temp_4_c=710))[1])["FUEL_SYSTEM_HEALTH"]
    assert degraded.health_score<normal.health_score
    assert degraded.confidence==1

def test_vibration_uses_window_statistics_and_confidence_grows_with_history():
    core=DigitalTwinCore(); first=assessments(core.synchronize(sample())[1])["VIBRATION_HEALTH"]
    last=first
    for i,value in enumerate((2.6,2.4,6.5,7.0,7.5),start=1):
        _,state=core.synchronize(sample(timestamp=BASE["timestamp"]+timedelta(seconds=5*i),vibration_rms=value))
        last=assessments(state)["VIBRATION_HEALTH"]
    assert last.confidence>first.confidence
    assert last.health_score<first.health_score
    assert last.evidence_signals["window_samples"]==6
    assert "rolling_std_rms" in last.evidence_signals

def test_sensor_health_uses_temporal_stuck_and_cross_sensor_evidence():
    core=DigitalTwinCore(); state=None
    for i in range(6):
        _,state=core.synchronize(sample(timestamp=BASE["timestamp"]+timedelta(seconds=5*i)))
    sensor=assessments(state)["SENSOR_HEALTH"]
    assert sensor.evidence_signals["temporally_stuck_signals"]>0
    assert sensor.confidence>0.8
    _,peer_state=DigitalTwinCore().synchronize(sample(cylinder_head_temp_1_c=260))
    peer=assessments(peer_state)["SENSOR_HEALTH"]
    assert peer.evidence_signals["invalid_or_missing_signals"]>0
    assert peer.health_score<100

def test_optional_battery_current_improves_electrical_confidence():
    without=assessments(DigitalTwinCore().synchronize(sample())[1])["ELECTRICAL_HEALTH"]
    with_current=assessments(DigitalTwinCore().synchronize(sample(battery_current_a=12,alternator_state="ONLINE"))[1])["ELECTRICAL_HEALTH"]
    assert with_current.confidence>without.confidence

def test_explicit_offline_alternator_state_reduces_electrical_health():
    online=assessments(DigitalTwinCore().synchronize(sample(alternator_state="ONLINE"))[1])["ELECTRICAL_HEALTH"]
    offline=assessments(DigitalTwinCore().synchronize(sample(alternator_state="OFFLINE"))[1])["ELECTRICAL_HEALTH"]
    assert offline.health_score<online.health_score
    assert offline.evidence_signals["alternator_state"]=="OFFLINE"

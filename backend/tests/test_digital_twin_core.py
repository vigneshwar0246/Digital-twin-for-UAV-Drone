from datetime import datetime, timedelta, timezone
from backend.app.core import DigitalTwinCore
from backend.app.schemas import Telemetry
from backend.app.states import QualityFlag
from backend.app.thresholds import CLASSIFICATION, ThresholdConfig

BASE={"engine_id":"CORE_ENGINE","mission_id":"CORE_MISSION","timestamp":datetime(2026,9,11,10,0,tzinfo=timezone.utc),"mission_phase":"cruise","rpm":2200,"cylinder_head_temp_1_c":160,"cylinder_head_temp_2_c":162,"cylinder_head_temp_3_c":164,"cylinder_head_temp_4_c":163,"exhaust_gas_temp_1_c":600,"exhaust_gas_temp_2_c":602,"exhaust_gas_temp_3_c":604,"exhaust_gas_temp_4_c":603,"oil_temperature_c":95,"oil_pressure_kpa":380,"fuel_flow_lph":27,"vibration_rms":2.5,"alternator_voltage":28.1,"battery_voltage":25.1,"injection_timing_deg":22,"engine_load_percent":65,"throttle_percent":67,"altitude_m":5200,"ambient_temperature_c":-10}

def sample(**changes):
    return Telemetry(**{**BASE,**changes})

def test_state_has_all_layers_units_and_prototype_threshold_notice():
    _,state=DigitalTwinCore().synchronize(sample())
    assert state.synchronized
    assert state.telemetry.parameters["oil_pressure_kpa"].unit=="kPa"
    assert state.telemetry.parameters["rpm"].quality==QualityFlag.VALID
    assert state.environment.density_ratio is not None
    assert state.physics.cht_mean_c==162.25
    assert state.performance.rpm==2200
    assert state.health.overall_index>90
    assert state.degradation.samples_observed==1
    assert state.faults.primary_fault=="Healthy"
    assert state.mission.sample_count==1
    assert "not a validated RUL" in state.prediction.method
    assert state.threshold_classification==CLASSIFICATION
    assert state.manufacturer_approved is False

def test_state_transition_updates_mission_degradation_and_prediction():
    core=DigitalTwinCore(); first=sample(); core.synchronize(first)
    _,state=core.synchronize(sample(timestamp=first.timestamp+timedelta(seconds=5),oil_pressure_kpa=70))
    assert state.mission.sample_count==2
    assert state.degradation.samples_observed==2
    assert state.degradation.cumulative_damage_index>0
    assert state.faults.primary_fault=="Lubrication_System_Degradation"
    assert state.prediction.rul_hours<1800
    assert state.alerts

def test_stale_telemetry_is_flagged_and_does_not_replace_latest_state():
    core=DigitalTwinCore(); current=sample(); core.synchronize(current)
    _,stale=core.synchronize(sample(timestamp=current.timestamp-timedelta(seconds=1),oil_pressure_kpa=1))
    assert not stale.synchronized
    assert stale.telemetry.parameters["oil_pressure_kpa"].quality==QualityFlag.STALE
    assert stale.telemetry.rejected_parameters
    assert core.latest_state("CORE_ENGINE").synchronized_at==current.timestamp

def test_missing_out_of_range_and_sensor_fault_are_rejected_by_quality_layer():
    core=DigitalTwinCore(); observed=BASE["timestamp"]
    missing=core.inspect_quality({k:v for k,v in BASE.items() if k!="rpm"},observed)
    assert missing.parameters["rpm"].quality==QualityFlag.MISSING
    out=core.inspect_quality({**BASE,"rpm":9000},observed)
    assert out.parameters["rpm"].quality==QualityFlag.OUT_OF_RANGE
    fault=core.inspect_quality({**BASE,"rpm":float("nan")},observed)
    assert fault.parameters["rpm"].quality==QualityFlag.SENSOR_FAULT
    assert "rpm" not in fault.accepted_parameters

def test_large_peer_disagreement_is_suspect_and_excluded_from_mean():
    core=DigitalTwinCore()
    _,state=core.synchronize(sample(cylinder_head_temp_1_c=260))
    assert state.telemetry.parameters["cylinder_head_temp_1_c"].quality==QualityFlag.SUSPECT
    assert "cylinder_head_temp_1_c" in state.telemetry.rejected_parameters
    assert state.physics.cht_mean_c==163

def test_new_mission_resets_mission_counter():
    core=DigitalTwinCore(); first=sample(); core.synchronize(first)
    _,state=core.synchronize(sample(timestamp=first.timestamp+timedelta(seconds=5),mission_id="NEXT_MISSION"))
    assert state.mission.sample_count==1
    assert state.mission.mission_id=="NEXT_MISSION"

def test_every_threshold_is_explicitly_prototype_classified():
    thresholds=ThresholdConfig()
    assert thresholds.manufacturer_approved is False
    assert all(item.classification==CLASSIFICATION for item in thresholds._items.values())

from datetime import datetime, timedelta, timezone
from backend.app.core import DigitalTwinCore
from backend.app.diagnostics import HybridDiagnosticEngine, SUPPORTED_DIAGNOSTICS
from backend.app.physics import PhysicsInput, PrototypePhysicsModel
from backend.app.schemas import Telemetry
from backend.app.sensor_fusion import FusionInput, SensorFusionEngine
from backend.app.states import ParameterState, QualityFlag

BASE={"engine_id":"DIAG_ENGINE","mission_id":"DIAG_MISSION","timestamp":datetime(2026,9,11,10,0,tzinfo=timezone.utc),"mission_phase":"cruise","rpm":2200,"cylinder_head_temp_1_c":160,"cylinder_head_temp_2_c":162,"cylinder_head_temp_3_c":164,"cylinder_head_temp_4_c":163,"exhaust_gas_temp_1_c":600,"exhaust_gas_temp_2_c":602,"exhaust_gas_temp_3_c":604,"exhaust_gas_temp_4_c":603,"oil_temperature_c":95,"oil_pressure_kpa":380,"fuel_flow_lph":27,"vibration_rms":2.5,"alternator_voltage":28.1,"battery_voltage":25.1,"injection_timing_deg":22,"engine_load_percent":65,"throttle_percent":67,"altitude_m":5200,"ambient_temperature_c":-10}
def sample(**changes): return Telemetry(**{**BASE,**changes})

def test_all_eleven_categories_are_explicitly_registered_in_state():
    _,state=DigitalTwinCore().synchronize(sample())
    assert len(SUPPORTED_DIAGNOSTICS)==11
    assert set(state.faults.supported_diagnostic_categories)==set(SUPPORTED_DIAGNOSTICS)

def test_diagnostic_contract_uses_engineering_score_not_probability():
    _,state=DigitalTwinCore().synchronize(sample(oil_pressure_kpa=70,oil_temperature_c=145))
    item=next(x for x in state.faults.diagnostics if x.fault_code=="LUBRICATION_ISSUE")
    assert item.fault_name=="Lubrication Issue"
    assert item.probability is None
    assert item.score_kind=="uncalibrated engineering score"
    assert 0<=item.engineering_score<=1 and item.health_impact>0
    assert item.evidence and item.affected_subsystems and item.recommended_action
    assert item.first_detected==item.last_detected==BASE["timestamp"]
    assert "offline classifier has no deployable artifact" in item.evidence["ml_status"]

def test_fault_lifecycle_preserves_first_and_updates_last_detection():
    core=DigitalTwinCore(); first=BASE["timestamp"]
    core.synchronize(sample(oil_pressure_kpa=70,oil_temperature_c=145))
    _,state=core.synchronize(sample(timestamp=first+timedelta(seconds=5),oil_pressure_kpa=65,oil_temperature_c=146))
    item=next(x for x in state.faults.diagnostics if x.fault_code=="LUBRICATION_ISSUE")
    assert item.first_detected==first and item.last_detected==first+timedelta(seconds=5)

def test_cooling_diagnostic_explains_correlated_environmental_evidence():
    _,state=DigitalTwinCore().synchronize(sample(ambient_temperature_c=45,rpm=2800,engine_load_percent=100,
        cylinder_head_temp_1_c=250,cylinder_head_temp_2_c=252,cylinder_head_temp_3_c=251,cylinder_head_temp_4_c=253,
        exhaust_gas_temp_1_c=850,exhaust_gas_temp_2_c=852,exhaust_gas_temp_3_c=851,exhaust_gas_temp_4_c=853))
    item=next(x for x in state.faults.diagnostics if x.fault_code=="COOLING_SYSTEM_DEGRADATION")
    evidence=item.evidence["rule_evidence"]
    assert "cht_context_residual_c" in evidence and "egt_context_residual_c" in evidence
    assert "load_proxy_percent" in evidence and "thermal_stress" in evidence
    assert item.uncertainty in {"low","medium","high"}

def test_statistical_evidence_uses_only_prior_mission_window():
    core=DigitalTwinCore()
    for i in range(6): core.synchronize(sample(timestamp=BASE["timestamp"]+timedelta(seconds=5*i),vibration_rms=2.5+i*.02))
    _,state=core.synchronize(sample(timestamp=BASE["timestamp"]+timedelta(seconds=30),vibration_rms=12))
    item=next(x for x in state.faults.diagnostics if x.fault_code=="ABNORMAL_VIBRATION")
    assert item.evidence["contributions"]["statistical_anomaly"]>0
    assert item.evidence["statistical_evidence"][0]["prior_samples"]>=5

class AlwaysFaultyML:
    calibrated=False; version="test-only"
    def __init__(self): self.called=False
    def scores(self,features): self.called=True; return {code:1.0 for code in SUPPORTED_DIAGNOSTICS}

def test_ml_is_blocked_when_required_telemetry_is_invalid():
    core=DigitalTwinCore(); telemetry=sample(); ts=core.inspect_quality(telemetry.model_dump(),telemetry.timestamp)
    ts.parameters["rpm"]=ParameterState(value=9000,unit="rpm",quality=QualityFlag.OUT_OF_RANGE,reason="test")
    model=PrototypePhysicsModel(); valid=lambda n: ts.parameters[n].value if ts.parameters[n].quality==QualityFlag.VALID else None
    physics=model.evaluate(PhysicsInput(rpm=None,throttle_percent=valid("throttle_percent"),reported_load_percent=valid("engine_load_percent"),fuel_flow_lph=valid("fuel_flow_lph"),altitude_m=valid("altitude_m"),ambient_temperature_c=valid("ambient_temperature_c"),ambient_pressure_kpa=None,humidity_percent=None,cht_values_c=tuple(valid(f"cylinder_head_temp_{i}_c") for i in range(1,5)),egt_values_c=tuple(valid(f"exhaust_gas_temp_{i}_c") for i in range(1,5)),oil_pressure_kpa=valid("oil_pressure_kpa"),oil_temperature_c=valid("oil_temperature_c"),vibration_rms=valid("vibration_rms"),battery_voltage=valid("battery_voltage"),alternator_voltage=valid("alternator_voltage"),injection_timing_deg=valid("injection_timing_deg")))
    fused=SensorFusionEngine().evaluate(FusionInput(telemetry.engine_id,telemetry.mission_id,ts.parameters,physics))
    provider=AlwaysFaultyML(); engine=HybridDiagnosticEngine(ml_provider=provider)
    records=engine.evaluate(telemetry.engine_id,telemetry.mission_id,telemetry.timestamp,ts.parameters,physics,fused)
    assert not provider.called
    assert all("blocked: invalid required telemetry" in x.evidence["ml_status"] for x in records)

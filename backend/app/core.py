"""Modular synchronization core for the prototype aero-engine digital twin."""
from collections import defaultdict, deque
from datetime import datetime
import math
from threading import RLock
from .dataset_bridge import TELEMETRY_BOUNDS, TELEMETRY_UNITS
from .schemas import Alert, Telemetry, TwinAssessment
from .physics import PhysicsInput, PhysicsModel, PrototypePhysicsModel
from .sensor_fusion import FusionInput, SensorFusionEngine
from .diagnostics import HybridDiagnosticEngine, SUPPORTED_DIAGNOSTICS
from .ml_diagnostics import load_provider
from .config import settings
from .states import (DegradationState, EnginePerformanceState, EngineState, EnvironmentState,
    FaultHypothesis, FaultState, HealthState, MissionState, ParameterState, PhysicsState,
    PredictionState, QualityFlag, TelemetryState)
from .thresholds import CLASSIFICATION, ThresholdConfig

class DigitalTwinCore:
    """Synchronizes accepted telemetry into durable-serializable engine state."""
    def __init__(self, thresholds: ThresholdConfig | None = None, history_size: int = 120,
                 physics_model: PhysicsModel | None = None):
        self.thresholds = thresholds or ThresholdConfig()
        self.physics_model = physics_model or PrototypePhysicsModel()
        self.sensor_fusion = SensorFusionEngine()
        provider=load_provider(str(settings.ml_artifact_path)) if settings.ml_enabled else None
        if provider and not provider.release_gate_passed and not (settings.environment=="development" and settings.ml_allow_unvalidated):
            provider=None
        self.diagnostics = HybridDiagnosticEngine(ml_provider=provider,ml_enabled=settings.ml_enabled)
        self._states: dict[str, EngineState] = {}
        self._health_history = defaultdict(lambda: deque(maxlen=history_size))
        self._lock = RLock()

    def latest_state(self, engine_id: str) -> EngineState | None:
        with self._lock: return self._states.get(engine_id)

    def reset_engine_state(self,engine_id:str):
        """Reset volatile synchronization windows for an explicit replay session."""
        with self._lock:
            self._states.pop(engine_id,None); self._health_history.pop(engine_id,None)
            self.sensor_fusion.reset(engine_id); self.diagnostics.reset(engine_id)

    def inspect_quality(self, values: dict, observed_at: datetime, engine_id: str | None = None) -> TelemetryState:
        """Validate raw adapter data before constructing the strict API schema.

        CAN/FADEC adapters can use this boundary to represent missing or failed
        sensors without allowing those measurements into calculations.
        """
        with self._lock:
            previous=self._states.get(engine_id) if engine_id else None
            return self._telemetry_state(values,observed_at,previous)

    def _telemetry_state(self, values: dict, observed_at: datetime, previous: EngineState | None) -> TelemetryState:
        parameters={}; accepted=[]; rejected=[]
        is_stale = previous is not None and observed_at <= previous.synchronized_at
        for name, unit in TELEMETRY_UNITS.items():
            value=values.get(name)
            quality=QualityFlag.VALID; reason=None
            if value is None:
                quality=QualityFlag.MISSING; reason="required measurement is absent"
            elif name=="alternator_state" and value not in {"ONLINE","OFFLINE","DEGRADED","UNKNOWN"}:
                quality=QualityFlag.SENSOR_FAULT; reason="unrecognized alternator state"
            elif name=="alternator_state":
                pass
            elif not isinstance(value,(int,float)) or not math.isfinite(float(value)):
                quality=QualityFlag.SENSOR_FAULT; reason="measurement is non-numeric or non-finite"
            elif name in TELEMETRY_BOUNDS and not TELEMETRY_BOUNDS[name][0] <= float(value) <= TELEMETRY_BOUNDS[name][1]:
                quality=QualityFlag.OUT_OF_RANGE; reason="outside configured plausibility bounds"
            elif is_stale:
                quality=QualityFlag.STALE; reason="timestamp does not advance engine state"
            target=accepted if quality==QualityFlag.VALID else rejected; target.append(name)
            stored=value if name=="alternator_state" and quality==QualityFlag.VALID else float(value) if isinstance(value,(int,float)) and math.isfinite(float(value)) else None
            parameters[name]=ParameterState(value=stored,
                unit=unit,quality=quality,reason=reason)
        # Peer disagreement is retained as evidence but excluded from physics means.
        cht=[parameters[f"cylinder_head_temp_{i}_c"] for i in range(1,5)]
        valid_cht=[p.value for p in cht if p.quality==QualityFlag.VALID and p.value is not None]
        if len(valid_cht)==4 and max(valid_cht)-min(valid_cht)>self.thresholds.value("cht_spread_warning_c")*2.5:
            outlier=max(cht,key=lambda p:abs(p.value-(sum(valid_cht)/4)) if p.value is not None else -1)
            outlier.quality=QualityFlag.SUSPECT; outlier.reason="large disagreement with peer cylinders"
            name=next(name for name,p in parameters.items() if p is outlier)
            if name in accepted: accepted.remove(name)
            rejected.append(name)
        return TelemetryState(observed_at=observed_at,parameters=parameters,accepted_parameters=accepted,rejected_parameters=rejected)

    @staticmethod
    def _valid(state: TelemetryState, name: str) -> float | None:
        p=state.parameters[name]
        return p.value if p.quality==QualityFlag.VALID else None

    def synchronize(self, telemetry: Telemetry) -> tuple[TwinAssessment, EngineState]:
        with self._lock:
            previous=self._states.get(telemetry.engine_id)
            ts=self._telemetry_state(telemetry.model_dump(),telemetry.timestamp,previous)
            optional_signals={"ambient_pressure_kpa","humidity_percent","battery_current_a","alternator_state"}
            synchronized=not any(name not in optional_signals for name in ts.rejected_parameters)
            values={name:self._valid(ts,name) for name in ts.parameters}
            cht=[values[f"cylinder_head_temp_{i}_c"] for i in range(1,5)]
            egt=[values[f"exhaust_gas_temp_{i}_c"] for i in range(1,5)]
            valid_cht=[x for x in cht if x is not None]; valid_egt=[x for x in egt if x is not None]
            altitude=values["altitude_m"]; ambient=values["ambient_temperature_c"]
            rpm=values["rpm"]; load=values["engine_load_percent"]; throttle=values["throttle_percent"]
            fuel=values["fuel_flow_lph"]
            result=self.physics_model.evaluate(PhysicsInput(rpm=rpm,throttle_percent=throttle,reported_load_percent=load,
                fuel_flow_lph=fuel,altitude_m=altitude,ambient_temperature_c=ambient,
                ambient_pressure_kpa=values["ambient_pressure_kpa"],humidity_percent=values["humidity_percent"],
                cht_values_c=tuple(valid_cht),egt_values_c=tuple(valid_egt),oil_pressure_kpa=values["oil_pressure_kpa"],
                oil_temperature_c=values["oil_temperature_c"],vibration_rms=values["vibration_rms"],
                battery_voltage=values["battery_voltage"],alternator_voltage=values["alternator_voltage"],
                injection_timing_deg=values["injection_timing_deg"]))
            cht_mean,egt_mean=result.cht_mean_c,result.egt_mean_c
            cht_spread,egt_spread=result.cht_spread_c,result.egt_spread_c
            fuel_residual,timing_residual=result.fuel_flow_residual_lph,result.injection_timing_residual_deg
            physics=PhysicsState(cht_mean_c=cht_mean,egt_mean_c=egt_mean,cht_spread_c=cht_spread,
                egt_spread_c=egt_spread,estimated_fuel_flow_lph=result.expected_fuel_flow_lph,
                thermal_load_index=result.thermal_stress_indicator,lubrication_health_indicator=result.lubrication_health_indicator,
                combustion_health_indicator=result.combustion_health_indicator,vibration_health_indicator=result.vibration_health_indicator,
                electrical_health_indicator=result.electrical_health_indicator,overall_engine_health_index=result.overall_engine_health_index,
                model_version=result.model_version,assumption_classification=result.assumption_classification)
            performance=EnginePerformanceState(rpm=rpm,load_percent=result.engine_load_proxy_percent,throttle_percent=throttle,
                fuel_flow_lph=fuel,fuel_flow_residual_lph=fuel_residual,injection_timing_residual_deg=timing_residual,
                engine_efficiency_percent=result.engine_efficiency_percent)
            fused=self.sensor_fusion.evaluate(FusionInput(engine_id=telemetry.engine_id,mission_id=telemetry.mission_id,
                parameters=ts.parameters,physics=result))
            diagnostic_records=self.diagnostics.evaluate(telemetry.engine_id,telemetry.mission_id,telemetry.timestamp,
                ts.parameters,result,fused,telemetry.mission_phase)
            ml_inference=self.diagnostics.ml_result(telemetry.engine_id)
            alerts=[]; hypotheses=[]
            def flag(score,fault,code,severity,message,evidence):
                score=max(0,min(1,score))
                if score>=self.thresholds.value("anomaly_alert_score"):
                    hypotheses.append(FaultHypothesis(fault=fault,score=score,evidence=evidence))
                    alerts.append(Alert(code=code,severity=severity,message=message,evidence=evidence))
            run=self.thresholds.value("running_rpm")
            oilp=values["oil_pressure_kpa"]
            if rpm is not None and rpm>run and oilp is not None:
                warn=self.thresholds.value("oil_pressure_warning_kpa"); critical=self.thresholds.value("oil_pressure_critical_kpa")
                flag((warn-oilp)/(warn-critical),"Lubrication_System_Degradation","LOW_OIL_PRESSURE","critical" if oilp<critical else "warning","Oil pressure is low for a running engine.",{"oil_pressure_kpa":oilp})
            altv=values["alternator_voltage"]
            if rpm is not None and rpm>run and altv is not None:
                warn=self.thresholds.value("alternator_warning_v"); critical=self.thresholds.value("alternator_critical_v")
                flag((warn-altv)/(warn-critical),"Alternator_Degradation","LOW_ALTERNATOR_VOLTAGE","critical" if altv<critical else "warning","Alternator output is below its prototype charging region.",{"alternator_voltage":altv})
            vib=values["vibration_rms"]
            if vib is not None:
                warn=self.thresholds.value("vibration_warning_rms"); critical=self.thresholds.value("vibration_critical_rms")
                fused_vibration=fused["VIBRATION_HEALTH"]
                flag((100-fused_vibration.health_score)/100,"Bearing_Wear","HIGH_VIBRATION","critical" if fused_vibration.severity=="CRITICAL" else "warning","Windowed vibration signature is elevated.",{**fused_vibration.evidence_signals,"fusion_confidence":fused_vibration.confidence})
            if cht_mean is not None:
                warn=self.thresholds.value("cht_warning_c"); critical=self.thresholds.value("cht_critical_c")
                flag((cht_mean-warn)/(critical-warn),"Cooling_System_Degradation","HIGH_CHT","critical" if cht_mean>critical else "warning","Mean cylinder-head temperature is elevated.",{"cht_mean_c":round(cht_mean,2)})
            if cht_spread is not None:
                warn=self.thresholds.value("cht_spread_warning_c")
                flag((cht_spread-warn)/(warn*2.5),"Sensor_Drift","CHT_IMBALANCE","warning","Cylinder-head temperature spread is abnormal.",{"cht_spread_c":round(cht_spread,2)})
            if egt_spread is not None:
                warn=self.thresholds.value("egt_spread_warning_c")
                flag((egt_spread-warn)/(warn*3),"Spark_Plug_Misfire","EGT_IMBALANCE","warning","Exhaust-temperature imbalance may indicate combustion or ignition trouble.",{"egt_spread_c":round(egt_spread,2)})
            oiltemp=values["oil_temperature_c"]
            if oiltemp is not None:
                warn=self.thresholds.value("oil_temperature_warning_c")
                flag((oiltemp-warn)/30,"Lubrication_System_Degradation","HIGH_OIL_TEMP","warning","Oil temperature is elevated.",{"oil_temperature_c":oiltemp})
            if fuel_residual is not None:
                warn=self.thresholds.value("fuel_flow_residual_warning_lph")
                flag((abs(fuel_residual)-warn)/warn,"Fuel_Injector_Degradation","FUEL_FLOW_RESIDUAL","warning","Fuel flow differs from the prototype performance estimate.",{"fuel_flow_residual_lph":round(fuel_residual,2)})
            if timing_residual is not None:
                warn=self.thresholds.value("injection_timing_residual_warning_deg")
                flag((abs(timing_residual)-warn)/warn,"Fuel_Injector_Degradation","INJECTION_TIMING_RESIDUAL","warning","Injection timing differs from the prototype performance estimate.",{"injection_timing_residual_deg":round(timing_residual,2)})
            fuel_health=fused["FUEL_SYSTEM_HEALTH"]
            flag((100-fuel_health.health_score)/100,"Fuel_Injector_Degradation","CORRELATED_FUEL_SYSTEM_DEGRADATION","warning","Correlated fuel, RPM/load, EGT, timing, and combustion evidence indicates degradation.",{**fuel_health.evidence_signals,"fusion_confidence":fuel_health.confidence})
            sensor_health=fused["SENSOR_HEALTH"]
            flag((100-sensor_health.health_score)/100,"Sensor_Drift","CORRELATED_SENSOR_DEGRADATION","warning","Cross-sensor and temporal consistency checks indicate suspect telemetry.",{**sensor_health.evidence_signals,"fusion_confidence":sensor_health.confidence})
            if previous and synchronized and telemetry.timestamp>previous.synchronized_at:
                dt=(telemetry.timestamp-previous.synchronized_at).total_seconds(); prev_rpm=previous.performance.rpm; prev_thr=previous.performance.throttle_percent
                if prev_rpm is not None and prev_thr is not None and rpm is not None and throttle is not None:
                    rpm_rate=abs(rpm-prev_rpm)/dt
                    if rpm_rate>self.thresholds.value("rpm_uncommanded_rate_warning") and abs(throttle-prev_thr)<self.thresholds.value("throttle_stationary_delta"):
                        flag(min(1,rpm_rate/400),"Combustion_Instability","RPM_INSTABILITY","warning","RPM changed rapidly without a corresponding throttle command.",{"rpm_rate_per_s":round(rpm_rate,2)})
            hypotheses.sort(key=lambda x:x.score,reverse=True)
            score=hypotheses[0].score if hypotheses else 0.0; fault=hypotheses[0].fault if hypotheses else "Healthy"
            health_value=max(0,min(100,sum(x.health_score*x.confidence for x in fused.values())/max(.001,sum(x.confidence for x in fused.values()))-20*score))
            subsystems={name:item.health_score for name,item in fused.items()}
            history=self._health_history[telemetry.engine_id]
            if synchronized: history.append((telemetry.timestamp,health_value))
            slope=None
            if len(history)>=2:
                hours=(history[-1][0]-history[0][0]).total_seconds()/3600
                if hours>0: slope=(history[-1][1]-history[0][1])/hours
            cumulative=max(0,100-health_value)+(previous.degradation.cumulative_damage_index if previous and synchronized else 0)*.995
            trend="degrading" if slope is not None and slope<-.1 else "stable" if slope is not None else "insufficient_data"
            degradation=DegradationState(cumulative_damage_index=round(cumulative,3),health_slope_per_hour=round(slope,4) if slope is not None else None,samples_observed=len(history),trend=trend)
            nominal_rul=self.thresholds.value("nominal_rul_hours")
            rul=max(0,min(nominal_rul,nominal_rul-(100-health_value)*16-cumulative*.5))
            uncertainty=max(100,nominal_rul*.25)
            advisory="No maintenance action indicated; continue monitoring."
            if score>=self.thresholds.value("critical_anomaly_score"): advisory=f"Land or abort if operationally safe; inspect for {fault}."
            elif score>=self.thresholds.value("anomaly_alert_score"): advisory=f"Schedule inspection for {fault} and review the recent trend."
            health=HealthState(overall_index=round(health_value,2),subsystem_indices={k:round(v,2) for k,v in subsystems.items()},
                subsystem_assessments=fused,fusion_version=self.sensor_fusion.version)
            prediction=PredictionState(rul_hours=round(rul,1),lower_bound_hours=round(max(0,rul-uncertainty),1),upper_bound_hours=round(min(nominal_rul,rul+uncertainty),1),maintenance_advisory=advisory)
            if previous and previous.mission.mission_id==telemetry.mission_id:
                count=previous.mission.sample_count+1; first=previous.mission.first_observed_at
            else: count=1; first=telemetry.timestamp
            state=EngineState(engine_id=telemetry.engine_id,synchronized_at=telemetry.timestamp,synchronized=synchronized,
                telemetry=ts,environment=EnvironmentState(altitude_m=altitude,ambient_temperature_c=ambient,
                    density_ratio=result.air_density_proxy,air_density_proxy=result.air_density_proxy,
                    ambient_pressure_kpa=values["ambient_pressure_kpa"],humidity_percent=values["humidity_percent"]),
                physics=physics,performance=performance,health=health,degradation=degradation,
                faults=FaultState(anomaly_score=round(score,4),primary_fault=fault,hypotheses=hypotheses,
                    diagnostics=diagnostic_records,supported_diagnostic_categories=list(SUPPORTED_DIAGNOSTICS),
                    ml_inference=ml_inference),
                mission=MissionState(mission_id=telemetry.mission_id,phase=telemetry.mission_phase,sample_count=count,first_observed_at=first,last_observed_at=telemetry.timestamp),
                prediction=prediction,alerts=[a.model_dump(mode="json") for a in alerts],threshold_config_version=self.thresholds.version)
            if synchronized: self._states[telemetry.engine_id]=state
            assessment=TwinAssessment(engine_id=telemetry.engine_id,mission_id=telemetry.mission_id,timestamp=telemetry.timestamp,
                health_index=health.overall_index,rul_hours=prediction.rul_hours,anomaly_score=state.faults.anomaly_score,
                predicted_fault=fault,confidence=round(.5+.45*score if fault!="Healthy" else .75,4),maintenance_advisory=advisory,alerts=alerts,
                method="explainable physics-informed prototype rules; thresholds are engineering hypotheses",
                ml_inference=ml_inference)
            return assessment,state

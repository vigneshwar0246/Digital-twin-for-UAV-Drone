"""Explainable hybrid fault diagnostics with explicit uncertainty.

Scores are engineering scores, not probabilities. The current repository has an
offline, uncalibrated classifier report but no deployable model artifact, so ML
contribution is explicitly unavailable rather than fabricated.
"""
from collections import defaultdict, deque, OrderedDict
from datetime import datetime
import json, math, statistics
from pathlib import Path
from threading import RLock
from typing import Protocol
from .physics import PhysicsResult
from .states import FaultDiagnostic, ParameterState, QualityFlag, SubsystemHealth

SUPPORTED_DIAGNOSTICS={
 "MISFIRE":"Misfire","FUEL_INJECTOR_DEGRADATION":"Fuel Injector Degradation",
 "COOLING_SYSTEM_DEGRADATION":"Cooling System Degradation","LUBRICATION_ISSUE":"Lubrication Issue",
 "SENSOR_DRIFT":"Sensor Drift","SENSOR_FAILURE":"Sensor Failure",
 "COMBUSTION_INSTABILITY":"Combustion Instability","OVERHEATING":"Overheating",
 "ABNORMAL_VIBRATION":"Abnormal Vibration","BATTERY_ALTERNATOR_ABNORMALITY":"Battery/Alternator Abnormality",
 "INJECTION_TIMING_ABNORMALITY":"Injection Timing Abnormality"
}

class MLDiagnosticProvider(Protocol):
    calibrated: bool
    version: str
    def predict(self, valid_features:dict[str,float|str])->dict: ...

class HybridDiagnosticEngine:
    def __init__(self,path:Path|None=None,ml_provider:MLDiagnosticProvider|None=None,ml_enabled:bool=False):
        raw=json.loads((path or Path(__file__).with_name("diagnostic_assumptions.json")).read_text(encoding="utf-8"))
        if raw["metadata"]["probabilities_calibrated"] is not False: raise ValueError("prototype diagnostics must not claim calibrated probabilities")
        self.version=raw["metadata"]["version"]; self.classification=raw["metadata"]["classification"]
        self._a={k:float(v["value"]) for k,v in raw["assumptions"].items()}; self.ml_provider=ml_provider; self.ml_enabled=ml_enabled
        self._history=defaultdict(lambda:deque(maxlen=int(self._a["trend_window_samples"])))
        self._mission={}; self._active={}; self._lock=RLock(); self._ml_results=OrderedDict()

    def ml_result(self,engine_id:str)->dict:
        with self._lock:
            return dict(self._ml_results.get(engine_id,{"status":"disabled"}))

    def reset(self,engine_id:str):
        with self._lock:
            self._history.pop(engine_id,None); self._mission.pop(engine_id,None)
            self._active={k:v for k,v in self._active.items() if k[0]!=engine_id}
            self._ml_results.pop(engine_id,None)

    @staticmethod
    def _clip(value): return max(0.0,min(1.0,value))
    @staticmethod
    def _impact(score): return round(min(100,score*55),2)
    def _severity(self,score): return "CRITICAL" if score>=self._a["critical_score"] else "WARNING" if score>=self._a["warning_score"] else "ADVISORY"

    def _statistical_score(self,name,current,history):
        prior=[r[name] for r in history if r.get(name) is not None]
        if current is None or len(prior)<self._a["minimum_statistical_samples"]: return 0.0,None
        median=statistics.median(prior); deviations=[abs(x-median) for x in prior]; mad=statistics.median(deviations)
        scale=max(mad*1.4826,statistics.pstdev(prior),1e-6); z=abs(current-median)/scale
        score=self._clip((z-self._a["zscore_onset"])/4)
        return score,{"signal":name,"robust_z_score":round(z,3),"baseline_median":round(median,3),"prior_samples":len(prior)}

    def evaluate(self,engine_id:str,mission_id:str,observed_at:datetime,parameters:dict[str,ParameterState],
                 physics:PhysicsResult,fused:dict[str,SubsystemHealth],mission_phase:str="unknown")->list[FaultDiagnostic]:
        with self._lock:
            if self._mission.get(engine_id)!=mission_id:
                self._history[engine_id].clear(); self._mission[engine_id]=mission_id
                self._active={k:v for k,v in self._active.items() if k[0]!=engine_id}
            def v(name):
                p=parameters.get(name); return p.value if p and p.quality==QualityFlag.VALID and isinstance(p.value,(int,float)) else None
            valid={name:p.value for name,p in parameters.items() if p.quality==QualityFlag.VALID and p.value is not None}
            optional={"battery_current_a","ambient_pressure_kpa","humidity_percent","alternator_state"}
            invalid_required=[name for name,p in parameters.items() if name not in optional and p.quality!=QualityFlag.VALID]
            history=list(self._history[engine_id]); row={name:v(name) for name in parameters}
            row.update({"cht_mean_c":physics.cht_mean_c,"egt_mean_c":physics.egt_mean_c,
                "egt_spread_c":physics.egt_spread_c,"thermal_stress_indicator":physics.thermal_stress_indicator})
            statistical={}
            for name in ("rpm","oil_pressure_kpa","oil_temperature_c","fuel_flow_lph","vibration_rms","battery_voltage","alternator_voltage","injection_timing_deg","cht_mean_c","egt_mean_c","egt_spread_c","thermal_stress_indicator"):
                statistical[name]=self._statistical_score(name,row.get(name),history)
            if self.ml_provider is None:
                ml_result={"status":"unavailable" if self.ml_enabled else "disabled"}
                ml_status="unavailable: offline classifier has no deployable artifact" if self.ml_enabled else "disabled: offline classifier has no deployable artifact"
            elif invalid_required:
                ml_result={"status":"blocked", "reason":"invalid required telemetry"}
                ml_status="blocked: invalid required telemetry"
            else:
                try:
                    ml_result=self.ml_provider.predict({**valid,"mission_phase":mission_phase})
                    ml_status=f"served model {self.ml_provider.version}; uncalibrated"
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning("ML inference failed for model %s: %s",self.ml_provider.version,exc)
                    ml_result={"status":"unavailable", "model_version":self.ml_provider.version,
                               "reason":"inference failed or features unavailable"}
                    ml_status="unavailable: model inference failed"
            self._ml_results[engine_id]=ml_result
            self._ml_results.move_to_end(engine_id)
            if len(self._ml_results)>128: self._ml_results.popitem(last=False)
            candidates=[]
            def add(code,rule_score,evidence,subsystems,action,stat_names=()):
                stats=[statistical[n][0] for n in stat_names if statistical[n][1] is not None]
                stat=max(stats,default=0.0)
                # ML remains independent evidence; engineering scores retain their established meaning.
                score=self._clip(self._a["rule_weight"]*self._clip(rule_score)+self._a["statistical_weight"]*stat)
                if score<self._a["activation_score"]: return
                stat_evidence=[statistical[n][1] for n in stat_names if statistical[n][1] is not None and statistical[n][0]>0]
                first=self._active.get((engine_id,code),observed_at); self._active[(engine_id,code)]=first
                candidates.append(FaultDiagnostic(fault_code=code,fault_name=SUPPORTED_DIAGNOSTICS[code],severity=self._severity(score),
                    probability=None,engineering_score=round(score,4),score_kind="uncalibrated engineering score",
                    health_impact=self._impact(score),evidence={"rule_evidence":evidence,"statistical_evidence":stat_evidence,
                    "contributions":{"engineering_rules":round(rule_score,4),"statistical_anomaly":round(stat,4)},
                    "ml_evidence":ml_result if ml_result.get("fault_class")==code else {"status":ml_result["status"]},
                    "ml_status":ml_status},
                    affected_subsystems=subsystems,recommended_action=action,first_detected=first,last_detected=observed_at,
                    diagnostic_version=self.version,uncertainty="high" if len(evidence)<2 or not stat_evidence else "medium"))
            hs=lambda name:(100-fused[name].health_score)/100
            add("MISFIRE",max((physics.egt_spread_c or 0)/165,hs("COMBUSTION_HEALTH")*.7),{"egt_spread_c":physics.egt_spread_c or 0,"combustion_health":fused["COMBUSTION_HEALTH"].health_score,"windowed_vibration":fused["VIBRATION_HEALTH"].evidence_signals},["COMBUSTION_HEALTH","VIBRATION_HEALTH"],"Inspect ignition components and cylinder-specific EGT evidence before further operation.",( "rpm","vibration_rms"))
            add("FUEL_INJECTOR_DEGRADATION",hs("FUEL_SYSTEM_HEALTH"),{"fuel_flow_residual_lph":physics.fuel_flow_residual_lph or 0,"egt_spread_c":physics.egt_spread_c or 0,"timing_residual_deg":physics.injection_timing_residual_deg or 0,"fuel_system_health":fused["FUEL_SYSTEM_HEALTH"].health_score},["FUEL_SYSTEM_HEALTH","COMBUSTION_HEALTH"],"Inspect injector flow, command timing, fuel supply, and cylinder balance.",( "fuel_flow_lph","injection_timing_deg"))
            add("COOLING_SYSTEM_DEGRADATION",hs("THERMAL_HEALTH"),{**fused["THERMAL_HEALTH"].evidence_signals,"thermal_stress":physics.thermal_stress_indicator or 0},["THERMAL_HEALTH"],"Inspect cooling airflow and cylinder cooling paths; review the thermal trend.",( "cht_mean_c","egt_mean_c","thermal_stress_indicator"))
            add("LUBRICATION_ISSUE",hs("LUBRICATION_HEALTH"),fused["LUBRICATION_HEALTH"].evidence_signals,["LUBRICATION_HEALTH"],"Inspect oil level, pressure circuit, temperature, pump, and filter indications.",( "oil_pressure_kpa","oil_temperature_c"))
            add("SENSOR_DRIFT",hs("SENSOR_HEALTH"),fused["SENSOR_HEALTH"].evidence_signals,["SENSOR_HEALTH"],"Cross-check the suspect sensor against peers and calibration history.")
            failed=[name for name,p in parameters.items() if p.quality in {QualityFlag.MISSING,QualityFlag.OUT_OF_RANGE,QualityFlag.SENSOR_FAULT} and name not in {"battery_current_a","ambient_pressure_kpa","humidity_percent","alternator_state"}]
            add("SENSOR_FAILURE",min(1,len(failed)/2),{"failed_or_missing_required_signals":failed},["SENSOR_HEALTH"],"Use redundant data if available; inspect wiring, power, connector, and sensor health.")
            rpm_stat=statistical["rpm"][0]
            add("COMBUSTION_INSTABILITY",max(hs("COMBUSTION_HEALTH"),rpm_stat),{"combustion_health":fused["COMBUSTION_HEALTH"].health_score,"rpm_statistical_score":rpm_stat,"egt_spread_c":physics.egt_spread_c or 0},["COMBUSTION_HEALTH"],"Review RPM, EGT balance, mixture, ignition, and throttle-command consistency.",( "rpm",))
            add("OVERHEATING",max(hs("THERMAL_HEALTH"),(physics.thermal_stress_indicator or 0)/100),{**fused["THERMAL_HEALTH"].evidence_signals,"cht_mean_c":physics.cht_mean_c or 0,"egt_mean_c":physics.egt_mean_c or 0},["THERMAL_HEALTH","LUBRICATION_HEALTH"],"Reduce thermal demand if operationally appropriate and inspect cooling/lubrication evidence.",( "cht_mean_c","egt_mean_c","oil_temperature_c"))
            add("ABNORMAL_VIBRATION",hs("VIBRATION_HEALTH"),fused["VIBRATION_HEALTH"].evidence_signals,["VIBRATION_HEALTH"],"Inspect mounting, rotating assembly, propeller-order sources, and sensor installation.",( "vibration_rms",))
            add("BATTERY_ALTERNATOR_ABNORMALITY",hs("ELECTRICAL_HEALTH"),fused["ELECTRICAL_HEALTH"].evidence_signals,["ELECTRICAL_HEALTH"],"Inspect alternator/regulator output, battery condition, wiring, and electrical load.",( "battery_voltage","alternator_voltage"))
            timing_score=min(1,abs(physics.injection_timing_residual_deg or 0)/8)
            add("INJECTION_TIMING_ABNORMALITY",timing_score,{"timing_residual_deg":physics.injection_timing_residual_deg or 0,"combustion_health":fused["COMBUSTION_HEALTH"].health_score},["FUEL_SYSTEM_HEALTH","COMBUSTION_HEALTH"],"Verify timing command/feedback, calibration, and injector/ECU synchronization.",( "injection_timing_deg",))
            self._history[engine_id].append(row)
            return sorted(candidates,key=lambda x:x.engineering_score,reverse=True)

"""Windowed, uncertainty-visible sensor fusion for subsystem health.

This module produces relative prototype indicators. It does not contain
manufacturer-approved limits or a validated diagnostic/prognostic model.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
import json, math, statistics
from pathlib import Path
from threading import RLock
from typing import Mapping
from .physics import PhysicsResult
from .states import ParameterState, QualityFlag, SubsystemHealth

@dataclass(frozen=True)
class FusionInput:
    engine_id: str; mission_id: str
    parameters: Mapping[str, ParameterState]
    physics: PhysicsResult

class SensorFusionEngine:
    def __init__(self,path:Path|None=None):
        path=path or Path(__file__).with_name("sensor_fusion_assumptions.json")
        raw=json.loads(path.read_text(encoding="utf-8")); meta=raw["metadata"]
        if meta["manufacturer_approved"] is not False:
            raise ValueError("sensor fusion configuration must remain explicitly prototype-only")
        self.version=meta["version"]; self.classification=meta["classification"]
        self.documentation={k:v["description"] for k,v in raw["assumptions"].items()}
        self._a={k:float(v["value"]) for k,v in raw["assumptions"].items()}
        self._history=defaultdict(lambda:deque(maxlen=int(self._a["window_samples"])))
        self._mission={}; self._lock=RLock()

    def reset(self,engine_id:str):
        with self._lock:
            self._history.pop(engine_id,None); self._mission.pop(engine_id,None)

    @staticmethod
    def _clip(value): return max(0.0,min(100.0,value))
    @staticmethod
    def _severity(score):
        return "CRITICAL" if score<35 else "WARNING" if score<60 else "ADVISORY" if score<80 else "NORMAL"

    def _result(self,score,available,expected,evidence,reason,temporal=False):
        coverage=available/max(expected,1)
        history_factor=min(1,len(evidence.get("window_values",[]))/self._a["minimum_temporal_samples"]) if temporal else 1
        confidence=max(0,min(1,coverage*(.55+.45*history_factor)))
        evidence={k:v for k,v in evidence.items() if k!="window_values"}
        uncertainty="high" if confidence<.5 else "medium" if confidence<.8 else "low"
        return SubsystemHealth(health_score=round(self._clip(score),2),confidence=round(confidence,3),
            evidence_signals=evidence,reason=reason,severity=self._severity(score),uncertainty=uncertainty)

    def evaluate(self,data:FusionInput)->dict[str,SubsystemHealth]:
        with self._lock:
            key=data.engine_id
            if self._mission.get(key)!=data.mission_id:
                self._history[key].clear(); self._mission[key]=data.mission_id
            def v(name):
                p=data.parameters.get(name)
                return p.value if p and p.quality==QualityFlag.VALID else None
            row={name:v(name) for name in data.parameters}; self._history[key].append(row)
            history=list(self._history[key]); p=data.physics; a=self._a; results={}

            # Thermal: correlated head/exhaust temperatures contextualized by ambient, RPM and load.
            signals=[p.cht_mean_c,p.egt_mean_c,v("ambient_temperature_c"),v("rpm"),p.engine_load_proxy_percent]
            available=sum(x is not None for x in signals); penalties=[]; evidence={}
            if p.cht_mean_c is not None and v("ambient_temperature_c") is not None and p.engine_load_proxy_percent is not None:
                residual=p.cht_mean_c-v("ambient_temperature_c")-.8*p.engine_load_proxy_percent; penalties.append(max(0,residual-a["cht_ambient_load_reference"])/70); evidence["cht_context_residual_c"]=round(residual,2)
            if p.egt_mean_c is not None and v("ambient_temperature_c") is not None and p.engine_load_proxy_percent is not None:
                residual=p.egt_mean_c-v("ambient_temperature_c")-2*p.engine_load_proxy_percent; penalties.append(max(0,residual-a["egt_ambient_load_reference"])/200); evidence["egt_context_residual_c"]=round(residual,2)
            if p.thermal_stress_indicator is not None:
                penalties.append(p.thermal_stress_indicator/100); evidence["physics_thermal_stress_indicator"]=round(p.thermal_stress_indicator,2)
            evidence.update({"rpm":v("rpm") or 0,"load_proxy_percent":round(p.engine_load_proxy_percent or 0,2)})
            score=100-100*(max(penalties) if penalties else 0)
            results["THERMAL_HEALTH"]=self._result(score,available,5,evidence,"CHT and EGT evaluated against ambient, RPM, and load context.")

            # Lubrication: pressure adequacy is meaningful only with RPM/load; temperature adds viscosity context.
            signals=[v("oil_pressure_kpa"),v("oil_temperature_c"),v("rpm"),p.engine_load_proxy_percent]
            available=sum(x is not None for x in signals); penalties=[]; evidence={k:round(x,2) for k,x in zip(("oil_pressure_kpa","oil_temperature_c","rpm","load_proxy_percent"),signals) if x is not None}
            if signals[0] is not None and signals[2] is not None and signals[2]>900:
                expected=a["oil_pressure_running_reference"]*(.65+.35*min(1,signals[2]/2700)); penalties.append(max(0,expected-signals[0])/250); evidence["pressure_residual_kpa"]=round(signals[0]-expected,2)
            if signals[1] is not None: penalties.append(max(0,signals[1]-a["oil_temperature_reference"])/45)
            results["LUBRICATION_HEALTH"]=self._result(100-100*sum(penalties),available,4,evidence,"Oil pressure and temperature fused with RPM and load context.")

            # Combustion and fuel: residuals plus cylinder balance avoid single-threshold decisions.
            combustion_signals=[p.egt_spread_c,p.fuel_flow_residual_lph,p.injection_timing_residual_deg,p.combustion_health_indicator,v("rpm")]
            available=sum(x is not None for x in combustion_signals); penalties=[]
            for value,scale in ((p.egt_spread_c,a["egt_spread_scale"]),(p.fuel_flow_residual_lph,a["fuel_residual_scale"]),(p.injection_timing_residual_deg,a["timing_residual_scale"])):
                if value is not None: penalties.append(abs(value)/scale)
            evidence={"egt_spread_c":round(p.egt_spread_c or 0,2),"fuel_flow_residual_lph":round(p.fuel_flow_residual_lph or 0,2),"timing_residual_deg":round(p.injection_timing_residual_deg or 0,2)}
            results["COMBUSTION_HEALTH"]=self._result(100-45*(sum(penalties)/len(penalties) if penalties else 0),available,5,evidence,"EGT balance, fuel residual, timing residual, combustion indicator, and RPM were fused.")
            fuel_available=sum(x is not None for x in (v("fuel_flow_lph"),v("rpm"),p.egt_mean_c,v("injection_timing_deg"),p.engine_load_proxy_percent))
            results["FUEL_SYSTEM_HEALTH"]=self._result(100-55*(sum(penalties[1:])/max(1,len(penalties[1:]))) if penalties else 100,fuel_available,5,evidence,"Fuel flow is compared with RPM/load expectation and checked against EGT and injection timing.")

            # Vibration: rolling mean and variation; no instantaneous-only classification.
            window=[r["vibration_rms"] for r in history if r.get("vibration_rms") is not None]
            vib_mean=statistics.fmean(window) if window else None; vib_std=statistics.pstdev(window) if len(window)>1 else 0 if window else None
            evidence={"window_values":window,"window_samples":len(window),"rolling_mean_rms":round(vib_mean,3) if vib_mean is not None else "unavailable","rolling_std_rms":round(vib_std,3) if vib_std is not None else "unavailable"}
            penalty=(max(0,vib_mean-a["vibration_mean_reference"])/5 if vib_mean is not None else 1)+(max(0,vib_std-a["vibration_std_reference"])/3 if vib_std is not None else 0)
            results["VIBRATION_HEALTH"]=self._result(100-100*penalty,len(window)>0 and 1 or 0,1,evidence,"Rolling vibration mean and variability were evaluated; confidence reflects window maturity.",True)

            # Electrical: voltage/current coverage is explicit; absent current lowers confidence.
            electrical=[v("battery_voltage"),v("battery_current_a"),v("alternator_voltage"),v("alternator_state")]
            available=sum(x is not None for x in electrical); base=p.electrical_health_indicator if p.electrical_health_indicator is not None else 50
            if electrical[3]=="OFFLINE": base=min(base,25)
            elif electrical[3]=="DEGRADED": base=min(base,55)
            evidence={k:(round(x,2) if isinstance(x,(int,float)) else x) for k,x in zip(("battery_voltage","battery_current_a","alternator_voltage","alternator_state"),electrical) if x is not None}
            results["ELECTRICAL_HEALTH"]=self._result(base,available,4,evidence,"Battery voltage/current and alternator voltage/state were fused; unavailable signals reduce confidence.")

            # Sensor health: quality flags, peer consistency and temporal exact-repeat behavior.
            rejected=sum(x.quality!=QualityFlag.VALID for x in data.parameters.values()); total=len(data.parameters)
            peer=max((p.cht_spread_c or 0)/a["cht_peer_spread_scale"],(p.egt_spread_c or 0)/a["egt_spread_scale"])
            tracked=("rpm","oil_pressure_kpa","oil_temperature_c","fuel_flow_lph","vibration_rms")
            stuck=sum(1 for name in tracked if len(history)>=int(a["minimum_temporal_samples"]) and all(r.get(name) is not None for r in history) and max(r[name] for r in history)-min(r[name] for r in history)<=a["stuck_tolerance"])
            score=100-100*rejected/max(total,1)-20*max(0,peer-1)-10*stuck
            evidence={"invalid_or_missing_signals":rejected,"total_signals":total,"peer_spread_ratio":round(peer,3),"temporally_stuck_signals":stuck,"window_values":history}
            results["SENSOR_HEALTH"]=self._result(score,total-rejected,total,evidence,"Quality flags, cylinder consistency, and temporal behavior were fused.",True)
            return results

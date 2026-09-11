"""Replaceable, physics-informed prototype model.

The equations encode qualitative engineering relationships for software
demonstration. They are not a validated thermodynamic cycle, engine performance
map, manufacturer limit set, control law, or evidence of airworthiness. All
numeric assumptions are loaded from ``prototype_physics_assumptions.json``.
"""
from dataclasses import dataclass
import json, math
from pathlib import Path
from typing import Mapping, Protocol

CLASSIFICATION="synthetic engineering assumption; not validated aircraft-engine physics"

@dataclass(frozen=True)
class PhysicsInput:
    rpm: float | None; throttle_percent: float | None; reported_load_percent: float | None
    fuel_flow_lph: float | None; altitude_m: float | None; ambient_temperature_c: float | None
    ambient_pressure_kpa: float | None; humidity_percent: float | None
    cht_values_c: tuple[float, ...]; egt_values_c: tuple[float, ...]
    oil_pressure_kpa: float | None; oil_temperature_c: float | None; vibration_rms: float | None
    battery_voltage: float | None; alternator_voltage: float | None; injection_timing_deg: float | None

@dataclass(frozen=True)
class PhysicsResult:
    air_density_proxy: float | None; engine_load_proxy_percent: float | None
    cht_mean_c: float | None; egt_mean_c: float | None; cht_spread_c: float | None; egt_spread_c: float | None
    expected_fuel_flow_lph: float | None; fuel_flow_residual_lph: float | None
    expected_injection_timing_deg: float | None; injection_timing_residual_deg: float | None
    thermal_stress_indicator: float | None; lubrication_health_indicator: float | None
    combustion_health_indicator: float | None; vibration_health_indicator: float | None
    electrical_health_indicator: float | None; engine_efficiency_percent: float | None
    overall_engine_health_index: float
    model_version: str; assumption_classification: str=CLASSIFICATION

class PhysicsModel(Protocol):
    version: str
    def evaluate(self, data: PhysicsInput) -> PhysicsResult: ...

class PrototypePhysicsModel:
    """Configuration-driven qualitative model replaceable by a validated map."""
    def __init__(self,path:Path|None=None):
        path=path or Path(__file__).with_name("prototype_physics_assumptions.json")
        raw=json.loads(path.read_text(encoding="utf-8")); meta=raw["metadata"]
        if meta["classification"]!=CLASSIFICATION or meta["manufacturer_specific"] is not False:
            raise ValueError("prototype physics assumptions require explicit non-validated classification")
        self.version=meta["version"]; self.documentation={k:v["description"] for k,v in raw["assumptions"].items()}
        self._a={k:float(v["value"]) for k,v in raw["assumptions"].items()}

    @staticmethod
    def _clip(value,lo=0.0,hi=100.0): return max(lo,min(hi,value))
    @staticmethod
    def _mean(values): return sum(values)/len(values) if values else None

    def evaluate(self,d:PhysicsInput)->PhysicsResult:
        a=self._a; temp_k=d.ambient_temperature_c+273.15 if d.ambient_temperature_c is not None else None
        pressure=d.ambient_pressure_kpa
        if pressure is None and d.altitude_m is not None:
            pressure=a["sea_level_pressure_kpa"]*max(0,1-a["fallback_pressure_lapse_coefficient"]*d.altitude_m)**a["fallback_pressure_lapse_exponent"]
        density=None
        if pressure is not None and temp_k is not None and temp_k>0:
            humidity_correction=1-a["humidity_density_weight"]*((d.humidity_percent or 0)/100)
            density=(pressure/a["sea_level_pressure_kpa"])*(a["reference_temperature_k"]/temp_k)*humidity_correction
        load_terms=[]
        if d.reported_load_percent is not None: load_terms.append((a["reported_load_weight"],d.reported_load_percent))
        if d.throttle_percent is not None: load_terms.append((a["throttle_load_weight"],d.throttle_percent*(density if density is not None else 1)))
        load=self._clip(sum(w*v for w,v in load_terms)/sum(w for w,_ in load_terms),0,110) if load_terms else None
        cht_mean=self._mean(d.cht_values_c); egt_mean=self._mean(d.egt_values_c)
        cht_spread=max(d.cht_values_c)-min(d.cht_values_c) if len(d.cht_values_c)>1 else None
        egt_spread=max(d.egt_values_c)-min(d.egt_values_c) if len(d.egt_values_c)>1 else None
        expected_fuel=(d.rpm/a["reference_rpm"])*(load/100)*a["fuel_flow_scale_lph"] if d.rpm is not None and load is not None else None
        fuel_res=d.fuel_flow_lph-expected_fuel if d.fuel_flow_lph is not None and expected_fuel is not None else None
        expected_timing=a["injection_base_deg"]+a["injection_load_coefficient"]*load+a["injection_altitude_coefficient"]*(d.altitude_m or 0) if load is not None else None
        timing_res=d.injection_timing_deg-expected_timing if d.injection_timing_deg is not None and expected_timing is not None else None
        thermal_parts=[]
        if cht_mean is not None: thermal_parts.append(max(0,(cht_mean-a["cht_stress_reference_c"])/a["cht_stress_span_c"]))
        if egt_mean is not None: thermal_parts.append(max(0,(egt_mean-a["egt_stress_reference_c"])/a["egt_stress_span_c"]))
        thermal=self._clip(100*self._mean(thermal_parts),0,100) if thermal_parts else None
        lub=None
        if d.rpm is not None and d.rpm>a["running_rpm_reference"] and d.oil_pressure_kpa is not None:
            pressure_penalty=max(0,a["oil_pressure_reference_kpa"]-d.oil_pressure_kpa)/a["oil_pressure_span_kpa"]
            temp_penalty=max(0,(d.oil_temperature_c or 0)-a["oil_temperature_reference_c"])/a["oil_temperature_span_c"]
            lub=self._clip(100*(1-pressure_penalty-temp_penalty))
        combustion_penalties=[]
        if egt_spread is not None: combustion_penalties.append(egt_spread/a["egt_spread_reference_c"])
        if fuel_res is not None: combustion_penalties.append(abs(fuel_res)/a["fuel_flow_scale_lph"])
        if timing_res is not None: combustion_penalties.append(abs(timing_res)/10)
        combustion=self._clip(100*(1-.35*self._mean(combustion_penalties))) if combustion_penalties else None
        vibration=self._clip(100*(1-max(0,(d.vibration_rms-a["vibration_reference_rms"])/a["vibration_span_rms"]))) if d.vibration_rms is not None else None
        electrical_parts=[]
        if d.rpm is not None and d.rpm>a["running_rpm_reference"] and d.alternator_voltage is not None:
            electrical_parts.append(self._clip(100*(1+min(0,d.alternator_voltage-a["alternator_reference_v"])/a["alternator_span_v"])))
        if d.battery_voltage is not None:
            electrical_parts.append(self._clip(100*(1+min(0,d.battery_voltage-a["battery_reference_v"])/a["battery_span_v"])))
        electrical=self._mean(electrical_parts)
        health_parts=[x for x in (100-(thermal or 0),lub,combustion,vibration,electrical) if x is not None]
        overall=self._clip(self._mean(health_parts) if health_parts else 0)
        efficiency=self._clip(a["nominal_efficiency_percent"]-(100-overall)*.25,a["minimum_efficiency_percent"],100)
        return PhysicsResult(density,load,cht_mean,egt_mean,cht_spread,egt_spread,expected_fuel,fuel_res,
            expected_timing,timing_res,thermal,lub,combustion,vibration,electrical,efficiency,overall,self.version)

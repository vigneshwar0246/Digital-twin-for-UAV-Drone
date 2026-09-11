"""Deterministic mission replay sessions and post-flight analysis."""
from dataclasses import dataclass, field
from datetime import datetime
import csv, math, uuid
from pathlib import Path
from threading import RLock
from typing import Callable
from pydantic import BaseModel, Field, field_validator
from .schemas import Telemetry, TwinAssessment
from .states import EngineState
from .twin import TwinEngine
from .thresholds import ThresholdConfig

class ReplayRequest(BaseModel):
    mission_id:str=Field(min_length=1,max_length=64)
    engine_id:str|None=None
    start_time:datetime|None=None
    end_time:datetime|None=None
    speed:float=Field(default=1,gt=0,le=100)
    @field_validator("start_time","end_time")
    @classmethod
    def aware(cls,value):
        if value is not None and value.tzinfo is None: raise ValueError("replay times must include a timezone")
        return value

class SeekRequest(BaseModel):
    time_seconds:float=Field(ge=0)

class AdvanceRequest(BaseModel):
    virtual_seconds:float=Field(default=5,gt=0,le=3600)

def csv_row_to_telemetry(row:dict)->Telemetry:
    values={"engine_id":row["engine_id"],"mission_id":row["mission_id"],"timestamp":row["timestamp"],"mission_phase":row["mission_phase"]}
    names=("rpm","cylinder_head_temp_1_c","cylinder_head_temp_2_c","cylinder_head_temp_3_c","cylinder_head_temp_4_c",
        "exhaust_gas_temp_1_c","exhaust_gas_temp_2_c","exhaust_gas_temp_3_c","exhaust_gas_temp_4_c","oil_temperature_c",
        "oil_pressure_kpa","fuel_flow_lph","vibration_rms","alternator_voltage","battery_voltage","injection_timing_deg",
        "engine_load_percent","throttle_percent","altitude_m","ambient_temperature_c","ambient_pressure_kpa","humidity_percent")
    for name in names:
        if row.get(name) not in (None,""): values[name]=float(row[name])
    values["alternator_state"]="ONLINE" if values["alternator_voltage"]>27 else "OFFLINE"
    return Telemetry.model_validate(values)

class MissionTelemetrySource:
    def __init__(self,csv_path:Path,simulation_config_loader:Callable[[str],dict|None]):
        self.csv_path=csv_path; self.simulation_config_loader=simulation_config_loader
    def load(self,request:ReplayRequest)->tuple[list[Telemetry],dict]:
        config=self.simulation_config_loader(request.mission_id)
        if config:
            from .simulation import build_mission
            from .schemas import SimulationRequest
            samples=build_mission(SimulationRequest.model_validate(config)).telemetry; source={"type":"stored_simulation","configuration":config}
        else:
            samples=[]
            if self.csv_path.exists():
                with self.csv_path.open(encoding="utf-8",newline="") as handle:
                    for row in csv.DictReader(handle):
                        if row.get("mission_id")==request.mission_id: samples.append(csv_row_to_telemetry(row))
            source={"type":"historical_csv","path":str(self.csv_path),"synthetic_dataset":True}
        if request.engine_id: samples=[x for x in samples if x.engine_id==request.engine_id]
        if request.start_time: samples=[x for x in samples if x.timestamp>=request.start_time]
        if request.end_time: samples=[x for x in samples if x.timestamp<=request.end_time]
        samples.sort(key=lambda x:x.timestamp)
        if not samples: raise ValueError("mission or requested replay interval has no telemetry")
        return samples,source

@dataclass
class ReplaySession:
    replay_id:str; request:ReplayRequest; samples:list[Telemetry]; source:dict
    processor:Callable[[Telemetry,TwinEngine],tuple[TwinAssessment,EngineState]]
    twin:TwinEngine=field(default_factory=TwinEngine); position:int=0; paused:bool=False
    assessments:list[TwinAssessment]=field(default_factory=list); states:list[EngineState]=field(default_factory=list)
    def status(self):
        current=self.samples[self.position-1].timestamp if self.position else self.samples[0].timestamp
        return {"replay_id":self.replay_id,"mission_id":self.request.mission_id,"engine_id":self.samples[0].engine_id,
            "start_time":self.samples[0].timestamp,"end_time":self.samples[-1].timestamp,"speed":self.request.speed,
            "paused":self.paused,"position":self.position,"total_samples":len(self.samples),"current_time":current,
            "completed":self.position>=len(self.samples),"source":self.source}
    def advance(self,virtual_seconds:float):
        if self.paused or self.position>=len(self.samples): return []
        interval=(self.samples[1].timestamp-self.samples[0].timestamp).total_seconds() if len(self.samples)>1 else 1
        count=max(1,int(math.ceil(virtual_seconds*self.request.speed/max(interval,1e-6))))
        output=[]
        for sample in self.samples[self.position:min(len(self.samples),self.position+count)]:
            assessment,state=self.processor(sample,self.twin); self.assessments.append(assessment); self.states.append(state)
            output.append({"telemetry":sample,"assessment":assessment,"state":state})
        self.position+=len(output); return output
    def seek(self,time_seconds:float):
        target=self.samples[0].timestamp.timestamp()+time_seconds
        index=next((i for i,x in enumerate(self.samples) if x.timestamp.timestamp()>=target),len(self.samples))
        self.twin=TwinEngine(); self.position=0; self.assessments=[]; self.states=[]
        # Rebuild causal windows through, but not including, the requested position.
        for sample in self.samples[:index]:
            assessment,state=self.processor(sample,self.twin); self.assessments.append(assessment); self.states.append(state)
        self.position=index; return self.status()

class ReplayManager:
    def __init__(self,source:MissionTelemetrySource,processor): self.source=source; self.processor=processor; self.sessions={}; self._lock=RLock()
    def create(self,request:ReplayRequest):
        samples,metadata=self.source.load(request); replay_id=str(uuid.uuid4())
        session=ReplaySession(replay_id,request,samples,metadata,self.processor)
        with self._lock: self.sessions[replay_id]=session
        return session
    def get(self,replay_id):
        session=self.sessions.get(replay_id)
        if not session: raise KeyError(replay_id)
        return session

def analyze_mission(session:ReplaySession)->dict:
    if session.position<len(session.samples):
        was_paused=session.paused; session.paused=False
        session.advance((session.samples[-1].timestamp-session.samples[0].timestamp).total_seconds()+1)
        session.paused=was_paused
    samples=session.samples; states=session.states; assessments=session.assessments
    cht=[max(getattr(x,f"cylinder_head_temp_{i}_c") for i in range(1,5)) for x in samples]
    egt=[max(getattr(x,f"exhaust_gas_temp_{i}_c") for i in range(1,5)) for x in samples]
    intervals=[(samples[i].timestamp-samples[i-1].timestamp).total_seconds() for i in range(1,len(samples))]
    fuel=sum((samples[i-1].fuel_flow_lph+samples[i].fuel_flow_lph)*.5*intervals[i-1]/3600 for i in range(1,len(samples)))
    abnormal_threshold=ThresholdConfig().value("anomaly_alert_score")
    abnormal=sum(intervals[i-1] for i in range(1,len(samples)) if assessments[i].anomaly_score>=abnormal_threshold)
    events={}
    for state in states:
        for item in state.faults.diagnostics:
            event=events.setdefault(item.fault_code,{"fault_code":item.fault_code,"fault_name":item.fault_name,"first_detected":item.first_detected,
                "last_detected":item.last_detected,"maximum_engineering_score":item.engineering_score,"maximum_severity":item.severity,"evidence":item.evidence})
            event["last_detected"]=item.last_detected
            if item.engineering_score>event["maximum_engineering_score"]: event.update(maximum_engineering_score=item.engineering_score,maximum_severity=item.severity,evidence=item.evidence)
    health=[x.health.overall_index for x in states]; degradation=[x.degradation.cumulative_damage_index for x in states]
    elapsed=max((samples[-1].timestamp-samples[0].timestamp).total_seconds()/3600,1e-9)
    recommendations=list(dict.fromkeys(a.maintenance_advisory for a in assessments if a.predicted_fault!="Healthy"))
    return {"mission_summary":{"mission_id":samples[0].mission_id,"engine_id":samples[0].engine_id,"start_time":samples[0].timestamp,
        "end_time":samples[-1].timestamp,"duration_seconds":int((samples[-1].timestamp-samples[0].timestamp).total_seconds()),"samples":len(samples),"source":session.source},
        "maximum_cht_c":max(cht),"maximum_egt_c":max(egt),"minimum_oil_pressure_kpa":min(x.oil_pressure_kpa for x in samples),
        "maximum_vibration_rms":max(x.vibration_rms for x in samples),"fuel_usage_liters":round(fuel,4),"time_spent_abnormal_seconds":round(abnormal,3),
        "fault_events":list(events.values()),"health_trend":{"start":health[0],"end":health[-1],"minimum":min(health),"change":round(health[-1]-health[0],3),"slope_per_hour":round((health[-1]-health[0])/elapsed,4)},
        "degradation_trend":{"start":degradation[0],"end":degradation[-1],"maximum":max(degradation),"change":round(degradation[-1]-degradation[0],3)},
        "maintenance_recommendations":recommendations or ["No prototype diagnostic maintenance recommendation generated."],
        "environment_conditions":{"altitude_m":{"minimum":min(x.altitude_m for x in samples),"maximum":max(x.altitude_m for x in samples)},
            "ambient_temperature_c":{"minimum":min(x.ambient_temperature_c for x in samples),"maximum":max(x.ambient_temperature_c for x in samples)},
            "ambient_pressure_kpa":{"minimum":min(x.ambient_pressure_kpa for x in samples if x.ambient_pressure_kpa is not None),"maximum":max(x.ambient_pressure_kpa for x in samples if x.ambient_pressure_kpa is not None)},
            "humidity_percent":{"minimum":min(x.humidity_percent for x in samples if x.humidity_percent is not None),"maximum":max(x.humidity_percent for x in samples if x.humidity_percent is not None)}},
        "rul_proxy":{"start_hours":states[0].prediction.rul_hours,"end_hours":states[-1].prediction.rul_hours,"method":states[-1].prediction.method},
        "deterministic_replay":True,"notice":"Synthetic/prototype analysis; not manufacturer-approved or flight-validation evidence."}

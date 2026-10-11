"""Deterministic simulated missions; not validated engine physics or limits."""
from datetime import datetime, timedelta, timezone
import math, random
from pydantic import BaseModel
from .schemas import DegradationScenario, MissionProfile, SimulationRequest, Telemetry

NOTICE="Generated prototype mission; not validated aircraft-engine behavior."
GENERATOR_VERSION="mission-simulator-v2"

def full_mission_point(progress:float)->tuple[str,float,float,float]:
    """Conceptual phase schedule: (phase, throttle %, altitude m, ambient degC)."""
    if progress<.08: return "ENGINE_START",18,0,20
    if progress<.17: return "WARM_UP",28,0,20
    if progress<.25: return "GROUND",32,0,20
    if progress<.35: return "TAKEOFF",94,350,17.7
    if progress<.50: return "CLIMB",82,350+4200*(progress-.35)/.15,17.7-27.3*(progress-.35)/.15
    if progress<.75: return "CRUISE",66,4550,-9.6
    if progress<.88: return "DESCENT",40,4550-4050*(progress-.75)/.13,-9.6+26.3*(progress-.75)/.13
    if progress<.95: return "LANDING",25,200,18.7
    return "SHUTDOWN",0,0,20

class ProfilePoint(BaseModel):
    time_seconds:int; value:float; unit:str
class ScenarioTruth(BaseModel):
    time_seconds:int; phase:str; scenario:str; fault_active:bool; progression:float
class SimulationMission(BaseModel):
    mission_id:str; engine_id:str; start_time:datetime; duration_seconds:int; profile:MissionProfile
    degradation_scenario:DegradationScenario; seed:int; interval_seconds:int; environment_parameters:dict
    altitude_profile:list[ProfilePoint]; ambient_temperature_profile:list[ProfilePoint]
    throttle_profile:list[ProfilePoint]; rpm_profile:list[ProfilePoint]; telemetry:list[Telemetry]
    generator_version:str=GENERATOR_VERSION; fault_onset_seconds:int|None=None
    scenario_truth:list[ScenarioTruth]
    model_notice:str=NOTICE

def build_mission(request:SimulationRequest)->SimulationMission:
    rng=random.Random(request.seed); count=request.duration_minutes*60//request.interval_seconds
    start=request.start_time or datetime.now(timezone.utc)
    mission_id=request.mission_id or f"SIM_{request.profile.value}_{start.strftime('%Y%m%dT%H%M%S')}_{request.seed}"
    output=[]; truth=[]; profiles={k:[] for k in ("altitude","ambient","throttle","rpm")}; oil_temp=None; previous_rpm=0.0; frozen_cht=None
    for i in range(count):
        seconds=i*request.interval_seconds; progress=i/max(count-1,1); throttle=65.; altitude=3500.; ambient=-2.; humidity=40.; phase=request.profile.value
        if request.profile==MissionProfile.HIGH_ALTITUDE: altitude=3500+4000*min(1,progress*1.4); throttle=78-8*progress; ambient=15-.0065*altitude; humidity=25
        elif request.profile==MissionProfile.ENDURANCE: altitude=5200+150*math.sin(i/60); throttle=50+3*math.sin(i/30); ambient=-10+1.5*math.sin(i/80); humidity=30
        elif request.profile==MissionProfile.HOT_WEATHER: altitude=800+150*math.sin(i/50); throttle=72+2*math.sin(i/25); ambient=43+3*math.sin(i/70); humidity=65
        elif request.profile==MissionProfile.RAPID_THROTTLE: altitude=3500; throttle=25+70*(.5+.5*math.sin(i*.35)); ambient=-3; humidity=38
        elif request.profile==MissionProfile.NORMAL_CRUISE: altitude=4200+80*math.sin(i/75); throttle=64+1.5*math.sin(i/45); ambient=-6; humidity=42
        elif request.profile==MissionProfile.FULL_MISSION: phase,throttle,altitude,ambient=full_mission_point(progress)
        pressure=101.325*max(0,1-2.25577e-5*altitude)**5.2559; density=(pressure/101.325)*(288.15/(ambient+273.15))
        load=min(108,throttle*(.72+.22*density)); target_rpm=0 if phase=="SHUTDOWN" else max(0,620+20.5*throttle+35*load/100)
        rpm=target_rpm if i==0 else previous_rpm+.35*(target_rpm-previous_rpm)+rng.gauss(0,10)
        scenario=request.degradation_scenario; degradation=request.degradation_severity*max(0,(progress-.2)/.8); instability=0.
        truth.append(ScenarioTruth(time_seconds=seconds,phase=phase,scenario=scenario.value,
            fault_active=scenario!=DegradationScenario.NONE and progress>.2,progression=round(degradation,6)))
        if scenario==DegradationScenario.COMBUSTION_INSTABILITY:
            instability=degradation*(110*math.sin(i*.31)+55*math.sin(i*.09)); rpm+=instability
        elif scenario==DegradationScenario.MISFIRE:
            rpm-=degradation*(80+65*abs(math.sin(i*.61)))
        previous_rpm=rpm; cht_base=ambient+67+1.3*load+.0014*altitude-8*density; egt_base=ambient+410+3.2*load
        oil_target=ambient+72+.35*load; oil_temp=oil_target if oil_temp is None else oil_temp+.08*(oil_target-oil_temp)
        oil_pressure=120+.12*rpm-1.1*max(0,oil_temp-105); fuel=max(0,rpm/2700*load/100*50)
        vibration=.5+.0007*rpm+rng.gauss(0,.06); timing=18+.055*load+.00035*altitude
        alternator=28.1 if rpm>900 else 24.4; battery=25.1 if alternator>27 else 24.3
        cht=[cht_base+j*1.5+rng.gauss(0,.6) for j in range(4)]; egt=[egt_base+j*2+rng.gauss(0,2) for j in range(4)]
        if scenario==DegradationScenario.COOLING_DEGRADATION: cht=[x+70*degradation*(1-.12*j) for j,x in enumerate(cht)]; oil_temp+=8*degradation
        elif scenario==DegradationScenario.INJECTOR_DEGRADATION: fuel*=1-.22*degradation; egt[0]+=130*degradation; cht[0]+=25*degradation; timing+=3*degradation
        elif scenario==DegradationScenario.LUBRICATION_DEGRADATION: oil_pressure-=240*degradation; oil_temp+=30*degradation; vibration+=3*degradation
        elif scenario==DegradationScenario.SENSOR_DRIFT: cht[0]+=75*degradation
        elif scenario==DegradationScenario.COMBUSTION_INSTABILITY: egt=[x+instability*(.5 if j%2==0 else -.35) for j,x in enumerate(egt)]; vibration+=abs(instability)/35
        elif scenario==DegradationScenario.VIBRATION_ANOMALY: vibration+=8*degradation*(.6+.4*abs(math.sin(i*.55)))
        elif scenario==DegradationScenario.MISFIRE: egt[0]-=125*degradation; cht[0]-=28*degradation; vibration+=2.8*degradation
        elif scenario==DegradationScenario.ALTERNATOR_DEGRADATION:
            alternator-=5*degradation; battery-=1.5*degradation
        elif scenario==DegradationScenario.SENSOR_FREEZE and progress>.2:
            if frozen_cht is None: frozen_cht=cht[0]
            cht[0]=frozen_cht
        telemetry=Telemetry(engine_id=request.engine_id,mission_id=mission_id,timestamp=start+timedelta(seconds=seconds),mission_phase=phase,
            rpm=max(0,min(3200,rpm)),**{f"cylinder_head_temp_{j+1}_c":max(-45,min(270,cht[j])) for j in range(4)},
            **{f"exhaust_gas_temp_{j+1}_c":max(-45,min(950,egt[j])) for j in range(4)},oil_temperature_c=max(-45,min(155,oil_temp)),
            oil_pressure_kpa=max(0,min(700,oil_pressure)),fuel_flow_lph=max(0,min(75,fuel)),vibration_rms=max(0,min(25,vibration)),
            alternator_voltage=alternator,alternator_state="ONLINE" if alternator>27 else "OFFLINE",battery_voltage=battery,
            battery_current_a=8 if alternator>27 else -4,injection_timing_deg=max(5,min(35,timing)),engine_load_percent=load,
            throttle_percent=throttle,altitude_m=altitude,ambient_temperature_c=ambient,ambient_pressure_kpa=pressure,humidity_percent=humidity)
        output.append(telemetry)
        for name,value,unit in (("altitude",altitude,"m"),("ambient",ambient,"degC"),("throttle",throttle,"percent"),("rpm",telemetry.rpm,"rpm")):
            profiles[name].append(ProfilePoint(time_seconds=seconds,value=round(value,3),unit=unit))
    return SimulationMission(mission_id=mission_id,engine_id=request.engine_id,start_time=start,duration_seconds=request.duration_minutes*60,
        profile=request.profile,degradation_scenario=request.degradation_scenario,seed=request.seed,interval_seconds=request.interval_seconds,
        fault_onset_seconds=next((item.time_seconds for item in truth if item.fault_active),None),scenario_truth=truth,
        environment_parameters={"pressure_model":"standard-atmosphere-shaped prototype proxy","humidity_available":True,
            "units":{"altitude":"m","temperature":"degC","pressure":"kPa","humidity":"percent"}},altitude_profile=profiles["altitude"],
        ambient_temperature_profile=profiles["ambient"],throttle_profile=profiles["throttle"],rpm_profile=profiles["rpm"],telemetry=output)

def simulate(request:SimulationRequest)->list[Telemetry]:
    """Compatibility function retained for existing adapters/callers."""
    return build_mission(request).telemetry

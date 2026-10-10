import asyncio, csv, json, os, re, secrets, uuid
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .schemas import SimulationRequest, Telemetry, TwinAssessment
from .simulation import build_mission
from .store import TelemetryStore
from .twin import TwinEngine
from .adapters.base import TelemetryPacket
from .adapters.factory import create_adapter
from .adapters.base import TelemetryAdapter
from .replay import (AdvanceRequest, MissionTelemetrySource, ReplayManager, ReplayRequest, SeekRequest, analyze_mission, csv_row_to_telemetry)
from .auth import AuthRepository,AuthService,AuthenticationError,CreateUserRequest,LoginRequest,PasswordHasher,Role,TokenService
from .security import RateLimiter,authorization_dependency,request_id_context

twin: TwinEngine | None=None; store: TelemetryStore | None=None; telemetry_adapter: TelemetryAdapter | None=None; replay_manager: ReplayManager | None=None
auth_service:AuthService|None=None; rate_limiter:RateLimiter|None=None
demo_task:asyncio.Task|None=None; demo_status={"enabled":False,"running":False}

def allow_demo(): return None

def require(*roles:Role):
    return allow_demo if settings.demo_mode else authorization_dependency(lambda:auth_service,lambda:rate_limiter,set(roles))
ALL_ROLES=(Role.ADMIN,Role.OPERATOR,Role.MAINTENANCE_ENGINEER,Role.ANALYST,Role.VIEWER)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global store, twin, telemetry_adapter, replay_manager, auth_service, rate_limiter, demo_task
    twin=TwinEngine()
    store=TelemetryStore(settings.database_path)
    telemetry_adapter=create_adapter(settings.adapter_mode,settings.can_mapping_path,settings.socketcan_channel)
    telemetry_adapter.start()
    source=MissionTelemetrySource(settings.replay_data_path,store.simulation_config)
    replay_manager=ReplayManager(source,lambda sample,session_twin:process_telemetry_state(sample,persist=False,twin_instance=session_twin))
    secret=settings.token_secret or secrets.token_urlsafe(48)
    auth_service=AuthService(AuthRepository(settings.database_path),TokenService(secret,settings.token_lifetime_minutes),PasswordHasher())
    rate_limiter=RateLimiter(settings.requests_per_minute)
    bootstrap_password=os.getenv("DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_username=os.getenv("DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME","admin")
    if bootstrap_password and auth_service.repository.count_users()==0:
        auth_service.create_user(bootstrap_username,bootstrap_password,Role.ADMIN)
    if settings.demo_mode:
        demo_task=asyncio.create_task(feed_demo_dataset())
    yield
    if demo_task:
        demo_task.cancel()
        try: await demo_task
        except asyncio.CancelledError: pass
    telemetry_adapter.stop()

async def feed_demo_dataset():
    """Continuously feed a CSV mission segment through the normal twin path."""
    global demo_status
    rows=[]
    with settings.replay_data_path.open(encoding="utf-8",newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("mission_id")==settings.demo_mission_id: rows.append(row)
    if not rows:
        demo_status={"enabled":True,"running":False,"error":"configured dataset mission was not found"}; return
    # Begin with one minute of healthy context, then reach the clearly
    # observable low-oil-pressure region quickly during a judge demo.
    first_fault=next((i for i,row in enumerate(rows)
        if float(row["rpm"])>1000 and float(row["oil_pressure_kpa"])<150),len(rows)//2)
    rows=rows[max(0,first_fault-60):]
    demo_status={"enabled":True,"running":True,"source":"backend/dataset/data/aero_engine_full.csv",
        "dataset_mission":settings.demo_mission_id,"engine_id":"DATASET_ENGINE_010","samples_in_loop":len(rows),"position":0}
    assert store is not None
    store.clear_engine("DATASET_ENGINE_010")
    virtual_clock=datetime.now(timezone.utc)
    while True:
        assert twin is not None
        twin.reset_engine_state("DATASET_ENGINE_010")
        base_time=virtual_clock; first_seconds=float(rows[0]["time_seconds"])
        for index,row in enumerate(rows):
            sample=csv_row_to_telemetry(row).model_copy(update={"engine_id":"DATASET_ENGINE_010",
                "mission_id":f"LIVE_{settings.demo_mission_id}",
                "timestamp":base_time+timedelta(seconds=float(row["time_seconds"])-first_seconds)})
            assessment,state=process_telemetry_state(sample,persist=True)
            demo_status.update(position=index+1,phase=sample.mission_phase,health_index=assessment.health_index,
                anomaly_score=assessment.anomaly_score,predicted_fault=assessment.predicted_fault,rul_hours=assessment.rul_hours,
                source_fault_label=row.get("fault_type"),last_timestamp=sample.timestamp.isoformat())
            await asyncio.sleep(.15)
        virtual_clock=sample.timestamp+timedelta(seconds=5)

app=FastAPI(title=settings.title,version=settings.version,lifespan=lifespan,
    description="Prototype digital-twin API. Generated test evidence only; not flight-certified.")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:5173","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["*"])

@app.middleware("http")
async def request_identity_and_audit(request:Request,call_next):
    supplied=request.headers.get("X-Request-ID","")
    request_id=supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}",supplied) else str(uuid.uuid4())
    token=request_id_context.set(request_id); request.state.request_id=request_id
    try:
        response=await call_next(request); status=response.status_code
    except Exception:
        status=500
        if auth_service: auth_service.repository.audit(request_id=request_id,actor=getattr(getattr(request.state,"principal",None),"username",None),role=getattr(getattr(getattr(request.state,"principal",None),"role",None),"value",None),method=request.method,path=request.url.path,status=status,event="request",detail="unhandled error",client_ip=request.client.host if request.client else None)
        request_id_context.reset(token); raise
    if auth_service: auth_service.repository.audit(request_id=request_id,actor=getattr(getattr(request.state,"principal",None),"username",None),role=getattr(getattr(getattr(request.state,"principal",None),"role",None),"value",None),method=request.method,path=request.url.path,status=status,event="request",detail=None,client_ip=request.client.host if request.client else None)
    response.headers["X-Request-ID"]=request_id; request_id_context.reset(token); return response

@app.get("/api/v1/health")
def health(): return {"status":"ok","version":settings.version,"mode":"dataset_demo" if settings.demo_mode else "prototype","flight_certified":False}

@app.get("/api/v1/demo/status")
def dataset_demo_status(): return demo_status

@app.post("/api/v1/auth/token")
def login(value:LoginRequest,request:Request):
    if auth_service is None: raise HTTPException(503,"authentication service unavailable")
    if rate_limiter and not rate_limiter.allow(f"login:{request.client.host if request.client else 'unknown'}"): raise HTTPException(429,"rate limit exceeded",headers={"Retry-After":"60"})
    try: return auth_service.authenticate(value.username,value.password)
    except AuthenticationError as exc: raise HTTPException(401,str(exc)) from exc

@app.post("/api/v1/auth/users",status_code=201,dependencies=[Depends(require(Role.ADMIN))])
def create_user(value:CreateUserRequest):
    assert auth_service is not None
    try: return auth_service.create_user(value.username,value.password,value.role)
    except Exception as exc: raise HTTPException(409,"user could not be created") from exc

@app.get("/api/v1/auth/audit",dependencies=[Depends(require(Role.ADMIN))])
def audit_events(limit:int=Query(100,ge=1,le=1000)):
    assert auth_service is not None
    return auth_service.repository.audit_events(limit)

@app.post("/api/v1/telemetry",response_model=TwinAssessment,status_code=201,dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR))])
def ingest(value: Telemetry):
    return process_telemetry(value)

@app.post("/api/v1/telemetry/synchronize",status_code=201,dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR))])
def synchronize_telemetry(value: Telemetry):
    """Return the assessment and quality-aware state for this exact sample.

    Existing ingestion contracts remain unchanged. In particular, rejected or
    suspect measurements return their own state, never an older valid snapshot.
    """
    assessment, state = process_telemetry_state(value)
    return {"telemetry": value, "assessment": assessment, "state": state}

def process_telemetry(value: Telemetry,persist:bool=True):
    """Single ingestion path shared by live, adapter, replay, and simulation inputs."""
    assessment,_=process_telemetry_state(value,persist=persist)
    return assessment

def process_telemetry_state(value:Telemetry,persist:bool=True,twin_instance:TwinEngine|None=None):
    engine=twin_instance or twin
    assert engine is not None
    assessment,state=engine.synchronize(value)
    assert store is not None
    if persist: store.add(value,assessment,state)
    return assessment,state

@app.post("/api/v1/telemetry/batch",response_model=list[TwinAssessment],status_code=201,dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR))])
def ingest_batch(values: list[Telemetry]):
    if not values or len(values)>5000: raise HTTPException(422,"batch must contain 1 to 5000 samples")
    return [ingest(value) for value in values]

@app.get("/api/v1/engines/{engine_id}/latest",dependencies=[Depends(require(*ALL_ROLES))])
def latest(engine_id: str):
    assert store is not None
    result=store.latest(engine_id)
    if not result: raise HTTPException(404,"engine has no ingested telemetry")
    return result

@app.get("/api/v1/engines/{engine_id}/history",dependencies=[Depends(require(*ALL_ROLES))])
def history(engine_id: str,limit:int=Query(100,ge=1,le=settings.max_history_rows)):
    assert store is not None
    return store.history(engine_id,limit)

@app.post("/api/v1/simulations",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def run_simulation(request: SimulationRequest, persist:bool=False):
    assert store is not None
    mission=build_mission(request); assessments=[]; states=[]
    assert twin is not None
    twin.reset_engine_state(mission.engine_id)
    # The exact same processor used by POST /telemetry is used here. Persist only
    # controls telemetry history; deterministic mission configuration is always stored.
    for sample in mission.telemetry:
        assessment,state=process_telemetry_state(sample,persist=persist)
        assessments.append(assessment); states.append(state)
    resolved=request.model_copy(update={"mission_id":mission.mission_id,"start_time":mission.start_time})
    store.save_simulation(mission.mission_id,mission.engine_id,mission.start_time.isoformat(),mission.seed,resolved.model_dump(mode="json"))
    return {**mission.model_dump(mode="json"),"sample_count":len(mission.telemetry),
        "assessments":[x.model_dump(mode="json") for x in assessments],
        "states":[x.model_dump(mode="json") for x in states],"persisted_telemetry":persist}

@app.get("/api/v1/simulations/{mission_id}/configuration",dependencies=[Depends(require(*ALL_ROLES))])
def simulation_configuration(mission_id:str):
    assert store is not None
    config=store.simulation_config(mission_id)
    if config is None: raise HTTPException(404,"simulation mission configuration not found")
    return config

@app.post("/api/v1/simulations/{mission_id}/replay",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def replay_simulation(mission_id:str,persist:bool=False):
    assert store is not None
    config=store.simulation_config(mission_id)
    if config is None: raise HTTPException(404,"simulation mission configuration not found")
    return run_simulation(SimulationRequest.model_validate(config),persist=persist)

@app.get("/api/v1/missions",dependencies=[Depends(require(*ALL_ROLES))])
def missions(limit:int=Query(120,ge=1,le=500)):
    if not settings.replay_data_path.exists(): raise HTTPException(503,"replay dataset is unavailable")
    found={}
    with settings.replay_data_path.open(encoding="utf-8",newline="") as handle:
        for row in csv.DictReader(handle):
            mid=row["mission_id"]
            if mid not in found: found[mid]={"mission_id":mid,"engine_id":row["engine_id"],"outcome":row["mission_outcome"],"faults":set(),"samples":0}
            found[mid]["samples"]+=1
            if row["fault_type"]!="Healthy": found[mid]["faults"].add(row["fault_type"])
            if len(found)>=limit and mid not in found: break
    return [{**x,"faults":sorted(x["faults"])} for x in list(found.values())[:limit]]

@app.get("/api/v1/missions/{mission_id}/replay",dependencies=[Depends(require(*ALL_ROLES))])
def replay(mission_id:str,offset:int=Query(0,ge=0),limit:int=Query(500,ge=1,le=5000)):
    rows=[]
    if not settings.replay_data_path.exists(): raise HTTPException(503,"replay dataset is unavailable")
    with settings.replay_data_path.open(encoding="utf-8",newline="") as handle:
        for row in csv.DictReader(handle):
            if row["mission_id"]==mission_id:
                if offset: offset-=1; continue
                rows.append(row)
                if len(rows)>=limit: break
    if not rows: raise HTTPException(404,"mission not found or offset exceeds mission length")
    return {"mission_id":mission_id,"samples":rows,"returned":len(rows)}

@app.post("/api/v1/replays",status_code=201,dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def create_replay(request:ReplayRequest):
    assert replay_manager is not None
    try: return replay_manager.create(request).status()
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc

def _replay_session(replay_id:str):
    assert replay_manager is not None
    try: return replay_manager.get(replay_id)
    except KeyError as exc: raise HTTPException(404,"replay session not found") from exc

@app.get("/api/v1/replays/{replay_id}",dependencies=[Depends(require(*ALL_ROLES))])
def replay_status(replay_id:str): return _replay_session(replay_id).status()

@app.post("/api/v1/replays/{replay_id}/pause",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def pause_replay(replay_id:str):
    session=_replay_session(replay_id); session.paused=True; return session.status()

@app.post("/api/v1/replays/{replay_id}/resume",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def resume_replay(replay_id:str):
    session=_replay_session(replay_id); session.paused=False; return session.status()

@app.post("/api/v1/replays/{replay_id}/seek",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def seek_replay(replay_id:str,request:SeekRequest): return _replay_session(replay_id).seek(request.time_seconds)

@app.post("/api/v1/replays/{replay_id}/advance",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.ANALYST))])
def advance_replay(replay_id:str,request:AdvanceRequest):
    session=_replay_session(replay_id); output=session.advance(request.virtual_seconds)
    return {"status":session.status(),"processed":len(output),"frames":output}

@app.get("/api/v1/replays/{replay_id}/report",dependencies=[Depends(require(*ALL_ROLES))])
def replay_report(replay_id:str): return analyze_mission(_replay_session(replay_id))

@app.get("/api/v1/missions/{mission_id}/report",dependencies=[Depends(require(*ALL_ROLES))])
def mission_report(mission_id:str,engine_id:str|None=None,start_time:datetime|None=None,end_time:datetime|None=None):
    assert replay_manager is not None
    try: session=replay_manager.create(ReplayRequest(mission_id=mission_id,engine_id=engine_id,start_time=start_time,end_time=end_time,speed=100))
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
    return analyze_mission(session)

@app.get("/api/v1/model/report",dependencies=[Depends(require(Role.ADMIN,Role.ANALYST,Role.MAINTENANCE_ENGINEER))])
def model_report():
    if not settings.metrics_path.exists(): raise HTTPException(503,"model report is unavailable")
    data=json.loads(settings.metrics_path.read_text(encoding="utf-8"))
    gate=data.get("release_gate",{})
    ready=bool(gate.get("passed",data.get("validation",{}).get("recall_requirement",{}).get("passed") and data.get("test",{}).get("recall_requirement",{}).get("passed")))
    return {"model":data.get("model"),"model_version":data.get("model_version"),"training_dataset_version":data.get("training_dataset_version"),
            "feature_schema_version":data.get("feature_schema_version"),"training_timestamp":data.get("training_timestamp"),"evaluation_timestamp":data.get("evaluation_timestamp"),
            "split_strategy":data.get("split_strategy"),"metrics":{k:data.get(k) for k in ("time_forward","validation","challenge","test") if data.get(k) is not None},
            "validation":data.get("validation"),"test":data.get("test"),"release_gate":gate,
            "MODEL_STATUS":data.get("model_status","NOT_VALIDATED") if not ready else data.get("model_status","VALIDATED_CANDIDATE"),
            "RELEASE_READINESS":data.get("release_readiness","NOT_RELEASE_READY") if not ready else data.get("release_readiness","RELEASE_CANDIDATE_REQUIRES_REAL_DATA_VALIDATION"),
            "release_gate_passed":ready,
            "warning":"Generated dataset performance is not evidence of flightworthiness."}

@app.get("/api/v1/engines/{engine_id}/state",dependencies=[Depends(require(*ALL_ROLES))])
def twin_state(engine_id: str):
    assert twin is not None
    state=twin.latest_state(engine_id)
    if state is None: raise HTTPException(404,"engine has no synchronized twin state")
    return state

@app.get("/api/v1/adapters/health",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR,Role.MAINTENANCE_ENGINEER))])
def adapter_health():
    if telemetry_adapter is None: raise HTTPException(503,"telemetry adapter is not initialized")
    return telemetry_adapter.adapter_health()

@app.post("/api/v1/adapters/packets",dependencies=[Depends(require(Role.ADMIN,Role.OPERATOR))])
def ingest_adapter_packet(packet: TelemetryPacket):
    """Validate/order a transport-neutral packet; complete signal sets enter the twin."""
    if telemetry_adapter is None: raise HTTPException(503,"telemetry adapter is not initialized")
    ready=telemetry_adapter.ingest_packet(packet)
    synchronized=[]; invalid=[]
    for item in ready:
        values={**item.signals,"timestamp":item.timestamp,"engine_id":item.engine_id,"mission_id":item.mission_id,
            "mission_phase":item.protocol_metadata.extra.get("mission_phase","unknown")}
        try: synchronized.append(ingest(Telemetry.model_validate(values)))
        except Exception as exc: invalid.append({"sequence_number":item.sequence_number,"reason":"packet does not yet contain a complete valid telemetry state"})
    return {"accepted_packets":len(ready),"synchronized_states":len(synchronized),"buffered":telemetry_adapter.adapter_health().buffered_messages,
        "incomplete_or_invalid_packets":invalid,"assessments":synchronized}

"""Transport-neutral telemetry packet validation and ordering."""
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ..states import QualityFlag

class AdapterMode(str,Enum):
    SIMULATOR="SIMULATOR"; CAN="CAN"; SOCKETCAN="SOCKETCAN"; FADEC="FADEC"

class ClockMetadata(BaseModel):
    clock_source:str="source_clock"
    synchronized:bool=False
    estimated_offset_ms:float|None=None
    uncertainty_ms:float|None=None

class ProtocolMetadata(BaseModel):
    protocol:str
    version:str|None=None
    channel:str|None=None
    frame_id:str|None=None
    clock:ClockMetadata=Field(default_factory=ClockMetadata)
    extra:dict[str,Any]=Field(default_factory=dict)

class TelemetryPacket(BaseModel):
    model_config=ConfigDict(extra="forbid")
    timestamp:datetime
    sequence_number:int=Field(ge=0)
    source:str=Field(min_length=1,max_length=64)
    engine_id:str=Field(min_length=1,max_length=64)
    mission_id:str=Field(min_length=1,max_length=64)
    signals:dict[str,float|int|str|bool|None]
    quality:dict[str,QualityFlag]=Field(default_factory=dict)
    protocol_metadata:ProtocolMetadata
    @field_validator("timestamp")
    @classmethod
    def aware(cls,value):
        if value.tzinfo is None: raise ValueError("packet timestamp must include a timezone")
        return value

class AdapterHealth(BaseModel):
    mode:AdapterMode
    source:str
    connected:bool=False
    status:str="disconnected"
    last_message:datetime|None=None
    messages_received:int=0
    messages_dropped:int=0
    sequence_errors:int=0
    stale_messages:int=0
    duplicate_messages:int=0
    invalid_frames:int=0
    missing_packets:int=0
    recovered_messages:int=0
    buffered_messages:int=0
    detail:str|None=None

class TelemetryAdapter(ABC):
    """Base adapter with ordered delivery, buffering, and loss recovery."""
    def __init__(self,mode:AdapterMode,source:str,max_age_seconds:float=30,max_future_skew_seconds:float=5,
                 buffer_size:int=256,recovery_timeout_seconds:float=2):
        self.health=AdapterHealth(mode=mode,source=source); self.max_age_seconds=max_age_seconds
        self.max_future_skew_seconds=max_future_skew_seconds; self.buffer_size=buffer_size
        self.recovery_timeout_seconds=recovery_timeout_seconds; self._expected:dict[tuple[str,str],int]={}
        self._seen:dict[tuple[str,str],deque[int]]={}; self._buffer:dict[tuple[str,str],dict[int,TelemetryPacket]]={}
        self._missing:dict[tuple[str,str],set[int]]={}
        self._gap_since:dict[tuple[str,str],datetime]={}; self._lock=RLock()

    def start(self): self.health.connected=True; self.health.status="connected"
    def stop(self): self.health.connected=False; self.health.status="disconnected"
    def adapter_health(self)->AdapterHealth:
        buffered=sum(len(x) for x in self._buffer.values()); self.health.buffered_messages=buffered
        return self.health.model_copy(deep=True)

    def invalid_frame(self,detail:str):
        self.health.invalid_frames+=1; self.health.messages_dropped+=1; self.health.detail=detail

    def ingest_packet(self,packet:TelemetryPacket,received_at:datetime|None=None)->list[TelemetryPacket]:
        now=received_at or datetime.now(timezone.utc); key=(packet.source,packet.engine_id)
        with self._lock:
            self.health.messages_received+=1
            age=(now-packet.timestamp.astimezone(timezone.utc)).total_seconds()
            if age>self.max_age_seconds or age < -self.max_future_skew_seconds:
                self.health.stale_messages+=1; self.health.messages_dropped+=1; return []
            seen=self._seen.setdefault(key,deque(maxlen=2048))
            if packet.sequence_number in seen or packet.sequence_number in self._buffer.setdefault(key,{}):
                self.health.duplicate_messages+=1; self.health.messages_dropped+=1; return []
            expected=self._expected.get(key)
            if expected is None: expected=packet.sequence_number
            if packet.sequence_number<expected:
                self.health.sequence_errors+=1; self.health.messages_dropped+=1; return []
            if packet.sequence_number>expected:
                self.health.sequence_errors+=1
                missing_set=self._missing.setdefault(key,set()); before=len(missing_set)
                missing_set.update(set(range(expected,packet.sequence_number))-set(self._buffer[key]))
                self.health.missing_packets+=len(missing_set)-before
                if len(self._buffer[key])>=self.buffer_size:
                    self.health.messages_dropped+=1; self.health.detail="reorder buffer full"; return []
                self._buffer[key][packet.sequence_number]=packet; self._gap_since.setdefault(key,now); return []
            ready=[packet]; seen.append(packet.sequence_number); expected+=1
            if packet.sequence_number in self._missing.setdefault(key,set()):
                self._missing[key].remove(packet.sequence_number); self.health.missing_packets=max(0,self.health.missing_packets-1)
            while expected in self._buffer[key]:
                recovered=self._buffer[key].pop(expected); ready.append(recovered); seen.append(expected)
                self.health.recovered_messages+=1
                if expected in self._missing[key]: self._missing[key].remove(expected); self.health.missing_packets=max(0,self.health.missing_packets-1)
                expected+=1
            self._expected[key]=expected
            if not self._buffer[key]: self._gap_since.pop(key,None)
            self.health.last_message=ready[-1].timestamp; return ready

    def recover_loss(self,now:datetime|None=None)->list[TelemetryPacket]:
        """After timeout, declare unresolved gaps lost and release buffered packets."""
        now=now or datetime.now(timezone.utc); released=[]
        with self._lock:
            for key,since in list(self._gap_since.items()):
                if (now-since).total_seconds()<self.recovery_timeout_seconds: continue
                buffer=self._buffer[key]
                if not buffer: continue
                first=min(buffer); expected=self._expected.get(key,first); lost=max(0,first-expected)
                self.health.messages_dropped+=lost; self.health.missing_packets=max(0,self.health.missing_packets-lost)
                self._missing.setdefault(key,set()).difference_update(range(expected,first))
                self._expected[key]=first; self._gap_since.pop(key,None)
                self.health.messages_received-=1
                released.extend(self.ingest_packet(buffer.pop(first),received_at=now))
        return released

    @abstractmethod
    def poll(self)->list[TelemetryPacket]: ...

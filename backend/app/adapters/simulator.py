from datetime import datetime, timedelta, timezone
from pathlib import Path
from .base import AdapterMode, ClockMetadata, ProtocolMetadata, TelemetryAdapter, TelemetryPacket
from .can import RawCANFrame
from ..schemas import SimulationRequest
from ..simulation import simulate
from ..states import QualityFlag

class SimulatorAdapter(TelemetryAdapter):
    def __init__(self,request:SimulationRequest|None=None,**kwargs):
        super().__init__(AdapterMode.SIMULATOR,"SIMULATOR",**kwargs); self.request=request or SimulationRequest(profile="endurance",duration_minutes=1); self._queue=[]
    def start(self):
        super().start()
        for sequence,item in enumerate(simulate(self.request)):
            signals=item.model_dump(exclude={"timestamp","engine_id","mission_id","mission_phase"})
            packet=TelemetryPacket(timestamp=item.timestamp,sequence_number=sequence,source="SIMULATOR",engine_id=item.engine_id,
                mission_id=item.mission_id,signals=signals,quality={k:QualityFlag.VALID for k in signals},
                protocol_metadata=ProtocolMetadata(protocol="SIMULATOR",version="1",clock=ClockMetadata(clock_source="UTC host",synchronized=True,estimated_offset_ms=0,uncertainty_ms=1),extra={"mission_phase":item.mission_phase,"synthetic":True}))
            self._queue.extend(self.ingest_packet(packet,received_at=item.timestamp))
    def poll(self): output,self._queue=self._queue,[]; return output

class SimulatedCANStream:
    """Produces deterministic raw frames for the sample synthetic CAN mapping."""
    def __init__(self,start:datetime|None=None): self.start=start or datetime.now(timezone.utc)
    def frames(self,count=10):
        for i in range(count):
            rpm=1800+i*20; throttle=55+i%5; raw=int(rpm/0.25)|(int(throttle/0.5)<<16)
            yield RawCANFrame(0x500,raw.to_bytes(8,"little"),self.start+timedelta(milliseconds=100*i))

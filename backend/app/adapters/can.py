"""Configuration-driven generic CAN decoding; no manufacturer IDs are embedded."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from .base import AdapterMode, ClockMetadata, ProtocolMetadata, TelemetryAdapter, TelemetryPacket
from ..states import QualityFlag

@dataclass(frozen=True)
class RawCANFrame:
    arbitration_id:int; data:bytes; timestamp:datetime; channel:str="synthetic-can"

class CANSignalDatabase:
    def __init__(self,path:Path):
        raw=json.loads(path.read_text(encoding="utf-8")); self.name=raw["name"]
        if raw.get("manufacturer_specific",True): raise ValueError("only explicitly non-manufacturer-specific mappings are accepted by the prototype")
        self.frames={int(k,0):v for k,v in raw["frames"].items()}
    def decode(self,frame:RawCANFrame)->dict:
        definition=self.frames.get(frame.arbitration_id)
        if not definition: raise ValueError(f"unmapped CAN frame 0x{frame.arbitration_id:X}")
        raw=int.from_bytes(frame.data,byteorder=definition.get("byte_order","little"),signed=False); signals={}
        for item in definition["signals"]:
            mask=(1<<item["length"])-1; value=(raw>>item["start_bit"])&mask
            if item.get("signed") and value&(1<<(item["length"]-1)): value-=1<<item["length"]
            signals[item["name"]]=value*item.get("scale",1)+item.get("offset",0)
        return {"signals":signals,"definition":definition}

class CANAdapter(TelemetryAdapter):
    def __init__(self,mapping_path:Path,source="CAN",**kwargs):
        super().__init__(AdapterMode.CAN,source,**kwargs); self.database=CANSignalDatabase(mapping_path); self._queue=[]
    def decode_frame(self,frame:RawCANFrame,engine_id:str,mission_id:str,sequence_number:int)->TelemetryPacket|None:
        try:
            decoded=self.database.decode(frame)
            return TelemetryPacket(timestamp=frame.timestamp,sequence_number=sequence_number,source=self.health.source,
                engine_id=engine_id,mission_id=mission_id,signals=decoded["signals"],
                quality={k:QualityFlag.VALID for k in decoded["signals"]},protocol_metadata=ProtocolMetadata(
                    protocol="CAN",channel=frame.channel,frame_id=f"0x{frame.arbitration_id:X}",
                    clock=ClockMetadata(clock_source="CAN adapter host",synchronized=False),extra={"signal_database":self.database.name}))
        except (ValueError,TypeError,KeyError) as exc:
            self.invalid_frame(str(exc)); return None
    def feed_frame(self,*args,**kwargs):
        packet=self.decode_frame(*args,**kwargs)
        if packet: self._queue.extend(self.ingest_packet(packet))
    def poll(self): output,self._queue=self._queue,[]; return output

"""Optional SocketCAN transport. Import/connect occurs only when explicitly started."""
from pathlib import Path
from .base import AdapterMode
from .can import CANAdapter

class SocketCANAdapter(CANAdapter):
    def __init__(self,mapping_path:Path,channel="can0",**kwargs):
        super().__init__(mapping_path,source="SOCKETCAN",**kwargs); self.health.mode=AdapterMode.SOCKETCAN; self.channel=channel; self._bus=None
    def start(self):
        try:
            import can
            self._bus=can.Bus(interface="socketcan",channel=self.channel)
            super().start(); self.health.detail="generic SocketCAN transport; real ECU compatibility is not claimed"
        except Exception as exc:
            self.health.connected=False; self.health.status="disconnected"; self.health.detail=f"SocketCAN unavailable: {exc}"
    def stop(self):
        if self._bus is not None: self._bus.shutdown()
        super().stop()

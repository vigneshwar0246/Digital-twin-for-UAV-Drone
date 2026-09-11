"""Protocol boundaries awaiting authorized ECU/FADEC specifications."""
from .base import AdapterMode, TelemetryAdapter

class ECUAdapter(TelemetryAdapter):
    def __init__(self,source="ECU",protocol_specification:dict|None=None,**kwargs):
        super().__init__(AdapterMode.FADEC,source,**kwargs); self.specification=protocol_specification
        self.health.detail="No ECU compatibility claimed; a supplied protocol specification is required."
    def start(self):
        if not self.specification:
            self.health.connected=False; self.health.status="disconnected"; return
        super().start()
    def poll(self): return []

class FADECAdapter(ECUAdapter):
    def __init__(self,protocol_specification:dict|None=None,**kwargs):
        super().__init__(source="FADEC",protocol_specification=protocol_specification,**kwargs)
        self.health.detail="No FADEC compatibility claimed; a supplied protocol specification is required."

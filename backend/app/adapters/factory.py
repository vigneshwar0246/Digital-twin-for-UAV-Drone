from pathlib import Path
from .base import AdapterMode, TelemetryAdapter
from .can import CANAdapter
from .protocols import FADECAdapter
from .simulator import SimulatorAdapter
from .socketcan import SocketCANAdapter

def create_adapter(mode:AdapterMode,mapping_path:Path,channel="can0")->TelemetryAdapter:
    if mode==AdapterMode.SIMULATOR: return SimulatorAdapter()
    if mode==AdapterMode.CAN: return CANAdapter(mapping_path)
    if mode==AdapterMode.SOCKETCAN: return SocketCANAdapter(mapping_path,channel=channel)
    if mode==AdapterMode.FADEC: return FADECAdapter(protocol_specification=None)
    raise ValueError(f"unsupported telemetry adapter mode: {mode}")

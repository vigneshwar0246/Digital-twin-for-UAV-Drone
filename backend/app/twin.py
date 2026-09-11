"""Compatibility facade for the modular digital-twin core."""
from .core import DigitalTwinCore
from .schemas import Telemetry, TwinAssessment

class TwinEngine(DigitalTwinCore):
    def assess(self, telemetry: Telemetry) -> TwinAssessment:
        assessment, _ = self.synchronize(telemetry)
        return assessment

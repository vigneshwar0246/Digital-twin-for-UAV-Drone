"""Versioned prototype thresholds. None are manufacturer-approved limits."""
from dataclasses import dataclass
import json
from pathlib import Path

CLASSIFICATION = "engineering hypothesis / prototype threshold"

@dataclass(frozen=True)
class Threshold:
    value: float
    unit: str
    classification: str

class ThresholdConfig:
    def __init__(self, path: Path | None = None):
        path = path or Path(__file__).with_name("engineering_thresholds.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw["metadata"].get("manufacturer_approved") is not False:
            raise ValueError("prototype threshold configuration must not claim manufacturer approval")
        self.version = raw["metadata"]["version"]
        self.manufacturer_approved = False
        self._items = {name: Threshold(**item) for name, item in raw["thresholds"].items()}
        if any(item.classification != CLASSIFICATION for item in self._items.values()):
            raise ValueError(f"every threshold must be classified as: {CLASSIFICATION}")

    def value(self, name: str) -> float:
        return self._items[name].value

    def describe(self, name: str) -> Threshold:
        return self._items[name]


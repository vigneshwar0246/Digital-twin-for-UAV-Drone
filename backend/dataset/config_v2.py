"""Configuration for synthetic engine dataset version 2.

Key changes from v1 (config.py):
- missions: 120 -> 240  (approx 27 missions per fault class)
- engines:   12 -> 20   (wider engine-disjoint generalisation)
- seed: 26054 -> 77777  (new generation seed; v1 dataset is untouched)
- data dirs: dataset/data -> dataset/dataset_v2/data
- Engine and cylinder assignments are independent of mission index.

Physical bounds, fault classes, severities, phases, and required columns are
imported from v1 so the evaluation pipeline can share them.
"""
from dataclasses import dataclass
from pathlib import Path

from .config import FAULT_CLASSES, SEVERITIES, PHASES, REQUIRED_COLUMNS, BOUNDS

DATASET_VERSION = "v2"
SEED_V2 = 77_777

PACKAGE_DIR    = Path(__file__).resolve().parent
DATA_DIR_V2    = PACKAGE_DIR / "dataset_v2" / "data"
REPORTS_DIR_V2 = PACKAGE_DIR / "dataset_v2" / "reports"
GRAPHS_DIR_V2  = PACKAGE_DIR / "dataset_v2" / "graphs"
MANIFEST_PATH  = DATA_DIR_V2 / "mission_manifest.json"

N_CYLINDERS = 4


@dataclass(frozen=True)
class DatasetConfigV2:
    rows: int = 200_000
    missions: int = 240
    sampling_interval_seconds: float = 5.0
    engines: int = 20
    seed: int = SEED_V2
    min_fault_samples: int = 600
    version: str = DATASET_VERSION


DEFAULT_CONFIG_V2 = DatasetConfigV2()

import hashlib
import pandas as pd
from backend.dataset.config import DATA_DIR, REQUIRED_COLUMNS, BOUNDS, DatasetConfig
from backend.dataset.generate_dataset import generate
from backend.dataset.validate_dataset import validate

def test_validation_passes():
    checks,df=validate(write_outputs=False)
    assert df is not None
    assert all(c["passed"] for c in checks if c["critical"]), checks

def test_schema_and_bounds():
    df=pd.read_csv(DATA_DIR/"aero_engine_full.csv",keep_default_na=False)
    assert list(df.columns)==list(REQUIRED_COLUMNS)
    assert all(df[c].between(*bounds).all() for c,bounds in BOUNDS.items())

def test_mission_splits_are_disjoint():
    sets=[set(pd.read_csv(DATA_DIR/f"aero_engine_{s}.csv",usecols=["mission_id"]).mission_id) for s in ("train","validation","test")]
    assert sets[0].isdisjoint(sets[1]) and sets[0].isdisjoint(sets[2]) and sets[1].isdisjoint(sets[2])

def test_reproducible_small_generation(tmp_path,monkeypatch):
    import backend.dataset.generate_dataset as module
    monkeypatch.setattr(module,"DATA_DIR",tmp_path/"data"); monkeypatch.setattr(module,"REPORTS_DIR",tmp_path/"reports"); monkeypatch.setattr(module,"GRAPHS_DIR",tmp_path/"graphs")
    cfg=DatasetConfig(rows=3600,missions=18,seed=42,min_fault_samples=10)
    a=generate(cfg).to_csv(index=False); b=generate(cfg).to_csv(index=False)
    assert hashlib.sha256(a.encode()).digest()==hashlib.sha256(b.encode()).digest()

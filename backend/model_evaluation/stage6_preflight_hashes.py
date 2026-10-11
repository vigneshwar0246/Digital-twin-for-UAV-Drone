"""Pre-run hash recording for Stage 6 preflight audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

files = {
    "dataset_v2_full": ROOT / "backend/dataset/dataset_v2/data/aero_engine_full.csv",
    "dataset_v1_full": ROOT / "backend/dataset/data/aero_engine_full.csv",
    "manifest_v2": ROOT / "backend/dataset/dataset_v2/data/mission_manifest.json",
    "cand_a_stage4": ROOT / "backend/model_evaluation/outputs_stage4/models/cand_a_reference.joblib",
    "c4_safety_weighted_v2": ROOT / "backend/model_evaluation/outputs_v2/models/c4_full_causal_safety_weighted.joblib",
}

hashes = {}
for label, path in files.items():
    if path.exists():
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        size = path.stat().st_size
        hashes[label] = {"sha256": sha, "size_bytes": size, "path": str(path)}
        print(f"{label}: {sha[:24]}... ({size:,} bytes)")
    else:
        hashes[label] = {"sha256": None, "error": "file not found"}
        print(f"{label}: NOT FOUND")

out = ROOT / "backend/model_evaluation/outputs_stage6/reports/stage6_preflight_hashes.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(hashes, indent=2), encoding="utf-8")
print(f"\nHashes saved to: {out}")

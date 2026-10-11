"""CLI and library function for deterministic generation of Dataset v2.

Key features:
1. Versioned outputs strictly written to dataset_v2/ (preserves v1 intact).
2. Engine pool of 20 engines with persistent, precomputed calibration dicts.
3. Mission assignment decouples engine identity and cylinder from mission order.
4. Cylinder-dependent faults (Cooling, Sensor Drift, Injector, Misfire) are
   balanced uniformly across cylinders 0..3.
5. Sensor_Drift affects parameterized cylinder, not hardcoded cylinder 0.
6. Generates complete manifest (mission_manifest.json) recording engine, fault,
   terminal severity, cylinder, and split assignment for each mission.
7. Produces aero_engine_full.csv, aero_engine_train.csv, aero_engine_validation.csv,
   and aero_engine_test.csv.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from .config import (
    FAULT_CLASSES,
    REQUIRED_COLUMNS,
)
from .config_v2 import (
    DEFAULT_CONFIG_V2,
    DATA_DIR_V2,
    REPORTS_DIR_V2,
    GRAPHS_DIR_V2,
    MANIFEST_PATH,
    DatasetConfigV2,
    N_CYLINDERS,
)
from .engine_simulator_v2 import (
    simulate_mission_v2,
    make_engine_calibration,
)

CYLINDER_FAULTS = {
    "Cooling_System_Degradation",
    "Sensor_Drift",
    "Fuel_Injector_Degradation",
    "Spark_Plug_Misfire",
}


def build_mission_plan(cfg: DatasetConfigV2, rng: np.random.Generator):
    """Plan fault, engine, cylinder, and severity assignments across all missions.

    Ensures:
    - Balanced fault class distribution.
    - Balanced terminal severity (None for Healthy; Low/Medium/High balanced for faults).
    - Balanced engine allocation (each of the 20 engines receives 12 missions).
    - High diversity of faults per engine (every engine covers at least 7 distinct classes).
    - Uniform distribution across all 4 cylinders for cylinder faults.
    - Shuffled mission ordering so mission_id does not correlate with engine or cylinder.
    """
    n_missions = cfg.missions
    n_engines = cfg.engines
    fault_classes = list(FAULT_CLASSES)
    n_classes = len(fault_classes)

    # 1. Base fault assignments
    base_per_class = n_missions // n_classes
    rem_classes = n_missions % n_classes
    fault_list = []
    for i, fc in enumerate(fault_classes):
        count = base_per_class + (1 if i < rem_classes else 0)
        fault_list.extend([fc] * count)

    # 2. Terminal severity assignment per fault
    severity_order = ["Low", "Medium", "High"]
    mission_records = []
    for fc in fault_classes:
        fc_missions = [m for m in fault_list if m == fc]
        if fc == "Healthy":
            for _ in fc_missions:
                mission_records.append({
                    "fault_type": "Healthy",
                    "terminal_severity": "None",
                })
        else:
            for j, _ in enumerate(fc_missions):
                sev = severity_order[j % 3]
                mission_records.append({
                    "fault_type": fc,
                    "terminal_severity": sev,
                })

    # Shuffle mission records
    rng.shuffle(mission_records)

    # 3. Engine assignment (240 missions / 20 engines = 12 missions per engine)
    # Stratify by fault type so each engine gets an even mix of fault types.
    # Group mission indices by fault_type:
    by_fault = {fc: [] for fc in fault_classes}
    for idx, rec in enumerate(mission_records):
        by_fault[rec["fault_type"]].append(idx)

    engine_allocations = [[] for _ in range(n_engines)]
    # Distribute each fault class across engines in round-robin with random starting offset
    engine_cursor = int(rng.integers(0, n_engines))
    for fc in fault_classes:
        indices = by_fault[fc]
        rng.shuffle(indices)
        for m_idx in indices:
            engine_allocations[engine_cursor].append(m_idx)
            engine_cursor = (engine_cursor + 1) % n_engines

    # Assign engine_no back to records
    for eng_no, allocated_indices in enumerate(engine_allocations):
        for m_idx in allocated_indices:
            mission_records[m_idx]["engine_no"] = eng_no

    # 4. Cylinder assignment for cylinder faults
    # For each cylinder fault, distribute uniformly across 0, 1, 2, 3
    for fc in CYLINDER_FAULTS:
        c_indices = [i for i, r in enumerate(mission_records) if r["fault_type"] == fc]
        rng.shuffle(c_indices)
        for k, c_idx in enumerate(c_indices):
            mission_records[c_idx]["affected_cylinder"] = k % N_CYLINDERS

    # For non-cylinder faults, affected_cylinder is assigned 0 (unused)
    for rec in mission_records:
        if "affected_cylinder" not in rec:
            rec["affected_cylinder"] = int(rng.integers(0, N_CYLINDERS))

    # 5. Shuffle overall order to break any cluster correlations
    rng.shuffle(mission_records)

    # Assign sequential mission IDs and row budgets
    base_rows, rem_rows = divmod(cfg.rows, cfg.missions)
    for i, rec in enumerate(mission_records):
        rec["mission_index"] = i
        rec["mission_id"] = f"MISSION_V2_{i + 1:04d}"
        rec["rows"] = base_rows + (1 if i < rem_rows else 0)

    return mission_records


def assign_splits(mission_records: list, rng: np.random.Generator) -> dict:
    """Split missions into train (70%), validation (15%), test (15%).

    Stratifies by (fault_type, terminal_severity).
    """
    df_meta = pd.DataFrame(mission_records)
    splits = {"train": [], "validation": [], "test": []}
    severity_order = ["Low", "Medium", "High"]

    for fault_index, (fault, group) in enumerate(df_meta.groupby("fault_type", sort=True)):
        mids = list(group["mission_id"])
        rng.shuffle(mids)
        if fault == "Healthy":
            # 27 Healthy missions: ~19 train, 4 val, 4 test
            val_count = max(2, round(0.15 * len(mids)))
            test_count = max(2, round(0.15 * len(mids)))
            val_ids = mids[:val_count]
            test_ids = mids[val_count:val_count + test_count]
            train_ids = mids[val_count + test_count:]
        else:
            # Group by severity within this fault
            by_sev = {s: group[group["terminal_severity"] == s]["mission_id"].tolist() for s in severity_order}
            for s in severity_order:
                rng.shuffle(by_sev[s])
            val_ids = []
            test_ids = []
            # Take ~15% for val and ~15% for test across severities
            for s in severity_order:
                s_mids = by_sev[s]
                v_take = max(1, round(0.15 * len(s_mids)))
                t_take = max(1, round(0.15 * len(s_mids)))
                val_ids.extend(s_mids[:v_take])
                test_ids.extend(s_mids[v_take:v_take + t_take])
            held = set(val_ids + test_ids)
            train_ids = [m for m in mids if m not in held]

        splits["train"].extend(train_ids)
        splits["validation"].extend(val_ids)
        splits["test"].extend(test_ids)

    return splits


def generate_v2(cfg: DatasetConfigV2 = DEFAULT_CONFIG_V2) -> pd.DataFrame:
    """Generate Dataset v2 with full decoupling and persistent calibrations."""
    for folder in (DATA_DIR_V2, REPORTS_DIR_V2, GRAPHS_DIR_V2):
        folder.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(cfg.seed)

    # 1. Precompute engine calibrations for the engine pool
    engine_calibrations = [
        make_engine_calibration(eng_no, cfg.seed + 20_000 + eng_no)
        for eng_no in range(cfg.engines)
    ]

    # 2. Build balanced mission plan
    mission_records = build_mission_plan(cfg, rng)

    # 3. Assign train / validation / test splits
    splits = assign_splits(mission_records, rng)
    split_lookup = {}
    for split_name, s_mids in splits.items():
        for mid in s_mids:
            split_lookup[mid] = split_name

    for rec in mission_records:
        rec["split"] = split_lookup.get(rec["mission_id"], "train")
        rec["engine_id"] = engine_calibrations[rec["engine_no"]]["engine_id"]

    # 4. Save mission manifest
    manifest_data = {
        "dataset_version": cfg.version,
        "seed": cfg.seed,
        "total_missions": cfg.missions,
        "total_rows": cfg.rows,
        "engine_count": cfg.engines,
        "missions": mission_records,
        "engine_calibrations": [
            {k: v for k, v in cal.items()}
            for cal in engine_calibrations
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # 5. Simulate each mission
    frames = []
    for rec in mission_records:
        eng_no = rec["engine_no"]
        cal = engine_calibrations[eng_no]
        m_frame = simulate_mission_v2(
            mission_index=rec["mission_index"],
            n=rec["rows"],
            fault=rec["fault_type"],
            cfg=cfg,
            rng=rng,
            terminal_severity=rec["terminal_severity"],
            engine_no=eng_no,
            affected_cylinder=rec["affected_cylinder"],
            calibration=cal,
        )
        frames.append(m_frame)

    full_df = pd.concat(frames, ignore_index=True)[list(REQUIRED_COLUMNS)]

    # 6. Save split datasets to DATA_DIR_V2
    full_path = DATA_DIR_V2 / "aero_engine_full.csv"
    full_df.to_csv(full_path, index=False, float_format="%.4f")

    for split_name, s_mids in splits.items():
        subset = full_df[full_df["mission_id"].isin(s_mids)]
        subset_path = DATA_DIR_V2 / f"aero_engine_{split_name}.csv"
        subset.to_csv(subset_path, index=False, float_format="%.4f")

    return full_df


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic engine dataset v2")
    parser.add_argument("--rows", type=int, default=DEFAULT_CONFIG_V2.rows)
    parser.add_argument("--missions", type=int, default=DEFAULT_CONFIG_V2.missions)
    parser.add_argument("--engines", type=int, default=DEFAULT_CONFIG_V2.engines)
    parser.add_argument("--seed", type=int, default=DEFAULT_CONFIG_V2.seed)
    args = parser.parse_args()

    cfg = DatasetConfigV2(
        rows=args.rows,
        missions=args.missions,
        engines=args.engines,
        seed=args.seed,
    )
    df = generate_v2(cfg)
    summary = {
        "status": "success",
        "version": cfg.version,
        "rows": len(df),
        "missions": int(df["mission_id"].nunique()),
        "engines": int(df["engine_id"].nunique()),
        "seed": cfg.seed,
        "output_dir": str(DATA_DIR_V2),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

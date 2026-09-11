"""CLI for deterministic generation and mission-level splitting."""
import argparse, json
import numpy as np
import pandas as pd
from .config import DEFAULT_CONFIG, DATA_DIR, REPORTS_DIR, GRAPHS_DIR, FAULT_CLASSES, REQUIRED_COLUMNS, DatasetConfig
from .engine_simulator import simulate_mission

def generate(cfg=DEFAULT_CONFIG):
    if cfg.missions < len(FAULT_CLASSES) * 2:
        raise ValueError("missions must be at least 18 for healthy/fault coverage")
    for folder in (DATA_DIR, REPORTS_DIR, GRAPHS_DIR): folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(cfg.seed)
    base, rem = divmod(cfg.rows, cfg.missions)
    sizes = [base + (i < rem) for i in range(cfg.missions)]
    assignments = [FAULT_CLASSES[i % len(FAULT_CLASSES)] for i in range(cfg.missions)]
    rng.shuffle(assignments)
    severity_cycle = {fault: iter((["Low","Medium","High"] * (cfg.missions//len(FAULT_CLASSES)+2))) for fault in FAULT_CLASSES if fault!="Healthy"}
    mission_severity = ["None" if f=="Healthy" else next(severity_cycle[f]) for f in assignments]
    frames = [simulate_mission(i, sizes[i], assignments[i], cfg, rng, mission_severity[i]) for i in range(cfg.missions)]
    full = pd.concat(frames, ignore_index=True)[list(REQUIRED_COLUMNS)]
    mission_fault = full.groupby("mission_id").fault_type.apply(lambda s: s[s!="Healthy"].iloc[0] if (s!="Healthy").any() else "Healthy")
    severity_rank={"None":0,"Low":1,"Medium":2,"High":3}
    mission_severity=full.groupby("mission_id").fault_severity.apply(lambda s:max(s,key=severity_rank.get))
    strata=pd.DataFrame({"fault":mission_fault,"severity":mission_severity})
    # Each fault contributes about 70/15/15. Held-out severity choices rotate by
    # fault, balancing Low/Medium/High globally despite only 18 missions per split.
    splits = {"train": [], "validation": [], "test": []}
    severity_order=["Low","Medium","High"]
    for fault_index,(fault, group) in enumerate(strata.groupby("fault",sort=True)):
        mids=list(group.index); rng.shuffle(mids)
        if len(mids)<6:
            a=max(1,round(.15*len(mids))); b=max(1,round(.15*len(mids)))
            validation_ids=mids[:a]; test_ids=mids[a:a+b]
        elif fault=="Healthy":
            validation_ids=mids[:2]; test_ids=mids[2:4]
        else:
            by_severity={s:[m for m in mids if group.loc[m,"severity"]==s] for s in severity_order}
            val_severities=[severity_order[fault_index%3],severity_order[(fault_index+1)%3]]
            test_severities=[severity_order[(fault_index+1)%3],severity_order[(fault_index+2)%3]]
            validation_ids=[by_severity[s].pop() for s in val_severities]
            test_ids=[by_severity[s].pop() for s in test_severities]
        held=set(validation_ids+test_ids)
        splits["validation"].extend(validation_ids); splits["test"].extend(test_ids)
        splits["train"].extend([m for m in mids if m not in held])
    full.to_csv(DATA_DIR/"aero_engine_full.csv", index=False, float_format="%.4f")
    for name, mids in splits.items():
        full[full.mission_id.isin(mids)].to_csv(DATA_DIR/f"aero_engine_{name}.csv", index=False, float_format="%.4f")
    return full

def main():
    p=argparse.ArgumentParser(); p.add_argument("--rows",type=int,default=DEFAULT_CONFIG.rows); p.add_argument("--missions",type=int,default=DEFAULT_CONFIG.missions); p.add_argument("--seed",type=int,default=DEFAULT_CONFIG.seed)
    a=p.parse_args(); df=generate(DatasetConfig(rows=a.rows,missions=a.missions,seed=a.seed)); print(json.dumps({"rows":len(df),"missions":df.mission_id.nunique(),"seed":a.seed}))
if __name__ == "__main__": main()

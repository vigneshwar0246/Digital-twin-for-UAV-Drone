"""Leakage-resistant evaluation splits for synthetic engine missions."""
from dataclasses import dataclass
import hashlib, itertools, json
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class EvaluationSplits:
    fit: pd.DataFrame
    time_forward: pd.DataFrame
    validation: pd.DataFrame
    challenge: pd.DataFrame
    manifest: dict

def mission_profile_fingerprint(group: pd.DataFrame) -> str:
    """Fingerprint phase durations and trajectory statistics, not mission IDs."""
    ordered=group.sort_values("time_seconds"); phase_fraction=ordered.mission_phase.value_counts(normalize=True).sort_index().round(4).to_dict()
    summary={"phase_fraction":phase_fraction,"altitude_mean":round(group.altitude_m.mean(),2),"altitude_std":round(group.altitude_m.std(),2),
        "temperature_mean":round(group.ambient_temperature_c.mean(),2),"temperature_std":round(group.ambient_temperature_c.std(),2),
        "throttle_mean":round(group.throttle_percent.mean(),2),"throttle_std":round(group.throttle_percent.std(),2),"duration":round(group.time_seconds.max(),2)}
    # Pandas/NumPy may return scalar subclasses (for example np.int64), which
    # the standard JSON encoder does not serialize directly.
    encoded=json.dumps(summary,sort_keys=True,default=lambda value:value.item() if isinstance(value,np.generic) else str(value))
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]

def _coverage(frame,engine_ids,target):
    return set(frame.loc[frame.engine_id.isin(engine_ids),target].unique())

def _select_engine_groups(frame,target="fault_type",seed=26054,holdout_size=3):
    """Select disjoint groups by class coverage/balance, never by model scores."""
    engines=sorted(frame.engine_id.unique()); classes=set(frame[target].unique())
    if len(engines)<holdout_size*2+2: raise ValueError("at least eight engines are required for engine-disjoint evaluation")
    counts=pd.crosstab(frame.engine_id,frame[target]).reindex(index=engines,columns=sorted(classes),fill_value=0)
    coverage={engine:set(counts.columns[counts.loc[engine].gt(0)]) for engine in engines}
    global_dist=counts.sum()/counts.to_numpy().sum()
    candidates=[]
    for group in itertools.combinations(engines,holdout_size):
        if set().union(*(coverage[e] for e in group))!=classes: continue
        dist=counts.loc[list(group)].sum(); dist=dist/dist.sum()
        imbalance=float(np.abs(dist-global_dist).sum())
        tie=hashlib.sha256((str(seed)+"|"+"|".join(group)).encode()).hexdigest()
        candidates.append((imbalance,tie,group))
    if not candidates: raise ValueError("no held-out engine group covers every class")
    candidates.sort(); joint=[]
    for val in candidates:
        for test in candidates:
            if set(val[2])&set(test[2]): continue
            training=tuple(e for e in engines if e not in val[2] and e not in test[2])
            if set().union(*(coverage[e] for e in training))!=classes: continue
            joint.append((val[0]+test[0],val[1]+test[1],training,val[2],test[2]))
    if not joint: raise ValueError("no disjoint train/validation/challenge engine allocation covers every class")
    joint.sort(); _,_,training,validation,challenge=joint[0]
    return training,validation,challenge

def build_evaluation_splits(frame:pd.DataFrame,target="fault_type",seed=26054)->EvaluationSplits:
    required={"engine_id","mission_id","timestamp","time_seconds","mission_phase","altitude_m","ambient_temperature_c","throttle_percent",target}
    missing=required-set(frame.columns)
    if missing: raise ValueError(f"missing split columns: {sorted(missing)}")
    data=frame.copy(); data["timestamp"]=pd.to_datetime(data.timestamp,utc=True)
    train_engines,val_engines,test_engines=_select_engine_groups(data,target,seed)
    training=data[data.engine_id.isin(train_engines)].copy()
    rank={"Healthy":0}
    mission_meta=training.groupby("mission_id").agg(start=("timestamp","min"),
        fault=(target,lambda s:next((x for x in s if x!="Healthy"),"Healthy"))).sort_values("start")
    classes=set(training[target].unique()); candidates=[]
    for cut in range(1,len(mission_meta)):
        before=set(mission_meta.fault.iloc[:cut]); after=set(mission_meta.fault.iloc[cut:])
        if before==classes and after==classes: candidates.append(cut)
    cut=min(candidates,key=lambda x:abs(x/len(mission_meta)-.8)) if candidates else max(1,int(np.floor(len(mission_meta)*.8)))
    fit_ids=list(mission_meta.index[:cut]); forward_ids=list(mission_meta.index[cut:])
    fit=training[training.mission_id.isin(fit_ids)].copy()
    forward=training[training.mission_id.isin(forward_ids)].copy()
    validation=data[data.engine_id.isin(val_engines)].copy()
    challenge=data[data.engine_id.isin(test_engines)].copy()
    for part in (fit,forward,validation,challenge):
        profile_map=part.groupby("mission_id",sort=False).apply(mission_profile_fingerprint,include_groups=False)
        part["mission_profile_id"]=part.mission_id.map(profile_map)
    sets={"fit":set(fit.engine_id),"time_forward":set(forward.engine_id),"validation":set(validation.engine_id),"challenge":set(challenge.engine_id)}
    manifest={"strategy":"engine-disjoint validation/challenge plus time-forward audit within training engines",
        "seed":seed,"engines":{k:sorted(v) for k,v in sets.items()},
        "missions":{k:int(x.mission_id.nunique()) for k,x in (("fit",fit),("time_forward",forward),("validation",validation),("challenge",challenge))},
        "profile_definition":"hash of phase-duration fractions and altitude/temperature/throttle trajectory statistics; mission identity is excluded",
        "challenge_profile_overlap_with_fit":sorted(set(challenge.mission_profile_id)&set(fit.mission_profile_id)),
        "engine_disjoint":{"fit_vs_validation":sets["fit"].isdisjoint(sets["validation"]),"fit_vs_challenge":sets["fit"].isdisjoint(sets["challenge"]),"validation_vs_challenge":sets["validation"].isdisjoint(sets["challenge"])},
        "mission_disjoint":len(set(fit.mission_id)&set(forward.mission_id)|set(fit.mission_id)&set(validation.mission_id)|set(fit.mission_id)&set(challenge.mission_id)|set(forward.mission_id)&set(validation.mission_id)|set(forward.mission_id)&set(challenge.mission_id)|set(validation.mission_id)&set(challenge.mission_id))==0,
        "time_forward":bool(fit.timestamp.max()<forward.timestamp.min()),
        "time_forward_class_coverage":sorted(set(forward[target].unique()))}
    return EvaluationSplits(fit,forward,validation,challenge,manifest)

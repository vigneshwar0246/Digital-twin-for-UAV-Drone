"""Dataset validation, summary reports, and quality visualizations."""
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .config import DATA_DIR, REPORTS_DIR, GRAPHS_DIR, REQUIRED_COLUMNS, BOUNDS, FAULT_CLASSES, PHASES, DEFAULT_CONFIG

def _result(name, passed, detail, critical=True):
    return {"check":name,"passed":bool(passed),"critical":critical,"detail":str(detail)}

def validate(write_outputs=True):
    paths={n:DATA_DIR/f"aero_engine_{n}.csv" for n in ("full","train","validation","test")}
    missing_files=[str(p) for p in paths.values() if not p.exists()]
    if missing_files: return [_result("required_files",False,missing_files)], None
    df=pd.read_csv(paths["full"],parse_dates=["timestamp"],keep_default_na=False)
    checks=[_result("required_files",True,"all four CSV files exist")]
    checks.append(_result("expected_columns",set(REQUIRED_COLUMNS).issubset(df.columns),f"{len(df.columns)} columns"))
    checks.append(_result("no_missing_values",not df.isna().any().any(),f"missing={int(df.isna().sum().sum())}"))
    checks.append(_result("no_duplicate_rows",not df.duplicated().any(),f"duplicates={int(df.duplicated().sum())}"))
    ordered=all(g.timestamp.is_monotonic_increasing and not g.timestamp.duplicated().any() for _,g in df.groupby("mission_id"))
    checks.append(_result("timestamps_increasing",ordered,"strictly increasing by mission"))
    continuous=all(np.allclose(np.diff(g.time_seconds),DEFAULT_CONFIG.sampling_interval_seconds) for _,g in df.groupby("mission_id"))
    checks.append(_result("continuous_time_seconds",continuous,f"interval={DEFAULT_CONFIG.sampling_interval_seconds}s"))
    failures={c:int((~df[c].between(*b)).sum()) for c,b in BOUNDS.items() if c in df and (~df[c].between(*b)).any()}
    checks.append(_result("physical_bounds",not failures,failures or "all values in bounds"))
    checks.append(_result("valid_categories",set(df.fault_type)<=set(FAULT_CLASSES) and set(df.fault_severity)<={"None","Low","Medium","High"},"fault and severity labels"))
    counts=df.fault_type.value_counts().reindex(FAULT_CLASSES,fill_value=0)
    threshold=min(DEFAULT_CONFIG.min_fault_samples,max(10,len(df)//500))
    checks.append(_result("fault_class_coverage",bool((counts>=threshold).all()),f"minimum={counts.min()}, required={threshold}"))
    mf=df.groupby("mission_id").fault_type.apply(lambda x:(x!="Healthy").any())
    checks.append(_result("healthy_and_faulty_missions",mf.any() and (~mf).any(),f"healthy={int((~mf).sum())}, faulty={int(mf.sum())}"))
    split_ids={n:set(pd.read_csv(p,usecols=["mission_id"]).mission_id.unique()) for n,p in paths.items() if n!="full"}
    overlap=(split_ids["train"]&split_ids["validation"])|(split_ids["train"]&split_ids["test"])|(split_ids["validation"]&split_ids["test"])
    checks.append(_result("mission_split_no_overlap",not overlap,f"overlap={len(overlap)}"))
    mission_meta=df.groupby("mission_id").agg(
        fault=("fault_type",lambda s:s[s.ne("Healthy")].iloc[0] if s.ne("Healthy").any() else "Healthy"),
        severity=("fault_severity",lambda s:max(s,key={"None":0,"Low":1,"Medium":2,"High":3}.get)))
    split_balance={}
    for name,ids in split_ids.items():
        part=mission_meta.loc[list(ids)]
        split_balance[name]={"missions":len(part),"fault_classes":part.fault.nunique(),"severities":sorted(part.severity.unique())}
    stratified=(split_balance["train"]["missions"]==84 and split_balance["validation"]["missions"]==18 and split_balance["test"]["missions"]==18 and all(v["fault_classes"]==len(FAULT_CLASSES) for v in split_balance.values()) and set(split_balance["validation"]["severities"])>={"None","Low","Medium","High"} and set(split_balance["test"]["severities"])>={"None","Low","Medium","High"})
    checks.append(_result("mission_fault_severity_stratification",stratified,split_balance))
    corr=df[["throttle_percent","rpm","engine_load_percent","fuel_flow_lph","altitude_m","ambient_pressure_kpa"]].corr()
    relations={"throttle_rpm":corr.loc["throttle_percent","rpm"],"load_fuel":corr.loc["engine_load_percent","fuel_flow_lph"],"altitude_pressure":corr.loc["altitude_m","ambient_pressure_kpa"]}
    checks.append(_result("expected_sensor_directions",relations["throttle_rpm"]>.65 and relations["load_fuel"]>.55 and relations["altitude_pressure"]<-.9,relations))
    healthy=df[df.fault_type=="Healthy"]
    cht_mean=df.filter(like="cylinder_head_temp_").mean(axis=1)
    # Remove the known ambient/load/altitude baseline before comparing cooling classes.
    cht_residual=cht_mean-df.ambient_temperature_c-1.18*df.engine_load_percent+.004*df.altitude_m
    effects={
      "misfire_vibration":df[df.fault_type=="Spark_Plug_Misfire"].vibration_rms.mean()>healthy.vibration_rms.mean()+.4,
      "lubrication_pressure":df[df.fault_type=="Lubrication_System_Degradation"].oil_pressure_kpa.mean()<healthy.oil_pressure_kpa.mean()-10,
      "bearing_vibration":df[df.fault_type=="Bearing_Wear"].vibration_rms.mean()>healthy.vibration_rms.mean()+.5,
      "alternator_voltage":df[df.fault_type=="Alternator_Degradation"].alternator_voltage.mean()<healthy.alternator_voltage.mean()-.5,
      "cooling_cht_residual":cht_residual[df.fault_type=="Cooling_System_Degradation"].mean()>cht_residual[df.fault_type=="Healthy"].mean()+5,
    }
    checks.append(_result("observable_fault_effects",all(effects.values()),effects))
    phase_rank={p:i for i,p in enumerate(PHASES)}
    valid_order=all(np.all(np.diff([phase_rank[p] for p in g.mission_phase])>=0) for _,g in df.groupby("mission_id"))
    checks.append(_result("valid_phase_order",valid_order,"canonical order with optional phases"))
    sev_rank={"None":0,"Low":1,"Medium":2,"High":3}
    severity_ok=all(np.all(np.diff([sev_rank[x] for x in g.fault_severity])>=0) for _,g in df.groupby("mission_id"))
    checks.append(_result("severity_progression",severity_ok,"non-decreasing by mission"))
    if write_outputs:
        REPORTS_DIR.mkdir(parents=True,exist_ok=True); GRAPHS_DIR.mkdir(parents=True,exist_ok=True)
        summary={"shape":[len(df),len(df.columns)],"missions":int(df.mission_id.nunique()),"engines":int(df.engine_id.nunique()),"duration_hours":float(df.groupby('mission_id').time_seconds.max().sum()/3600),"columns":list(df.columns),"missing_values":int(df.isna().sum().sum()),"duplicate_rows":int(df.duplicated().sum()),"numeric_statistics":df.describe().round(3).to_dict()}
        (REPORTS_DIR/"validation_report.json").write_text(json.dumps({"all_critical_passed":all(x["passed"] for x in checks if x["critical"]),"checks":checks},indent=2),encoding="utf-8")
        (REPORTS_DIR/"dataset_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        pd.DataFrame({"fault_type":counts.index,"count":counts.values,"percentage":counts.values/len(df)*100}).to_csv(REPORTS_DIR/"class_distribution.csv",index=False)
        make_graphs(df,checks,relations,split_ids)
    return checks,df

def make_graphs(df,checks,relations,split_ids):
    plt.style.use("seaborn-v0_8-whitegrid")
    def save(name): plt.tight_layout(); plt.savefig(GRAPHS_DIR/name,dpi=160,bbox_inches="tight"); plt.close()
    c=df.fault_type.value_counts().reindex(FAULT_CLASSES); c.plot.bar(figsize=(11,5),color="#2878B5"); plt.ylabel("Telemetry samples"); plt.title("Fault-class distribution"); save("01_class_distribution.png")
    pd.Series({k:len(v) for k,v in split_ids.items()}).plot.bar(color=["#2878B5","#F2A104","#D9534F"]); plt.ylabel("Complete missions"); plt.title("Mission-level split"); save("02_mission_splits.png")
    pd.Series({x["check"]:100 if x["passed"] else 0 for x in checks}).plot.barh(figsize=(9,7),color=["#2E8B57" if x["passed"] else "#C33" for x in checks]); plt.xlabel("Validation score (%)"); plt.xlim(0,105); plt.title("Dataset validation scores (not ML accuracy)"); save("03_validation_scores.png")
    faulty_ids=df.loc[df.anomaly_label.eq(1),"mission_id"].unique()
    sample=df[df.mission_id==faulty_ids[len(faulty_ids)//2]].copy()
    sample["degradation_percent"]=100-sample.health_index
    ax=sample.plot(x="time_seconds",y=["throttle_percent","engine_load_percent","health_index","degradation_percent"],figsize=(13,6))
    onset=sample.loc[sample.anomaly_label.eq(1),"time_seconds"].min(); mission_fault=sample.loc[sample.fault_type.ne("Healthy"),"fault_type"].iloc[0]
    ax.axvline(onset,color="black",ls="--",lw=1.5,label=f"fault onset: {onset:.0f}s")
    colors={"Low":"#F9E79F","Medium":"#F5B041","High":"#E74C3C"}
    for severity,color in colors.items():
        region=sample[sample.fault_severity.eq(severity)]
        if not region.empty: ax.axvspan(region.time_seconds.min(),region.time_seconds.max(),color=color,alpha=.18,label=severity)
    ax.set_title(f"Mission telemetry and degradation — {sample.mission_id.iloc[0]} — {mission_fault}"); ax.legend(ncol=3); save("04_mission_profile.png")
    pd.DataFrame(relations,index=["correlation"]).T.plot.bar(legend=False,color="#6F4E7C"); plt.axhline(0,color="black",lw=.8); plt.ylim(-1,1); plt.title("Physics relationship correlations"); save("05_physics_correlations.png")
    df.groupby("fault_severity")[["health_index","mission_reliability_percent"]].mean().reindex(["None","Low","Medium","High"]).plot.bar(figsize=(8,5)); plt.ylabel("Mean score"); plt.title("Health and reliability by severity"); save("06_health_reliability.png")
    df=df.copy(); cht=[f"cylinder_head_temp_{i}_c" for i in range(1,5)]; egt=[f"exhaust_gas_temp_{i}_c" for i in range(1,5)]
    df["cht_spread_c"]=df[cht].max(axis=1)-df[cht].min(axis=1); df["egt_spread_c"]=df[egt].max(axis=1)-df[egt].min(axis=1)
    sensors=["rpm","fuel_flow_lph","air_fuel_ratio","cht_spread_c","egt_spread_c","oil_pressure_kpa","oil_temperature_c","vibration_rms","alternator_voltage"]
    normalized=df.groupby("fault_type")[sensors].mean(); normalized=(normalized-normalized.min())/(normalized.max()-normalized.min())
    normalized.plot.bar(figsize=(12,6)); plt.ylabel("Normalized class mean"); plt.title("Observable sensor effects by fault class"); save("07_fault_sensor_effects.png")

def main():
    checks,_=validate(True); passed=all(x["passed"] for x in checks if x["critical"]); print(json.dumps({"passed":passed,"checks":checks},indent=2)); raise SystemExit(0 if passed else 1)
if __name__=="__main__": main()

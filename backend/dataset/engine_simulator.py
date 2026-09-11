"""Correlated, stateful aero-piston-engine telemetry simulator."""
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
from .config import BOUNDS
from .mission_profiles import mission_phases, smooth_targets
from .fault_simulator import fault_profile, severity_labels

def _clip(name, values):
    lo, hi = BOUNDS[name]
    return np.clip(values, lo, hi)

def simulate_mission(mission_index, n, fault, cfg, rng, terminal_severity="High"):
    phases = mission_phases(n, rng)
    throttle, altitude, airspeed = smooth_targets(phases, rng)
    dt = cfg.sampling_interval_seconds
    time_s = np.arange(n) * dt
    engine_no = mission_index % cfg.engines
    erng = np.random.default_rng(cfg.seed + 10_000 + engine_no)
    compression = erng.normal(1, .025); fuel_cal = erng.normal(1, .035)
    thermal_factor = erng.normal(1, .045); vibration_balance = abs(erng.normal(0, .16))
    rpm_lag = erng.uniform(.13, .23); thermal_lag = erng.uniform(.014, .027)
    sensor_bias = erng.normal(0, [2.0, 2.0, 2.0, 2.0])
    ambient0 = rng.uniform(10, 38)
    weather = np.cumsum(rng.normal(0, .015, n))
    ambient = ambient0 - .0065 * altitude + weather + rng.normal(0, .38, n)
    pressure = 101.325 * np.power(1 - 2.25577e-5 * altitude, 5.2559) + rng.normal(0, .16, n)
    humidity = np.clip(rng.uniform(30, 82) - altitude * .003 + rng.normal(0, 1, n), 5, 100)
    payload = rng.uniform(.72, 1.05)
    load = np.clip((throttle ** 1.035) * (.63 + .24 * payload) + np.where(np.array(phases)=="climb", 9, 0) + rng.normal(0,1.1,n), 0, 108)
    running = ~np.isin(phases, ["shutdown"])
    free_rpm = 620 + 18.7 * throttle + 4.1*np.sqrt(throttle*load+1)*compression + .55*load
    governed={"engine_start":550,"warm_up":1050,"takeoff":2780,"climb":2550,"cruise":2350,
              "endurance_cruise":2100,"rapid_throttle_transition":2400,"descent":1850,"landing":1200,"shutdown":0}
    governed_rpm=np.array([governed[p] for p in phases])*erng.normal(1,.018)
    rpm_target=np.where(running,.64*free_rpm+.36*governed_rpm,0)
    rpm = np.empty(n); rpm[0] = 150 if phases[0] == "engine_start" else rpm_target[0]
    manifold = np.empty(n); manifold[0] = 35
    oil_temp = np.empty(n); oil_temp[0] = ambient[0]
    cht = np.full((n,4), ambient[0]); egt = np.full((n,4), ambient[0])
    progress, anomaly = fault_profile(fault, n, rng, terminal_severity)
    cylinder = mission_index % 4
    for i in range(1, n):
        rpm[i] = rpm[i-1] + rpm_lag*(rpm_target[i]-rpm[i-1]) + rng.normal(0, 13)
        turbo_comp = 17*(1-np.exp(-altitude[i]/3200))*(throttle[i]/100)**1.4
        mp_target = 29 + 1.03*throttle[i] + turbo_comp + .0006*altitude[i]
        manifold[i] = manifold[i-1] + rng.uniform(.10,.19)*(mp_target-manifold[i-1]) + rng.normal(0,.55)
        oil_target = ambient[i] + (59 + .38*load[i] + .0012*altitude[i]) * (1 if running[i] else 0)
        oil_temp[i] = oil_temp[i-1] + .012*(oil_target-oil_temp[i-1]) + rng.normal(0,.08)
        afr_i = 12.8 + 1.15*(altitude[i]/8000)**1.25 - .007*load[i] + .12*np.sin(i/83)
        for c in range(4):
            cooling = 10*(airspeed[i]/220)**.65 + 5*(pressure[i]/101.3)
            ct = ambient[i] + (64 + 1.25*load[i] + .0014*altitude[i])*thermal_factor - cooling + c*1.3 + sensor_bias[c]
            et = ambient[i] + 408 + 3.25*load[i] - 9*(afr_i-13.25)**2 + c*2 + sensor_bias[c]
            cht[i,c] = cht[i-1,c] + thermal_lag*(ct-cht[i-1,c]) + rng.normal(0,.36)
            egt[i,c] = egt[i-1,c] + rng.uniform(.038,.068)*(et-egt[i-1,c]) + rng.normal(0,1.5)
    afr = 12.8 + 1.15*(altitude/8000)**1.25 - .007*load + .12*np.sin(np.arange(n)/83) + rng.normal(0,.14,n)
    fuel_target=np.maximum(0,fuel_cal*(rpm/2700)*(load/100)**1.08*52*(14.0/afr))
    fuel=np.empty(n); fuel[0]=fuel_target[0]
    for i in range(1,n): fuel[i]=max(0,fuel[i-1]+erng.uniform(.14,.28)*(fuel_target[i]-fuel[i-1])+rng.normal(0,.52))
    vibration = .3 + vibration_balance + .00058*rpm + .00000011*rpm**2 + .0055*load + rng.normal(0,.12,n)
    efficiency = 88 - .05*np.abs(load-65) - .0008*altitude + rng.normal(0,.35,n)
    alt_v = np.where(rpm > 900, 28.1, 24.4) + rng.normal(0,.08,n)
    injection = 18 + .055*load + .00035*altitude + rng.normal(0,.12,n)
    # Fault effects are gradual and affect related groups rather than isolated labels.
    if fault == "Spark_Plug_Misfire":
        # Intermittent firing loss creates bursts, not a smooth permanent offset.
        gate = (rng.random(n) < (.12 + .48*progress)).astype(float)
        intermittent = np.convolve(gate, np.array([.25,.5,1,.5,.25]), mode="same")
        intermittent = np.clip(intermittent,0,1.5)*progress
        egt[:,cylinder] -= 175*intermittent; cht[:,cylinder] -= 52*intermittent
        rpm += (rng.normal(0,42,n)-70*gate)*intermittent
        vibration += (2.2+2.8*np.abs(np.sin(np.arange(n)*.55)))*intermittent
    elif fault == "Fuel_Injector_Degradation":
        afr += 2.0*progress; fuel *= 1-.18*progress
        egt[:,cylinder] += 95*progress; cht[:,cylinder] += 25*progress
    elif fault == "Lubrication_System_Degradation":
        oil_temp += 25*progress; vibration += 3.2*progress
    elif fault == "Cooling_System_Degradation":
        # Uneven fin/duct degradation: load and thin/hot air raise CHT while
        # airspeed still provides partial cooling. The deficit has thermal lag.
        weights = np.roll(np.array([1.0,.88,.58,.30]), cylinder)
        deficit = np.zeros(n)
        forcing = progress*(.32+.9*(load/100)**1.6)*(1+.35*altitude/8000)*(1+.012*np.maximum(ambient-20,0))/(1+.38*(airspeed/220)**.7)
        for i in range(1,n): deficit[i]=deficit[i-1]+.045*(forcing[i]*88-deficit[i-1])
        cht += deficit[:,None]*weights[None,:]
        oil_temp += 7*progress*(load/100)
    elif fault == "Bearing_Wear":
        vibration += 7*progress*(.4+.6*rpm/3000); efficiency -= 9*progress; oil_temp += 9*progress
    elif fault == "Combustion_Instability":
        phase=np.arange(n)
        wave=(np.sin(phase*.27)+.48*np.sin(phase*.071+1.2))*progress
        afr += 1.05*wave
        rpm += 105*wave + rng.normal(0,22,n)*progress
        egt += (82*wave)[:,None] * np.array([1,.88,1.12,.94])[None,:]
        vibration += 2.8*np.abs(wave)+1.2*progress*np.abs(np.sin(phase*.61))
    elif fault == "Sensor_Drift":
        # CHT1 sensor alone drifts; peer cylinders preserve the engine's true thermal trend.
        cht[:,0] += 65*progress
    elif fault == "Alternator_Degradation":
        alt_v -= 6.5*progress + 1.2*progress*np.sin(np.arange(n)*.25)
    lub_loss = progress if fault == "Lubrication_System_Degradation" else 0
    oil_pressure = np.where(rpm>0, 120 + .12*rpm - 1.25*np.maximum(oil_temp-95,0), 0) - 230*lub_loss + rng.normal(0,3,n)
    battery = 24.3 + np.where(alt_v>26, .8, 0) - np.maximum(25-alt_v,0)*.12 + rng.normal(0,.04,n)
    health = np.clip(98.5 - 45*progress - np.maximum(0, mission_index-90)*.025 + rng.normal(0,.45,n), 0, 100)
    rul = np.clip(1800 - mission_index*5 - 1450*progress + rng.normal(0,8,n), 0, 2500)
    remaining_h = (n-1-np.arange(n))*dt/3600
    reliability = np.clip(99.4 - .38*(100-health) - 3*progress - remaining_h*.08 - np.maximum(load-95,0)*.035 + rng.normal(0,.18,n), 0, 100)
    outcome = "Completed"
    if progress.max() > .92 and fault in ("Lubrication_System_Degradation","Bearing_Wear"):
        outcome = "Failed"
    elif progress.max() > .78:
        outcome = "Aborted"
    start = datetime(2026,1,1,tzinfo=timezone.utc) + timedelta(days=mission_index)
    d = {
        "timestamp": [(start+timedelta(seconds=float(x))).isoformat() for x in time_s],
        "mission_id": f"MISSION_{mission_index+1:04d}", "engine_id": f"ENGINE_{mission_index%cfg.engines+1:03d}",
        "time_seconds": time_s, "mission_phase": phases,
        "operating_hours": mission_index*18 + time_s/3600, "cycle_count": mission_index//cfg.engines+1,
        "altitude_m": altitude, "ambient_temperature_c": ambient, "ambient_pressure_kpa": pressure,
        "humidity_percent": humidity, "airspeed_kmh": airspeed, "throttle_percent": throttle,
        "engine_load_percent": load, "rpm": rpm, "manifold_pressure_kpa": manifold,
        "fuel_flow_lph": fuel, "air_fuel_ratio": afr,
        **{f"cylinder_head_temp_{c+1}_c": cht[:,c] for c in range(4)},
        **{f"exhaust_gas_temp_{c+1}_c": egt[:,c] for c in range(4)},
        "oil_temperature_c": oil_temp, "oil_pressure_kpa": oil_pressure,
        "vibration_rms": vibration, "alternator_voltage": alt_v, "battery_voltage": battery,
        "injection_timing_deg": injection, "engine_efficiency_percent": efficiency,
        "fault_type": np.where(anomaly, fault, "Healthy"), "fault_severity": severity_labels(progress),
        "anomaly_label": anomaly.astype(int), "health_index": health, "rul_hours": rul,
        "mission_reliability_percent": reliability, "mission_outcome": outcome,
    }
    frame = pd.DataFrame(d)
    for col in BOUNDS:
        frame[col] = _clip(col, frame[col].to_numpy())
    return frame

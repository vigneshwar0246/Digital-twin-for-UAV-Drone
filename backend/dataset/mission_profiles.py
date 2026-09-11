"""Mission profile construction with smooth phase transitions."""
import numpy as np
from .config import PHASES

PHASE_TARGETS = {
    "engine_start": (8, 0, 0), "warm_up": (22, 0, 0), "takeoff": (100, 0, 125),
    "climb": (82, 4500, 180), "cruise": (67, 5200, 205),
    "endurance_cruise": (52, 5600, 150), "rapid_throttle_transition": (90, 5400, 190),
    "descent": (42, 700, 165), "landing": (24, 0, 70), "shutdown": (0, 0, 0),
}

def mission_phases(sample_count: int, rng: np.random.Generator) -> list[str]:
    phases = list(PHASES)
    if rng.random() < .35:
        phases.remove("rapid_throttle_transition")
    if rng.random() < .25:
        phases.remove("endurance_cruise")
    weights = {p: 1.0 for p in phases}
    weights.update(engine_start=.025, warm_up=.07, takeoff=.045, climb=.12,
                   cruise=.28, endurance_cruise=.24, rapid_throttle_transition=.04,
                   descent=.12, landing=.04, shutdown=.02)
    raw = np.array([weights[p] for p in phases], dtype=float)
    counts = np.maximum(3, np.floor(raw / raw.sum() * sample_count).astype(int))
    counts[np.argmax(counts)] += sample_count - counts.sum()
    return [p for p, n in zip(phases, counts) for _ in range(n)]

def smooth_targets(phases: list[str], rng: np.random.Generator):
    n = len(phases)
    throttle = np.zeros(n); altitude = np.zeros(n); airspeed = np.zeros(n)
    previous = np.array(PHASE_TARGETS[phases[0]], float)
    for i, phase in enumerate(phases):
        target = np.array(PHASE_TARGETS[phase], float)
        if phase == "rapid_throttle_transition":
            target[0] = 35 + 60 * (0.5 + 0.5 * np.sin(i * .7))
        alpha = .12 if phase not in ("climb", "descent") else .025
        previous += alpha * (target - previous)
        throttle[i], altitude[i], airspeed[i] = previous
    altitude *= rng.uniform(.75, 1.15)
    throttle += rng.normal(0, .7, n)
    airspeed += rng.normal(0, 1.2, n)
    return np.clip(throttle, 0, 100), np.clip(altitude, 0, 8000), np.clip(airspeed, 0, 260)

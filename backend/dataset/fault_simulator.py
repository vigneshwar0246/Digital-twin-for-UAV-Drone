"""Gradual single-fault profiles and physically interpretable effects."""
import numpy as np

def fault_profile(fault: str, n: int, rng: np.random.Generator, terminal_severity="High"):
    if fault == "Healthy":
        return np.zeros(n), np.zeros(n, dtype=bool)
    onset = int(n * rng.uniform(.30, .55))
    progress = np.zeros(n)
    ranges = {"Low": (.20, .31), "Medium": (.45, .64), "High": (.78, 1.0)}
    progress[onset:] = np.linspace(.03, rng.uniform(*ranges[terminal_severity]), n - onset)
    # Small varying progression prevents labels from being one exact sensor threshold.
    progress[onset:] *= np.clip(1 + rng.normal(0, .025, n-onset), .9, 1.1)
    progress = np.maximum.accumulate(np.clip(progress, 0, 1))
    return progress, progress >= .08

def severity_labels(progress):
    return np.select([progress == 0, progress < .34, progress < .67],
                     ["None", "Low", "Medium"], default="High")

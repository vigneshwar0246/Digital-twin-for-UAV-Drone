# Stage 6 independent audit — 2026-10-11

Scope: read-only inspection of the existing Stage 4/6 code and artifacts. No model was trained, loaded for inference, or promoted. Dataset and historical output files were not modified.

## Verified directly

- SHA-256 hashes and byte sizes in `reports/stage6_preflight_hashes.json` match the current Dataset v1 and v2 full CSVs, v2 mission manifest, Stage 4 Candidate A model, and v2 C4 model. The last two model files have identical hashes.
- All seven comparable Candidate A metrics in `reports/stage6_candidate_comparison.csv` match `outputs_stage4/reports/stage4_candidate_comparison.csv` exactly for validation, challenge, time-forward, and known-engine validation. This is **artifact-to-artifact agreement**, not an independent inference rerun.
- Rebuilding splits with the current `evaluation_protocol.build_evaluation_splits`, seed 26054, and the current v2 full CSV yields 200,000 rows: fit 111,672; validation 30,002; challenge 30,004; time-forward 28,322. Missions are disjoint; validation and challenge engines are disjoint from fit and from each other. Time-forward intentionally shares 13 engines with fit, but no missions. The rebuilt manifest reports chronological fit/time-forward separation and nine-class coverage. Exact duplicate full rows: zero.
- The stored comparison marks Candidate B as gate-failing on every partition. Cooling recall is 0.6165 validation, 0.7012 challenge, 0.5799 time-forward, and 0.5163 known-engine; validation fuel-injector recall is 0.7894. Each is below the frozen 0.80 required-class threshold. These are **reported metrics**, not independently reproduced scores.
- The Stage 6 evaluator trains `StandardScaler`, `OneHotEncoder`, and `HistGradientBoostingClassifier` on the fit partition only. A and B use the same split dictionary and metric function in the current source. The stored confusion matrices and reports are present for all four evaluation partitions.

## Methodological blockers

1. **Partition reproduction mismatch.** The Stage 6 coverage report says fit 111,760, challenge 30,032, and time-forward 28,143 frames (its validation count is 30,002). The current split code on the same SHA-256 verified CSV returns 111,672, 30,004, and 28,322. The reported Stage 6 samples therefore cannot be established as the current protocol's samples. Investigate historical code or split manifests without overwriting results. The Candidate A metric agreement alone does not resolve this mismatch.
2. **Cruise eligibility is not consecutive.** `evaluate_stage6.compute_causal_cruise_baseline_features` appends eligible frames to `accumulated_cht`, but does not clear the list when a frame is ineligible. It can lock after 36 eligible frames separated by gaps, contrary to the stated consecutive 180-second window. It also does not verify actual timestamp spacing.
3. **Lock-frame timing differs from the report.** The function applies normalized features on the 36th accumulation frame, although the report says they apply only on subsequent frames. The report says per-cylinder *median*; code uses *mean*. The code checks mean spread over the accumulated window, not rejection of each frame above 16 °C. These differences require a corrected method and a new, isolated evaluation before Candidate B can be used.
4. **Coverage detail is insufficient.** `baseline_coverage_audit.json` contains mission and aggregate frame percentages only. It does not identify phase, fallback reason, or per-mission frame counts. The one time-forward mission without lock is visible only in aggregate.
5. **No Stage 6 offline/live parity evidence.** The 56-feature cruise-normalized schema is implemented in the offline evaluator, while the application provider expects the 21-feature `live-telemetry-v1` schema. Candidate B cannot be safely attached to the current runtime. Artifact checksum/registry metadata for the Stage 6 B model is also absent from a trusted runtime registry.

## Interpretation and decision

The reported false-alarm rate is the proportion of healthy frames predicted as *any* fault; counts of healthy frames predicted specifically as cooling are a separate measure. The reported reduction in total false alarms must not be described as a cooling-only reduction. The stored ECE values are evaluation metrics and do not establish a calibrated runtime probability. Detection delay is in seconds; false-alarm rate is a fraction of healthy frames. Full-population evaluation is reported, including baseline-unavailable frames, but cannot be independently reproduced until the split discrepancy is resolved.

**Decision:** Stage 6 independent audit is complete with unresolved reproducibility and method blockers. Candidate B remains research-only and is not integrated into live diagnostics. No further training is justified until split provenance and baseline semantics are corrected in a new isolated experiment. The existing frozen release gate and default-disabled ML behavior remain unchanged.

## Commands used

- Python `hashlib.file_digest(..., 'sha256')` over the five preflight paths.
- Python `csv.DictReader` comparison of Stage 4 and Stage 6 Candidate A rows.
- Python `pandas.read_csv(..., keep_default_na=False)` and `build_evaluation_splits(frame, 'fault_type', 26054)` with mission, engine, and duplicate-row checks.

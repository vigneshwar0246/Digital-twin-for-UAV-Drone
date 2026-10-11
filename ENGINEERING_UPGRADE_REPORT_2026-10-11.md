# AERION engineering upgrade record — 2026-10-11

> **Current status:** This is a chronological engineering log. Earlier branch, working-tree, and publication statements describe the state at the time of each section. The latest code and documentation are on `main`; the historical nine-class ML release gate remains failed. For current startup instructions use [README.md](README.md) and [backend/README.md](backend/README.md).

## Scope and baseline

The working tree was clean on `main` at commit `d913e89` before this work. The existing FastAPI, React/Vite/Three.js, physics, sensor fusion, diagnostics, auth, dataset, evaluation, and SQLite modules were retained. The pre-change Python suite in the scikit-learn 1.9.1 virtual environment had **95 passed, 2 failed**: both failures explicitly required the separate 1.7.2 experimental environment. Frontend unit tests (3) and TypeScript checking passed.

Historical Dataset v1/v2, saved model artifacts, Stage 4–6 evidence, and their release criteria were not edited. No commit, push, or deployment was performed.

## Implemented and verified

| Area | Change | Evidence |
| --- | --- | --- |
| Mission persistence | SQLite schema v3 adds `simulation_snapshots`. New simulations save their exact telemetry, original assessments, and twin states. A mission ID cannot be reused with different configuration. | Migration, conflict, snapshot, and replay tests pass. |
| Replay | Session replay reads recorded telemetry and labels current-rule findings as re-analysis. The direct simulation replay endpoint returns the original snapshot. Configuration-only legacy missions are labelled as regenerated. Interactive sessions are capped at 32 per process and expire after 30 minutes. | Focused replay, capacity, and expiry tests plus a fresh Uvicorn 12-sample workflow pass. |
| Reports and comparison | Mission reports now include rejected-signal counts, unsynchronized-sample counts, diagnostic source counts, model versions, and re-analysis semantics. Reports no longer retain an interactive replay session. A typed two-mission comparison returns both reports and descriptive metric differences; the replay page exposes it. | Report and comparison tests pass. |
| Simulation | `FULL_MISSION` adds conceptual start, warm-up, ground, takeoff, climb, cruise, descent, landing, and shutdown. Runtime generator v2 exposes per-sample scenario truth and fault onset. Added misfire, alternator degradation, and frozen-sensor scenarios. | Determinism, phase, onset, and signal-effect tests pass. |
| Frontend | Backend simulation displays its saved mission ID. Mission Replay lists saved simulations and labels current-rule replay. Misfire and alternator controls now map to the corresponding runtime scenarios. Sensor fault quality is preserved when a faulty sample has no numeric value. | Unit tests, TypeScript, production build, and all seven browser acceptance cases pass. |
| Security and hygiene | Removed the fixed development password from the frontend and launcher, added a blank-value `.env.example`, and stopped tracking 102 generated `.pyc` files without deleting local copies. Added ignores for browser test and temporary build outputs. | Source search found no remaining occurrence of the removed fixed password in the working tree; Git index shows bytecode removals. The old value remains in Git history and must be rotated wherever reused. |
| CI | Added separate Windows jobs for the 1.9.1 software suite, 1.7.2 experimental tests, read-only dataset validation, release-gate assertion, dependency consistency, tracked bytecode/private-key filename checks, frontend tests, type checks, build, and Chromium browser acceptance. | Workflow YAML parsed locally and its commands were matched to the repository scripts and dependencies; hosted CI execution has not yet been observed. |

The [scenario mapping](backend/app/SCENARIOS.md) records where runtime scenarios, historical dataset classes, and engineering codes differ. The [backend guide](backend/README.md), [frontend guide](frontend/README.md), [security guide](backend/SECURITY.md), and [root README](README.md) were updated.

## ML evaluation and release status

The existing `live-telemetry-v1` Dataset v1 candidate was re-trained and evaluated using `backend.model_evaluation.live_candidate.run()` with its output redirected to a temporary directory. The rerun selected `hgb_regularized`; validation, challenge, and time-forward macro F1 matched the saved sidecar exactly, as did every saved per-class recall (maximum difference **0.0**). The temporary artifacts were deleted. The training data, splits, model artifact, and historical reports were not changed.

| Class | Validation recall | Challenge recall | Time-forward recall |
| --- | ---: | ---: | ---: |
| Alternator degradation | 0.980 | 0.966 | 0.980 |
| Bearing wear | 0.448 | 0.428 | 0.280 |
| Combustion instability | 0.035 | 0.119 | 0.143 |
| Cooling degradation | 0.021 | 0.155 | 0.177 |
| Fuel injector degradation | 0.199 | 0.212 | 0.149 |
| Healthy | 0.885 | 0.865 | 0.876 |
| Lubrication degradation | 0.307 | 0.276 | 0.432 |
| Sensor drift | 0.522 | 0.974 | 0.000 |
| Spark plug misfire | 0.516 | 0.646 | 0.138 |

Macro F1 is **0.430 validation**, **0.509 challenge**, and **0.373 time-forward**. The unchanged minimum 0.80 recall gate for every required fault class fails. The model remains disabled by default and available only through the explicit development research override; its score is uncalibrated. No new model was promoted. The saved offline benchmark and Stage 6 Candidate B were not rerun or changed; the [Stage 6 independent audit](backend/model_evaluation/outputs_stage6/stage6_independent_audit.md) still blocks Candidate B.

## Commands executed and outcomes

All commands below were run from the repository root unless a directory is specified.

| Command or check | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q` (baseline) | 95 passed, 2 failed due to the tests' explicit scikit-learn 1.7.2 requirement in a 1.9.1 environment. |
| Same suite with those two exact tests deselected (final) | **103 passed, 2 deselected**. |
| `python -m pytest backend/tests/test_experimental_live_features.py -q` in installed 1.7.2 environment | **2 passed**. |
| `npm.cmd test` from `frontend/` | **3 passed**. |
| `npx.cmd tsc --noEmit` from `frontend/` | Passed. |
| `npm.cmd run build -- --outDir .verify-final-build` from `frontend/` | Passed; existing Three.js chunk-size advisory. Temporary output removed. |
| `validate(False)` and `validate_v2(False)` | Dataset v1: **16/16** checks; v2: **19/19** checks. No reports overwritten. |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements. |
| `npm.cmd audit --omit=dev --audit-level=high --offline` | Reported 0 vulnerabilities from the local offline audit cache; this is not an online advisory refresh. |
| Isolated rerun of the live-compatible candidate | Selected model and all reported per-class recalls reproduced exactly; gate failed. |
| Fresh Uvicorn on loopback, isolated SQLite database | `/ready` ready; 12 generated samples, 12 saved samples, 12 replayed frames, and a 12-sample report. Temporary database removed. |
| `npx.cmd playwright test e2e/workspace.spec.js --reporter=list` | **3 passed**, clean exit, including a sensor fault quality regression check. An earlier run with the line reporter had stalled during teardown and was interrupted. |
| `npm.cmd run test:e2e -- --reporter=line` from `frontend/`, with `DEBUG=pw:webserver` | **7 passed**, exit code **0**. Debug trace showed server startup, availability, termination, and completed teardown; port 5174 and Vite/Playwright processes were absent afterward. |
| `.\.venv\Scripts\python.exe -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q -p no:cacheprovider --basetemp=...` with the two version-specific tests deselected | **103 passed, 2 deselected**. A preceding run using pytest's default temp root produced 5 setup errors from `PermissionError` on `C:\Users\yogap\AppData\Local\Temp\pytest-of-yogap`; its other 98 tests passed. |
| `.\.venv\Scripts\python.exe -m pytest backend/tests/test_mission_replay.py backend/tests/test_mission_simulation.py backend/tests/test_application_pipeline.py -q -p no:cacheprovider --basetemp=...` | **31 passed**, including simulation → persistence → recorded replay → report and comparison behavior. |
| Isolated Python 3.12 environment with `scikit-learn==1.7.2`: `python -m pytest backend/tests/test_experimental_live_features.py -q` | **2 passed**. The temporary verification environment was removed afterward. |
| `npm.cmd test`, `npx.cmd tsc --noEmit`, `npm.cmd run build` from `frontend/` | **3 passed**, type check passed, production build passed; existing 500 kB bundle advisory. |
| `pip check`, read-only dataset validators, release-gate assertion, YAML parse, tracked artifact check | No broken requirements; Dataset v1 **16/16**, v2 **19/19**; release gate remains `false`; workflow parsed with three jobs; no tracked `.pyc`, `.pem`, or `.key` paths in the current index. |
| `git diff --check` | No whitespace errors. |

## Important remaining limits

- This is a synthetic software demonstrator. No physical engine, UAV, ECU/FADEC, CAN hardware, manufacturer limits, real run-to-failure data, calibration, or airworthiness validation was available. Physics coefficients, alerts, and RUL remain prototype assumptions.
- Dataset v1/v2 do not become new training data through the runtime simulator. Its scenario truth is metadata only. `SENSOR_FREEZE` has no corresponding historical ML class; vibration anomaly does not prove bearing wear. No missing-sample or delayed-packet mission scenario has been added to the runtime generator.
- The ML release gate fails decisively. The offline/live feature-performance gap, Stage 6 split mismatch, and Stage 6 cruise-baseline method issue still need controlled research before any model promotion.
- Legacy configuration-only missions cannot recover the original telemetry if the generator has changed; those replays are explicitly marked as regenerated. New schema v3 missions retain their exact samples.
- The earlier Playwright teardown stall was not reproduced, so a unique causal handle could not be proven. The prior configuration used an `npm.cmd` wrapper and could reuse an unrelated server on port 5173. Browser tests now own a strict, dedicated Vite instance on port 5174 and Playwright's teardown trace confirms it terminates; all seven tests exit cleanly. CI includes this suite. Hosted CI has not run because this workflow is uncommitted and GitHub CLI is unauthenticated here. The prior fixed demo credential remains in Git history; rotate any reused accounts or secrets.
- Mission snapshots and reports are prototype local-storage features. Long-term retention, distributed concurrency, approved authentication, TLS, and immutable audit storage remain deployment work.

## Run locally

From PowerShell at the repository root, run `.\run_project.bat`. It starts the backend at `http://127.0.0.1:8000` and Vite at `http://127.0.0.1:5173`, with local demo mode and engineering diagnostics by default. Open `/twin`, then use **Mission Simulation** and **Mission Replay**. For separate terminals, authentication, environment variables, and optional research ML, follow the [backend setup](backend/README.md). The research model is never part of the default trusted path.

## Git status at handoff

Branch `main`: modified tracked source and documentation, five untracked entries (`.env.example`, `.github/`, this report, `backend/app/SCENARIOS.md`, and `frontend/src/workspace/MissionComparison.tsx`), plus 102 staged removals of tracked `.pyc` files from the index. Those bytecode files were not deleted from the local filesystem. No commit or push was made.

## First-release continuation (2026-10-11)

The release work moved to `codex/aerion-first-reviewed-release`. The request for 85–95% model accuracy cannot be represented as achieved: the saved live-compatible candidate reaches 0.671 validation, 0.699 challenge, and 0.616 time-forward accuracy, and its required-fault recall gate remains failed. No historical dataset, evaluation artifact, feature split, or blocked model was changed. A synthetic benchmark is not evidence of real-aircraft performance.

The current software checks were rerun from this branch. The Python command `python -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q -p no:cacheprovider --basetemp=backend/runtime/pytest-final` with the two scikit-learn 1.7.2-specific tests deselected completed with **103 passed, 2 deselected**. `npm test` completed with **3 passed**; `npx tsc --noEmit` and `npm run build` exited 0. Browser acceptance initially exposed slow cinematic scroll reversal and repeated stalls while capturing software-WebGL screenshots. The scroll controller now follows Lenis' smoothed page position without a second GSAP scrub delay. Incidental screenshots were removed from the acceptance suite while all state and navigation assertions remain. The replay test now compares the displayed telemetry set rather than assuming the first RPM metric changes between its endpoints. The final `npm run test:e2e -- --reporter=list` completed with **7 passed**, exit code **0**, in 1.0 minute.

The repository has a GitHub remote, but local `gh auth status` reports no GitHub CLI session. The connected GitHub integration reports push permission for the repository. Publication and hosted Actions results must be recorded separately after any actual remote update; a local build does not constitute deployment. No production cloud target, TLS domain, or hosted database credentials have been configured for the full FastAPI/SQLite application.

## Local backend ML continuation — 2026-10-11 (uncommitted)

After the request was narrowed to backend-only local work, no further Git commit or push was made. This section records new local work; the earlier feature branch push and draft PR occurred before that correction.

Production now rejects demo mode because it bypasses route authorization. A separate, disabled-by-default synthetic-scenario classifier trains on the runtime mission generator, using only current and earlier telemetry. It does not modify Dataset v1/v2, their saved models, or the frozen nine-fault release gate. Four isolated protocols were evaluated. The initial fixed-severity model failed at 0.2 severity; the next two protocols exposed sensor-freeze and low-severity combustion misses. Protocol `severity-v4` adds causal cylinder-one and paired-cylinder EGT history features and uses new challenge seeds. The selected Extra Trees model passed the synthetic 0.80 per-scenario recall gate at each of 0.2, 0.5, and 0.8 severity on validation and challenge. Aggregate validation accuracy was 0.9508 (macro F1 0.9533); challenge accuracy was 0.9528 (macro F1 0.9546). Lowest fault recall was 0.8620 validation and 0.8498 challenge at severity 0.2. A clean second run reproduced all metric dictionaries and artifact SHA-256 exactly. A separate 0.65-severity probe on other seeds reached 0.9724 accuracy and 0.9462 minimum fault recall.

The local artifact is under ignored `backend/runtime/scenario_model/`; the original fixed-severity artifact was backed up locally. The endpoint `GET /api/v1/simulations/{mission_id}/research-scenario-diagnostics` requires `AERION_ENABLE_SCENARIO_RESEARCH=true`, an authorized user, a saved synthetic mission, ten-minute duration, and five-second sampling. Production refuses the flag. Loading checks a fixed path, artifact checksum, generator and feature-source hashes, dependency version, feature order, class mapping, and synthetic gate before deserialization. Scores are explicitly uncalibrated. An authenticated HTTP smoke test returned 120 predictions for an evaluated mission and HTTP 503 for an unsupported one-minute mission; removing scenario truth did not change predictions.

Final local checks: the pinned scikit-learn 1.9.1 backend/dataset/evaluation suite had **114 passed, 2 deselected**; the two 1.7.2-specific tests had **2 passed** in their matching environment. Read-only Dataset v1 validation passed **16/16**, Dataset v2 **19/19**, and `pip check` found no broken requirements. The original historical live-candidate release gate remains **false** and its dataset hash still matches. The only pytest warnings are third-party TestClient/AnyIO deprecations.

This is a simulator benchmark. Its engine IDs are random-seed labels without engine-specific physics, and every split uses the same generator and five-second sampling. No physical UAV telemetry, independent real dataset, calibration, deployment evidence, or airworthiness claim is supplied. The historical nine-fault model remains blocked.

## Local research integration completion — 2026-10-11

This continuation used project files and local runtime only. The research endpoint now validates all 120 saved telemetry rows against the strict telemetry schema, exact five-second timestamps, finite ordered features, and model output shape/range before returning a result. The response includes per-sample timestamp and score type, model protocol and SHA-256, input SHA-256, feature schema, and synthetic-only validation status. SQLite schema v4 stores the complete response atomically by mission, model checksum, and input checksum; a repeated request returns the original stored response. A failed prediction or write returns HTTP 503 without altering the saved mission or engineering diagnostic history. The Diagnostics page can explicitly load this research result for a backend simulation and labels scores as uncalibrated.

The saved `severity-v4` evaluation record was read without retraining: its fresh synthetic challenge split has **43,200 rows**, **0.9527778 accuracy**, and **0.9545517 macro F1**. Per-class precision, recall, and false-negative rates, plus the location of the complete 10×10 confusion matrix, are recorded in `backend/model_evaluation/README.md`. The fitting, validation, and challenge seed and mission IDs are disjoint; feature inputs exclude truth, IDs, severity, and absolute timestamps. Every split still shares one simulator, so this cannot validate a physical UAV. The historical nine-fault release gate and evaluation artifacts remain unchanged and blocked.

Final commands and results from the repository root: `.\.venv\Scripts\python.exe -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q -p no:cacheprovider --basetemp=backend/runtime/pytest-ml-local-milestone` with the two named 1.7.2-only tests deselected: **118 passed, 2 deselected**, with two third-party deprecation warnings. `C:\Users\yogap\anaconda3\python.exe -m pytest backend/tests/test_experimental_live_features.py -q -p no:cacheprovider --basetemp=backend/runtime/pytest-ml-172-local`: **2 passed**. `.\.venv\Scripts\python.exe -m pip check`: no broken requirements. From `frontend/`, `npm.cmd test`: **3 passed**; `npx.cmd tsc --noEmit`: passed; `npm.cmd run build`: passed with the existing large-chunk advisory. An authenticated FastAPI TestClient run using an isolated SQLite database saved a ten-minute mission, returned HTTP 200 with 120 predictions, wrote one prediction record, and returned an identical response on repeat with the record count still one. TestClient executed the actual startup lifespan. A separate loopback Uvicorn launch command was rejected by the local command policy before execution, so no independent Uvicorn process result is claimed.

No independent real engine telemetry, external validation set, calibrated model probabilities, or operational approval is available. The documented local startup and request commands are in `backend/README.md`; production continues to reject this opt-in research mode.

## Main-branch publication verification — 2026-10-11

The current local project was checked before publication: the Python 1.9.1 suite had **118 passed, 2 deselected**; the two 1.7.2-specific tests had **2 passed** in their matching environment. Frontend unit tests had **3 passed**, TypeScript checking and the production build exited successfully, and `pip check` found no broken requirements. Playwright browser acceptance had **7 passed** and exited cleanly. The build retained its existing large-chunk advisory. The local research artifact and SQLite databases remain runtime files, outside the source publication; a fresh checkout must train the opt-in research artifact as documented before using that endpoint. These software results do not change the historical ML release gate or establish real-aircraft validation.

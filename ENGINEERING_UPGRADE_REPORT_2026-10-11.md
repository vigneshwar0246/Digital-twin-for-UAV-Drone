# AERION engineering upgrade record — 2026-10-11

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

# AERION backend and research ML integration — 2026-10-11

> **Historical Phase 2 record:** Schema, test counts, and publication statements below describe that milestone. The current SQLite schema is v4 and current verification is in the [engineering upgrade record](../ENGINEERING_UPGRADE_REPORT_2026-10-11.md).

## Implemented

- `app/config.py`: validated history bounds, database target, demo dataset, and production research-mode restriction. `AERION_ENABLE_ML_DIAGNOSTICS` defaults to `0`; the prior `DIGITAL_TWIN_ML_ENABLED` name remains a fallback.
- `app/store.py`: versioned the existing SQLite schema with `PRAGMA user_version = 2`, preserving legacy telemetry rows and adding `state_json` when absent. Added a database readiness probe and bounded, deterministic history ordering.
- `app/main.py` and `app/schemas.py`: added a typed `/api/v1/ready` contract and a typed diagnostic result on telemetry assessments. Liveness and readiness are separate. Readiness stays available for engineering fallback when ML cannot load.
- `app/ml_diagnostics.py`: runtime loads only the existing repository live-compatible candidate, verifies its SHA-256 and sidecar before deserializing it, retains the strict scikit-learn and feature-schema checks, and rejects malformed class-score dimensions. No artifact was rewritten.
- `app/core.py`: returns a distinct research ML prediction when a trusted model is explicitly enabled, an engineering result when disabled/unavailable, and an unavailable result for stale or invalid required telemetry. The legacy `predicted_fault` remains the engineering-rule result. A previously uncalibrated numeric `confidence` heuristic is now null; `diagnostic_result.score_kind` describes the actual score.
- Frontend `workspace/api.ts`, `types.ts`, `MLStatus.tsx`, and `Panels.tsx`: consume the real diagnostic result, show model version, source, sensor quality, uncalibrated score warning, backend readiness, and bounded persisted history. Removed hardcoded dataset counts and mission claims from Settings. The Three.js experience was left intact.
- `run_project.ps1`: waits for truthful backend readiness rather than liveness; PowerShell syntax was parsed successfully.
- `tests/test_application_pipeline.py`: added config, migration, readiness, persistence, stale-input, invalid-input, checksum, and malformed-score tests.

## Candidate and gate

The integrated artifact is **Dataset v1 live-telemetry candidate v1.0.0**, selected as `hgb_regularized` in `model_evaluation/outputs/live_candidate/evaluation.json`. It shares the ordered `live-telemetry-v1` feature contract with inference. Its SHA-256 is `e8c637760bb2a4154af4042258e1bbc7956056514cd5ef9100829cf3787049b3`; its recorded dataset SHA-256 is `2b9a25ab4600bebb4d3d1d95504e22889ce86714bb680b7e68d524d3cb68041e`. Runtime scikit-learn 1.9.1 matches the artifact record. The model is **research-only** and disabled by default.

The saved evaluation reports minimum required-fault recalls of **0.021 validation**, **0.119 challenge**, and **0.000 time-forward**. Cooling recall is 0.021, 0.155, and 0.177 respectively. The frozen 0.80 per-class release gate **fails**. Scores are uncalibrated; even a high score is not a validated fault probability. The dataset is synthetic. Stage 6 Candidate B remains blocked by the Phase 1 audit and was not used or changed.

## Executed verification

- `.venv/Scripts/python.exe -m pytest backend/tests/test_application_pipeline.py backend/tests/test_api.py backend/tests/test_ml_diagnostics.py -q`: **26 passed** after the final confidence-contract and database-transaction changes.
- `.venv/Scripts/python.exe -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q`: **94 passed, 2 failed**. The two experimental feature tests explicitly assert scikit-learn 1.7.2; `.venv` has 1.9.1. They were then run under the 1.7.2 environment as part of the matching-environment suite.
- `python -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q --deselect=backend/tests/test_ml_diagnostics.py::test_repository_candidate_loads_with_all_synthetic_classes`: **96 passed, 1 deselected**. The deselected artifact-load test was exercised successfully under `.venv`.
- `.venv/Scripts/python.exe -m pytest backend/tests backend/model_evaluation/tests backend/dataset/tests -q --deselect=backend/tests/test_experimental_live_features.py::test_offline_streaming_feature_parity --deselect=backend/tests/test_experimental_live_features.py::test_bad_telemetry_and_mission_reset`: **95 passed, 2 deselected**. Those two passed under the 1.7.2 suite above.
- `npm.cmd test`: **3 passed**. `npx.cmd tsc --noEmit`: passed. `npm.cmd run build -- --outDir .verify-ml-build`: passed. Default `dist` build could not replace a protected pre-existing asset, so the build used a separate temporary output directory.
- `npx.cmd playwright test e2e/workspace.spec.js`: both tests printed **ok**; the process stalled during teardown and was interrupted, so no clean suite exit is claimed.
- Fresh Uvicorn fallback server on port 8765: `/health` 200, `/ready` 200 with `engineering_rules` and ML `disabled`, telemetry POST 201, persisted history GET 200 with identical engineering result.
- Isolated research-mode API lifespan: `/ready` 200 with `ml_research` and ML `ready`; telemetry POST 201 returned a real `Healthy` prediction with uncalibrated score 0.9994; persisted history returned the same result.
- Live research-mode backend plus Vite plus Playwright browser on ports 8766/5174: the Diagnostics panel rendered a real `Spark_Plug_Misfire` research prediction, score 0.517 labelled uncalibrated, model version, failed-gate warning, ML readiness, and ten persisted history entries. Browser reported zero page errors.

## How to run locally (PowerShell, two terminals)

Install once from the repository root if `.venv` does not already contain dependencies:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd install
```

Terminal 1, fallback mode (the default):

```powershell
cd 'D:\projects D\aircraft'
$env:AERION_ENABLE_ML_DIAGNOSTICS='0'
$env:DIGITAL_TWIN_DEMO_MODE='true'
$env:DIGITAL_TWIN_DB=Join-Path $env:TEMP 'aerion-demo.db'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

For an explicit **research-only** ML demo, replace the first environment assignment with:

```powershell
$env:AERION_ENABLE_ML_DIAGNOSTICS='1'
$env:DIGITAL_TWIN_ML_ALLOW_UNVALIDATED='true'
```

Terminal 2:

```powershell
cd 'D:\projects D\aircraft\frontend'
npm.cmd run dev
```

Open `http://127.0.0.1:5173/diagnostics`. The demo dataset stream populates the backend engine `DATASET_ENGINE_010`. Use **Load saved diagnostic history** in Diagnostics. Check `http://127.0.0.1:8000/api/v1/ready` and `http://127.0.0.1:8000/docs`. With demo mode off, authenticated clients can POST validated telemetry to `/api/v1/telemetry` and GET `/api/v1/engines/{engine_id}/history?limit=20`. The demo engine's stream is intentionally cleared when demo mode restarts; separately ingested engine history persists in the selected SQLite file.

## Remaining limits and safety review

- The two scikit-learn versions serve different historical experiment tests. Do not weaken either version guard. Use `.venv` (1.9.1) to serve the live-compatible model and the current base Python environment (1.7.2) for the controlled experimental-feature tests.
- The live-compatible model fails the release gate badly. It is useful only as an honest synthetic research demonstration. No real-flight or airworthiness validation exists. Stage 6 Candidate B's split and baseline-method blockers remain unresolved.
- Browser rendering and history retrieval were verified in a live demo. Full frontend acceptance and deployment were not performed.
- Pre-existing uncommitted Dataset v2, Stage 4–6 artifacts, Python bytecode changes, and the Phase 1 reports were preserved. New work consists of the source, test, frontend, and this report listed above. Dataset files, frozen models, published metrics, the release gate, and Candidate B source were not modified. No commit, push, merge, or deployment occurred.
- Final branch: `investigation/synthetic-data-v2-design`. Git status still shows the pre-existing modified tracked bytecode and untracked Dataset v2/Stage 4–6 trees. This work additionally modified `backend/app/{config,core,main,ml_diagnostics,schemas,store}.py`, `frontend/src/workspace/{MLStatus,Panels,api,types}.*`, and `run_project.ps1`; it added `backend/tests/test_application_pipeline.py` and this report. The generated frontend verification build was removed after use. `git diff --check` reported no whitespace errors.

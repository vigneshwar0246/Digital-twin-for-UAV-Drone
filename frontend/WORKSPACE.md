# AERO-TWIN workspace

Run `npm.cmd run dev` from `D:\projects D\aircraft\frontend` after starting the backend. The cinematic remains at `/`; its ENTER button opens `/twin`. Direct links to sidebar routes work with Vite's SPA fallback. Hosting outside local development would need an `index.html` fallback and an `/api` proxy.

The workspace uses ordinary navigation and page scrolling. Unmounting the introduction removes its GSAP/Lenis controllers. No scroll-driven camera exists inside the workspace.

## Data flow

`demo.ts` or `api.ts` -> normalized quality-aware Frame -> bounded store -> engine, inspector, chart, diagnostics and reports. Real mode is the initial source. Backend transport polls the existing history endpoint for the latest sample, backs off on failure, discards old timestamps and marks telemetry stale after 10 seconds. A configured WebSocket can replace polling when the backend implements one; no WebSocket backend is provided now. Bearer tokens are held in session storage for authenticated mode; requests have timeouts and request IDs. Local dataset demo mode permits access without a token.

Interactive local demo equations are UI demonstration relationships, not validated aircraft physics. Scores from scripted faults are engineering scores, not ML probabilities. Local demo does not supply RUL, performance maps, FFT, CAN frames or calibrated uncertainty. Missing data stays missing. The interactive demo sends telemetry to `/telemetry/synchronize` and displays the returned assessment when available. Backend simulations use `/simulations`; they do not submit unsupported custom throttle or environment values. Backend-generated telemetry is played with matching assessments. Replay sessions fetch frames through the existing backend twin replay processor.

The Diagnostics panel reads the typed `assessment.diagnostic_result`. It displays the model's fault class, version, score kind, source, sensor quality, and warning if explicit research ML is enabled. It polls `/ready` and loads the latest bounded persisted history on demand. For a saved backend simulation, a separate button requests the opt-in scenario-research endpoint. Its response is stored in SQLite with model/input checksums and displays simulator classes with uncalibrated scores; it does not replace engineering fault cards. The engineering fault cards and visualization continue to reflect rule/statistical diagnostics; a research ML score does not drive physical fault highlighting or imply a calibrated probability.

Playback uses telemetry timestamps and a separate simulation clock. The conceptual SVG cutaway slows the crank motion for visibility. It is not the supplied photograph or a validated kinematic engine model. The reference PNG was not available as a filesystem attachment: use Import engine PNG in the viewer. Image imports are session-local; the component maintains aspect ratio and supports exterior/cutaway, pan, zoom and reset. A future shipped image can replace this input; no remote asset URL is invented.

Current limitations: fleet inventory, raw CAN stream, maintenance persistence, performance maps and preflight approval have no supplied backend contracts. Their pages expose available data and explicit unavailable states. Acknowledgements and maintenance notes are session-local. Chart history is 240 frames; recordings are capped at 14,400 frames. Reports describe this bounded recording. Historical backend datasets and backend physics/RUL remain prototype and simulation based.

## Verification

`npm.cmd run build`, `npm.cmd test`, `npx.cmd tsc --noEmit`, `npm.cmd run test:e2e`.

# AERO-TWIN workspace

Run `npm.cmd run dev` from `D:\aircraft\frontend`. The cinematic remains at `/`; its orange ENTER button opens `/twin`. Direct links to all sidebar routes work with Vite's SPA fallback. Configure production hosting to serve index.html for frontend routes, with `/api` proxied separately.

The workspace uses ordinary navigation and page scrolling. Unmounting the introduction removes its GSAP/Lenis controllers. No scroll-driven camera exists inside the workspace.

## Data flow

`demo.ts` or `api.ts` -> normalized quality-aware Frame -> bounded store -> engine, inspector, chart, diagnostics and reports. Backend transport polls the existing latest endpoint once per second, backs off on failure, discards old timestamps and marks telemetry stale after 10 seconds. A configured WebSocket can replace polling when the backend implements one. Authentication tokens remain in memory and requests have timeouts and request IDs.

Demo is the initial mode. Local equations are UI demonstration relationships, not validated aircraft physics. Scores from scripted faults are engineering scores, not ML probabilities. Local demo does not supply RUL, performance maps, FFT, CAN frames or calibrated uncertainty. Missing data stays missing. Backend simulations use existing /simulations; they do not submit unsupported custom throttle or environment values. Backend-generated telemetry is played with its matching assessments. Replay sessions fetch frames through the existing backend twin replay processor.

Playback uses telemetry timestamps and a separate simulation clock. The conceptual SVG cutaway slows the crank motion for visibility. It is not the supplied photograph or a validated kinematic engine model. The reference PNG was not available as a filesystem attachment: use Import engine PNG in the viewer. Image imports are session-local; the component maintains aspect ratio and supports exterior/cutaway, pan, zoom and reset. A future shipped image can replace this input; no remote asset URL is invented.

Current limitations: fleet inventory, raw CAN stream, maintenance persistence, performance maps and preflight approval have no supplied backend contracts. Their pages expose available data and explicit unavailable states. Acknowledgements and maintenance notes are session-local. Chart history is 240 frames; recordings are capped at 14,400 frames. Reports describe this bounded recording. Historical backend datasets and backend physics/RUL remain prototype and simulation based.

## Verification

`npm.cmd run build`, `npm.cmd test`, `npx.cmd tsc --noEmit`, `npm.cmd run test:e2e`.

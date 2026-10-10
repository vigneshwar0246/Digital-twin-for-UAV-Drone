# Engine fault visualization

The workspace opens with the previous **2D cutaway** by default. Faults add simple component tints, one active label, and a compact score/uncertainty overlay; the complete evidence stays in the diagnostic cards. Large halos, surface flashing, and assembly shaking are disabled in this simplified view. Every active fault remains selectable below the engine. The optional **3D engine** button is retained.

The workspace also reuses the existing `components/Engine.jsx` Three.js geometry in a separate scene. The cinematic aircraft, GSAP timelines, and Lenis code are unchanged. The original SVG cutaway and imported-image view remain available using the viewer controls.

## Diagnostic data flow

Live history and mission replay already contain `state.faults.diagnostics`. Backend simulation now returns a parallel `states` array for every telemetry sample. The interactive demo sends generated telemetry to `/api/v1/telemetry/synchronize`; the returned assessment/state drives visualization and recording. If that request fails, the demo pauses with an error and clears diagnostic highlights.

`api.ts` preserves `fault_code`, `fault_name`, `severity`, `engineering_score`, `affected_subsystems`, `evidence`, and `uncertainty`. Only faults tagged `BACKEND_DIAGNOSTIC` enter the visualization controller. Legacy assessment alerts and locally scripted faults cannot activate physical effects. Scores are displayed as engineering scores.

`FaultVisualizationController.ts` maps these results into semantic regions, colors, intensity, pulse behavior, and vibration amplitude. `EngineFaultScene.jsx` adapts those regions to the existing mesh names and drives emissive materials and the camera. `useFaultSurfaces.ts` applies the same mapping to the SVG component groups.

## Fault mapping

| Backend code | Physical response |
|---|---|
| MISFIRE | Irregular glow on cylinders/combustion; a single cylinder is used only with explicit cylinder metadata |
| FUEL_INJECTOR_DEGRADATION | Amber/orange/red injector material glow |
| COOLING_SYSTEM_DEGRADATION | Cylinder cooling-fin/head region glow |
| LUBRICATION_ISSUE | Oil sump highlight and lubrication label; patterned warning in cutaway |
| SENSOR_DRIFT | Sensor marker highlight and uncertainty evidence; dashed cutaway indicator |
| SENSOR_FAILURE | Red sensor material and failure label; broken/dashed cutaway outline |
| COMBUSTION_INSTABILITY | Irregular cylinder/combustion glow |
| OVERHEATING | Strong severity-dependent head/body glow; broad animated heat halo in cutaway |
| ABNORMAL_VIBRATION | Bounded engine-assembly movement plus region glow; the page and camera remain steady |
| BATTERY_ALTERNATOR_ABNORMALITY | Electrical proxy geometry and pulsing warning glow |
| INJECTION_TIMING_ABNORMALITY | Injector pulses with differing phase; moving dashed timing outline in cutaway |

LOW/ADVISORY, MEDIUM/WARNING, HIGH, and CRITICAL map to increasing amber/orange/red intensity. Backend score influences intensity within a bounded range. Reduced-motion preferences disable surface pulses and vibration.

## Interaction

The viewer shows an active-fault evidence overlay and a compact button for every active diagnostic. Click a label, a viewer fault button, or a diagnostic card's Focus component button to focus the affected region. Orbit/zoom controls remain usable. Reset view restores the overview camera. Shared regions use their strongest active effect while every fault remains independently selectable. Removing diagnostics clears their surfaces and labels.

## Component limits

The geometry is conceptual. Cooling, heads, and combustion share the cylinder bank; individual injectors exist, but most current diagnostics do not identify a particular cylinder. There is one sensor marker and an electrical proxy, rather than a complete sensor inventory or manufacturer battery/alternator assembly. Unknown fault codes map to the engine body. Evidence containing a temperature-channel name alone is never interpreted as proof of cylinder localization. An imported image has no mesh anatomy; use the 3D or cutaway view for component effects.

The existing live diagnostics generally provide subsystem evidence, not exact component identity. The UI reports this limitation. To replace the engine model, adapt the region-to-mesh resolver without changing the backend contract or fault controller.

## Changed files

- Backend: `backend/app/main.py`, `backend/tests/test_frontend_sync.py`.
- Data contracts and demo: `frontend/src/workspace/types.ts`, `api.ts`, `demo.ts`, `store.ts`.
- Viewer and cards: `frontend/src/workspace/EngineViewer.tsx`, `Panels.tsx`.
- New visualization modules: `frontend/src/workspace/FaultVisualizationController.ts`, `EngineFaultScene.jsx`, `useFaultSurfaces.ts`, `fault-visualization.css`.
- Browser checks: `frontend/e2e/fault-visualization.spec.js`, `workspace.spec.js`.

## Verification

Frontend build, TypeScript check, and three Node tests pass. Six Playwright checks pass, covering the cinematic introduction, responsive layout, backend faults, focus/reset, clearing, backend demo/recorded replay, navigation, exports, and backend failure. Twelve focused backend tests pass, including one-state-per-simulation-sample diagnostic contract coverage. Browser fixtures are confined to tests; no test faults are injected into application code.

Vite still reports the Three.js shared bundle exceeding its 500 kB advisory. Backend tests report existing Starlette/HTTPX deprecation warnings.

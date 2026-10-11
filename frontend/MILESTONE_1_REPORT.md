# Milestone 1 implementation and verification

> **Historical Milestone 1 record:** This describes the original cinematic-only frontend. The current backend-connected workspace is documented in [README.md](README.md) and [WORKSPACE.md](WORKSPACE.md).

## Initial project audit

The existing frontend directory contained empty src and public directories.
There were no frontend dependencies, entry point, router, components, styles,
UAV models or engine models. No existing frontend functionality was replaced.
The backend and its audit report were left untouched by this milestone.

## Delivered

- React/Vite app with one persistent React Three Fiber scene.
- Off-white aerospace presentation, orange atmosphere, metallic concept UAV,
  rotating translucent propeller, HUD, hover outline and selection pulse.
- Reversible GSAP ScrollTrigger flight timeline with scrub.
- Hard click checkpoint: the page has no engine scroll range until selection.
- Actual aircraft raycast selection, accessible prompt and Enter shortcut.
- A separate reversible camera timeline targeting the embedded piston engine.
- Airframe opacity transitions from 100% to 10%; the engine stays in the same
  scene throughout. The final camera pose has no automatic orbit or drift.
- Responsive desktop/mobile framing, capped DPR, lazy scene loading and cleanup.
- Semantic engine nodes for later component bindings, without telemetry logic.

## Verification

Production build succeeded. Three state/path tests and two Chromium browser
tests passed. Browser tests covered all nine requested interaction scenarios,
including clicking the 3D aircraft itself on desktop, the accessible prompt on
mobile, reverse flight/zoom, scroll locking before selection and refresh reset.
The desktop test captured no page exceptions or console errors.

Generated desktop intro, settled and engine screenshots and a mobile settled
screenshot were inspected visually. These are automated browser checks with
visual inspection, not a claim of manual testing on every device.

Vite reports a large lazy-loaded 3D chunk (approximately 923 KB uncompressed,
254 KB gzip), mostly Three.js/R3F/Drei. This is a performance warning, not a
compilation error. Real-device frame-time profiling remains useful before
deploying to low-power hardware.

## Files

- `src/main.jsx`, `App.jsx`: entry and experience composition.
- `src/components/`: UAVScene, Aircraft, Propeller, Engine, Clouds, AircraftHUD,
  SelectionPrompt.
- `src/animation/`: aircraftTimeline, engineZoom, scrollController.
- `src/state/experienceState.js`: transition and selection policy.
- `src/styles.css`, `refinements.css`: presentation and responsive styling.
- `tests/`, `e2e/`, `playwright.config.js`: logic and browser verification.
- `package.json`, `package-lock.json`, `vite.config.js`, `index.html`: build setup.
- `public/models/README.md`: future GLB orientation and replacement guide.

## Model limitation

Both objects are procedural concept geometry, visibly identified as such in the
experience. No external models are fetched. Place future licensed assets at
`public/models/uav.glb` and `public/models/piston-engine.glb`, then integrate them
at the documented Aircraft and Engine component slots. Merely placing a file in
the folder does not automatically replace the procedural model.

## Start

```powershell
cd D:\aircraft\frontend
npm.cmd run dev
```

Visit http://127.0.0.1:5173. On a fresh checkout run `npm.cmd ci` first.

# AERION frontend — current application

The React/Vite workspace at `/twin` consumes the FastAPI backend through `src/workspace/api.ts`. It displays telemetry, engineering diagnostics, an explicitly labelled research ML prediction when enabled, backend readiness, and bounded SQLite diagnostic history. The cinematic Three.js aircraft introduction remains at `/`; the 2D cutaway and optional 3D engine views are conceptual visualizations.

Start the backend first using the [root README](../README.md), then from the repository root:

```powershell
cd 'D:\projects D\aircraft\frontend'
npm.cmd install
npm.cmd run dev
```

Open `http://127.0.0.1:5173/diagnostics`. Vite proxies `/api` to `http://127.0.0.1:8000` by default; `DIGITAL_TWIN_API_TARGET` changes that development proxy target. `VITE_API_BASE_URL` defaults to `/api/v1`. `VITE_WS_URL` should remain empty until an actual WebSocket backend is supplied.

The Diagnostics page keeps engineering fault cards separate from `diagnostic_result`, which identifies `engineering_rules`, `ml_research`, or `unavailable`. Research ML scores are uncalibrated and the model failed its release gate. The **Load saved diagnostic history** control reads persisted, bounded backend history. The browser's local simulation controls and visual models are still demonstrators; they do not establish aircraft performance.

The **Run backend simulation** control saves a mission snapshot and displays its mission ID. Its standard profile now covers start through shutdown; weather and throttle variants remain available. In **Mission Replay**, load backend missions, select a saved simulation, and open it to re-analyze the recorded telemetry with current rules. The page can also compare two mission reports side by side. Replay and comparison are labelled as re-analysis; the recorded original assessment remains available through the simulation snapshot API. The browser no longer contains a default admin password. The Windows launcher uses local demo mode; authenticated setups require a separately provisioned account.

Verify from `frontend/` with `npm.cmd test`, `npx.cmd tsc --noEmit`, and `npm.cmd run build`. `npx.cmd playwright test e2e/workspace.spec.js` covers workspace navigation and backend failure fixtures. A live research-mode browser and history check is recorded in the [backend implementation report](../backend/PHASE2_IMPLEMENTATION_REPORT.md). See [WORKSPACE.md](WORKSPACE.md) for data-flow and UI limits.

## Historical Milestone 1 notes

The section below records the original cinematic-only milestone. Its scope statements describe that milestone, not the current integrated application.

# AERION — Milestone 1

Run from the repository root in PowerShell:

```powershell
cd 'D:\projects D\aircraft\frontend'
npm.cmd install
npm.cmd run dev
```

Open http://127.0.0.1:5173. `npm.cmd` avoids PowerShell's npm.ps1 execution-policy restriction.

The project audit found empty src/public folders, with no package.json, router,
styles, UI or assets. This milestone creates one React/Vite experience, using
Three.js, React Three Fiber, Drei, GSAP ScrollTrigger and Lenis. No services or
external model/image/font URLs are needed. All changes are inside frontend.

The aircraft and engine are clearly labeled procedural concept placeholders.
Model replacement locations and orientation requirements are in
`public/models/README.md`.

## Interaction

INTRO → AIRCRAFT_FLIGHT → AIRCRAFT_SETTLED. Scroll drives the same flight
timeline forward and backward. The page ends at the settled aircraft until the
aircraft or its keyboard-accessible selection prompt is clicked.

Selection unlocks additional scroll distance: AIRCRAFT_SELECTED → ENGINE_ZOOM →
ENGINE_HERO. The aircraft stays in place and the camera moves to its embedded
engine as the shell fades to 10% opacity. Scrolling upward reverses that exact
path. Selection remains unlocked until refresh, which resets progress to zero.

`src/state/experienceState.js` owns transitions; `src/animation` owns flight,
camera and scroll behavior. Components separate aircraft, rotor, engine,
atmosphere, HUD and prompt. Per-frame Three.js state uses mutable refs rather
than React rerenders. DPR is capped at 1.5 and the scene bundle is lazy loaded.

## Verification

```powershell
npm.cmd run build
npm.cmd test
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Browser tests cover refresh, flight reversal, the click gate, zoom reversal,
mobile selection, horizontal overflow and page errors, and save screenshots.
Concept meshes do not represent an approved manufacturer's aircraft or engine.
Dashboard, telemetry, login and backend integration are outside this milestone.

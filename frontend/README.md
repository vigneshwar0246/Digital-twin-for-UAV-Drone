# AERION — Milestone 1

Run from the repository root in PowerShell:

```powershell
cd D:\aircraft\frontend
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

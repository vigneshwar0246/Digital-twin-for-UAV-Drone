# Model replacement slots

Place a licensed UAV model at `public/models/uav.glb` and a piston-engine model
at `public/models/piston-engine.glb`. No model is downloaded or requested until
explicitly integrated. The default scene uses local procedural concept geometry.

Use metres and +X as the aircraft tail/propulsion direction; the wing spans Z
and Y is up. Align the engine with ENGINE_ANCHOR in `src/animation/engineZoom.js`.
Replace the shell geometry in Aircraft.jsx using a cloned useGLTF scene and
clone its materials before changing opacity. Preserve the parent group, click
handlers and Engine child so scroll and selection work identically.

Engine replacement belongs in Engine.jsx. Preserve semantic object names:
crankshaft, cylinders, pistons, injector, oil-system, sensors. These are the
Milestone 2 binding points. Models need correct pivots, normals and sensible
polygon/texture budgets; their visual framing must be rechecked after replacement.

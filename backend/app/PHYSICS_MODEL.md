# Prototype physics model assumptions

Status: **generated engineering model; not validated aircraft-engine physics**.
It contains no manufacturer-approved limits, performance maps, control laws, or
airworthiness evidence. It is intended to exercise the digital-twin software and
to produce explainable relative indicators.

All numeric coefficients and references are stored with units and descriptions
in `prototype_physics_assumptions.json`. Changing that file changes model
behavior and therefore requires regression testing and a new model version.

## Structural assumptions

1. **Air-density proxy.** Pressure divided by a reference pressure is multiplied
   by inverse absolute temperature and a small humidity correction. This is a
   dimensionless comparison proxy, not an atmospheric state solution. If
   pressure is unavailable, a standard-atmosphere-shaped altitude expression is
   used and the original pressure measurement remains marked `MISSING`.
2. **Engine-load proxy.** Reported load is blended with density-corrected
   throttle. This is not brake torque, BMEP, or shaft-power measurement.
3. **Fuel-flow estimate.** Fuel flow is assumed proportional to normalized RPM
   and the load proxy. It is deliberately simple and must eventually be replaced
   by a validated engine map.
4. **Injection-timing estimate.** Timing is represented by a linear load and
   altitude relationship. It is not an ECU command recommendation.
5. **Thermal stress.** Mean CHT and EGT above configured reference points produce
   a bounded relative stress indicator. Reference points are scaling values, not
   safe/unsafe limits.
6. **Lubrication health.** While the engine is considered running, lower oil
   pressure and higher oil temperature reduce a bounded relative indicator. Oil
   viscosity grade, pump map, bearing clearances, and transient behavior are not
   modeled.
7. **Combustion health.** Cylinder EGT spread, fuel-flow residual, and timing
   residual reduce a relative indicator. Lambda, ignition energy, detonation,
   pressure traces, and cylinder-specific fuel delivery are not modeled.
8. **Vibration health.** Only scalar RMS is evaluated. Frequency content,
   mounting transfer functions, sensor bandwidth, propeller order, and modal
   behavior are not modeled.
9. **Electrical health.** Battery and alternator voltages are compared with
   prototype references. Current, state of charge, temperature, internal
   resistance, regulator behavior, and load demand are not modeled.
10. **Efficiency and overall health.** Efficiency is a presentation proxy derived
    from relative health indicators. Overall health is their unvalidated equal
    average. Neither represents measured thermodynamic efficiency or failure
    probability.

## Replacement interface

`PhysicsModel.evaluate(PhysicsInput) -> PhysicsResult` is the integration
boundary. A future validated implementation can use an engine performance map,
cycle model, system-identification model, or approved external service without
placing physics calculations in API routes or changing the digital-twin state
contract.

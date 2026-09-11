from backend.app.physics import CLASSIFICATION, PhysicsInput, PrototypePhysicsModel

def inputs(**changes):
    base=dict(rpm=2200,throttle_percent=65,reported_load_percent=62,fuel_flow_lph=26,
        altitude_m=2000,ambient_temperature_c=15,ambient_pressure_kpa=None,humidity_percent=None,
        cht_values_c=(160,162,164,163),egt_values_c=(600,602,604,603),oil_pressure_kpa=360,
        oil_temperature_c=95,vibration_rms=2.5,battery_voltage=25.0,alternator_voltage=28.0,
        injection_timing_deg=22.0)
    return PhysicsInput(**{**base,**changes})

def test_model_is_deterministic_and_explicitly_non_validated():
    model=PrototypePhysicsModel(); first=model.evaluate(inputs()); second=model.evaluate(inputs())
    assert first==second
    assert first.assumption_classification==CLASSIFICATION
    assert model.version.startswith("prototype-")
    assert model.documentation and all(model.documentation.values())

def test_density_proxy_decreases_with_altitude_when_pressure_is_estimated():
    model=PrototypePhysicsModel()
    low=model.evaluate(inputs(altitude_m=0)).air_density_proxy
    high=model.evaluate(inputs(altitude_m=7000)).air_density_proxy
    assert low is not None and high is not None and high<low

def test_density_proxy_decreases_as_temperature_increases_at_fixed_pressure():
    model=PrototypePhysicsModel()
    cold=model.evaluate(inputs(ambient_temperature_c=-20,ambient_pressure_kpa=80)).air_density_proxy
    hot=model.evaluate(inputs(ambient_temperature_c=40,ambient_pressure_kpa=80)).air_density_proxy
    assert cold is not None and hot is not None and hot<cold

def test_load_and_expected_fuel_increase_with_throttle_and_rpm():
    model=PrototypePhysicsModel()
    low=model.evaluate(inputs(throttle_percent=30,reported_load_percent=30,rpm=1400))
    high=model.evaluate(inputs(throttle_percent=90,reported_load_percent=90,rpm=2600))
    assert high.engine_load_proxy_percent>low.engine_load_proxy_percent
    assert high.expected_fuel_flow_lph>low.expected_fuel_flow_lph

def test_thermal_stress_increases_with_cylinder_and_exhaust_temperature():
    model=PrototypePhysicsModel()
    cool=model.evaluate(inputs(cht_values_c=(140,141,142,143),egt_values_c=(550,551,552,553)))
    hot=model.evaluate(inputs(cht_values_c=(220,221,222,223),egt_values_c=(800,801,802,803)))
    assert hot.thermal_stress_indicator>cool.thermal_stress_indicator
    assert hot.overall_engine_health_index<cool.overall_engine_health_index

def test_lubrication_vibration_and_electrical_indicators_are_monotonic():
    model=PrototypePhysicsModel()
    nominal=model.evaluate(inputs())
    degraded=model.evaluate(inputs(oil_pressure_kpa=100,oil_temperature_c=140,vibration_rms=8,
        alternator_voltage=21,battery_voltage=21))
    assert degraded.lubrication_health_indicator<nominal.lubrication_health_indicator
    assert degraded.vibration_health_indicator<nominal.vibration_health_indicator
    assert degraded.electrical_health_indicator<nominal.electrical_health_indicator
    assert degraded.overall_engine_health_index<nominal.overall_engine_health_index

def test_humidity_is_optional_but_used_when_supplied():
    model=PrototypePhysicsModel()
    dry=model.evaluate(inputs(ambient_pressure_kpa=80,humidity_percent=0)).air_density_proxy
    humid=model.evaluate(inputs(ambient_pressure_kpa=80,humidity_percent=100)).air_density_proxy
    assert dry is not None and humid is not None and humid<dry

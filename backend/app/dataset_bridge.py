"""Explicit unit and plausibility metadata shared by the live twin."""
TELEMETRY_UNITS={
    "rpm":"rpm","cylinder_head_temp_1_c":"degC","cylinder_head_temp_2_c":"degC",
    "cylinder_head_temp_3_c":"degC","cylinder_head_temp_4_c":"degC",
    "exhaust_gas_temp_1_c":"degC","exhaust_gas_temp_2_c":"degC","exhaust_gas_temp_3_c":"degC","exhaust_gas_temp_4_c":"degC",
    "oil_temperature_c":"degC","oil_pressure_kpa":"kPa","fuel_flow_lph":"L/h","vibration_rms":"RMS",
    "alternator_voltage":"V","alternator_state":"state","battery_voltage":"V","battery_current_a":"A","injection_timing_deg":"deg","engine_load_percent":"percent",
    "throttle_percent":"percent","altitude_m":"m","ambient_temperature_c":"degC",
    "ambient_pressure_kpa":"kPa","humidity_percent":"percent"
}
TELEMETRY_BOUNDS={
    "rpm":(0,3200),"cylinder_head_temp_1_c":(-45,270),"cylinder_head_temp_2_c":(-45,270),"cylinder_head_temp_3_c":(-45,270),"cylinder_head_temp_4_c":(-45,270),
    "exhaust_gas_temp_1_c":(-45,950),"exhaust_gas_temp_2_c":(-45,950),"exhaust_gas_temp_3_c":(-45,950),"exhaust_gas_temp_4_c":(-45,950),
    "oil_temperature_c":(-45,155),"oil_pressure_kpa":(0,700),"fuel_flow_lph":(0,75),"vibration_rms":(0,25),
    "alternator_voltage":(0,32),"battery_voltage":(18,30),"battery_current_a":(-300,300),"injection_timing_deg":(5,35),"engine_load_percent":(0,110),
    "throttle_percent":(0,100),"altitude_m":(0,8000),"ambient_temperature_c":(-45,50),
    "ambient_pressure_kpa":(35,105),"humidity_percent":(0,100)
}

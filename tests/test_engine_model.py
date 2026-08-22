import math

from app.engine_model import EngineInputs, ReducedOrderPistonEngine


def test_throttle_increases_load_and_thermal_output():
    model = ReducedOrderPistonEngine()
    low = model.predict(EngineInputs(throttle=0.35))
    high = model.predict(EngineInputs(throttle=0.80))
    assert high["Load"] > low["Load"]
    assert high["Fuel_Flow"] > low["Fuel_Flow"]
    assert high["EGT2"] > low["EGT2"]
    assert high["CHT"] > low["CHT"]


def test_rpm_increases_mechanical_and_combustion_response():
    model = ReducedOrderPistonEngine()
    low = model.predict(EngineInputs(rpm=2200, throttle=0.60))
    high = model.predict(EngineInputs(rpm=3600, throttle=0.60))
    assert high["Fuel_Flow"] > low["Fuel_Flow"]
    assert high["Vibration"] > low["Vibration"]
    assert high["EGT2"] > low["EGT2"]


def test_altitude_reduces_air_density_and_changes_map_response():
    model = ReducedOrderPistonEngine()
    sea = model.predict(EngineInputs(altitude_ft=0))
    high = model.predict(EngineInputs(altitude_ft=25000))
    assert high["Air_Density_Ratio"] < sea["Air_Density_Ratio"]
    assert high["MAP_Injector"] < sea["MAP_Injector"]
    assert high["Fuel_Flow"] > sea["Fuel_Flow"]


def test_hot_weather_increases_thermal_loading():
    model = ReducedOrderPistonEngine()
    normal = model.predict(EngineInputs(ambient_c=25))
    hot = model.predict(EngineInputs(ambient_c=45))
    assert hot["EGT2"] > normal["EGT2"]
    assert hot["CHT"] > normal["CHT"]
    assert hot["Oil_Temp"] > normal["Oil_Temp"]


def test_explicit_load_increases_engine_stress():
    model = ReducedOrderPistonEngine()
    low = model.predict(EngineInputs(load=0.30))
    high = model.predict(EngineInputs(load=0.90))
    assert high["Fuel_Flow"] > low["Fuel_Flow"]
    assert high["CHT"] > low["CHT"]
    assert high["Vibration"] > low["Vibration"]


def test_outputs_are_finite_and_bounded_under_extreme_inputs():
    model = ReducedOrderPistonEngine()
    for inputs in [
        EngineInputs(rpm=1200, throttle=0, altitude_ft=0, ambient_c=-40),
        EngineInputs(rpm=4000, throttle=1, altitude_ft=40000, ambient_c=60),
    ]:
        output = model.predict(inputs)
        assert all(math.isfinite(float(value)) for value in output.values())
        assert 0.55 <= output["Air_Density_Ratio"] <= 1.15
        assert 0.20 <= output["Efficiency"] <= 0.78
        assert 35.0 <= output["Oil_Pressure"] <= 95.0


def test_stable_inputs_are_deterministic():
    model = ReducedOrderPistonEngine()
    inputs = EngineInputs(rpm=3000, throttle=0.60, altitude_ft=3000, ambient_c=25)
    first = model.predict(inputs)
    second = model.predict(inputs)
    assert first == second

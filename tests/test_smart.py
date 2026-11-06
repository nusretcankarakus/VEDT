import pytest

from disktest.smart import interpret


def test_zero_exit_without_health_is_unknown():
    assert interpret({}, 0)["health"] == "UNKNOWN"
    assert interpret({}, 0)["temperature_c"] is None


def test_healthy_and_real_temperature():
    result = interpret({"smart_status": {"passed": True}, "temperature": {"current": 34}}, 0)
    assert result["health"] == "PASS"
    assert result["temperature_c"] == 34


@pytest.mark.parametrize("bit", [0, 1, 2])
def test_acquisition_failure_not_health_success(bit):
    result = interpret({"smart_status": {"passed": True}}, 1 << bit)
    assert not result["acquisition_ok"]
    assert result["health"] == "UNKNOWN"


@pytest.mark.parametrize("bit", [3, 4])
def test_current_device_failure(bit):
    assert interpret({"smart_status": {"passed": True}}, 1 << bit)["health"] == "FAIL"


@pytest.mark.parametrize("bit", [5, 6, 7])
def test_historical_warning_is_not_clean_pass(bit):
    assert interpret({"smart_status": {"passed": True}}, 1 << bit)["health"] == "WARNING"


def test_failed_health_overrides_zero_exit():
    assert interpret({"smart_status": {"passed": False}}, 0)["health"] == "FAIL"


def test_return_status_must_match_json():
    with pytest.raises(ValueError):
        interpret({"smartctl": {"exit_status": 2}}, 0)


@pytest.mark.parametrize("value", [True, "34", 999, None])
def test_unsupported_temperature_not_zero(value):
    assert interpret({"temperature": {"current": value}}, 0)["temperature_c"] is None

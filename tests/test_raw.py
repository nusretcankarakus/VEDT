from dataclasses import replace

import pytest

from disktest.device import SafetyError
from disktest.raw import RawSettings, smart_delta
from disktest.safety import Identity

TARGET = Identity('DT-RAW-SATA1', 'QEMU HARDDISK', 67108864, '0x5000000000000101')


def settings():
    return RawSettings(TARGET, allow_destroy=True, laboratory=True)


def test_lab_confirmation():
    settings().validate(TARGET.serial)
    with pytest.raises(SafetyError):
        settings().validate('different')


@pytest.mark.parametrize('kwargs', [
    {'allow_destroy': False},
    {'target': replace(TARGET, serial='CUSTOMER-DISK')},
    {'target': replace(TARGET, size_bytes=128 * 1024**2)}])
def test_lab_gate_cannot_accept_other_devices(kwargs):
    candidate = replace(settings(), **kwargs)
    with pytest.raises(SafetyError):
        candidate.validate(candidate.target.serial)


@pytest.mark.parametrize('kwargs', [{'timeout_seconds': float('nan')}, {'stall_seconds': 0},
    {'maximum_temperature_c': float('inf')}, {'mixed_operations': 0}, {'mixed_operations': True}])
def test_invalid_limits_rejected(kwargs):
    with pytest.raises(ValueError):
        replace(settings(), **kwargs).validate(TARGET.serial)


def test_smart_counters_compare_only_available_fields():
    before = {'raw': {'nvme_smart_health_information_log': {'media_errors': 1},
                      'ata_smart_attributes': {'table': [{'id': 197, 'raw': {'value': 0}}]}}}
    after = {'raw': {'nvme_smart_health_information_log': {'media_errors': 3},
                     'ata_smart_attributes': {'table': [{'id': 197, 'raw': {'value': 2}}]}}}
    changes, warnings = smart_delta(before, after)
    assert changes['media_errors']['delta'] == 2
    assert changes['ata_197']['delta'] == 2
    assert 'critical_warning' not in changes
    assert warnings == []


def test_operator_mode_requires_separate_runtime_consent(tmp_path):
    from disktest.raw import run_raw
    candidate = replace(settings(), laboratory=False)
    with pytest.raises(SafetyError, match='silme onayı'):
        run_raw(candidate, candidate.target.serial, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_physical_mode_never_allows_fault_injection():
    with pytest.raises(SafetyError, match='bozulma'):
        replace(settings(), laboratory=False, inject_corruption=True).validate(TARGET.serial)


@pytest.mark.parametrize('size', [64*1024**2, 64*1024**2+512, 64*1024**2+4096, 1000204886016])
def test_large_block_ranges_cover_every_byte_including_tail(size):
    from disktest.raw import capacity_ranges
    ranges = capacity_ranges(size, 512)
    assert ranges[0]['bs'] == 1024**2
    assert sum(row['size'] for row in ranges) == size
    offset = 0
    for row in ranges:
        assert row['offset'] == offset
        assert row['offset'] % 512 == 0
        assert row['size'] % row['bs'] == 0
        assert row['bs'] % row['verify_interval'] == 0
        offset += row['size']
    assert len(ranges) <= 2

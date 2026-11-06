from dataclasses import replace

import pytest

from disktest.safety import Authorization, Identity, validate_identity

DISK = Identity("SERIAL-TEST-001", "Virtual disk", 64 * 1024**2, "wwn-test-001")


def validate(auth=None, candidates=None, **kwargs):
    return validate_identity(auth or Authorization(DISK, True),
                             candidates if candidates is not None else [DISK],
                             protected=kwargs.get("protected", []),
                             in_use=kwargs.get("in_use", False),
                             inventory_complete=kwargs.get("inventory_complete", True))


def test_exact_authorized_identity():
    assert validate() == DISK


@pytest.mark.parametrize("change", [{"serial": ""}, {"model": ""},
                                   {"size_bytes": 0}, {"wwn": ""}])
def test_incomplete_authorization_blocks(change):
    with pytest.raises(ValueError):
        validate(Authorization(replace(DISK, **change), True))


@pytest.mark.parametrize("change", [{"serial": "different"}, {"model": "different"},
                                   {"size_bytes": DISK.size_bytes + 512}, {"wwn": "different"}])
def test_device_substitution_blocks(change):
    with pytest.raises(ValueError):
        validate(candidates=[replace(DISK, **change)])


def test_duplicate_serial_is_ambiguous():
    with pytest.raises(ValueError):
        validate(candidates=[DISK, replace(DISK, wwn="different")])


@pytest.mark.parametrize("kwargs", [{"protected": [DISK]}, {"in_use": True},
                                   {"inventory_complete": False}])
def test_boot_disk_and_active_or_unknown_topology_blocks(kwargs):
    with pytest.raises(ValueError):
        validate(**kwargs)


def test_no_authorization_blocks():
    with pytest.raises(ValueError):
        validate(Authorization(DISK))

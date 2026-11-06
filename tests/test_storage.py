from copy import deepcopy

import pytest

from disktest.storage import select_report_partition


def inventory():
    return {"blockdevices": [{"path": "/dev/sda", "type": "disk", "children": [
        {"path": "/dev/sda1", "type": "part", "label": "DISKTEST"},
        {"path": "/dev/sda3", "type": "part", "label": "DTREPORTS", "fstype": "vfat", "uuid": "A123", "ro": False},
    ]}]}


def test_same_boot_usb_only():
    assert select_report_partition(inventory(), "/dev/sda1")["path"] == "/dev/sda3"


def test_unrelated_usb_refused():
    data = inventory()
    part = data["blockdevices"][0]["children"].pop()
    part["path"] = "/dev/sdb1"
    data["blockdevices"].append({"path": "/dev/sdb", "type": "disk", "children": [part]})
    with pytest.raises(ValueError):
        select_report_partition(data, "/dev/sda1")


def test_duplicate_report_label_refused():
    data = inventory()
    data["blockdevices"][0]["children"].append(deepcopy(data["blockdevices"][0]["children"][1]))
    with pytest.raises(ValueError):
        select_report_partition(data, "/dev/sda1")


@pytest.mark.parametrize("change", [{"fstype": "ext4"}, {"uuid": ""}, {"ro": True}, {"type": "disk"}])
def test_invalid_report_partition_refused(change):
    data = inventory()
    data["blockdevices"][0]["children"][1].update(change)
    with pytest.raises(ValueError):
        select_report_partition(data, "/dev/sda1")

from copy import deepcopy
from dataclasses import replace

import pytest

from disktest.device import SafetyError, select_target
from disktest.safety import Authorization, Identity

TARGET = Identity('DT-RAW-SATA1', 'QEMU HARDDISK', 67108864, '0x5000000000000101')


def disk(path, serial, mounted=None):
    return {'path': path, 'type': 'disk', 'size': 67108864, 'model': 'QEMU HARDDISK',
            'serial': serial, 'wwn': '0x5000000000000101' if serial == TARGET.serial else 'root-wwn',
            'mountpoints': mounted or [], 'ro': False, 'maj:min': '8:0' if serial == TARGET.serial else '254:0'}


def graph():
    root = disk('/dev/vda', 'ROOT')
    root['children'] = [{'path': '/dev/vda1', 'type': 'part', 'mountpoints': ['/'],
                         'ro': False, 'maj:min': '254:1'}]
    return {'blockdevices': [root, disk('/dev/sda', TARGET.serial)]}


def test_target_selection_requires_exact_full_identity():
    assert select_target(graph(), Authorization(TARGET, True))['path'] == '/dev/sda'


@pytest.mark.parametrize('change', [{'serial': 'wrong'}, {'model': 'wrong'},
                                   {'size_bytes': 1}, {'wwn': 'wrong'}])
def test_identity_substitution_is_rejected(change):
    with pytest.raises(SafetyError):
        select_target(graph(), Authorization(replace(TARGET, **change), True))


def test_root_partition_mount_protects_its_whole_disk():
    data = graph()
    data['blockdevices'][1]['children'] = [{'path': '/dev/sda1', 'type': 'part',
        'mountpoints': ['/run/live/medium'], 'ro': True, 'maj:min': '8:1'}]
    with pytest.raises(SafetyError):
        select_target(data, Authorization(TARGET, True))


def test_ambiguous_serial_rejected():
    data = graph()
    duplicate = deepcopy(data['blockdevices'][1])
    duplicate['path'] = '/dev/sdb'
    data['blockdevices'].append(duplicate)
    with pytest.raises(SafetyError):
        select_target(data, Authorization(TARGET, True))


@pytest.mark.parametrize('case', ['readonly', 'no_mounts', 'missing_use_info', 'bad_device_number'])
def test_unknown_or_unsafe_topology_rejected(case):
    data = graph()
    if case == 'readonly':
        data['blockdevices'][1]['ro'] = True
    elif case == 'no_mounts':
        data['blockdevices'][0]['children'] = []
    elif case == 'missing_use_info':
        del data['blockdevices'][1]['mountpoints']
    else:
        data['blockdevices'][1]['maj:min'] = ''
    with pytest.raises(SafetyError):
        select_target(data, Authorization(TARGET, True))

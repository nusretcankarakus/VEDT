from copy import deepcopy
from disktest.batch import plan


def graph():
    nodes = []
    for path, serial, tran, mounted in [('/dev/sda', 'BOOT', 'usb', ['/run/live/medium']),
          ('/dev/sdb', 'SATA', 'sata', []), ('/dev/nvme0n1', 'NVME', 'nvme', [])]:
        nodes.append({'path': path, 'serial': serial, 'model': 'Model', 'size': 67108864,
                      'wwn': 'wwn-' + serial, 'type': 'disk', 'maj:min': f'8:{len(nodes) * 16}',
                      'tran': tran, 'rm': False, 'ro': False, 'mountpoints': mounted})
    return {'blockdevices': nodes}


def paths(data):
    return {n['path']: '/sys/devices/pci0000:00/disk' for n in data['blockdevices']}


def test_unattended_queue_selects_all_internal_but_never_boot_usb():
    data = graph()
    queue, skipped = plan(data, paths(data))
    assert {x.serial for x in queue} == {'SATA', 'NVME'}
    assert skipped[0]['path'] == '/dev/sda'


def test_usb_ancestor_cannot_masquerade_as_sata():
    data = graph()
    mapping = paths(data)
    mapping['/dev/sdb'] = '/sys/devices/pci0000:00/usb2/2-1/disk'
    queue, _ = plan(data, mapping)
    assert [x.serial for x in queue] == ['NVME']


def test_mounted_internal_and_missing_transport_are_protected():
    data = graph()
    data['blockdevices'][1]['mountpoints'] = ['/mnt/used']
    data['blockdevices'][2]['tran'] = None
    queue, skipped = plan(data, paths(data))
    assert not queue and len(skipped) == 3


def test_duplicate_wwn_is_not_two_independent_targets():
    data = graph()
    data['blockdevices'][2]['wwn'] = data['blockdevices'][1]['wwn']
    queue, _ = plan(data, paths(data))
    assert queue == []

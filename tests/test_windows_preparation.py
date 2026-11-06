import importlib.util
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import pytest


def module(name):
    path = Path(__file__).resolve().parents[1] / 'windows' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_old_disabled_plan_cannot_trigger_windows_installation(tmp_path):
    handoff = module('handoff')
    with pytest.raises(ValueError):
        handoff.validate(tmp_path, {'schema_version': 1, 'enabled': False}, [], set())


def test_answer_file_creates_local_test_account_and_one_first_logon_command():
    generator = module('make_unattend')
    data = generator.create('DT-12345678')
    root = ET.fromstring(data)
    ns = {'u': generator.NS}
    assert root.find('.//u:LocalAccount/u:Name', ns).text == 'VEDT1'
    assert root.find('.//u:AutoLogon/u:Username', ns).text == 'VEDT1'
    assert root.find('.//u:HideOnlineAccountScreens', ns).text == 'true'
    assert root.find('.//u:UILanguage', ns).text == 'tr-TR'
    assert len(root.findall('.//u:SynchronousCommand', ns)) == 1
    assert root.find('.//u:SkipMachineOOBE', ns) is None
    assert root.find('.//u:SkipUserOOBE', ns) is None


@pytest.mark.parametrize('name', ['bad name', 'A&<B', '', 'A' * 16, '1234567'])
def test_answer_file_rejects_invalid_computer_names(name):
    with pytest.raises(ValueError):
        module('make_unattend').create(name)


def test_storage_descriptor_does_not_follow_untrusted_offsets():
    data = bytearray(64)
    struct.pack_into('<I', data, 16, 200)
    with pytest.raises(ValueError):
        module('win_devices').descriptor(bytes(data))


def test_storage_identifier_parser_preserves_device_wwn():
    data = struct.pack('<III', 1, 36, 1) + struct.pack('<IIHHI', 1, 3, 8, 0, 0) + bytes.fromhex('5000000000000501')
    parsed = module('win_devices').identifiers(data)
    assert parsed[0]['hex'] == '5000000000000501' and parsed[0]['association'] == 0


def test_windows_match_requires_wwn_in_addition_to_serial_model_and_capacity():
    expected = {'serial': 'TEST', 'model': 'Model', 'size_bytes': 80 * 1024**3, 'wwn': '0x5000000000000501'}
    device = {'serial': 'TEST', 'model': 'Model', 'size_bytes': 80 * 1024**3, 'removable': False,
              'bus_type': 11, 'identifiers': [{'code': 1, 'type': 3, 'association': 0, 'hex': '5000000000000501'}]}
    matcher = module('identity_match')
    assert matcher.select(expected, [device]) == device
    device['identifiers'][0]['hex'] = '5000000000009999'
    with pytest.raises(matcher.IdentityMismatch):
        matcher.select(expected, [device])


def test_usb_bridge_cannot_become_windows_target_with_copied_identity():
    expected = {'serial': 'TEST', 'model': 'Model', 'size_bytes': 80 * 1024**3, 'wwn': '0x5000000000000501'}
    device = {**expected, 'bus_type': 7, 'removable': False}
    matcher = module('identity_match')
    with pytest.raises(matcher.IdentityMismatch):
        matcher.select(expected, [device])


def test_nvme_controller_response_uses_hardware_serial():
    payload = bytearray(4096)
    struct.pack_into('<H', payload, 0, 0x1b36)
    payload[4:24] = b'DT-WIN-NVME'.ljust(20)
    payload[24:64] = b'QEMU NVMe Ctrl'.ljust(40)
    header = struct.pack('<12I', 48, 48, 3, 1, 1, 0, 40, 4096, 0, 0, 0, 0)
    parsed = module('win_devices').nvme_controller(header + payload)
    assert parsed == {'vendor_id': 0x1b36, 'serial': 'DT-WIN-NVME', 'model': 'QEMU NVMe Ctrl'}

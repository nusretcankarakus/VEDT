import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import pytest


def load():
    folder = Path(__file__).resolve().parents[1] / 'windows'
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location('handoff', folder / 'handoff.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path, *, full=True, bytes_match=True):
    identity = {'serial': 'UNIT-TARGET', 'model': 'Unit model', 'size_bytes': 80 * 1024**3,
                'wwn': '0x5000000000000001'}
    name = 'a' * 24
    folder = tmp_path / name
    folder.mkdir()
    stages = [{'status': 'PASS', 'bytes': identity['size_bytes'] if bytes_match else 1} for _ in range(6)]
    session = {'mode': 'raw-device', 'identity_authorized': True, 'full_capacity_verified': full,
               'status': 'WARNING', 'error': None, 'stages': stages,
               'smart_before': {'health':'PASS', 'acquisition_ok':True},
               'smart_after': {'health':'PASS', 'acquisition_ok':True},
               'target': {'identity': identity, 'bytes': identity['size_bytes']}}
    (folder / 'session.json').write_text(json.dumps(session))
    (folder / 'report.html').write_text('UNIT TEST STUB')
    (folder / 'report.pdf').write_bytes(b'UNIT TEST STUB')
    manifest = {'algorithm': 'SHA-256', 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    item = {'identity': identity, 'test_report': name,
            'manifest_sha256': hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest()}
    plan = {'schema_version': 1, 'enabled': True, 'edition': 'Professional', 'language': 'tr-TR',
            'account_name': 'test', 'targets': [item]}
    device = {**identity, 'number': 4, 'bus_type': 11, 'removable': False,
              'identifiers': [{'code': 1, 'type': 3, 'association': 0, 'hex': '5000000000000001'}]}
    return plan, device, folder


def test_valid_synthetic_unit_evidence_can_be_matched_without_writes(tmp_path):
    plan, device, folder = fixture(tmp_path)
    result = load().validate(tmp_path, plan, [device], {9})
    assert result[0]['device']['number'] == 4 and result[0]['report'] == folder


@pytest.mark.parametrize('case', ['disabled', 'incomplete', 'partial-capacity', 'tampered', 'boot-usb', 'duplicate'])
def test_handoff_rejects_unsafe_or_unverified_cases(tmp_path, case):
    plan, device, folder = fixture(tmp_path, full=case != 'incomplete', bytes_match=case != 'partial-capacity')
    protected = {4} if case == 'boot-usb' else {9}
    if case == 'disabled':
        plan['enabled'] = False
    if case == 'tampered':
        (folder / 'report.html').write_text('changed')
    if case == 'duplicate':
        plan['targets'].append(plan['targets'][0])
    with pytest.raises(ValueError):
        load().validate(tmp_path, plan, [device], protected)


@pytest.mark.skipif(os.name != 'nt', reason='Windows sürücü harfi çözümleme akışı')
@pytest.mark.parametrize('source_disk', [4, 9, None])
def test_media_preflight_derives_protection_and_refuses_unknown_volume(tmp_path, monkeypatch, source_disk):
    plan, device, folder = fixture(tmp_path)
    boot = tmp_path / 'boot'
    boot.mkdir()
    image = tmp_path / 'install.wim'
    image.write_bytes(b'UNIT STUB - no image deployment is performed')
    module = load()
    import win_devices
    queried = []

    def resolve(letter):
        queried.append(letter)
        if source_disk is None:
            raise OSError('Birim fiziksel diske çözümlenemedi.')
        return {source_disk}

    monkeypatch.setattr(win_devices, 'volume_disk_numbers', resolve)
    if source_disk == 9:
        result = module.validate_media(tmp_path, plan, [device], boot_root=boot, image=image)
        assert result[0]['device']['number'] == 4
    else:
        with pytest.raises((ValueError, OSError)):
            module.validate_media(tmp_path, plan, [device], boot_root=boot, image=image)
    assert queried == [tmp_path.drive[0].upper()]

import json
from pathlib import Path
import pytest
from disktest import combined
from disktest.naming import report_stem
from disktest.report_content import ai_prompt


def media(tmp_path):
    reports = tmp_path / 'reports'
    reports.mkdir()
    (tmp_path / 'VEDT-MEDIA.json').write_text(json.dumps({'schema_version': 1, 'role': 'reports', 'media_id': 'a' * 32}))
    return reports


def active(tmp_path, phase):
    (tmp_path / 'VEDT-ACTIVE.json').write_text(json.dumps({'machine_uuid': 'machine', 'media_id': 'a' * 32, 'job_id': 'b' * 24, 'phase': phase}))


def test_interrupted_job_never_repeats_destructive_tests(tmp_path, monkeypatch):
    reports = media(tmp_path)
    active(tmp_path, 'testing')
    monkeypatch.setattr(combined, 'machine_id', lambda: 'machine')
    with pytest.raises(ValueError, match='yeniden silme engellendi'):
        combined.run(reports)


def test_ready_job_goes_to_winpe_without_retesting(tmp_path, monkeypatch):
    reports = media(tmp_path)
    active(tmp_path, 'windows-ready')
    monkeypatch.setattr(combined, 'machine_id', lambda: 'machine')
    calls = []
    monkeypatch.setattr(combined, 'next_boot', lambda *args: calls.append(args))
    assert combined.run(reports)
    assert calls == [('winpe',)]


def test_completed_windows_job_boots_its_esp_without_retesting(tmp_path, monkeypatch):
    reports = media(tmp_path)
    active(tmp_path, 'windows-ready')
    folder = reports / 'jobs' / ('b' * 24)
    folder.mkdir(parents=True)
    (folder / 'windows-install.json').write_text(json.dumps({'complete': True, 'targets': [{'phase': 'complete', 'esp_uuid': '1234-ABCD'}]}))
    monkeypatch.setattr(combined, 'machine_id', lambda: 'machine')
    calls = []
    monkeypatch.setattr(combined, 'next_boot', lambda *args: calls.append(args))
    assert combined.run(reports)
    assert calls == [('windows', '1234-ABCD')]


def test_report_filename_uses_same_account_and_safe_serial():
    value = {'account_name': 'VEDT54', 'target': {'identity': {'serial': 'SN/ABC:123'}}}
    assert report_stem(value) == 'VEDT54_SN_ABC_123'
    assert value['target']['identity']['serial'] == 'SN/ABC:123'
    value['target']['identity']['serial'] = 'X' * 200
    assert len(report_stem(value)) < 76


def test_prompt_contains_evidence_and_does_not_invent_missing_temperature():
    prompt = ai_prompt({'status': 'INCOMPLETE', 'stages': [], 'target': {'identity': {'serial': 'PRIVATE-SERIAL'}}})
    assert 'INCOMPLETE' in prompt and 'RAPOR-REHBERI-V1.md' in prompt
    assert 'PRIVATE-SERIAL' not in prompt and 'sağlıklı sayma' in prompt


def test_new_disk_starts_new_job_only_after_completed_job():
    old = {'serial': 'OLD'}
    new = {'serial': 'NEW'}
    active = {'target_identities': [old], 'phase': 'finished-no-windows', 'batch_complete': True}
    assert combined.target_change(active, [old], False) is False
    assert combined.target_change(active, [new], False) is True
    with pytest.raises(ValueError):
        combined.target_change(active, [], False)
    active['batch_complete'] = False
    with pytest.raises(ValueError):
        combined.target_change(active, [new], False)
    assert combined.target_change(active, [new], True) is True

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
    monkeypatch.setattr(combined, 'current_targets', lambda: [])
    monkeypatch.setattr(combined, 'machine_id', lambda: 'machine')
    with pytest.raises(ValueError, match='yeniden silme engellendi'):
        combined.run(reports)


def test_ready_job_goes_to_winpe_without_retesting(tmp_path, monkeypatch):
    from disktest import deployment
    monkeypatch.setattr(deployment, 'validate_installation_targets', lambda job: {})
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


def test_restart_requires_both_confirmations_and_preserves_old_files(tmp_path, monkeypatch):
    reports = media(tmp_path)
    previous = {'job_id': 'b' * 24, 'phase': 'testing'}
    folder = reports / 'jobs' / previous['job_id']
    folder.mkdir(parents=True)
    evidence = folder / 'old-report.pdf'
    evidence.write_bytes(b'old evidence')
    targets = [{'serial': 'SN1', 'model': 'SSD', 'size_bytes': 1000000000}]
    monkeypatch.setattr(combined.os, 'sync', lambda: None, raising=False)
    for responses in [('N',), ('R', 'HAYIR')]:
        answers = iter(responses)
        assert not combined.request_restart(reports, previous, targets, lambda _: next(answers))
        assert list(folder.glob('yeniden-baslatma-*.json')) == []
    answers = iter(['r', 'SIL'])
    assert combined.request_restart(reports, previous, targets, lambda _: next(answers))
    assert evidence.read_bytes() == b'old evidence'
    audit = json.loads(next(folder.glob('yeniden-baslatma-*.json')).read_text(encoding='utf-8'))
    assert audit['new_targets'] == targets
    assert audit['previous_job'] == previous


def test_unattended_restart_never_accepts_implicit_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(combined.sys.stdin, 'isatty', lambda: False)
    assert not combined.request_restart(tmp_path, {}, [])
    assert list(tmp_path.iterdir()) == []


def test_confirmed_restart_creates_new_job_keeps_evidence_and_counter(tmp_path, monkeypatch):
    from disktest import batch
    reports=media(tmp_path)
    active(tmp_path,'testing')
    old=reports/'jobs'/('b'*24);old.mkdir(parents=True)
    (old/'evidence.txt').write_text('keep')
    counter=reports/'vedt-numaralar';counter.mkdir()
    (counter/'VEDT54.json').write_text('reserved')
    targets=[{'serial':'SN1','model':'SSD','size_bytes':67108864,'wwn':'wwn1'}]
    monkeypatch.setattr(combined,'machine_id',lambda:'machine')
    monkeypatch.setattr(combined,'current_targets',lambda:targets)
    monkeypatch.setattr(combined.os,'sync',lambda:None,raising=False)
    actual=combined.request_restart;answers=iter(['R','SIL'])
    monkeypatch.setattr(combined,'request_restart',lambda *args:actual(*args,read=lambda _:next(answers)))
    calls=[]
    def fake_batch(folder,**kwargs):
        calls.append((folder,kwargs))
        (folder/'windows-hazirlik.json').write_text(json.dumps({'targets':[]}))
        return {'queue':targets,'complete':False}
    monkeypatch.setattr(batch,'run_batch',fake_batch)
    assert combined.run(reports)
    assert len(calls)==1 and calls[0][0]!=old
    assert calls[0][1]['numbering_reports']==reports
    assert (old/'evidence.txt').read_text()=='keep'
    assert (counter/'VEDT54.json').read_text()=='reserved'
    assert len(list(old.glob('yeniden-baslatma-*.json')))==1
    new=json.loads((tmp_path/'VEDT-ACTIVE.json').read_text())
    assert new['job_id']!='b'*24 and new['target_identities']==targets

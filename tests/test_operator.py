from copy import deepcopy
from pathlib import Path

from disktest import operator
from disktest.safety import Identity


TARGET = Identity('TARGET-123', 'Test disk', 128 * 1024**2, 'wwn-test')


def prepare(monkeypatch):
    import disktest.raw
    monkeypatch.setattr(disktest.raw, 'persistent_reports', lambda _: None)
    monkeypatch.setattr(operator, 'settle', lambda: None)
    monkeypatch.setattr(operator, 'inventory', lambda: {'blockdevices': [
        {'path': '/dev/test', 'type': 'disk'}]})
    monkeypatch.setattr(operator, 'identity', lambda _: TARGET)
    monkeypatch.setattr(operator, 'select_target', lambda data, auth: {'path': '/dev/test'})
    monkeypatch.setattr(operator, 'active_users', lambda _: None)


def test_inexact_erasure_confirmation_never_calls_engine(monkeypatch, tmp_path):
    prepare(monkeypatch)
    answers = iter(['1', 'SİL WRONG'])
    monkeypatch.setattr(operator, 'run_raw', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('I/O')))
    operator.choose_and_run(tmp_path, read=lambda _: next(answers), write=lambda _: None)
    assert list(tmp_path.iterdir()) == []


def test_protected_disk_cannot_be_selected(monkeypatch, tmp_path):
    prepare(monkeypatch)
    def locked(*_):
        raise operator.SafetyError('protected')
    monkeypatch.setattr(operator, 'select_target', locked)
    operator.choose_and_run(tmp_path, read=lambda _: (_ for _ in ()).throw(AssertionError('prompt')),
                            write=lambda _: None)


def test_explicit_confirmation_passes_identity_and_separate_consent(monkeypatch, tmp_path):
    prepare(monkeypatch)
    import disktest.autorun
    removed = []
    monkeypatch.setattr(disktest.autorun, 'remove', lambda path: removed.append(path))
    answers = iter(['1', 'SİL TARGET-123', ''])
    received = []
    def run(settings, confirmation, reports, event, **kwargs):
        received.append((settings, confirmation, kwargs))
        return {'status': 'WARNING', 'error': None}
    monkeypatch.setattr(operator, 'run_raw', run)
    monkeypatch.setattr(operator, 'write_report', lambda *args: tmp_path)
    operator.choose_and_run(tmp_path, read=lambda _: next(answers), write=lambda _: None)
    assert len(received) == 1
    settings, serial, consent = received[0]
    assert settings.target == TARGET and settings.allow_destroy and not settings.laboratory
    assert serial == TARGET.serial and consent == {'accept_data_loss': True}
    assert removed == [tmp_path]

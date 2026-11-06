import json
import shutil
import sys
import subprocess

import pytest

from disktest.engine import Settings
from disktest.fio import FioError, FioDataMismatch, parse_result, run_fio_demo


def test_verification_does_not_count_phantom_writes():
    raw = json.dumps({"jobs": [{"error": 0, "read": {"io_bytes": 1048576}, "write": {"io_bytes": 1048576}}]})
    assert parse_result(raw, 0, verify_only=True)[1] == 1048576


@pytest.mark.parametrize("raw,code", [
    ('{"jobs": [{"error": 84}]}', 0), ('{"jobs": [{"error": 0}]}', 1),
    ('{"jobs": [{"error": 0}]}', 0), ('{}', 0), ('not json', 0), ('{"jobs": []}', 0)])
def test_fio_error_or_missing_work_is_never_pass(raw, code):
    with pytest.raises(FioError):
        parse_result(raw, code)


def test_real_fio_error_prefix_preserves_data_mismatch_classification():
    raw = 'fio: pid=1156, err=84/file:io_u.c:2252\n' + json.dumps({
        'fio version': 'fio-3.39', 'jobs': [{'error': 84, 'read': {'io_bytes': 65536}}]})
    with pytest.raises(FioDataMismatch):
        parse_result(raw, 84, verify_only=True)


def test_trailing_garbage_is_not_silently_accepted():
    raw = 'fio: diagnostic\n' + json.dumps({'jobs': [{'error': 0, 'read': {'io_bytes': 512}}]}) + 'truncated'
    with pytest.raises(FioError):
        parse_result(raw, 0)


def test_fio_spawn_failure_still_has_a_reportable_stage(tmp_path, monkeypatch):
    import disktest.fio as module
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/usr/bin/fio")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess([], 0, stdout="fio-3.39"))
    def cannot_spawn(*a, **kw):
        raise OSError("process creation failed")
    monkeypatch.setattr(module.subprocess, "Popen", cannot_spawn)
    result = run_fio_demo(Settings(size_mib=1), scratch=tmp_path)
    assert result["status"] == "FAIL"
    assert result["stages"][0]["status"] == "FAIL"
    assert result["stages"][0]["seconds"] >= 0
    assert list(tmp_path.iterdir()) == []


real_fio = pytest.mark.skipif(sys.platform != "linux" or shutil.which("fio") is None,
                            reason="Gerçek Linux fio gerekli")


@real_fio
def test_real_fio_complete_chain(tmp_path):
    result = run_fio_demo(Settings(size_mib=1, mixed_operations=64, timeout_seconds=90), scratch=tmp_path)
    assert result["status"] == "WARNING", result
    assert len(result["stages"]) == 4
    assert all(s["status"] == "PASS" for s in result["stages"])
    assert all(s["bytes"] == 1048576 for s in result["stages"] if "doğrulama" in s["name"])
    assert list(tmp_path.iterdir()) == []


@real_fio
def test_real_fio_corruption_blocks_mixed(tmp_path):
    result = run_fio_demo(Settings(size_mib=1, scenario="data-mismatch", timeout_seconds=90), scratch=tmp_path)
    assert result["status"] == "FAIL"
    assert len(result["stages"]) == 2
    assert "fio_failure_stderr" in result
    assert list(tmp_path.iterdir()) == []


@real_fio
def test_real_fio_deadline_cleans_up(tmp_path):
    result = run_fio_demo(Settings(size_mib=1, timeout_seconds=0.001), scratch=tmp_path)
    assert result["status"] == "INCOMPLETE"
    assert list(tmp_path.iterdir()) == []

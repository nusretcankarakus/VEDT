import json
from pathlib import Path

import pytest

from disktest.engine import BLOCK, Settings, pattern, run_demo
from disktest.report import verify_manifest, write_report


def test_normal_chain_and_private_target_cleanup(tmp_path):
    result = run_demo(Settings(size_mib=1, mixed_operations=64), scratch=tmp_path)
    assert result["status"] == "WARNING"
    assert len(result["stages"]) == 4
    assert all(s["status"] == "PASS" for s in result["stages"])
    assert not result["physical_hardware_tested"]
    assert result["temperature_c"] is None
    assert list(tmp_path.iterdir()) == []


def test_corruption_is_found_before_mixed_test(tmp_path):
    result = run_demo(Settings(size_mib=1, scenario="data-mismatch"), scratch=tmp_path)
    assert result["status"] == "FAIL"
    assert result["error"]["offset_bytes"] == BLOCK + 17
    assert len(result["stages"]) == 2
    assert result["stages"][-1]["status"] == "FAIL"
    assert list(tmp_path.iterdir()) == []


def test_io_failure_does_not_proceed(tmp_path):
    result = run_demo(Settings(size_mib=1, scenario="io-error"), scratch=tmp_path)
    assert result["status"] == "FAIL"
    assert result["error"]["kind"] == "OSError"
    assert len(result["stages"]) == 1


def test_deadline_is_not_pass(tmp_path):
    result = run_demo(Settings(size_mib=1, scenario="timeout"), scratch=tmp_path)
    assert result["status"] == "INCOMPLETE"
    assert len(result["stages"]) == 1


def test_operator_cancel_cleans_target(tmp_path):
    def cancel(_):
        raise KeyboardInterrupt()
    result = run_demo(Settings(size_mib=1), cancel, scratch=tmp_path)
    assert result["status"] == "CANCELLED"
    assert list(tmp_path.iterdir()) == []


def test_patterns_detect_block_aliasing_and_stale_generation():
    seed = b"a" * 32
    assert pattern(seed, 0) != pattern(seed, 1)
    assert pattern(seed, 1) != pattern(seed, 1, 1)
    assert pattern(seed, 1) != pattern(b"b" * 32, 1)


@pytest.mark.parametrize("kwargs", [{"size_mib": 0}, {"size_mib": 257},
                                      {"mixed_operations": 0}, {"timeout_seconds": -1},
                                      {"scenario": "unknown"}])
def test_invalid_config_does_no_io(tmp_path, kwargs):
    with pytest.raises(ValueError):
        run_demo(Settings(**kwargs), scratch=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_user_file_is_untouched(tmp_path):
    sentinel = tmp_path / "customer.bin"
    sentinel.write_bytes(b"customer data")
    run_demo(Settings(size_mib=1), scratch=tmp_path)
    assert sentinel.read_bytes() == b"customer data"
    assert list(tmp_path.iterdir()) == [sentinel]


def test_manifest_detects_tampered_report(tmp_path):
    result = run_demo(Settings(size_mib=1))
    directory = write_report(result, tmp_path, with_pdf=False)
    assert verify_manifest(directory) == []
    (directory / "report.html").write_text("changed")
    assert len(verify_manifest(directory)) == 1


def test_manifest_refuses_traversal(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"../secret": "0"}}))
    assert any("Geçersiz" in e for e in verify_manifest(tmp_path))


def test_report_does_not_overwrite_previous(tmp_path):
    result = run_demo(Settings(size_mib=1))
    write_report(result, tmp_path, with_pdf=False)
    with pytest.raises(FileExistsError):
        write_report(result, tmp_path, with_pdf=False)

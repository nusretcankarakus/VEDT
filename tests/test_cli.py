import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("scenario,expected,status", [
    ("normal", 0, "WARNING"), ("data-mismatch", 1, "FAIL"),
    ("io-error", 1, "FAIL"), ("timeout", 2, "INCOMPLETE")])
def test_cli_exit_and_manifest(tmp_path, scenario, expected, status):
    result = subprocess.run([sys.executable, "-m", "disktest", "demo", "--size-mib", "1",
                             "--scenario", scenario, "--reports", str(tmp_path),
                             "--no-pdf", "--quiet"], capture_output=True,
                            text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
    assert result.returncode == expected, result.stderr
    assert status in result.stdout
    directory = next(tmp_path.iterdir())
    check = subprocess.run([sys.executable, "-m", "disktest", "verify-report", str(directory)],
                           capture_output=True)
    assert check.returncode == 0


def test_cli_refuses_user_target(tmp_path):
    target = tmp_path / "valuable.bin"
    target.write_bytes(b"do not touch")
    result = subprocess.run([sys.executable, "-m", "disktest", "demo", "--target", str(target)],
                            capture_output=True)
    assert result.returncode == 2
    assert target.read_bytes() == b"do not touch"

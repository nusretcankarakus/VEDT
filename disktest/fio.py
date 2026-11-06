"""Real fio on a newly created file only. No raw device input is accepted."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import errno
import os
from pathlib import Path
import secrets
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

from .engine import Settings, DeadlineExceeded
from . import __version__


class FioError(RuntimeError):
    pass


class FioDataMismatch(FioError):
    pass


def parse_result(stdout: str, returncode: int, *, verify_only: bool = False) -> tuple[dict, int]:
    try:
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            # fio can print an I/O diagnostic before the final JSON document,
            # even with output-format=json. Accept only a complete final object.
            candidates = []
            decoder = json.JSONDecoder()
            for match in re.finditer(r'(?m)^\s*\{', stdout):
                start = stdout.find('{', match.start())
                try:
                    value, length = decoder.raw_decode(stdout[start:])
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict) and 'jobs' in value and not stdout[start + length:].strip():
                    candidates.append(value)
            if len(candidates) != 1:
                raise ValueError('Tek bir tamamlanmış fio JSON belgesi alınamadı.')
            result = candidates[0]
        jobs = result["jobs"]
        if not isinstance(jobs, list) or len(jobs) != 1:
            raise ValueError("Tek iş bekleniyor.")
        # fio runs on Linux; its error numbers must not depend on the host
        # platform used to inspect a saved result (Windows EILSEQ differs).
        if returncode == 84 or any(job['error'] == 84 for job in jobs):
            raise FioDataMismatch('fio veri doğrulamasında uyuşmazlık tespit etti (EILSEQ).')
        if returncode != 0 or any(job["error"] != 0 for job in jobs):
            raise FioError(f"fio hata kodu: {returncode}; iş hataları: {[j['error'] for j in jobs]}")
        count = sum(int(job.get("read", {}).get("io_bytes", 0))
                    + (0 if verify_only else int(job.get("write", {}).get("io_bytes", 0))) for job in jobs)
        if count <= 0:
            raise FioError("fio başarılı kod döndürdü fakat tamamlanan I/O yok.")
        return result, count
    except (ValueError, KeyError, TypeError) as exc:
        raise FioError(f"Geçersiz fio JSON sonucu: {exc}") from exc


def _stop(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.communicate()
        return
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=5)


def run_fio_demo(settings: Settings, event=lambda _: None, scratch: Path | None = None) -> dict:
    settings.validate()
    if sys.platform != "linux":
        raise RuntimeError("Gerçek fio demosu Linux gerektirir.")
    if settings.scenario not in {"normal", "data-mismatch"}:
        raise ValueError("fio demosunda normal/data-mismatch senaryoları destekleniyor.")
    executable = shutil.which("fio")
    if not executable:
        raise RuntimeError("fio kurulu değil.")
    version = subprocess.run([executable, "--version"], capture_output=True,
                             text=True, check=True, timeout=10).stdout.strip()
    if not version.startswith("fio-"):
        raise RuntimeError("Bulunan fio, Flexible I/O Tester değil.")
    started = time.monotonic()
    size = settings.size_mib * 1024**2
    session = {
        "schema_version": 1, "version": __version__, "id": secrets.token_hex(12),
        "started_at": datetime.now(timezone.utc).isoformat(), "mode": "fio-file-demo",
        "physical_hardware_tested": False, "target": {"kind": "new-temporary-regular-file", "bytes": size},
        "settings": {"size_mib": settings.size_mib, "mixed_operations": settings.mixed_operations,
                     "timeout_seconds": settings.timeout_seconds, "scenario": settings.scenario},
        "fio_version": version, "fio_results": [], "stages": [], "status": "RUNNING",
        "temperature_c": None, "error": None,
        "warnings": ["DEMO: Sanal/normal dosya testi, fiziksel disk sağlığı ölçülmedi.",
                     "Ölçüm motoru fio; direct=1, psync, kuyruk derinliği 1. Sanal makine ve ana sistem etkileri vardır.",
                     "Sıcaklık ve SMART normal dosya demosunda desteklenmiyor."],
    }
    base = Path(scratch) if scratch else Path(tempfile.gettempdir())

    try:
        if shutil.disk_usage(base).free < size + 16 * 1024**2:
            raise OSError("Geçici dosya için alan yetersiz.")
        with tempfile.TemporaryDirectory(prefix="disktest-fio-", dir=base) as directory:
            target = Path(directory) / "target.bin"
            with target.open("xb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise OSError("Hedef normal dosya değil.")
                stream.truncate(size)

            def stage(name, options, verify_only=False, require_full=False):
                elapsed = time.monotonic() - started
                if elapsed >= settings.timeout_seconds:
                    raise DeadlineExceeded("fio zinciri toplam süre sınırı aşıldı.")
                row = {"name": name, "status": "RUNNING", "bytes": 0, "mib_per_s": 0}
                session["stages"].append(row)
                since = time.monotonic()
                command = [executable, "--name=disktest", f"--filename={target}",
                           f"--size={size}", "--bs=64k", "--ioengine=psync", "--iodepth=1", "--numjobs=1",
                           "--direct=1", "--fallocate=none", "--allow_file_create=0", "--eta=never",
                           "--output-format=json", "--verify_state_save=0", "--verify_state_load=0",
                           "--verify_fatal=1", "--end_fsync=1"] + options
                process = None
                stdout = stderr = ""
                try:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, start_new_session=True, cwd=directory)
                    while True:
                        left = settings.timeout_seconds - (time.monotonic() - started)
                        if left <= 0:
                            raise DeadlineExceeded("fio zinciri toplam süre sınırı aşıldı.")
                        try:
                            stdout, stderr = process.communicate(timeout=min(0.5, left))
                            break
                        except subprocess.TimeoutExpired:
                            event({"stage": name, "percent": None, "mib_per_s": None,
                                   "temperature_c": None, "elapsed_seconds": time.monotonic() - started})
                    result, io_bytes = parse_result(stdout, process.returncode, verify_only=verify_only)
                    if require_full and io_bytes != size:
                        raise FioError(f"Tam kapasite aşaması eksik: {io_bytes}/{size} bayt.")
                    row["bytes"] = io_bytes
                    row["status"] = "PASS"
                    job = result["jobs"][0]
                    row["fio_mib_per_s"] = (job.get("read", {}).get("bw_bytes", 0)
                        + (0 if verify_only else job.get("write", {}).get("bw_bytes", 0))) / 1024**2
                    session["fio_results"].append({"stage": name, "argv": command,
                                                   "result": result, "stderr": stderr,
                                                   "verify_only_phantom_writes_excluded": verify_only})
                except BaseException as exc:
                    if process is not None:
                        _stop(process)
                    row["status"] = "STOPPED" if isinstance(exc, KeyboardInterrupt) else "FAIL"
                    if isinstance(exc, FioError):
                        session["fio_failure_stderr"] = stderr[-6000:]
                        session["fio_failure_stdout"] = stdout[-30000:]
                    raise
                finally:
                    row["seconds"] = time.monotonic() - since
                    row["mib_per_s"] = row.get("fio_mib_per_s", 0)

            stage("fio sıralı yazma / SHA-256", ["--rw=write", "--verify=sha256", "--do_verify=0"], require_full=True)
            if settings.scenario == "data-mismatch":
                with target.open("r+b", buffering=0) as stream:
                    stream.seek(65553)
                    value = stream.read(1)
                    stream.seek(65553)
                    stream.write(bytes([value[0] ^ 255]))
                    os.fsync(stream.fileno())
            verify_options = ["--rw=write", "--verify=sha256", "--verify_only=1", "--do_verify=1"]
            stage("fio tam geri okuma doğrulaması", verify_options, verify_only=True, require_full=True)
            stage("fio karışık okuma/yazma", ["--rw=randrw", "--rwmixread=50",
                  f"--number_ios={settings.mixed_operations}", "--verify=sha256", "--do_verify=0",
                  "--verify_header_seed=0", "--verify_write_sequence=0"])
            stage("fio karışık test sonrası doğrulama", verify_options, verify_only=True, require_full=True)
            session["status"] = "WARNING"
    except KeyboardInterrupt:
        session["status"] = "CANCELLED"
        session["error"] = {"kind": "cancelled", "message": "Operatör durdurdu."}
    except (FioError, DeadlineExceeded, OSError, subprocess.SubprocessError) as exc:
        session["status"] = "INCOMPLETE" if isinstance(exc, DeadlineExceeded) else "FAIL"
        session["error"] = {"kind": type(exc).__name__, "message": str(exc)}
    session["elapsed_seconds"] = time.monotonic() - started
    session["finished_at"] = datetime.now(timezone.utc).isoformat()
    return session

"""Auditable file-only correctness engine. Owns its target from creation to cleanup.

This engine accepts NO target filename. It cannot be aimed at an existing file
or a raw device. Timing includes Python, buffering and flush overhead and is not
a hardware benchmark. The offset-dependent pseudorandom pattern catches aliasing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import random
import secrets
import shutil
import stat
import tempfile
import time
from typing import Callable
from . import __version__

BLOCK = 64 * 1024


class DataMismatch(RuntimeError):
    def __init__(self, offset: int):
        super().__init__(f"Veri uyuşmazlığı; bayt adresi: {offset}")
        self.offset = offset


class DeadlineExceeded(RuntimeError):
    pass


def pattern(seed: bytes, block: int, generation: int = 0) -> bytes:
    return hashlib.shake_256(seed + block.to_bytes(8, "big")
                             + generation.to_bytes(8, "big")).digest(BLOCK)


@dataclass(frozen=True)
class Settings:
    size_mib: int = 32
    mixed_operations: int = 256
    timeout_seconds: float = 120
    scenario: str = "normal"

    def validate(self):
        if not 1 <= self.size_mib <= 256:
            raise ValueError("Demo boyutu 1-256 MiB olmalı.")
        if not 1 <= self.mixed_operations <= 4096:
            raise ValueError("Karışık işlem sayısı 1-4096 olmalı.")
        if not 0 < self.timeout_seconds <= 3600:
            raise ValueError("Süre sınırı 0-3600 saniye aralığında olmalı.")
        if self.scenario not in {"normal", "data-mismatch", "io-error", "timeout"}:
            raise ValueError("Bilinmeyen demo senaryosu.")


def run_demo(settings: Settings, event: Callable[[dict], None] = lambda _: None,
             scratch: Path | None = None) -> dict:
    settings.validate()
    size = settings.size_mib * 1024**2
    started = time.monotonic()
    session = {
        "schema_version": 1, "version": __version__,
        "id": secrets.token_hex(12),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": "file-demo", "physical_hardware_tested": False,
        "target": {"kind": "new-temporary-regular-file", "bytes": size},
        "settings": asdict(settings), "stages": [], "status": "RUNNING",
        "warnings": ["DEMO: Fiziksel diskin sağlığı ölçülmedi.",
                     "Hızlar Python ve dosya sistemi önbelleğini içerir; donanım kıyaslaması değildir.",
                     "Sıcaklık/SMART bu dosya demosunda desteklenmiyor."],
        "temperature_c": None, "error": None,
    }
    seed = secrets.token_bytes(32)
    session["pattern_seed_hex"] = seed.hex()
    count = size // BLOCK
    generations = [0] * count
    rng = random.Random(86)

    def check():
        if time.monotonic() - started > settings.timeout_seconds:
            raise DeadlineExceeded("Toplam süre sınırı aşıldı.")

    def progress(name, done, total, since):
        check()
        event({"stage": name, "done_bytes": done, "total_bytes": total,
               "percent": round(100 * done / total, 1),
               "mib_per_s": done / 1024**2 / max(time.monotonic() - since, 1e-9),
               "temperature_c": None, "elapsed_seconds": time.monotonic() - started})

    def stage(name, operation):
        check()
        row = {"name": name, "status": "RUNNING", "bytes": 0}
        session["stages"].append(row)
        since = time.monotonic()
        try:
            row["bytes"] = operation(since)
            check()
            row["status"] = "PASS"
        except BaseException as exc:
            row["status"] = "STOPPED" if isinstance(exc, KeyboardInterrupt) else "FAIL"
            raise
        finally:
            row["seconds"] = time.monotonic() - since
            row["mib_per_s"] = row["bytes"] / 1024**2 / max(row["seconds"], 1e-9)

    try:
        base = Path(scratch) if scratch else Path(tempfile.gettempdir())
        if shutil.disk_usage(base).free < size + 16 * 1024**2:
            raise OSError("Geçici dosya için yeterli boş alan yok.")
        with tempfile.TemporaryDirectory(prefix="disktest86-", dir=base) as directory:
            # Exclusive creation in a private temporary directory; never truncate an input path.
            with open(Path(directory) / "target.bin", "x+b", buffering=0) as target:
                if not stat.S_ISREG(os.fstat(target.fileno()).st_mode):
                    raise OSError("Hedef normal dosya değil.")

                def write(since):
                    for block in range(count):
                        check()
                        if settings.scenario == "io-error" and block == count // 2:
                            raise OSError("Kontrollü demo I/O hatası")
                        data = pattern(seed, block)
                        if target.write(data) != BLOCK:
                            raise OSError("Kısa yazma")
                        session["stages"][-1]["bytes"] = (block + 1) * BLOCK
                        if block % 16 == 0:
                            progress("Sıralı yazma", (block + 1) * BLOCK, size, since)
                    os.fsync(target.fileno())
                    progress("Sıralı yazma", size, size, since)
                    return size

                def verify(since):
                    target.seek(0)
                    for block in range(count):
                        check()
                        actual = target.read(BLOCK)
                        expected = pattern(seed, block, generations[block])
                        if actual != expected:
                            first = next((i for i, pair in enumerate(zip(actual, expected))
                                          if pair[0] != pair[1]), len(actual))
                            raise DataMismatch(block * BLOCK + first)
                        session["stages"][-1]["bytes"] = (block + 1) * BLOCK
                        if block % 16 == 0:
                            progress("Geri okuma ve doğrulama", (block + 1) * BLOCK, size, since)
                    progress("Geri okuma ve doğrulama", size, size, since)
                    return size

                def mixed(since):
                    for index in range(settings.mixed_operations):
                        check()
                        block = rng.randrange(count)
                        target.seek(block * BLOCK)
                        if rng.randrange(2):
                            generations[block] += 1
                            if target.write(pattern(seed, block, generations[block])) != BLOCK:
                                raise OSError("Kısa karışık yazma")
                        elif target.read(BLOCK) != pattern(seed, block, generations[block]):
                            raise DataMismatch(block * BLOCK)
                        session["stages"][-1]["bytes"] = (index + 1) * BLOCK
                        if index % 16 == 0:
                            progress("Karışık okuma/yazma", (index + 1) * BLOCK,
                                     settings.mixed_operations * BLOCK, since)
                    os.fsync(target.fileno())
                    progress("Karışık okuma/yazma", settings.mixed_operations * BLOCK,
                             settings.mixed_operations * BLOCK, since)
                    return settings.mixed_operations * BLOCK

                stage("Sıralı yazma", write)
                if settings.scenario == "data-mismatch":
                    target.seek(BLOCK + 17)
                    original = target.read(1)
                    target.seek(BLOCK + 17)
                    target.write(bytes([original[0] ^ 255]))
                    os.fsync(target.fileno())
                if settings.scenario == "timeout":
                    raise DeadlineExceeded("Kontrollü demo süre aşımı")
                stage("Geri okuma ve doğrulama", verify)
                stage("Karışık okuma/yazma", mixed)
                stage("Karışık test sonrası tam doğrulama", verify)
                session["status"] = "WARNING"
    except KeyboardInterrupt:
        session["status"] = "CANCELLED"
        session["error"] = {"kind": "cancelled", "message": "Operatör durdurdu."}
    except (DataMismatch, DeadlineExceeded, OSError) as exc:
        session["status"] = "INCOMPLETE" if isinstance(exc, DeadlineExceeded) else "FAIL"
        session["error"] = {"kind": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, DataMismatch):
            session["error"]["offset_bytes"] = exc.offset
    session["elapsed_seconds"] = time.monotonic() - started
    session["finished_at"] = datetime.now(timezone.utc).isoformat()
    return session

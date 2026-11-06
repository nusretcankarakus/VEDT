"""Read-only smartctl JSON acquisition and documented exit-bit interpretation."""
from __future__ import annotations

import json
from pathlib import Path
import stat
import subprocess
import sys
import shutil

BITS = {
    0: "Komut satırı ayrıştırılamadı.",
    1: "Cihaz açılamadı/kimlik alınamadı veya düşük güç durumunda.",
    2: "SMART komutu başarısız veya veri checksum hatalı.",
    3: "SMART cihazın arızalı olduğunu bildiriyor.",
    4: "Bir ön arıza özniteliği eşik altında.",
    5: "Geçmişte eşik altına inmiş öznitelik var.",
    6: "Cihaz hata günlüğünde kayıt var.",
    7: "Cihaz self-test günlüğünde hata kaydı var.",
}


def interpret(data: dict, exit_code: int) -> dict:
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise ValueError("smartctl çıkışı 8 bit durum maskesi olmalı.")
    reported = data.get("smartctl", {}).get("exit_status")
    if reported is not None and reported != exit_code:
        raise ValueError("JSON ile süreç SMART çıkış durumları uyuşmuyor.")
    acquisition_ok = not bool(exit_code & 0b111)
    passed = data.get("smart_status", {}).get("passed")
    if passed is not True and passed is not False:
        passed = None
    if passed is False or exit_code & 0b11000:
        health = "FAIL"
    elif not acquisition_ok or passed is None:
        health = "UNKNOWN"
    elif exit_code & 0b11100000:
        health = "WARNING"
    else:
        health = "PASS"
    temperature = data.get("temperature", {}).get("current")
    if type(temperature) not in (int, float) or not -90 <= temperature <= 200:
        temperature = None
    return {
        "health": health, "acquisition_ok": acquisition_ok, "exit_status": exit_code,
        "exit_bits": [bit for bit in BITS if exit_code & (1 << bit)],
        "messages": [text for bit, text in BITS.items() if exit_code & (1 << bit)],
        "temperature_c": temperature,
        "model": data.get("model_name", data.get("model_number")),
        "serial": data.get("serial_number"),
        "firmware": data.get("firmware_version"),
        "smart_passed": passed,
        "raw": data,
    }


def read_smart(device: Path, timeout=20) -> dict:
    if sys.platform != "linux":
        raise RuntimeError("SMART okuma bu sürümde Linux gerektirir.")
    device = device.resolve(strict=True)
    if not str(device).startswith("/dev/") or not stat.S_ISBLK(device.stat().st_mode):
        raise ValueError("SMART için /dev altında gerçek blok aygıtı gerekli.")
    executable = shutil.which("smartctl")
    if not executable and Path("/usr/sbin/smartctl").is_file():
        executable = "/usr/sbin/smartctl"
    if not executable:
        raise RuntimeError("smartctl kurulu değil.")
    result = subprocess.run([executable, "-a", "-j", str(device)],
                            capture_output=True, text=True, timeout=timeout, check=False)
    return interpret(json.loads(result.stdout), result.returncode)

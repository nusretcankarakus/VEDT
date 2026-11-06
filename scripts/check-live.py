#!/usr/bin/env python3
"""Networkless UEFI smoke test using only new regular files as guest disks.

This checks boot, enumeration, fio FILE tests and report persistence. It does NOT
claim SATA/NVMe block-device write verification or physical hardware acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import time


def run(args):
    for path in (args.image, args.firmware, args.variables):
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"Normal dosya gerekli: {path}")
    output = args.output.resolve()
    if any("," in str(p.resolve()) for p in (output, args.firmware, args.image)):
        raise ValueError("QEMU yol ayracı nedeniyle virgülsüz bir klasör kullanın.")
    output.mkdir(parents=True, exist_ok=False)
    usb = output / "usb.img"
    target = output / "target.raw"
    shutil.copyfile(args.image, usb)
    shutil.copyfile(args.variables, output / "vars.fd")
    with target.open("xb") as stream:
        stream.truncate(64 * 1024**2)
    command = [str(args.qemu), "-machine", "q35,accel=tcg", "-cpu", "max", "-m", "2048", "-smp", "2",
        "-display", "none", "-nic", "none", "-no-reboot",
        "-drive", f"if=pflash,format=raw,readonly=on,file={args.firmware.resolve().as_posix()}",
        "-drive", f"if=pflash,format=raw,file={(output / 'vars.fd').as_posix()}",
        "-device", "qemu-xhci,id=xhci", "-drive", f"if=none,id=stick,format=raw,file={usb.as_posix()}",
        "-device", "usb-storage,drive=stick,bus=xhci.0,serial=DT-BOOT-001,bootindex=1",
        "-drive", f"if=none,id=target,format=raw,file={target.as_posix()}",
        "-serial", f"file:{(output / 'serial.log').as_posix()}"]
    if args.qmp_port:
        command += ['-qmp', f'tcp:127.0.0.1:{args.qmp_port},server=on,wait=off']
    serial = "DT-VM-SATA1" if args.backend == "sata" else "DT-VM-NVME1"
    if args.backend == "sata":
        command += ["-device", "ich9-ahci,id=ahci", "-device",
                    "ide-hd,drive=target,bus=ahci.0,serial=DT-VM-SATA1,wwn=0x5000000000000001"]
    else:
        command += ["-device", "nvme,id=nvme0,serial=DT-VM-NVME1", "-device",
                    "nvme-ns,drive=target,bus=nvme0,nsid=1,eui64=0x1122334455667788"]
    (output / "command.json").write_text(json.dumps(command, indent=2), encoding="utf-8")
    started = time.monotonic()
    with (output / "qemu.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            result = process.wait(timeout=args.timeout)
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            raise
    if result:
        raise RuntimeError(f"QEMU çıkış kodu {result}; qemu.log dosyasını inceleyin.")
    lines = (output / "serial.log").read_text(errors="replace").splitlines()
    payloads = [line.split("DT_AUTOTEST_RESULT=", 1)[1] for line in lines if "DT_AUTOTEST_RESULT=" in line]
    if len(payloads) != 1:
        raise RuntimeError("Tek bir Live kabul sonucu alınamadı.")
    evidence = json.loads(payloads[0])
    if not evidence["uefi"] or not evidence["persistent_reports"] or evidence["manifest_errors"]:
        raise RuntimeError(f"UEFI/kalıcı rapor kabulü geçmedi: {evidence}")
    if evidence["status"] != "WARNING" or len(evidence["stages"]) != 4 or any(
            stage["status"] != "PASS" for stage in evidence["stages"]):
        raise RuntimeError(f"fio dosya zinciri tamamlanmadı: {evidence}")
    if not any(device["serial"] == serial for device in evidence["detected_devices"]):
        raise RuntimeError(f"Beklenen {args.backend} hedef keşfedilemedi.")
    expected = hashlib.sha256(bytes(64 * 1024**2)).hexdigest()
    with target.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError("Dosya demosu ham sanal hedefi değiştirdi!")
    evidence.update({"backend": args.backend, "network": "none", "raw_target_tested": False,
                     "target_unchanged_sha256": actual, "seconds": time.monotonic() - started})
    with args.image.open('rb') as stream:
        evidence['source_image_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image", "output", "qemu", "firmware", "variables"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--backend", choices=["sata", "nvme"], required=True)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--qmp-port", type=int, default=0)
    run(parser.parse_args())

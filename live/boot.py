#!/usr/bin/env python3
"""Live console, including explicitly provisioned unattended destructive mode."""
import subprocess
import sys
from pathlib import Path
import json
import os

from disktest import __version__
from disktest.storage import report_store


def configure_console():
    font = Path("/usr/share/consolefonts/Uni2-Terminus16.psf.gz")
    if not font.is_file():
        return {"font": None, "returncode": None}
    subprocess.run(["kbd_mode", "-u", "-C", "/dev/tty1"], check=False)
    result = subprocess.run(["setfont", "-C", "/dev/tty1", str(font)], check=False)
    return {"font": str(font), "returncode": result.returncode}


def autotest(console):
    from disktest.engine import Settings
    from disktest.fio import run_fio_demo
    from disktest.report import write_report, verify_manifest
    from disktest.discovery import discover
    store, persistent, message = report_store()
    session = run_fio_demo(Settings(size_mib=32, timeout_seconds=300), scratch=store)
    session["warnings"].append("Live demo hedefi rapor alanında yeni dosyadır; bağlı HDD/SSD üzerinde test yapılmadı.")
    session["warnings"].append(message)
    report = write_report(session, store)
    evidence = {"version": __version__, "uefi": Path("/sys/firmware/efi").exists(),
                "persistent_reports": persistent, "session_id": session["id"],
                "status": session["status"], "stages": session["stages"],
                "report_directory": str(report), "manifest_errors": verify_manifest(report)}
    evidence["detected_devices"] = [
        {key: device.get(key) for key in ("path", "type", "model", "serial", "size", "wwn", "tran")}
        for device in discover()["blockdevices"] if device.get("type") == "disk"]
    evidence["hardware_target_tested"] = False
    evidence["console"] = console
    payload = "DT_AUTOTEST_RESULT=" + json.dumps(evidence, ensure_ascii=True)
    print(payload, flush=True)
    with open("/dev/ttyS0", "w") as serial:
        serial.write(payload + "\n")
        serial.flush()
    os.sync()
    subprocess.run(["systemctl", "poweroff"], check=False)


def main():
    console = configure_console()
    print(f"\033[2J\033[HVEDT — Vektron Elektronik Disk Test / {__version__}\n")
    if "disktest.autotest=1" in Path("/proc/cmdline").read_text().split():
        autotest(console)
        return 0
    if 'disktest.unattended=1' in Path('/proc/cmdline').read_text().split():
        store, persistent, message = report_store()
        print(message)
        if not persistent:
            print('\033[1;31mAçılış USB rapor alanı doğrulanamadı. Hiçbir diske yazılmadı.\033[0m')
            return 2
        from disktest.batch import run_batch
        record = run_batch(store, boot_usb_verified=True)
        if 'disktest.batchcheck=1' in Path('/proc/cmdline').read_text().split():
            payload = 'DT_BATCH_RESULT=' + json.dumps(record, ensure_ascii=True)
            with open('/dev/ttyS0', 'w') as serial:
                serial.write(payload + '\n')
            os.sync()
            subprocess.run(['systemctl', 'poweroff'], check=False)
        return 0
    print("Geliştirme sürümü - fiziksel donanım kabulü tamamlanmadı.\n")
    store, persistent, message = report_store()
    if persistent and 'disktest.menuonly=1' not in Path('/proc/cmdline').read_text().split():
        from disktest.autorun import boot
        boot(store)
    print("1. Diskleri görüntüle (salt okunur)\n2. Güvenli Python dosya demosu\n3. Gerçek fio dosya demosu\n4. Kapat\n5. Disk seç ve tam yazma/doğrulama testi başlat (VERİ SİLER)\n6. Kayıtlı otomatik testi kapat\n")
    while True:
        try:
            choice = input("Seçim: ").strip()
        except EOFError:
            return 0
        if choice == "1":
            subprocess.run([sys.executable, "-m", "disktest", "discover"], check=False)
        elif choice in {"2", "3"}:
            store, persistent, message = report_store()
            print(message)
            command = "demo" if choice == "2" else "fio-demo"
            subprocess.run([sys.executable, "-m", "disktest", command, "--reports", str(store),
                            "--scratch-directory", str(store)], check=False)
        elif choice == "4":
            subprocess.run(["systemctl", "poweroff"], check=False)
            return 0
        elif choice == '5':
            from disktest.operator import choose_and_run
            store, persistent, message = report_store()
            print(message)
            if not persistent:
                print('Kalıcı rapor USB alanı olmadan ham test başlatılamaz.')
                continue
            try:
                choose_and_run(store)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                print(f'Test başlatılamadı: {exc}')
            except KeyboardInterrupt:
                print('\nİptal edildi.')
        elif choice == '6':
            from disktest.autorun import remove
            store, persistent, message = report_store()
            if persistent:
                remove(store)
                print('Kayıtlı otomatik test kaldırıldı.')
            else:
                print('Kalıcı rapor alanı bulunamadı.')
        else:
            print("1, 2, 3, 4, 5 veya 6 seçin.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        if 'disktest.unattended=1' in Path('/proc/cmdline').read_text().split():
            print('\033[1;31mOtomatik işlem durduruldu. USB rapor alanı, araçlar veya aygıt koşulları doğrulanamadı.\033[0m', flush=True)
            raise SystemExit(2)
        if "disktest.autotest=1" in Path("/proc/cmdline").read_text().split():
            with open("/dev/ttyS0", "w") as serial:
                serial.write("DT_AUTOTEST_ERROR=" + repr(exc) + "\n")
                serial.flush()
            os.sync()
            subprocess.run(["systemctl", "poweroff"], check=False)
        raise

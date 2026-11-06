"""Use DTREPORTS only when it is a unique FAT partition on the boot USB."""
from pathlib import Path
import json
import stat
import subprocess


def select_report_partition(inventory: dict, boot_source: str) -> dict:
    nodes = []

    def walk(node, root):
        nodes.append((node, root))
        for child in node.get("children", []):
            walk(child, root)

    for root in inventory["blockdevices"]:
        walk(root, root)
    boot = [(node, root) for node, root in nodes if node["path"] == boot_source]
    reports = [(node, root) for node, root in nodes if node.get("label") == "DTREPORTS"]
    if len(boot) != 1 or len(reports) != 1:
        raise ValueError("Açılış veya DTREPORTS bölümü tekil olarak bulunamadı.")
    report, report_root = reports[0]
    _, boot_root = boot[0]
    if report_root["type"] != "disk" or report_root["path"] != boot_root["path"]:
        raise ValueError("DTREPORTS, açılış USB'si üzerinde değil.")
    if report["path"] == boot_source or report["type"] != "part":
        raise ValueError("Rapor alanı ayrı bölüm olmalı.")
    if report.get("fstype") != "vfat" or not report.get("uuid") or report.get("ro"):
        raise ValueError("Rapor alanı yazılabilir ve kimlikli FAT bölümü olmalı.")
    return report


def report_store() -> tuple[Path, bool, str]:
    fallback = Path("/run/disktest-reports")
    try:
        boot = subprocess.run(["findmnt", "--json", "--evaluate", "--mountpoint", "/run/live/medium",
                               "--output", "SOURCE"], capture_output=True, text=True, check=True, timeout=10)
        boot_source = json.loads(boot.stdout)["filesystems"][0]["source"]
        devices = subprocess.run(["lsblk", "--json", "--tree", "--paths", "--bytes", "--output",
                                  "PATH,TYPE,LABEL,FSTYPE,UUID,MOUNTPOINTS,RO"],
                                 capture_output=True, text=True, check=True, timeout=15)
        partition = select_report_partition(json.loads(devices.stdout), boot_source)
        device = Path(partition["path"])
        if not stat.S_ISBLK(device.stat().st_mode):
            raise ValueError("Rapor hedefi blok bölümü değil.")
        mounted = [p for p in (partition.get("mountpoints") or []) if p]
        if mounted == ["/run/disktest-media"]:
            output = Path("/run/disktest-media/reports")
            output.mkdir(exist_ok=True)
            return output, True, "Raporlar aynı USB'nin DTREPORTS bölümüne kaydedilecek."
        if mounted:
            raise ValueError("Rapor bölümü önceden bağlı; bu prototipte otomatik kullanılamıyor.")
        mountpoint = Path("/run/disktest-media")
        mountpoint.mkdir(exist_ok=True)
        subprocess.run(["mount", "-t", "vfat", "-o", "rw,nosuid,nodev,noexec,umask=0077",
                        str(device), str(mountpoint)], check=True, capture_output=True, timeout=15)
        output = mountpoint / "reports"
        output.mkdir(exist_ok=True)
        return output, True, "Raporlar aynı USB'nin DTREPORTS bölümüne kaydedilecek."
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
        fallback.mkdir(exist_ok=True)
        return fallback, False, f"Kalıcı USB rapor alanı kullanılamadı; RAM raporu kapanınca kaybolur. Ayrıntı: {exc}"

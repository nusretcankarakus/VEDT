"""Linux block-device safety gates. No writes occur in this module.

A descriptor is held exclusively for the whole session. fio must inherit it;
stages never reopen a mutable /dev pathname as their I/O target.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import time

from .safety import Authorization, Identity, validate_identity


class SafetyError(RuntimeError):
    pass


class DeviceInUse(SafetyError):
    pass


def inventory():
    result = subprocess.run(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                             'PATH,TYPE,SIZE,MODEL,SERIAL,WWN,MOUNTPOINTS,RO,MAJ:MIN,TRAN,RM'],
                            check=True, capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


def identity(node):
    size = node.get('size')
    if type(size) is not int or size <= 0:
        raise SafetyError('Geçersiz kapasite bilgisi.')
    return Identity(str(node.get('serial') or '').strip(), str(node.get('model') or '').strip(),
                    size, str(node.get('wwn') or '').strip())


def descendants(node):
    yield node
    for child in node.get('children') or []:
        yield from descendants(child)


def select_target(data, authorization):
    roots = data.get('blockdevices')
    if not isinstance(roots, list) or not roots:
        raise SafetyError('Disk keşfi boş veya eksik.')
    disks = [node for root in roots for node in descendants(root) if node.get('type') == 'disk']
    unique = {node['path']: node for node in disks}
    disks = list(unique.values())
    mounted = []
    for node in disks:
        for item in descendants(node):
            if 'mountpoints' not in item or item.get('ro') not in (True, False, 0, 1):
                raise SafetyError('Bağlantı/kullanım keşfi eksik.')
        if any(any(item.get('mountpoints') or []) for item in descendants(node)):
            mounted.append(node)
    if not mounted:
        raise SafetyError('Sistem/açılış diski topolojisi doğrulanamadı.')
    try:
        selected = validate_identity(authorization, [identity(d) for d in disks],
                                     protected=[identity(d) for d in mounted],
                                     in_use=False, inventory_complete=True)
    except ValueError as exc:
        raise SafetyError(str(exc)) from exc
    target = next(d for d in disks if identity(d) == selected)
    if target.get('ro'):
        raise SafetyError('Hedef salt okunur.')
    for node in descendants(target):
        if not re.fullmatch(r'\d+:\d+', str(node.get('maj:min', ''))):
            raise SafetyError('Aygıt numarası eksik.')
        if not str(node.get('path', '')).startswith('/dev/'):
            raise SafetyError('Geçersiz aygıt yolu.')
    return target


def require_lab():
    if sys.platform != 'linux' or os.geteuid() != 0:
        raise SafetyError('Laboratuvar ham testi Linux içinde root gerektirir.')
    detected = subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True,
                              text=True, timeout=5, check=False)
    vendor = Path('/sys/class/dmi/id/sys_vendor').read_text().strip()
    if detected.returncode != 0 or detected.stdout.strip() != 'qemu' or vendor != 'QEMU':
        raise SafetyError('Bu geliştirme sürümü yalnızca QEMU laboratuvarına açıktır.')


def settle():
    command = shutil.which('udevadm') or '/usr/bin/udevadm'
    subprocess.run([command, 'settle', '--timeout=10'], capture_output=True,
                   check=True, timeout=12)


def _device_numbers(node):
    return {os.makedev(*map(int, item['maj:min'].split(':'))) for item in descendants(node)}


def active_users(node, own_fd=None):
    numbers = _device_numbers(node)
    for item in descendants(node):
        holders = Path('/sys/dev/block') / item['maj:min'] / 'holders'
        if not holders.is_dir():
            raise SafetyError('Sysfs holder bilgisi eksik.')
        if any(holders.iterdir()):
            raise DeviceInUse('Hedefin aktif üst aygıtı (LVM/RAID/holder) var.')
    swaps = Path('/proc/swaps').read_text().splitlines()[1:]
    for line in swaps:
        path = line.split()[0]
        info = os.stat(path)
        if stat.S_ISBLK(info.st_mode) and info.st_rdev in numbers:
            raise DeviceInUse('Hedefte aktif swap var.')
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal():
            continue
        try:
            descriptors = list((process / 'fd').iterdir())
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise SafetyError('Süreç aygıt kullanımı tam okunamadı.') from exc
        for entry in descriptors:
            if process.name == str(os.getpid()) and entry.name == str(own_fd):
                continue
            try:
                info = entry.stat()
            except FileNotFoundError:
                continue
            except PermissionError as exc:
                raise SafetyError('Açık aygıt tanıtıcısı denetlenemedi.') from exc
            if stat.S_ISBLK(info.st_mode) and info.st_rdev in numbers:
                try:
                    name = (process / 'comm').read_text().strip()
                except OSError:
                    name = 'unknown'
                raise DeviceInUse(f'Hedef açık: PID={process.name}, süreç={name}')


@dataclass
class PinnedDevice:
    authorization: Authorization
    laboratory: bool = True
    fd: int = -1
    path: Path | None = None
    rdev: int = 0
    logical_sector: int = 0

    def guard(self):
        node = select_target(inventory(), self.authorization)
        active_users(node, self.fd)
        if self.fd >= 0:
            if Path(node['path']).resolve() != self.path:
                raise SafetyError('Hedef yolu/kimliği değişti.')
            self.check_fd()
        return node

    def check_fd(self):
        import fcntl
        info = os.fstat(self.fd)
        current = self.path.stat()
        if not stat.S_ISBLK(info.st_mode) or info.st_rdev != self.rdev or current.st_rdev != self.rdev:
            raise SafetyError('Açık hedef tanıtıcısı değişti.')
        size = struct.unpack('<Q', fcntl.ioctl(self.fd, 0x80081272, bytes(8)))[0]
        if size != self.authorization.target.size_bytes:
            raise SafetyError('Açık hedefin kapasitesi değişti.')

    def boundary(self):
        # Only called before starting a worker or after the previous one exited.
        # Every retry repeats the complete identity/use checks; no rule is skipped.
        for attempt in range(3):
            settle()
            try:
                return self.guard()
            except DeviceInUse:
                if attempt == 2:
                    raise
                time.sleep(0.2)

    def __enter__(self):
        import fcntl
        if sys.platform != 'linux' or os.geteuid() != 0:
            raise SafetyError('Ham disk testi Linux içinde root gerektirir.')
        if self.laboratory:
            require_lab()
        if self.laboratory and self.authorization.target.serial not in {'DT-RAW-SATA1', 'DT-RAW-NVME1'}:
            raise SafetyError('Yalnızca oluşturulmuş laboratuvar hedefleri kabul edilir.')
        node = self.boundary()
        self.path = Path(node['path']).resolve(strict=True)
        if not stat.S_ISBLK(self.path.stat().st_mode):
            raise SafetyError('Hedef blok aygıtı değil.')
        self.rdev = os.makedev(*map(int, node['maj:min'].split(':')))
        self.fd = os.open(self.path, os.O_RDWR | os.O_EXCL | os.O_CLOEXEC)
        try:
            self.check_fd()
            self.logical_sector = struct.unpack('<I', fcntl.ioctl(self.fd, 0x1268, bytes(4)))[0]
            if self.logical_sector not in (512, 4096) or self.authorization.target.size_bytes % self.logical_sector:
                raise SafetyError('Desteklenmeyen sektör/kapasite düzeni.')
            self.boundary()
        except BaseException:
            os.close(self.fd)
            self.fd = -1
            raise
        return self

    def __exit__(self, *args):
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def stats(self):
        self.check_fd()
        values = (Path('/sys/dev/block') / f'{os.major(self.rdev)}:{os.minor(self.rdev)}' / 'stat').read_text().split()
        if len(values) < 11:
            raise SafetyError('Tamamlanan aygıt I/O sayaçları okunamadı.')
        return int(values[2]) * 512, int(values[6]) * 512

    def native_ids(self):
        """Namespace identifiers shared with Windows, bound to this open fd."""
        self.check_fd()
        base = Path('/sys/dev/block') / f'{os.major(self.rdev)}:{os.minor(self.rdev)}'
        result = []
        for name, length, prefix in [('eui', 16, 'eui.'), ('nguid', 32, '0x'), ('uuid', 32, 'uuid.')]:
            try:
                value = (base / name).read_text(encoding='ascii').strip().lower().replace('-', '')
            except FileNotFoundError:
                continue
            if re.fullmatch('[0-9a-f]{' + str(length) + '}', value) and value.strip('0'):
                result.append(prefix + value)
        if (base / 'nsid').is_file():
            from .nvme_identity import read_namespace_ids
            nsid = int((base / 'nsid').read_text(encoding='ascii').strip())
            try:
                result.extend(read_namespace_ids(self.fd, nsid))
            except OSError:
                # Raw tests can still run; Windows preflight refuses a missing
                # cross-platform identity instead of guessing by disk number.
                pass
        self.check_fd()
        return list(dict.fromkeys(result))

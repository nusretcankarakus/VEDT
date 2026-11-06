#!/usr/bin/env python3
"""Create a NEW GPT regular image: EFI / Live FAT32 / DTREPORTS FAT32.

No host block devices are opened. Requires the project's vmtest dependencies.
Unlike an ISO-hybrid, the Live filesystem occupies its own partition; mounting
it cannot claim the whole USB and block the report partition.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import uuid
import zlib

import shutil
import subprocess
import re
from pyfatfs.PyFatFS import PyFatFS
from boot_checksums import update_sums
from fat_paths import resolve

SECTOR = 512
MIB = 1024**2
ESP = uuid.UUID('c12a7328-f81f-11d2-ba4b-00a0c93ec93b').bytes_le
DATA = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7').bytes_le


def partitions():
    start = 2048
    result = []
    for name, mib, kind in [('DTESP', 64, ESP), ('DTLIVE', 1280, DATA), ('DTREPORTS', 256, DATA)]:
        sectors = mib * MIB // SECTOR
        result.append({'name': name, 'first': start, 'last': start + sectors - 1,
                       'type': kind.hex(), 'guid': str(uuid.uuid4()), 'bytes': mib * MIB})
        start += sectors
    total = ((start + 33 + 2047) // 2048) * 2048
    return result, total


def write_gpt(path, layout, total):
    table = bytearray(128 * 128)
    for index, part in enumerate(layout):
        entry = bytearray(128)
        entry[:16] = bytes.fromhex(part['type'])
        entry[16:32] = uuid.UUID(part['guid']).bytes_le
        struct.pack_into('<QQQ', entry, 32, part['first'], part['last'], 0)
        name = part['name'].encode('utf-16-le')
        entry[56:56 + len(name)] = name
        table[index * 128:(index + 1) * 128] = entry
    disk_guid = uuid.uuid4().bytes_le
    def header(current, backup, entries):
        data = bytearray(512)
        data[:8] = b'EFI PART'
        struct.pack_into('<III', data, 8, 0x10000, 92, 0)
        struct.pack_into('<QQQQ', data, 24, current, backup, 34, total - 34)
        data[56:72] = disk_guid
        struct.pack_into('<QIII', data, 72, entries, 128, 128, zlib.crc32(table))
        struct.pack_into('<I', data, 16, zlib.crc32(data[:92]))
        return data
    mbr = bytearray(512)
    mbr[446:462] = struct.pack('<B3sB3sII', 0, b'\0\x02\0', 0xee, b'\xff' * 3, 1, min(total - 1, 0xffffffff))
    mbr[510:512] = b'\x55\xaa'
    with path.open('r+b') as stream:
        stream.truncate(total * SECTOR)
        stream.seek(0)
        stream.write(mbr)
        stream.seek(SECTOR)
        stream.write(header(1, total - 1, 2))
        stream.seek(2 * SECTOR)
        stream.write(table)
        stream.seek((total - 33) * SECTOR)
        stream.write(table)
        stream.seek((total - 1) * SECTOR)
        stream.write(header(total - 1, 1, total - 33))
        stream.flush()
        os.fsync(stream.fileno())


def make(source, output, interactive=False, unattended=False):
    if interactive and unattended:
        raise ValueError('Menülü ve tam otomatik kip aynı anda seçilemez.')
    if not source.is_dir() or not (source / 'live/filesystem.squashfs').is_file():
        raise ValueError('Kaynak, live-build binary klasörü olmalı.')
    if output.exists() or output.suffix.lower() != '.img':
        raise ValueError('Çıktı mevcut olmayan bir .img dosyası olmalı.')
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix('.img.partial')
    layout, total = partitions()
    mkfs = shutil.which('mkfs.vfat') or '/usr/sbin/mkfs.vfat'
    mcopy = shutil.which('mcopy')
    if not Path(mkfs).is_file() or not mcopy:
        raise RuntimeError('Linux mkfs.vfat ve mtools gerekli.')
    with partial.open('xb') as stream:
        stream.truncate(total * SECTOR)
    for index, part in enumerate(layout):
        cluster_sectors = (1, 8, 4)[index]
        subprocess.run([mkfs, '-F', '32', '-s', str(cluster_sectors), '-n', part['name'], '-i', f'{0xD15C0001 + index:08x}',
                        f"--offset={part['first']}", str(partial), str(part['bytes'] // 1024)], check=True)
    write_gpt(partial, layout, total)
    live_image = f"{partial}@@{layout[1]['first'] * SECTOR}"
    esp_image = f"{partial}@@{layout[0]['first'] * SECTOR}"
    for item in sorted(source.iterdir()):
        print('Live kopyalanıyor:', item.name, flush=True)
        subprocess.run([mcopy, '-s', '-o', '-i', live_image, str(item), '::/'], check=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='disktest-package-') as directory:
        temporary = Path(directory)
        config = (Path(__file__).resolve().parent.parent / 'live/grub-config.cfg').read_bytes()
        grub = (source / 'boot/grub/grub.cfg').read_bytes()
        if interactive:
            grub = grub.replace(b'disktest.autotest=1', b'')
        if unattended:
            config = config.replace(b'set timeout=3', b'set timeout=0')
            lines = []
            count = 0
            for line in grub.splitlines():
                if re.match(rb'\s*linux\s', line):
                    line = re.sub(rb'\s+disktest\.(autotest|menuonly|unattended)=1', b'', line)
                    line += b' disktest.unattended=1 quiet loglevel=3 systemd.show_status=0'
                    count += 1
                lines.append(line)
            if not count:
                raise ValueError('Otomatik açılış için Linux girdisi bulunamadı.')
            grub = b'\n'.join(lines) + b'\n'
        changes = {'./boot/grub/config.cfg': config, './boot/grub/grub.cfg': grub}
        sums = update_sums((source / 'sha256sum.txt').read_bytes(), changes)
        for name, data, target in [('config.cfg', config, '::/boot/grub/config.cfg'),
                                   ('grub.cfg', grub, '::/boot/grub/grub.cfg'),
                                   ('sha256sum.txt', sums, '::/sha256sum.txt')]:
            file = temporary / name
            file.write_bytes(data)
            subprocess.run([mcopy, '-o', '-i', live_image, str(file), target], check=True)
        efi = temporary / 'efi'
        efi.mkdir()
        subprocess.run([mcopy, '-s', '-i', str(source / 'boot/grub/efi.img'), '::/*', str(efi)], check=True)
        for item in efi.iterdir():
            subprocess.run([mcopy, '-s', '-o', '-i', esp_image, str(item), '::/'], check=True)
    with PyFatFS(str(partial), offset=layout[1]['first'] * SECTOR, read_only=True) as live:
        # Verify the installed Live files against the embedded checksum list.
        checked = 0
        for line in live.readtext(resolve(live, '/sha256sum.txt'), encoding='utf-8').splitlines():
            expected, name = line.split('  ', 1)
            digest = hashlib.sha256()
            with live.openbin(resolve(live, '/' + name.removeprefix('./')), 'r') as stream:
                for chunk in iter(lambda: stream.read(8 * MIB), b''):
                    digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError('Live dosyası checksum uyuşmazlığı: ' + name)
            checked += 1
        print('Live checksum kayıtları:', checked, flush=True)
    write_gpt(partial, layout, total)
    with partial.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    # Atomic publish without overwriting any existing file.
    os.link(partial, output)
    partial.unlink()
    output.with_suffix('.img.sha256').write_text(sha + '  ' + output.name + '\n', encoding='ascii')
    output.with_suffix('.img.build.json').write_text(json.dumps({
        'version': '0.4.0', 'interactive': interactive, 'unattended': unattended, 'partitions': layout,
        'bytes': total * SECTOR, 'sha256': sha, 'live_checksums_verified': checked,
        'physical_hardware_tested': False,
    }, indent=2), encoding='utf-8')
    print('GPT USB imajı hazır:', output, total * SECTOR, sha, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--interactive', action='store_true')
    parser.add_argument('--unattended', action='store_true')
    args = parser.parse_args()
    make(args.source, args.output, args.interactive, args.unattended)

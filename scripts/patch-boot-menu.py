#!/usr/bin/env python3
"""Patch an owned regular image without moving any ISO or GPT extents.

Requires pycdlib >=1.22. Updates SHA-256 records for changed boot files.
"""
import argparse
import io
from pathlib import Path
import stat
import pycdlib
from boot_checksums import update_sums


def patch(path, interactive=False):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Normal imaj dosyası gerekli.')
    reader = pycdlib.PyCdlib()
    reader.open(str(path))
    def read(name):
        stream = io.BytesIO()
        reader.get_file_from_iso_fp(stream, rr_path=name)
        return stream.getvalue()
    config = read('/boot/grub/config.cfg')
    grub = read('/boot/grub/grub.cfg')
    sums = read('/sha256sum.txt')
    reader.close()
    if b'set timeout=3' not in config:
        raise ValueError('Beklenen otomatik GRUB yapılandırması yok.')
    changes = {'./boot/grub/config.cfg': config}
    if interactive:
        if b'disktest.autotest=1' not in grub:
            raise ValueError('Kabul imajı parametresi bulunamadı.')
        grub = grub.replace(b'disktest.autotest=1', b'disktest.menuonly=1')
        changes['./boot/grub/grub.cfg'] = grub
    updated = update_sums(sums, changes)
    if len(updated) != len(sums):
        raise ValueError('Checksum liste boyutu değişti.')
    with pycdlib.InPlaceEditor(str(path)) as editor:
        if interactive:
            editor.modify_file(io.BytesIO(grub), len(grub), rr_path='/boot/grub/grub.cfg')
        editor.modify_file(io.BytesIO(updated), len(updated), rr_path='/sha256sum.txt')
    print('Boot menüsü/checksum güncellendi:', path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    patch(args.image, args.interactive)

#!/usr/bin/env python3
"""Verify GPT, separate FAT volumes and every embedded Live SHA-256 record."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from pyfatfs.PyFatFS import PyFatFS
from fat_paths import resolve

spec = importlib.util.spec_from_file_location('reports', Path(__file__).with_name('read-usb-reports.py'))
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    volumes = {name: reports.report_offset(args.image, name) for name in ['DTESP', 'DTLIVE', 'DTREPORTS']}
    records = {}
    with PyFatFS(str(args.image), offset=volumes['DTLIVE'], read_only=True) as live:
        for line in live.readtext(resolve(live, '/sha256sum.txt'), encoding='utf-8').splitlines():
            expected, name = line.split('  ', 1)
            with live.openbin(resolve(live, '/' + name.removeprefix('./')), 'r') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if expected != actual:
                raise ValueError('Checksum uyuşmazlığı: ' + name)
            records[name] = actual
    result = {'fat_offsets': volumes, 'live_checksum_records': records}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('GPT/FAT ve Live SHA-256 kayıtları doğrulandı:', len(records))

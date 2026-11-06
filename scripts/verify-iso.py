#!/usr/bin/env python3
"""Check every embedded SHA-256 record without mounting or changing an image."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import pycdlib


class HashSink:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.size = 0

    def write(self, data):
        self.digest.update(data)
        self.size += len(data)
        return len(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not stat.S_ISREG(args.image.stat().st_mode):
        raise ValueError('Normal imaj dosyası gerekli.')
    reader = pycdlib.PyCdlib()
    reader.open(str(args.image))
    listing = io.BytesIO()
    reader.get_file_from_iso_fp(listing, rr_path='/sha256sum.txt')
    record = {}
    for line in listing.getvalue().decode('utf-8').splitlines():
        expected, name = line.split('  ', 1)
        path = '/' + name.removeprefix('./')
        sink = HashSink()
        reader.get_file_from_iso_fp(sink, rr_path=path)
        actual = sink.digest.hexdigest()
        if actual != expected:
            raise ValueError('ISO checksum uyuşmazlığı: ' + path)
        record[path] = {'sha256': actual, 'bytes': sink.size}
    reader.close()
    if args.output:
        args.output.write_text(json.dumps(record, indent=2), encoding='utf-8')
    print('ISO checksum kayıtları doğrulandı:', len(record))

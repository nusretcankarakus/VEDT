"""Read DTREPORTS directly from a regular GPT image; never mounts host disks."""
import argparse
import json
from pathlib import Path, PurePosixPath
import stat
import struct
import zlib

from pyfatfs.PyFatFS import PyFatFS
from disktest.report import verify_manifest
from fat_paths import resolve


def report_offset(image, label='DTREPORTS'):
    if not stat.S_ISREG(image.stat().st_mode):
        raise ValueError("A regular image file is required")
    length = image.stat().st_size
    with image.open("rb") as stream:
        stream.seek(512)
        header = bytearray(stream.read(512))
        assert header[:8] == b"EFI PART"
        header_size = struct.unpack_from("<I", header, 12)[0]
        expected_crc = struct.unpack_from("<I", header, 16)[0]
        header[16:20] = b"\0" * 4
        assert zlib.crc32(header[:header_size]) == expected_crc
        table_lba = struct.unpack_from("<Q", header, 72)[0]
        count, entry_size, table_crc = struct.unpack_from("<III", header, 80)
        assert count <= 1024 and 128 <= entry_size <= 1024
        stream.seek(table_lba * 512)
        entries = stream.read(count * entry_size)
        assert zlib.crc32(entries) == table_crc
        offsets = []
        for index in range(count):
            entry = entries[index * entry_size:(index + 1) * entry_size]
            if entry[:16] == b"\0" * 16:
                continue
            first, last = struct.unpack_from("<QQ", entry, 32)
            assert 0 < first <= last and (last + 1) * 512 <= length
            stream.seek(first * 512)
            boot = stream.read(512)
            if boot[82:90] == b"FAT32   " and boot[71:82].strip() == label.encode('ascii'):
                offsets.append(first * 512)
        assert len(offsets) == 1, offsets
        return offsets[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    offset = report_offset(args.image)
    with PyFatFS(str(args.image), offset=offset, read_only=True) as filesystem:
        root = resolve(filesystem, '/reports')
        for session in filesystem.listdir(root):
            if '/' in session or session in {'.', '..'}:
                raise ValueError('Geçersiz oturum klasörü.')
            remote = root + '/' + session
            manifest = filesystem.readbytes(resolve(filesystem, remote + '/manifest.json'))
            record = json.loads(manifest)
            destination = args.output / session
            destination.mkdir()
            for name in record['files']:
                if '/' in name or '\\' in name or name in {'.', '..'}:
                    raise ValueError('Geçersiz manifest dosya adı.')
                (destination / name).write_bytes(filesystem.readbytes(resolve(filesystem, remote + '/' + name)))
            (destination / 'manifest.json').write_bytes(manifest)
    for directory in args.output.iterdir():
        assert verify_manifest(directory) == [], directory
        session = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        assert session["status"] == "WARNING"
        assert len(session["stages"]) == 4
        print("USB report manifest OK:", directory, session["status"])
    print("FAT32 offset:", offset)

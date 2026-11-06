#!/usr/bin/env python3
"""Remove only zero padding after a regular image's verified backup GPT."""
from pathlib import Path
import stat
import struct
import sys
import zlib


def finalize(path):
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Yalnızca normal imaj dosyası kabul edilir.")
    with path.open("r+b") as image:
        image.seek(512)
        header = bytearray(image.read(512))
        if header[:8] != b"EFI PART":
            raise ValueError("GPT başlığı bulunamadı.")
        size = struct.unpack_from("<I", header, 12)[0]
        crc = struct.unpack_from("<I", header, 16)[0]
        header[16:20] = b"\0" * 4
        if not 92 <= size <= 512 or zlib.crc32(header[:size]) != crc:
            raise ValueError("GPT başlık doğrulaması başarısız.")
        backup_lba = struct.unpack_from("<Q", header, 32)[0]
        end = (backup_lba + 1) * 512
        if end > path.stat().st_size:
            raise ValueError("Yedek GPT dosya sınırları dışında.")
        image.seek(backup_lba * 512)
        backup = bytearray(image.read(512))
        if backup[:8] != b"EFI PART":
            raise ValueError("Yedek GPT başlığı bulunamadı.")
        expected = struct.unpack_from("<I", backup, 16)[0]
        backup[16:20] = b"\0" * 4
        if zlib.crc32(backup[:size]) != expected:
            raise ValueError("Yedek GPT başlık doğrulaması başarısız.")
        image.seek(end)
        tail = image.read()
        if any(tail):
            raise ValueError("GPT sonrasında sıfır olmayan veri var; imaj değiştirilmedi.")
        image.truncate(end)
    print(f"GPT dosya sonu doğrulandı: {end} bayt")


if __name__ == "__main__":
    finalize(Path(sys.argv[1]))

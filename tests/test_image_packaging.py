import importlib.util
from pathlib import Path
import struct
import zlib
import hashlib

import pytest

spec = importlib.util.spec_from_file_location('finalize_gpt', Path(__file__).resolve().parents[1] / 'scripts/finalize-gpt.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
checksum_spec = importlib.util.spec_from_file_location('boot_checksums', Path(__file__).resolve().parents[1] / 'scripts/boot_checksums.py')
checksums = importlib.util.module_from_spec(checksum_spec)
checksum_spec.loader.exec_module(checksums)


def header(current, backup):
    data = bytearray(512)
    data[:8] = b'EFI PART'
    struct.pack_into('<III', data, 8, 0x10000, 92, 0)
    struct.pack_into('<QQ', data, 24, current, backup)
    struct.pack_into('<I', data, 16, zlib.crc32(data[:92]))
    return data


def image(tmp_path, tail=b'\0' * 512):
    data = bytearray(64 * 512)
    data[512:1024] = header(1, 63)
    data[63 * 512:64 * 512] = header(63, 1)
    target = tmp_path / 'test.img'
    target.write_bytes(data + tail)
    return target


def test_only_zero_padding_removed(tmp_path):
    target = image(tmp_path)
    expected = target.read_bytes()[:64 * 512]
    module.finalize(target)
    assert target.read_bytes() == expected


def test_nonzero_trailing_data_preserved(tmp_path):
    target = image(tmp_path, b'important')
    original = target.read_bytes()
    with pytest.raises(ValueError):
        module.finalize(target)
    assert target.read_bytes() == original


@pytest.mark.parametrize('offset', [512 + 16, 63 * 512 + 16])
def test_corrupt_header_never_changes_file(tmp_path, offset):
    target = image(tmp_path)
    original = bytearray(target.read_bytes())
    original[offset] ^= 1
    target.write_bytes(original)
    with pytest.raises(ValueError):
        module.finalize(target)
    assert target.read_bytes() == original


def test_missing_backup_never_extends_file(tmp_path):
    target = image(tmp_path)
    target.write_bytes(target.read_bytes()[:4096])
    original = target.read_bytes()
    with pytest.raises(ValueError):
        module.finalize(target)
    assert target.read_bytes() == original


def test_non_gpt_file_not_modified(tmp_path):
    target = tmp_path / 'customer.txt'
    target.write_bytes(b'customer data' * 100)
    original = target.read_bytes()
    with pytest.raises(ValueError):
        module.finalize(target)
    assert target.read_bytes() == original


def test_boot_checksum_changes_preserve_other_entries_and_size():
    before = b'0' * 64 + b'  ./boot/grub/config.cfg\n' + b'1' * 64 + b'  ./live/filesystem.squashfs\n'
    result = checksums.update_sums(before, {'./boot/grub/config.cfg': b'new configuration'})
    assert result[:64] == hashlib.sha256(b'new configuration').hexdigest().encode()
    assert result.splitlines()[1] == before.splitlines()[1]
    assert len(result) == len(before)


def test_missing_boot_checksum_entry_is_error():
    with pytest.raises(ValueError):
        checksums.update_sums(b'0' * 64 + b'  ./other\n', {'./boot/grub/config.cfg': b'new'})


def test_duplicate_boot_checksum_entry_is_error():
    line = b'0' * 64 + b'  ./boot/grub/config.cfg\n'
    with pytest.raises(ValueError):
        checksums.update_sums(line + line, {'./boot/grub/config.cfg': b'new'})

"""Read-only NVMe Identify Namespace on an already pinned Linux descriptor."""
import ctypes
import struct


def decode_namespace(data):
    if len(data) != 4096:
        raise ValueError('NVMe ad alanı kimlik yanıtı eksik.')
    result = []
    for start, length, prefix in ((104, 16, '0x'), (120, 8, 'eui.')):
        value = data[start:start + length]
        if any(value):
            result.append(prefix + value.hex())
    return result


def read_namespace_ids(fd, nsid):
    import fcntl
    if type(nsid) is not int or not 1 <= nsid < 0xffffffff:
        raise ValueError('Geçersiz NVMe ad alanı numarası.')
    data = ctypes.create_string_buffer(4096)
    command = bytearray(struct.pack('<BBHIIIQQ10I', 6, 0, 0, nsid, 0, 0, 0, ctypes.addressof(data),
                                   0, 4096, 0, 0, 0, 0, 0, 0, 5000, 0))
    assert len(command) == 72
    # opcode 0x06 / CNS 0 is Identify Namespace: it does not change media.
    request = (3 << 30) | (72 << 16) | (ord('N') << 8) | 0x41
    status = fcntl.ioctl(fd, request, command, True)
    if status != 0:
        raise OSError('NVMe ad alanı kimliği okunamadı.')
    return decode_namespace(data.raw)

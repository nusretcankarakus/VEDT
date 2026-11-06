"""Read-only Windows storage queries. This module never opens a write handle."""
import ctypes
from ctypes import wintypes
import struct


def descriptor(data):
    if len(data) < 36:
        raise ValueError('Aygıt tanımlayıcısı eksik.')
    def text(offset):
        if offset == 0:
            return ''
        if not 36 <= offset < len(data):
            raise ValueError('Aygıt metin konumu geçersiz.')
        return data[offset:].split(b'\0', 1)[0].decode('ascii', errors='strict').strip()
    vendor, model, firmware, serial = struct.unpack_from('<IIII', data, 12)
    return {'vendor': text(vendor), 'model': text(model), 'firmware': text(firmware),
            'serial': text(serial), 'bus_type': struct.unpack_from('<I', data, 28)[0],
            'removable': bool(data[10])}


def identifiers(data):
    if len(data) < 12:
        raise ValueError('Aygıt kimliği yanıtı eksik.')
    count = struct.unpack_from('<I', data, 8)[0]
    if count > 256:
        raise ValueError('Aygıt kimliği sayısı geçersiz.')
    result, offset = [], 12
    for index in range(count):
        if offset + 16 > len(data):
            raise ValueError('Aygıt kimliği sınır dışında.')
        code, kind, size, following, association = struct.unpack_from('<IIHHI', data, offset)
        end = offset + 16 + size
        if end > len(data):
            raise ValueError('Aygıt kimliği verisi eksik.')
        value = data[offset + 16:end]
        result.append({'code': code, 'type': kind, 'association': association,
                       'hex': value.hex(), 'text': value.decode('ascii', errors='replace') if code in (2, 3) else None})
        if index < count - 1 and following < 16 + size:
            raise ValueError('Aygıt kimliği bağlantısı geçersiz.')
        offset += following
    return result


def nvme_controller(data):
    if len(data) < 48:
        raise ValueError('NVMe denetleyici yanıtı eksik.')
    offset, length = struct.unpack_from('<II', data, 24)
    start = 8 + offset
    if offset < 40 or length < 4096 or start + length > len(data):
        raise ValueError('NVMe denetleyici veri sınırı geçersiz.')
    payload = data[start:start + length]
    return {'vendor_id': struct.unpack_from('<H', payload)[0],
            'serial': payload[4:24].decode('ascii').strip(),
            'model': payload[24:64].decode('ascii').strip()}


def volume_disk_numbers(letter):
    """Locate a report/source volume's physical disks without requesting write access.

    Errors propagate: a volume whose backing disks are unknown is not safe to
    ignore when protecting boot media before deployment.
    """
    if not isinstance(letter, str) or len(letter) != 1 or letter not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        raise ValueError('Tek bir büyük sürücü harfi gerekli.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW('\\\\.\\' + letter + ':', 0, 3, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        buffer = ctypes.create_string_buffer(65536)
        received = wintypes.DWORD()
        if not kernel.DeviceIoControl(handle, 0x560000, None, 0, buffer, len(buffer), ctypes.byref(received), None):
            raise ctypes.WinError(ctypes.get_last_error())
        data = buffer.raw[:received.value]
        if len(data) < 8:
            raise ValueError('Birim fiziksel disk yanıtı eksik.')
        count = struct.unpack_from('<I', data)[0]
        if not 1 <= count <= 256 or len(data) < 8 + count * 24:
            raise ValueError('Birim fiziksel disk listesi geçersiz.')
        numbers = set()
        for index in range(count):
            number, start, length = struct.unpack_from('<I4xqq', data, 8 + index * 24)
            if start < 0 or length <= 0:
                raise ValueError('Birim fiziksel aralığı geçersiz.')
            numbers.add(number)
        return numbers
    finally:
        kernel.CloseHandle(handle)


def inventory():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    result = []
    for number in range(32):
        path = rf'\\.\PhysicalDrive{number}'
        handle = kernel.CreateFileW(path, 0, 3, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            continue
        def ioctl(code, value=b''):
            incoming = ctypes.create_string_buffer(value) if value else None
            outgoing = ctypes.create_string_buffer(65536)
            received = wintypes.DWORD()
            if not kernel.DeviceIoControl(handle, code, incoming, len(value), outgoing, len(outgoing), ctypes.byref(received), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return outgoing.raw[:received.value]
        try:
            row = descriptor(ioctl(0x2d1400, struct.pack('<III', 0, 0, 0)))
            geometry = ioctl(0x700a0)
            if len(geometry) < 32:
                raise ValueError('Kapasite yanıtı eksik.')
            row.update({'number': number, 'path': path, 'size_bytes': struct.unpack_from('<Q', geometry, 24)[0],
                        'logical_sector': struct.unpack_from('<I', geometry, 20)[0]})
            if row['bus_type'] == 17:
                try:
                    request = struct.pack('<12I', 49, 0, 3, 1, 1, 0, 40, 4096, 0, 0, 0, 0) + bytes(4096)
                    controller = nvme_controller(ioctl(0x2d1400, request))
                    row['descriptor_serial'] = row['serial']
                    row.update({'serial': controller['serial'], 'model': controller['model'],
                                'nvme_controller': controller})
                except (OSError, ValueError) as exc:
                    row['controller_error'] = str(exc)
            try:
                row['identifiers'] = identifiers(ioctl(0x2d1400, struct.pack('<III', 2, 0, 0)))
            except (OSError, ValueError) as exc:
                row['identifiers'] = []
                row['identity_error'] = str(exc)
            result.append(row)
        except (OSError, ValueError) as exc:
            result.append({'number': number, 'path': path, 'error': str(exc)})
        finally:
            kernel.CloseHandle(handle)
    return result

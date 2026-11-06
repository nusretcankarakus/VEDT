"""Pure Linux-to-Windows target matching. No disk-number fallback is permitted."""
import re


class IdentityMismatch(ValueError):
    pass


def canonical(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    for prefix in ('0x', 'eui.', 'naa.', 'uuid.'):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    value = value.replace('-', '')
    if not re.fullmatch(r'[a-f0-9]{16}|[a-f0-9]{32}', value) or not value.strip('0'):
        return None
    return value


def select(expected, devices, native_ids=()):
    if not all(isinstance(expected.get(k), str) and expected[k].strip() for k in ('serial', 'model', 'wwn')):
        raise IdentityMismatch('Hedef kimliği eksik.')
    same_serial = [d for d in devices if d.get('serial') == expected['serial']]
    if len(same_serial) != 1:
        raise IdentityMismatch('Seri numarası tekil olarak eşleştirilemedi.')
    target = same_serial[0]
    if target.get('error') or target.get('removable') is not False or target.get('bus_type') not in {1, 3, 10, 11, 17}:
        raise IdentityMismatch('Aygıt güvenli dahili hedef olarak doğrulanamadı.')
    if target.get('model') != expected['model'] or target.get('size_bytes') != expected['size_bytes']:
        raise IdentityMismatch('Model veya kapasite değişti.')
    if target['bus_type'] == 17 and not target.get('nvme_controller'):
        raise IdentityMismatch('NVMe donanım seri numarası doğrulanamadı.')
    wanted = {v for value in (expected['wwn'], *native_ids) if (v := canonical(value))}
    observed = {v for item in target.get('identifiers', []) if item.get('association') == 0
                and item.get('type') in {2, 3, 8} and
                (v := canonical(item.get('text') if item.get('code') in (2, 3) else item.get('hex')))}
    if not wanted or not wanted.intersection(observed):
        raise IdentityMismatch('Dünya çapında aygıt kimliği eşleşmiyor; yazma engellendi.')
    return target

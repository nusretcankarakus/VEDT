"""Update only named entries in an ISO's existing SHA-256 listing."""
import hashlib


def update_sums(original, changes):
    seen = set()
    result = []
    for line in original.splitlines(keepends=True):
        name = line[66:].strip().decode('utf-8') if len(line) >= 66 else ''
        if name in changes:
            if name in seen:
                raise ValueError('Çift checksum kaydı: ' + name)
            seen.add(name)
            digest = hashlib.sha256(changes[name]).hexdigest().encode('ascii')
            line = digest + line[64:]
        result.append(line)
    if seen != set(changes):
        raise ValueError('Checksum listesinde eksik: ' + str(set(changes) - seen))
    return b''.join(result)

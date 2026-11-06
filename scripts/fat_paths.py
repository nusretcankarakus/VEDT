"""Resolve FAT names case-insensitively, including DOS short-name case flags."""


def resolve(fs, path):
    current = '/'
    for part in path.strip('/').split('/'):
        if not part:
            continue
        if part in {'.', '..'}:
            raise ValueError('Geçersiz FAT yolu.')
        matches = [name for name in fs.listdir(current) if name.casefold() == part.casefold()]
        if len(matches) != 1:
            raise ValueError('FAT dosyası eksik veya belirsiz: ' + path)
        current = current.rstrip('/') + '/' + matches[0]
    return current

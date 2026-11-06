"""Package an owned WinPE working tree as a new UEFI ISO; never opens disks."""
import argparse
import os
import re
from pathlib import Path
import pycdlib


def make(tree, output):
    boot = tree / 'efi/microsoft/boot/efisys_noprompt.bin'
    if not boot.is_file() or not (tree / 'sources/boot.wim').is_file():
        raise ValueError('Windows PE açılış dosyaları eksik.')
    if output.exists() or output.suffix.lower() != '.iso':
        raise ValueError('Yeni bir ISO çıktı dosyası gerekli.')
    partial = output.with_suffix('.iso.partial')
    with partial.open('xb'):
        pass
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, udf='2.60', vol_ident='DISKTEST86_WINPE')
    names = set()
    def iso_name(relative, file=False):
        parts = relative.parts
        pieces = [re.sub('[^A-Z0-9_]', '_', p.upper()) for p in parts[:-1]]
        last = parts[-1].upper()
        if file:
            stem, dot, extension = last.rpartition('.')
            if not dot:
                stem, extension = last, ''
            last = re.sub('[^A-Z0-9_]', '_', stem) + ('.' + re.sub('[^A-Z0-9_]', '_', extension) if extension else '') + ';1'
        else:
            last = re.sub('[^A-Z0-9_]', '_', last)
        result = '/' + '/'.join(pieces + [last])
        if result in names:
            raise ValueError('ISO ad eşleştirmesi belirsiz: ' + result)
        names.add(result)
        return result
    for folder in sorted((p for p in tree.rglob('*') if p.is_dir()), key=lambda p: len(p.parts)):
        name = '/' + folder.relative_to(tree).as_posix()
        iso.add_directory(iso_path=iso_name(folder.relative_to(tree)), joliet_path=name, udf_path=name)
    for file in sorted(p for p in tree.rglob('*') if p.is_file()):
        name = '/' + file.relative_to(tree).as_posix()
        iso.add_file(str(file), iso_path=iso_name(file.relative_to(tree), True), joliet_path=name, udf_path=name)
    iso.add_eltorito('/EFI/MICROSOFT/BOOT/EFISYS_NOPROMPT.BIN;1', bootcatfile='/BOOT.CAT;1',
                    joliet_bootcatfile='/boot.cat', udf_bootcatfile='/boot.cat', efi=True,
                    platform_id=0xef, boot_load_size=boot.stat().st_size // 512)
    iso.write(str(partial))
    iso.close()
    os.link(partial, output)
    partial.unlink()
    print('Windows PE ISO hazır:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    make(args.tree, args.output)

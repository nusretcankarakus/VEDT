#!/usr/bin/env python3
"""Prepare local Windows media from a user-supplied ISO; never distributes or installs it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import pycdlib


def prepare(iso_path, python_embed, wimlib, output):
    if not iso_path.is_file() or not (python_embed / 'python.exe').is_file() or not wimlib.is_file():
        raise ValueError('ISO, çıkarılmış x64 gömülü Python ve wimlib-imagex gerekli.')
    output.mkdir(parents=True, exist_ok=False)
    tree = output / 'winpe'
    media = output / 'media'
    media.mkdir()
    tree.mkdir()
    iso = pycdlib.PyCdlib()
    iso.open(str(iso_path))
    def folder(path):
        target = tree / path.lstrip('/')
        target.mkdir(parents=True, exist_ok=True)
        for entry in iso.list_children(udf_path=path):
            name = entry.file_identifier().decode('utf-16-be')
            if name in ('', '.', '..'):
                continue
            if '/' in name or '\\' in name:
                raise ValueError('ISO dosya yolu geçersiz.')
            child = path.rstrip('/') + '/' + name
            if entry.is_dir():
                folder(child)
            else:
                iso.get_file_from_iso(local_path=str(tree / child.lstrip('/')), udf_path=child)
    try:
        folder('/boot')
        folder('/efi')
        for name in ('bootmgr', 'bootmgr.efi'):
            iso.get_file_from_iso(local_path=str(tree / name), udf_path='/' + name)
        (tree / 'sources').mkdir()
        iso.get_file_from_iso(local_path=str(tree / 'sources/boot.wim'), udf_path='/sources/boot.wim')
        wim = media / 'install.wim'
        class HashWriter:
            def __init__(self, stream):
                self.stream = stream
                self.sha = hashlib.sha256()
                self.bytes = 0
            def write(self, data):
                self.stream.write(data)
                self.sha.update(data)
                self.bytes += len(data)
                return len(data)
        with wim.open('xb') as stream:
            sink = HashWriter(stream)
            iso.get_file_from_iso_fp(sink, udf_path='/sources/install.wim')
        digest = sink.sha.hexdigest()
    finally:
        iso.close()
    info = subprocess.run([str(wimlib), 'info', str(wim), '--xml'], check=True, capture_output=True).stdout
    images = ET.fromstring(info).findall('IMAGE')
    choices = [image for image in images if image.findtext('WINDOWS/EDITIONID') == 'Professional' and
               image.findtext('WINDOWS/ARCH') == '9' and image.findtext('WINDOWS/LANGUAGES/DEFAULT') == 'tr-TR']
    if len(choices) != 1:
        raise ValueError('Tekil Türkçe amd64 Windows 11 Pro imajı bulunamadı.')
    image = choices[0]
    if int(image.findtext('WINDOWS/VERSION/BUILD', '0')) < 22000:
        raise ValueError('Windows 11 veya daha yeni desteklenen medya gerekli.')
    metadata = {'schema_version': 1, 'edition': 'Professional', 'language': 'tr-TR',
                'index': int(image.attrib['INDEX']), 'bytes': wim.stat().st_size, 'sha256': digest,
                'build': image.findtext('WINDOWS/VERSION/BUILD')}
    (output / 'windows-media.json').write_text(json.dumps(metadata, indent=2))
    injection = output / 'injection'
    app = injection / 'DiskTest86'
    app.mkdir(parents=True)
    if any(path.is_symlink() for path in python_embed.rglob('*')):
        raise ValueError('Gömülü Python kaynağı bağlantı içeremez.')
    shutil.copytree(python_embed, app / 'python')
    pths = list((app / 'python').glob('python*._pth'))
    if len(pths) != 1:
        raise ValueError('Tekil gömülü Python yol dosyası gerekli.')
    pths[0].write_text(pths[0].read_text() + '\n..\n', encoding='ascii')
    source = Path(__file__).resolve().parent.parent / 'windows'
    for path in source.iterdir():
        if path.suffix in {'.py', '.cmd', '.ps1'} and path.name != 'lab_install.py':
            shutil.copyfile(path, app / path.name)
    (app / 'install.cmd').write_bytes(b'@echo off\r\nchcp 65001 >nul\r\nX:\\DiskTest86\\python\\python.exe -I X:\\DiskTest86\\install.py\r\nwpeutil shutdown\r\n')
    ini = injection / 'winpeshl.ini'
    ini.write_bytes(b'[LaunchApps]\r\n%SYSTEMROOT%\\System32\\wpeinit.exe\r\n%SYSTEMROOT%\\System32\\cmd.exe, /c X:\\DiskTest86\\install.cmd\r\n')
    commands = 'add "' + app.resolve().as_posix() + '" "/DiskTest86"\nadd "' + ini.resolve().as_posix() + '" "/Windows/System32/winpeshl.ini"\n'
    subprocess.run([str(wimlib), 'update', str(tree / 'sources/boot.wim'), '2', '--no-acls'],
                   input=commands.encode('utf-8'), check=True)
    print('Yerel Windows medyası hazır. Genel dağıtım izni vermez: ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('iso', 'python_embed', 'wimlib', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    prepare(args.iso, args.python_embed, args.wimlib, args.output)

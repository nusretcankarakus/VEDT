#!/usr/bin/env python3
"""Build a NEW regular GPT image from owned Live/WinPE/WIM files; no physical disks."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

spec = importlib.util.spec_from_file_location('base_image', Path(__file__).with_name('make-usb-image.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
MIB = 1024**2


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def make(live, winpe, wim, metadata, output, defer_host_verification=False):
    for path in (live, winpe, wim, metadata):
        if not path.exists() or path.is_symlink():
            raise ValueError('Yerel kaynak dosyası veya ağacı geçersiz: ' + str(path))
    if output.exists() or output.suffix != '.img':
        raise ValueError('Yeni .img çıktı adı gerekli.')
    config = json.loads(metadata.read_text())
    if config.get('edition') != 'Professional' or config.get('language') != 'tr-TR' or wim.stat().st_size != config['bytes']:
        raise ValueError('Windows kaynak özeti veya sürümü uyuşmuyor.')
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix('.img.partial')
    start = 2048
    layout = []
    for name, size, kind in [('DTESP', 1024, base.ESP), ('DTLIVE', 1280, base.DATA), ('DTREPORTS', 512, base.DATA), ('DTPAYLOAD', 10240, base.DATA)]:
        sectors = size * MIB // 512
        layout.append({'name': name, 'first': start, 'last': start + sectors - 1, 'bytes': size * MIB,
                       'type': kind.hex(), 'guid': str(uuid.uuid4())})
        start += sectors
    total = ((start + 33 + 2047) // 2048) * 2048
    with partial.open('xb') as stream:
        stream.truncate(total * 512)
    for i, part in enumerate(layout[:3]):
        subprocess.run(['mkfs.vfat', '-F', '32', '-s', str((8, 8, 4)[i]), '-n', part['name'], '-i', f'{0xD15C0001+i:08x}',
                        '--offset=' + str(part['first']), str(partial), str(part['bytes'] // 1024)], check=True)
    base.write_gpt(partial, layout, total)
    esp, data, reports = [str(partial) + '@@' + str(p['first'] * 512) for p in layout[:3]]
    media_id = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='vedt-build-') as temporary:
        temp = Path(temporary)
        def copy(source, volume, target='::/'):
            subprocess.run(['mcopy', '-s', '-o', '-i', volume, str(source), target], check=True)
        for item in live.iterdir():
            copy(item, data)
        efi = temp / 'efi'
        efi.mkdir()
        subprocess.run(['mcopy', '-s', '-i', str(live / 'boot/grub/efi.img'), '::/*', str(efi)], check=True)
        for item in efi.iterdir():
            copy(item, esp)
        # Preserve GRUB at EFI/BOOT; put Windows manager alongside it.
        microsoft = temp / 'Microsoft'
        shutil.copytree(winpe / 'efi/microsoft', microsoft)
        shutil.copyfile(winpe / 'efi/boot/bootx64.efi', microsoft / 'boot/bootmgfw.efi')
        copy(microsoft, esp, '::/EFI/')
        copy(winpe / 'boot', esp)
        copy(winpe / 'sources', esp)
        for name in ('bootmgr', 'bootmgr.efi'):
            copy(winpe / name, esp)
        kernel = next(p.name for p in (live / 'live').glob('vmlinuz-*'))
        initrd = next(p.name for p in (live / 'live').glob('initrd.img-*'))
        grub = temp / 'grub.cfg'
        grub.write_text("""set default=0
set timeout=0
serial --unit=0 --speed=115200
terminal_output console serial
insmod part_gpt
insmod fat
insmod chain
load_env -f /boot/grub/grubenv next_stage target_uuid
if [ "$next_stage" = "winpe" ]; then
    set next_stage=linux
    save_env -f /boot/grub/grubenv next_stage
    search --no-floppy --label DTESP --set=root
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
    boot
fi
if [ "$next_stage" = "windows" ]; then
    set next_stage=linux
    save_env -f /boot/grub/grubenv next_stage
    search --no-floppy --fs-uuid $target_uuid --set=root
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
    boot
fi
insmod all_video
set gfxmode=1920x1080,1280x720,1024x768,auto
set gfxpayload=keep
if loadfont /boot/grub/unicode.pf2; then
    terminal_output gfxterm serial
fi
menuentry 'VEDT — Vektron Elektronik Disk Test' {
    linux /live/KERNEL boot=live components locales=tr_TR.UTF-8 keyboard-layouts=tr console=tty1 console=ttyS0,115200 disktest.unattended=1 quiet loglevel=3 systemd.show_status=0
    initrd /live/INITRD
}
""".replace('KERNEL', kernel).replace('INITRD', initrd), encoding='utf-8')
        copy(grub, data, '::/boot/grub/grub.cfg')
        env = temp / 'grubenv'
        subprocess.run(['grub-editenv', str(env), 'create'], check=True)
        subprocess.run(['grub-editenv', str(env), 'set', 'next_stage=linux'], check=True)
        copy(env, data, '::/boot/grub/grubenv')
        for role, volume in [('reports', reports), ('boot', esp)]:
            marker = temp / 'VEDT-MEDIA.json'
            marker.write_text(json.dumps({'schema_version': 1, 'media_id': media_id, 'role': role}), encoding='utf-8')
            copy(marker, volume)
        for source_name, target_name in [('docs/KULLANIM.md', 'KULLANIM.txt'), ('docs/RAPOR-REHBERI-V1.md', 'RAPOR-REHBERI.txt'), ('LICENSE', 'VEDT-LICENSE.txt'), ('THIRD-PARTY-NOTICES.md', 'UCUNCU-TARAF-NOTLARI.txt')]:
            doc = temp / target_name
            doc.write_bytes((Path(__file__).resolve().parent.parent / source_name).read_bytes())
            copy(doc, reports)
        sums = temp / 'sha256sum.txt'
        rows = []
        for path in sorted(live.rglob('*')):
            if path.is_file() and path.name != 'sha256sum.txt':
                rel = path.relative_to(live).as_posix()
                source = grub if rel == 'boot/grub/grub.cfg' else path
                rows.append(digest(source) + '  ./' + rel)
        # grubenv is mutable state and intentionally excluded from static checksums.
        sums.write_text('\n'.join(rows) + '\n', encoding='utf-8')
        copy(sums, data)
        # The loop device is restricted to the payload range of this newly created
        # regular image. No physical device path is accepted from the caller.
        if not partial.is_file() or partial.is_symlink() or partial.stat().st_size != total * 512:
            raise ValueError('Yeni düzenli imaj dosyası doğrulanamadı.')
        loop = subprocess.check_output(['losetup', '--find', '--show', '--offset', str(layout[3]['first'] * 512),
                                       '--sizelimit', str(layout[3]['bytes']), str(partial.resolve())], text=True).strip()
        if not re.fullmatch('/dev/loop[0-9]+', loop):
            raise ValueError('Geçersiz imaj döngü aygıtı.')
        mounted = False
        try:
            backing = Path('/sys/block') / Path(loop).name / 'loop/backing_file'
            if Path(backing.read_text().strip()).resolve() != partial.resolve():
                raise ValueError('Döngü aygıtı bu imaja ait değil.')
            subprocess.run(['mkfs.ntfs', '-Q', '-F', '-L', 'DTPAYLOAD', loop], check=True)
            mount = temp / 'payload-mount'
            mount.mkdir()
            subprocess.run(['ntfs-3g', loop, str(mount)], check=True)
            mounted = True
            (mount / 'sources').mkdir()
            shutil.copyfile(metadata, mount / 'windows-media.json')
            (mount / 'VEDT-MEDIA.json').write_text(json.dumps({'schema_version': 1, 'media_id': media_id, 'role': 'payload'}))
            subprocess.run(['sync'], check=True)
            subprocess.run(['umount', str(mount)], check=True)
            mounted = False
            copied = subprocess.run(['ntfscp', '-f', loop, str(wim), '/sources/install.wim'], check=True, capture_output=True, text=True)
            if 'Aborting write' in copied.stdout + copied.stderr:
                raise RuntimeError('Windows kaynak kopyası yarıda kesildi.')
            if not defer_host_verification:
                with subprocess.Popen(['ntfscat', loop, '/sources/install.wim'], stdout=subprocess.PIPE) as process:
                    actual = hashlib.file_digest(process.stdout, 'sha256').hexdigest()
                    if process.wait() or actual != config['sha256']:
                        raise ValueError('NTFS Windows kaynak kopyası bozuk.')
        finally:
            if mounted:
                subprocess.run(['umount', str(mount)], check=True)
            subprocess.run(['losetup', '-d', loop], check=True)
    base.write_gpt(partial, layout, total)
    sha = None if defer_host_verification else digest(partial)
    os.link(partial, output)
    partial.unlink()
    result = {'version': '0.5.0.dev0', 'media_id': media_id, 'bytes': output.stat().st_size,
              'sha256': sha, 'partitions': layout, 'windows': config, 'physical_hardware_verified': False,
              'secure_boot_verified': False, 'release_status': 'development-candidate', 'integrity_status': 'pending-host-verification' if defer_host_verification else 'verified'}
    output.with_suffix('.img.build.json').write_text(json.dumps(result, indent=2))
    if sha:
        output.with_suffix('.img.sha256').write_text(sha + '  ' + output.name + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('live', 'winpe', 'wim', 'metadata', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--defer-host-verification', action='store_true', help='SHA-256 denetimini paketleyen ana bilgisayara bırakır; doğrulama tamamlanmadan dağıtmayın.')
    args = parser.parse_args()
    make(args.live, args.winpe, args.wim, args.metadata, args.output, args.defer_host_verification)

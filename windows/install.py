"""WinPE-only combined installer. Requires matching media, machine and full test evidence."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import uuid
from handoff import read_json, sha256, validate_media
from identity_match import select
from win_devices import inventory, volume_disk_numbers
from make_unattend import create


def machine_uuid():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = kernel.GetSystemFirmwareTable
    function.argtypes = [wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    function.restype = wintypes.UINT
    provider = int.from_bytes(b'RSMB', 'big')
    length = function(provider, 0, None, 0)
    if not 8 <= length <= 1024 * 1024:
        raise ValueError('Bilgisayar kimlik tablosu alınamadı.')
    data = ctypes.create_string_buffer(length)
    if function(provider, 0, data, length) != length:
        raise ValueError('Bilgisayar kimlik tablosu değişti.')
    raw = data.raw[8:]
    pos = 0
    while pos + 4 <= len(raw):
        kind, size = raw[pos], raw[pos + 1]
        if size < 4 or pos + size > len(raw):
            break
        if kind == 1 and size >= 25:
            value = str(uuid.UUID(bytes_le=raw[pos + 8:pos + 24]))
            if value in {'00000000-0000-0000-0000-000000000000', 'ffffffff-ffff-ffff-ffff-ffffffffffff'}:
                break
            return value
        end = raw.find(b'\x00\x00', pos + size)
        if end < 0:
            break
        pos = end + 2
    raise ValueError('Tekil bilgisayar kimliği doğrulanamadı.')


def save(path, value):
    temporary = path.with_name(path.name + '.new')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def esp_uuid():
    serial = wintypes.DWORD()
    if not ctypes.windll.kernel32.GetVolumeInformationW('S:\\', None, 0, ctypes.byref(serial), None, None, None, 0):
        raise ctypes.WinError()
    value = f'{serial.value:08X}'
    return value[:4] + '-' + value[4:]


def main():
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\MiniNT'):
        pass
    if os.environ.get('SystemRoot', '').lower() != r'x:\windows':
        raise ValueError('Yalnız Windows PE ortamında çalışır.')
    firmware = wintypes.DWORD()
    if not ctypes.windll.kernel32.GetFirmwareType(ctypes.byref(firmware)) or firmware.value != 2:
        raise ValueError('UEFI açılışı gerekli.')
    roles = {}
    for letter in 'CDEFGHIJKLMNOPQRSTUVWYZ':
        root = Path(letter + ':\\')
        marker = root / 'VEDT-MEDIA.json'
        if marker.is_file():
            data = read_json(marker, 65536)
            role = data.get('role')
            if role in roles:
                raise ValueError('Aynı rolde birden fazla USB bulundu.')
            roles[role] = (root, data)
    if not {'reports', 'payload'}.issubset(roles):
        raise ValueError('VEDT rapor ve Windows kaynak medyası bulunamadı.')
    root, marker = roles['reports']
    payload, source_marker = roles['payload']
    media_id = marker.get('media_id')
    if not re.fullmatch('[0-9a-f]{32}', media_id or '') or source_marker.get('media_id') != media_id:
        raise ValueError('USB medya kimlikleri eşleşmiyor.')
    report_disks = volume_disk_numbers(root.drive[0])
    payload_disks = volume_disk_numbers(payload.drive[0])
    if len(report_disks) != 1 or report_disks != payload_disks:
        raise ValueError('Kaynak ve rapor alanı aynı fiziksel USB üzerinde değil.')
    devices = inventory()
    usb = [d for d in devices if d['number'] in report_disks]
    if len(usb) != 1 or usb[0].get('bus_type') != 7:
        raise ValueError('Birleşik açılış medyası USB olarak doğrulanamadı.')
    active = read_json(root / 'VEDT-ACTIVE.json', 65536)
    if active.get('media_id') != media_id or active.get('machine_uuid') != machine_uuid() or active.get('phase') != 'windows-ready':
        raise ValueError('USB işi bu bilgisayara ait değil veya testler tamamlanmadı.')
    job_id = active.get('job_id')
    if not re.fullmatch('[0-9a-f]{24}', job_id or ''):
        raise ValueError('İş kimliği geçersiz.')
    job = root / 'reports/jobs' / job_id
    plan = read_json(job / 'windows-hazirlik.json', 8 * 1024**2)
    if any(plan.get(key) != active.get(key) for key in ('media_id', 'machine_uuid', 'job_id')) or plan.get('schema_version') != 2:
        raise ValueError('Test ve kurulum işi eşleşmiyor.')
    image = payload / 'sources/install.wim'
    config = read_json(payload / 'windows-media.json', 65536)
    if config.get('edition') != 'Professional' or config.get('language') != 'tr-TR' or type(config.get('index')) is not int or config['index'] < 1:
        raise ValueError('Windows sürüm kaydı desteklenmiyor.')
    print('Windows kaynak dosyası doğrulanıyor. Lütfen bekleyin.', flush=True)
    if image.stat().st_size != config.get('bytes') or sha256(image) != config.get('sha256'):
        raise ValueError('Windows kaynak imajının özeti uyuşmuyor.')
    targets = validate_media(job, plan, devices, boot_root=root, image=image)
    journal_path = job / 'windows-install.json'
    journal = read_json(journal_path, 8 * 1024**2) if journal_path.exists() else {
        'schema_version': 1, 'job_id': job_id, 'machine_uuid': active['machine_uuid'], 'complete': False, 'targets': []}
    if journal.get('job_id') != job_id or journal.get('machine_uuid') != active['machine_uuid']:
        raise ValueError('Önceki kurulum kaydı farklı işe ait.')
    for target in targets:
        old = [t for t in journal['targets'] if t['report_id'] == target['report'].name]
        if old:
            if len(old) == 1 and old[0].get('phase') == 'complete' and old[0].get('identity') == target['identity']:
                continue
            raise ValueError('Önceki kurulum yarım kalmış; yeniden silme engellendi.')
        for letter in ('S', 'W', 'R'):
            if Path(letter + ':\\').exists():
                raise ValueError('Kurulum sürücü harfi kullanımda: ' + letter)
        row = {'report_id': target['report'].name, 'identity': target['identity'], 'account_name': target['account_name'],
               'phase': 'started', 'steps': []}
        journal['targets'].append(row)
        save(journal_path, journal)
        def run(name, command, timeout=3600):
            step = {'name': name, 'state': 'running'}
            row['steps'].append(step)
            save(journal_path, journal)
            log = job / (row['report_id'] + '-' + str(len(row['steps'])) + '.log')
            with log.open('wb') as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            step.update(state='done' if result.returncode == 0 else 'failed', exit_code=result.returncode)
            save(journal_path, journal)
            if result.returncode:
                raise RuntimeError('İşlem başarısız: ' + name)
            return log
        # Re-read and match report, physical identity and USB protection immediately before clean.
        fresh = validate_media(job, plan, inventory(), boot_root=root, image=image)
        again = next(t for t in fresh if t['report'] == target['report'])
        number = again['device']['number']
        if number != target['device']['number'] or type(number) is not int or not 0 <= number < 4096:
            raise ValueError('Disk numarası değişti veya geçersiz.')
        script = Path(r'X:\DiskTest86\layout.txt')
        script.write_bytes((f'select disk {number}\r\nclean\r\nconvert gpt\r\n'
            'create partition efi size=300\r\nformat quick fs=fat32 label=SYSTEM\r\nassign letter=S\r\n'
            'create partition msr size=16\r\ncreate partition primary\r\nshrink minimum=1024\r\n'
            'format quick fs=ntfs label=Windows\r\nassign letter=W\r\n'
            'create partition primary\r\nformat quick fs=ntfs label=Recovery\r\nassign letter=R\r\n'
            'set id=de94bba4-06d1-4d40-a16a-bfd50179d6ac\r\ngpt attributes=0x8000000000000001\r\nexit\r\n').encode('ascii'))
        run('Bölümleme', ['diskpart.exe', '/s', str(script)], 180)
        run('Windows uygula', ['dism.exe', '/Apply-Image', '/ImageFile:' + str(image), '/Index:' + str(config['index']),
                              '/ApplyDir:W:\\', '/CheckIntegrity', '/Verify'], 7200)
        edition = run('Sürümü doğrula', ['dism.exe', '/Image:W:\\', '/Get-CurrentEdition'], 180)
        if 'Professional' not in edition.read_bytes().replace(b'\0', b'').decode('utf-8', errors='ignore'):
            raise ValueError('Kurulan Windows Professional değil.')
        panther = Path(r'W:\Windows\Panther')
        panther.mkdir(exist_ok=True)
        (panther / 'unattend.xml').write_bytes(create('VEDT', target['account_name']))
        base = Path(r'W:\ProgramData\DiskTest86')
        base.mkdir(parents=True)
        for name in ('Apply-TestDesktop.ps1', 'Complete-FirstLogon.ps1', 'Complete-FirstLogon.cmd'):
            shutil.copyfile(Path(r'X:\DiskTest86') / name, base / name)
        shutil.copytree(target['report'], base / 'test-report')
        (base / 'expected-manifest.txt').write_text(target['manifest_sha256'], encoding='ascii')
        context = {'media_id': media_id, 'job_id': job_id, 'report_id': target['report'].name}
        save(base / 'deployment-context.json', context)
        desktop = Path(r'W:\Users\Default\Desktop') / target['account_name']
        shutil.copytree(target['report'], desktop)
        for copy in (base / 'test-report', desktop):
            for item in target['report'].iterdir():
                if sha256(copy / item.name) != sha256(item):
                    raise ValueError('Hedef rapor kopyası doğrulanamadı.')
        recovery = Path(r'W:\Windows\System32\Recovery\winre.wim')
        if recovery.is_file():
            target_recovery = Path(r'R:\Recovery\WindowsRE')
            target_recovery.mkdir(parents=True)
            shutil.copyfile(recovery, target_recovery / 'winre.wim')
            run('Kurtarma kaydı', [r'W:\Windows\System32\reagentc.exe', '/SetReImage', '/Path', str(target_recovery), '/Target', r'W:\Windows'], 180)
        run('UEFI açılışı', [r'W:\Windows\System32\bcdboot.exe', r'W:\Windows', '/s', 'S:', '/f', 'UEFI'], 180)
        row['esp_uuid'] = esp_uuid()
        remove = Path(r'X:\DiskTest86\release-letters.txt')
        remove.write_bytes(b'select volume S\r\nremove letter=S\r\nselect volume W\r\nremove letter=W\r\nselect volume R\r\nremove letter=R\r\nexit\r\n')
        run('Geçici harfleri kaldır', ['diskpart.exe', '/s', str(remove)], 180)
        row['phase'] = 'complete'
        save(journal_path, journal)
    journal['complete'] = True
    save(journal_path, journal)
    print('Windows imajları hazırlandı. İlk oturum için yeniden başlatılıyor.', flush=True)
    subprocess.run(['wpeutil.exe', 'reboot'], check=True)


if __name__ == '__main__':
    import traceback
    try:
        main()
    except Exception:
        print('VEDT kurulumu güvenli biçimde durdurdu. Otomatik yeniden silme yapılmayacak.', flush=True)
        traceback.print_exc()
        for letter in 'CDEFGHIJKLMNOPQRSTUVWYZ':
            root = Path(letter + ':\\')
            if (root / 'VEDT-MEDIA.json').is_file():
                try:
                    (root / 'VEDT-install-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
                except OSError:
                    pass
        subprocess.run(['wpeutil.exe', 'shutdown'], check=False)

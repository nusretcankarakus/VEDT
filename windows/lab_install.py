"""Windows-only deployment acceptance on one explicitly owned QEMU fixture.

NOT a production installer: requires WinPE, QEMU DMI, a laboratory USB marker
and the exact 80-GiB DT-WIN-SATA device + WWN. No generic disk-number input.
The Linux full-disk test is not represented by this separate Windows fixture.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import winreg

from identity_match import select
from make_unattend import create
from win_devices import inventory

EXPECTED = {'serial': 'DT-WIN-SATA', 'model': 'QEMU HARDDISK',
            'size_bytes': 80 * 1024**3, 'wwn': '0x5000000000000501'}


def main():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\MiniNT'):
        pass
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\BIOS') as key:
        manufacturer = winreg.QueryValueEx(key, 'SystemManufacturer')[0]
    if manufacturer != 'QEMU' or os.environ.get('SystemRoot', '').lower() != r'x:\windows':
        raise RuntimeError('Yalnız WinPE/QEMU laboratuvarı kabul edilir.')
    roots = [Path(letter + ':\\') for letter in 'CDEFGHIJKLMNOPQRSTUVWYZ']
    logs = [p for p in roots if (p / 'DT-WINPE-LAB.json').is_file()]
    if len(logs) != 1:
        raise RuntimeError('Tekil laboratuvar kayıt USB’si bulunamadı.')
    root = logs[0]
    marker = json.loads((root / 'DT-WINPE-LAB.json').read_text())
    if marker != {'mode': 'windows-stage-only', 'serial': 'DT-WIN-SATA'}:
        raise RuntimeError('Laboratuvar yetkisi eşleşmiyor.')
    if (root / 'installation-complete.json').exists():
        raise RuntimeError('Bu laboratuvar hedefi zaten hazırlanmış; yeniden silinmedi.')
    payload = [p / 'sources/install.wim' for p in roots if (p / 'sources/install.wim').is_file()]
    if len(payload) != 1:
        raise RuntimeError('Tekil Windows kaynak imajı bulunamadı.')
    devices = inventory()
    target = select(EXPECTED, devices)
    for letter in ('S', 'W', 'R'):
        if Path(letter + ':\\').exists():
            raise RuntimeError('Laboratuvar sürücü harfi kullanımda: ' + letter)
    record = {'mode': 'windows-stage-only', 'target': target, 'devices': devices, 'linux_full_test_performed': False,
              'test_report_is_fixture': True, 'network': 'none', 'steps': [], 'complete': False}
    def save():
        path = root / 'windows-install-log.json'
        with path.open('w', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    def run(name, command, timeout=1800):
        row = {'name': name, 'state': 'running'}
        record['steps'].append(row)
        save()
        with (root / (str(len(record['steps'])) + '-command.log')).open('wb') as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
        row.update({'exit_code': result.returncode, 'state': 'done' if result.returncode == 0 else 'failed'})
        save()
        if result.returncode:
            raise RuntimeError('İşlem başarısız: ' + name)
    save()
    # No device writes above this point. Re-read the full identity immediately
    # before the fixture-only DiskPart command; refuse changed numbering too.
    again = select(EXPECTED, inventory())
    if again['number'] != target['number']:
        raise RuntimeError('Aygıt numarası değişti.')
    script = Path(r'X:\DiskTest86\layout.txt')
    script.write_bytes((f"select disk {target['number']}\r\nclean\r\nconvert gpt\r\n"
        'create partition efi size=300\r\nformat quick fs=fat32 label=SYSTEM\r\nassign letter=S\r\n'
        'create partition msr size=16\r\ncreate partition primary\r\nshrink minimum=1024\r\n'
        'format quick fs=ntfs label=Windows\r\nassign letter=W\r\n'
        'create partition primary\r\nformat quick fs=ntfs label=Recovery\r\nassign letter=R\r\n'
        'set id=de94bba4-06d1-4d40-a16a-bfd50179d6ac\r\ngpt attributes=0x8000000000000001\r\nexit\r\n').encode('ascii'))
    run('Bölümleme', ['diskpart.exe', '/s', str(script)], 180)
    run('Windows 11 Pro imajını uygula', ['dism.exe', '/Apply-Image', '/ImageFile:' + str(payload[0]),
                                        '/Index:4', '/ApplyDir:W:\\', '/CheckIntegrity', '/Verify'], 3600)
    run('Sürümü doğrula', ['dism.exe', '/Image:W:\\', '/Get-CurrentEdition'], 120)
    edition_log = (root / '3-command.log').read_bytes().replace(b'\0', b'').decode('utf-8', errors='ignore')
    if 'Professional' not in edition_log:
        raise RuntimeError('Professional sürümü doğrulanamadı.')
    panther = Path(r'W:\Windows\Panther')
    panther.mkdir(exist_ok=True)
    (panther / 'unattend.xml').write_bytes(create())
    destination = Path(r'W:\ProgramData\DiskTest86')
    destination.mkdir(parents=True)
    for name in ('Apply-TestDesktop.ps1', 'Complete-FirstLogon.ps1', 'Complete-FirstLogon.cmd'):
        shutil.copyfile(Path(r'X:\DiskTest86') / name, destination / name)
    shutil.copytree(Path(r'X:\DiskTest86\test-report'), destination / 'test-report')
    shutil.copyfile(Path(r'X:\DiskTest86\expected-manifest.txt'), destination / 'expected-manifest.txt')
    recovery = Path(r'W:\Windows\System32\Recovery\winre.wim')
    if recovery.is_file():
        target_recovery = Path(r'R:\Recovery\WindowsRE')
        target_recovery.mkdir(parents=True)
        shutil.copyfile(recovery, target_recovery / 'winre.wim')
        run('Kurtarma ortamını kaydet', [r'W:\Windows\System32\reagentc.exe', '/SetReImage',
                                      '/Path', str(target_recovery), '/Target', r'W:\Windows'], 120)
    run('UEFI açılışını hazırla', [r'W:\Windows\System32\bcdboot.exe', r'W:\Windows', '/s', 'S:', '/f', 'UEFI'], 120)
    record['complete'] = True
    save()
    (root / 'installation-complete.json').write_text(json.dumps({'target': EXPECTED, 'windows_applied': True,
        'first_logon_verified': False, 'production_installer': False}), encoding='utf-8')


if __name__ == '__main__':
    import traceback
    try:
        main()
    except BaseException:
        for letter in 'CDEFGHIJKLMNOPQRSTUVWYZ':
            root = Path(letter + ':\\')
            if (root / 'DT-WINPE-LAB.json').is_file():
                (root / 'installation-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        subprocess.run(['wpeutil.exe', 'shutdown'], check=False)

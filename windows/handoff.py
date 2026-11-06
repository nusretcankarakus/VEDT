"""Validate Linux test evidence before any general Windows deployment writes.

This is a read-only preflight. Old enabled=false plans and laboratory reports
are deliberately rejected. Matching by a cached disk number is never allowed.
"""
import hashlib
import json
from pathlib import Path
import re
from identity_match import select, IdentityMismatch


def read_json(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Geçersiz veya aşırı büyük hazırlık dosyası.')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_report(root, item):
    name = item.get('test_report')
    if not isinstance(name, str) or not re.fullmatch('[0-9a-f]{24}', name):
        raise ValueError('Rapor klasör kimliği geçersiz.')
    folder = Path(root) / name
    if folder.is_symlink() or folder.resolve().parent != Path(root).resolve():
        raise ValueError('Rapor kök klasörün dışında.')
    manifest_path = folder / 'manifest.json'
    expected_hash = item.get('manifest_sha256')
    if not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-f]{64}', expected_hash) or sha256(manifest_path) != expected_hash:
        raise ValueError('Rapor dosya özeti değişti.')
    manifest = read_json(manifest_path, 65536)
    files = manifest.get('files')
    if manifest.get('algorithm') != 'SHA-256' or not isinstance(files, dict) or not 3 <= len(files) <= 16:
        raise ValueError('Dosya özeti listesi geçersiz.')
    if 'session.json' not in files:
        raise ValueError('Zorunlu rapor dosyası eksik.')
    if len({name.casefold() for name in files}) != len(files):
        raise ValueError('Dosya adları Windows üzerinde belirsiz.')
    for filename, digest in files.items():
        if not isinstance(filename, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,80}', filename) or filename in {'.', '..', 'manifest.json'}:
            raise ValueError('Geçersiz rapor dosya yolu.')
        path = folder / filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024**2:
            raise ValueError('Rapor dosyası geçersiz.')
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or sha256(path) != digest:
            raise ValueError('Rapor içeriği değiştirilmiş.')
    session = read_json(folder / 'session.json', 64 * 1024**2)
    account = session.get('account_name')
    report_name = session.get('report_file_stem', 'report')
    if not isinstance(report_name, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,75}', report_name) or (account and not report_name.startswith(account + '_')):
        raise ValueError('Rapor adı hesap numarasıyla eşleşmiyor.')
    if not {report_name + '.pdf', report_name + '.html'}.issubset(files):
        raise ValueError('Numaralı rapor dosyaları eksik.')
    expected = item.get('identity')
    if (session.get('mode') != 'raw-device' or session.get('identity_authorized') is not True or
        session.get('full_capacity_verified') is not True or session.get('status') not in {'PASS', 'WARNING'} or session.get('error') is not None):
        raise ValueError('Başarılı tam disk testi kanıtı bulunamadı.')
    if session.get('target', {}).get('identity') != expected or session['target'].get('bytes') != expected.get('size_bytes'):
        raise ValueError('Test edilen hedef ile kurulum hedefi farklı.')
    stages = session.get('stages')
    if not isinstance(stages, list) or len(stages) != 6 or any(row.get('status') != 'PASS' for row in stages):
        raise ValueError('Altı test aşamasının tamamı başarılı değil.')
    for index in (2, 3, 5):
        if stages[index].get('bytes') != expected['size_bytes']:
            raise ValueError('Tam kapasite yazma veya doğrulama eksik.')
    for key in ('smart_before', 'smart_after'):
        if session.get(key, {}).get('health') == 'FAIL':
            raise ValueError('Aygıt güncel arıza bildiriyor.')
    critical = {'media_errors', 'critical_warning', 'ata_5', 'ata_187', 'ata_188', 'ata_197', 'ata_198'}
    if any(value.get('delta', 0) > 0 for key, value in session.get('smart_changes', {}).items() if key in critical):
        raise ValueError('Kritik aygıt hata sayacı yükselmiş.')
    return session, folder


def validate(root, plan, devices, protected_numbers):
    if (plan.get('schema_version') not in {1, 2} or plan.get('enabled') is not True or
        plan.get('edition') != 'Professional' or plan.get('language') != 'tr-TR' or (plan.get('schema_version') == 1 and plan.get('account_name') != 'test')):
        raise ValueError('Windows hazırlık kaydı etkin veya desteklenen biçimde değil.')
    targets = plan.get('targets')
    if not isinstance(targets, list) or not 1 <= len(targets) <= 64:
        raise ValueError('Kurulum hedef listesi geçersiz.')
    result, numbers = [], set()
    for item in targets:
        expected = item.get('identity', {})
        if type(expected.get('size_bytes')) is not int or expected['size_bytes'] < 64 * 1024**3:
            raise ValueError('Windows hedefi en az 64 GiB olmalı.')
        session, folder = verified_report(root, item)
        account = item.get('account_name') if plan['schema_version'] == 2 else 'test'
        if plan['schema_version'] == 2 and (not isinstance(account, str) or not re.fullmatch(r'VEDT[1-9][0-9]{0,14}', account) or session.get('account_name') != account):
            raise ValueError('VEDT hesap numarası test raporuyla eşleşmiyor.')
        device = select(expected, devices, session.get('native_ids', ()))
        number = device['number']
        if number in protected_numbers or number in numbers:
            raise IdentityMismatch('Açılış/rapor diski veya yinelenen hedef seçilemez.')
        numbers.add(number)
        result.append({'device': device, 'identity': expected, 'report': folder,
                       'manifest_sha256': item['manifest_sha256'], 'account_name': account})
    return result


def validate_media(root, plan, devices, *, boot_root, image):
    """Derive protected disks from actual media volumes, never caller disk numbers.

    Read-only preflight for the future deployment entry point. Volume lookup
    failure propagates; an unknown boot/report/source disk cannot be ignored.
    This does not validate the Windows image contents or perform installation.
    """
    from win_devices import volume_disk_numbers
    root, boot_root, image = (Path(p).resolve(strict=True) for p in (root, boot_root, image))
    if not root.is_dir() or not boot_root.is_dir() or not image.is_file() or image.suffix.lower() != '.wim':
        raise ValueError('Açılış, rapor veya Windows imajı yolu geçersiz.')
    protected = set()
    drives = set()
    for path in (root, boot_root, image):
        if not re.fullmatch('[A-Za-z]:', path.drive):
            raise ValueError('Fiziksel birime ait yerel medya yolu gerekli.')
        drives.add(path.drive[0].upper())
    for letter in sorted(drives):
        protected.update(volume_disk_numbers(letter))
    if not protected:
        raise ValueError('Açılış ve rapor medyası korunamadı.')
    return validate(root, plan, devices, protected)

"""Non-executable handoff plan. Installation awaits an official Windows ISO."""
import json
from pathlib import Path
from .report import digest, verify_manifest


def prepare_plan(reports, batch):
    reports = Path(reports)
    targets, skipped = [], []
    identities = {target['serial']: target for target in batch['queue']}
    for row in batch['results']:
        target = identities[row['serial']]
        folder = reports / row['report']
        from .installation_policy import installation_decision
        session = json.loads((folder / 'session.json').read_text(encoding='utf-8'))
        decision = installation_decision(session)
        if not decision['eligible'] or target['size_bytes'] < 64 * 1024**3 or not row.get('windows_eligible_test_result') or verify_manifest(folder):
            skipped.append({'serial': target['serial'], 'reason': 'Windows için en az 64 GiB, tam başarılı test ve uygun SMART gerekli. ' + ' '.join(decision['reasons'])})
            continue
        targets.append({'identity': target, 'test_report': row['report'],
                        'manifest_sha256': digest(folder / 'manifest.json'),
                        'account_name': row['account_name'],
                        'desktop_report': 'Users/Default/Desktop/' + row['account_name'],
                        'installation_state': 'pending-winpe'})
    plan = {'schema_version': 2, 'enabled': False, 'edition': 'Professional', 'language': 'tr-TR',
            'account_policy': 'per-target-vedt-number', 'visible_windows_volumes': 1,
            'separate_report_partition': False, 'targets': targets, 'skipped': skipped,
            'wallpaper_title': 'VEDT — Vektron Elektronik Disk Test',
            'wallpaper_warning': 'Bu sistem disk testi amacıyla hazırlanmıştır. Kişisel kullanımdan önce diski silerek temiz Windows kurulumu yapın.',
            'requirements': ['Resmî Türkçe Windows 11 Pro 64 bit ISO', 'Windows 11 donanım uygunluk kontrolü',
                             'UEFI/GPT sistem bölümleri', 'Secure Boot imza zinciri doğrulaması',
                             'Kurulumdan hemen önce tam hedef kimliğinin yeniden doğrulanması'],
            'note': 'Bu dosya kurulum komutu değildir. Windows veya masaüstü kopyası henüz oluşturulmadı.'}
    (reports / 'windows-hazirlik.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    return plan


def validate_installation_targets(job):
    """Recheck persistent jobs with current rules before rebooting to older WinPE."""
    from .installation_policy import installation_decision
    job = Path(job)
    plan = json.loads((job / 'windows-hazirlik.json').read_text(encoding='utf-8'))
    if not plan.get('targets'):
        raise ValueError('Windows hedefi bulunamadı.')
    for item in plan['targets']:
        import re
        name = item.get('test_report', '')
        if not re.fullmatch('[0-9a-f]{24}', name):raise ValueError('Windows rapor yolu geçersiz.')
        folder = job / name
        if folder.is_symlink() or verify_manifest(folder) or digest(folder / 'manifest.json') != item.get('manifest_sha256'):
            raise ValueError('Windows rapor bütünlüğü doğrulanamadı.')
        session = json.loads((folder / 'session.json').read_text(encoding='utf-8'))
        decision = installation_decision(session)
        if not decision['eligible'] or session.get('target', {}).get('identity') != item.get('identity'):
            raise ValueError('Windows kurulmayacak: ' + ' '.join(decision['reasons']))
    return plan

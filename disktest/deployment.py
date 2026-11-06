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
        if not row.get('windows_eligible_test_result') or verify_manifest(folder):
            skipped.append({'serial': target['serial'], 'reason': 'Bütün disk testleri başarıyla tamamlanmadı.'})
            continue
        targets.append({'identity': target, 'test_report': row['report'],
                        'manifest_sha256': digest(folder / 'manifest.json'),
                        'account_name': row['account_name'],
                        'desktop_report': 'Users/Default/Desktop/VEDT-Rapor',
                        'installation_state': 'iso-and-installer-not-ready'})
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

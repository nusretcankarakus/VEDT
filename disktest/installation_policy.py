"""One fail-closed eligibility rule used by reports and installation handoff."""
CRITICAL = {'media_errors', 'critical_warning', 'ata_5', 'ata_187', 'ata_188', 'ata_197', 'ata_198'}


def installation_decision(session):
    reasons = []
    stages = session.get('stages', [])
    if session.get('mode') != 'raw-device' or session.get('identity_authorized') is not True:
        reasons.append('Kimliği doğrulanmış gerçek aygıt testi gerekli; dosya/laboratuvar demosundan Windows kurulmaz.')
    if session.get('status') not in {'PASS', 'WARNING'} or session.get('error'):
        reasons.append('Test başarısız, durdurulmuş veya tamamlanmamış.')
    if session.get('full_capacity_verified') is not True or len(stages) != 6 or any(x.get('status') != 'PASS' for x in stages):
        reasons.append('Altı aşamanın tamamı ve tam kapasite doğrulaması gerekli.')
    size = session.get('target', {}).get('bytes')
    if type(size) is not int or size < 64*1024**3:
        reasons.append('Windows hedefi en az 64 GiB olmalı.')
    if len(stages) == 6 and any(stages[i].get('bytes') != size for i in (2,3,5)):
        reasons.append('Tam kapasite aşamalarının bayt sayıları hedef kapasiteyle uyuşmuyor.')
    if session.get('worker_may_still_be_running'):
        reasons.append('Test işleminin durduğu doğrulanamadı.')
    for key, label in [('smart_before', 'Başlangıç'), ('smart_after', 'Bitiş')]:
        data = session.get(key, {})
        if data.get('health') != 'PASS' or data.get('acquisition_ok') is not True:
            reasons.append(label + ' SMART verisi eksik, uyarılı veya başarısız.')
    try:
        from .health import comparison_rows
    except ImportError:  # Standalone WinPE application
        from health import comparison_rows
    rows = comparison_rows(session)
    for row in rows:
        if row['delta'] is not None and row['delta'] != 0:
            reasons.append(row['label'] + ': sayaç değişti; inceleme gerekli.')
        elif row['key'] in CRITICAL and any(isinstance(v, (int, float)) and v > 0 for v in (row['before'], row['after'])):
            reasons.append(row['label'] + ': mevcut hata/uyarı kaydı var.')
    return {'eligible': not reasons, 'policy': 'complete-test-clean-smart-v1',
            'reasons': reasons or ['Altı aşama ve tam kapasite doğrulandı; başlangıç/bitiş SMART kontrolleri uygun.'],
            'note': 'Bu karar yalnız disk testi kapısıdır; Windows donanım uygunluğunu veya kurulumu tamamlandığını göstermez.'}

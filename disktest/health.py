"""Comparable SMART raw counters; absence is never encoded as zero."""
LABELS = {'media_errors': 'Ortam / veri bütünlüğü hatası', 'num_err_log_entries': 'NVMe hata günlüğü kaydı',
    'critical_warning': 'NVMe kritik uyarı maskesi', 'ata_5': 'Yeniden eşlenen sektör',
    'ata_187': 'Bildirilen düzeltilemeyen hata', 'ata_188': 'Komut zaman aşımı',
    'ata_196': 'Yeniden eşleme olayı', 'ata_197': 'Bekleyen sektör',
    'ata_198': 'Çevrimdışı düzeltilemeyen sektör', 'ata_199': 'Arayüz CRC hatası'}


def counters(smart):
    raw = smart.get('raw', {})
    nvme = raw.get('nvme_smart_health_information_log', {})
    values = {key: nvme.get(key) for key in ('media_errors', 'num_err_log_entries', 'critical_warning')}
    for item in raw.get('ata_smart_attributes', {}).get('table', []):
        values['ata_' + str(item.get('id'))] = item.get('raw', {}).get('value')
    return {k: v for k, v in values.items() if k in LABELS and type(v) is int}


def comparison_rows(session):
    old = counters(session.get('smart_before', {})); new = counters(session.get('smart_after', {}))
    # Also understand older saved sessions whose only retained counters are deltas.
    for key, row in session.get('smart_changes', {}).items():
        if key in LABELS:
            if type(row.get('before')) is int: old.setdefault(key, row['before'])
            if type(row.get('after')) is int: new.setdefault(key, row['after'])
    rows = []
    for key, label in LABELS.items():
        a, b = old.get(key), new.get(key)
        delta = b-a if a is not None and b is not None else None
        state = 'Karşılaştırılamadı' if delta is None else 'Değişmedi' if delta == 0 else 'Arttı — inceleyin' if delta > 0 else 'Azaldı / sıfırlanmış olabilir'
        if key == 'critical_warning' and delta not in (None, 0): state = 'Uyarı maskesi değişti — inceleyin'
        rows.append(dict(key=key, label=label, before=a, after=b, delta=delta, state=state))
    return rows

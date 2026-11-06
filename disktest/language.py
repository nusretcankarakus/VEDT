"""Turkish labels shared by the console and human-readable reports."""
STATUS = {'PASS': 'Başarılı', 'FAIL': 'Başarısız', 'WARNING': 'Uyarılı',
          'UNKNOWN': 'Bilgi alınamadı', 'INCOMPLETE': 'Tamamlanamadı',
          'CANCELLED': 'İptal edildi', 'RUNNING': 'Çalışıyor', 'STOPPED': 'Durduruldu'}


def status_text(value):
    return STATUS.get(value, 'Belirlenemedi')


def conclusion(session):
    if session.get('status') == 'FAIL':
        return ('Disk testi başarıyla tamamlanamadı. Bu disk için sağlamdır denilemez. '
                'Aşağıdaki hata ve teknik bulgular incelenmelidir.')
    if session.get('mode') not in {'raw-device', 'lab-raw'} and session.get('stages') and all(
            row['status'] == 'PASS' for row in session['stages']):
        return 'Dosya denemesi tamamlandı. Bu sonuç fiziksel diskin sağlık durumunu göstermez.'
    if session.get('full_capacity_verified'):
        return ('Planlanan testlerin tamamı bitti. Yazılan veriler geri okunarak doğrulandı; '
                'bu test sırasında veri uyuşmazlığı bulunmadı. '
                'Bu sonuç, diskin ileride hiç arızalanmayacağı anlamına gelmez.')
    return ('Testin tamamı bitirilemedi. Eksik test nedeniyle diskin sağlığı hakkında '
            'kesin bir değerlendirme yapılamaz.')


def error_text(session):
    error = session.get('error')
    if not error:
        return 'Testi durduran bir hata kaydedilmedi.'
    region = session.get('verification_failure_range')
    if region:
        return (f"Yazılan veriyle okunan veri eşleşmedi. Hatalı blok başlangıcı: {region['offset_bytes']} bayt; "
                f"blok uzunluğu: {region['length_bytes']} bayt.")
    return {'ThermalLimit': 'Sıcaklık güvenli sınırı aştığı için test durduruldu.',
            'DeadlineExceeded': 'Süre sınırı aşıldı veya diskten beklenen sürede yanıt alınamadı.',
            'FioDataMismatch': 'Yazılan veri ile okunan veri arasında uyuşmazlık bulundu.',
            'FioError': 'Disk okuma, yazma veya veri doğrulama işlemi tamamlanamadı.',
            'SafetyError': 'Disk kimliği veya güvenli kullanım koşulları doğrulanamadı.',
            'DeviceInUse': 'Disk başka bir işlem tarafından kullanıldığı için işlem yapılmadı.',
            'cancelled': 'Test durduruldu.'}.get(error.get('kind'), 'Disk erişimi veya test işlemi sırasında hata oluştu.')

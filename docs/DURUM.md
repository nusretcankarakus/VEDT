# Geliştirme durumu — 6 Kasım 2026

Kaynak: 0.5.0.dev0. Birleşik geliştirme imajı `VEDT-combined-0.5-dev.img` oluşturuldu: 13.692.305.408 bayt. Windows kaynak kontrolünde 151 test geçti, 3 Linux testi atlandı. Envanter korumasından önceki Linux kontrolünde 150 test geçti, 3 Windows testi atlandı; envanter koruması ayrıca hedefli kontrollerden geçirildi. Bunlar donanım test sayıları değildir.

## Eklenenler

- Linux testi → WinPE → doğrulanmış hedeflere Windows uygulama akışı.
- USB'de bilgisayar/iş kimliğine bağlı kalıcı kayıt; yeniden başlatmada yeniden silmeyi engelleme.
- Windows PE'de kaynak/rapor USB'sinin korunması, hedef kimliğinin ve tam kapasite test kanıtının tekrar kontrolü.
- Windows oturumu `VEDT54`, rapor `VEDT54_SERI-NUMARASI.pdf`, masaüstü klasörü `VEDT54`.
- Verisi dahil hazır yapay zekâ yorumlama alıntısı; Türkçe PDF/HTML raporu.
- Kendi Windows ISO'nuzdan medya ve imaj oluşturma betikleri; [kullanım kılavuzu](KULLANIM.md).

Doğrulama sonuçları `docs/validation-0.5/acceptance.json` dosyasında kayıtlıdır. Kontrol kapsamını bu dosyadan okuyun; sanal disk testini fiziksel kabul olarak değerlendirmeyin.

## Birleşik imaj kontrolleri

64 MiB sanal SATA ve NVMe hedeflerinde altı aşama geçti; numaralı PDF/HTML raporlarının SHA-256 manifestleri doğrulandı. Bu küçük hedefler Windows için yetersiz olduğundan Windows kurulmadı. Linux → yeniden başlatma → WinPE geçişi, eşleşmeyen iş kimliğinin hedefe yazılmadan reddedilmesiyle doğrulandı. Sanal disk sensör değerleri gerçek donanım sıcaklığı kabulü değildir.

## Windows kabulünün sınırı

Önceki ayrı laboratuvarda `test` hesabıyla çevrimdışı ilk oturum, rapor kopyası ve duvar kâğıdı doğrulandı; o denemede Linux tam kapasite testi yapılmadı. AppXSvc/Windows uygulama hazırlığı çökme uyarıları çözümlenmedi. Yeni VEDT hesapları ve rapor yolları kod kontrollerinden geçti; en az 64 GiB tam disk testi → yeni Windows ilk oturumu zincirinin kabulü yapılmadı.

## Kalan işler

- Yeni numaralı hesaplarla tam kurulum, ilk oturum ve iki rapor nüshasının uçtan uca kabulü.
- Birden fazla hedefin bağımsız Windows açılışının kabulü.
- Fiziksel SATA/NVMe, güç kesintisi, sürücü/donanım uygunluğu ve Secure Boot kabulü.
- Windows uygulama hizmeti uyarılarının kök neden incelemesi.
- Herkese açık ikili dağıtım öncesi lisans/kaynak envanteri ve Windows yeniden dağıtım izni.

ATTO dahil değildir. Windows lisansı/etkinleştirme VEDT tarafından sağlanmaz. Windows içeren dosya GitHub'a herkese açık yüklenmedi; kaynak ve kendi medyanızla oluşturma yönergeleri yayımlanır.

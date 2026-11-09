# VEDT 0.7 — koyu grafik ekran ve süreler

0.7, onaylanan lacivert temayı çalışan test ekranına uygular. Testin kapsamı değişmez: aynı altı aşama, tam kapasite yazma, SHA-256 ve iki tam okuma korunur.

[Tüm sürüm ve güncelleme paketleri — Google Drive arşivi](https://drive.google.com/drive/folders/1jhm70ZRFvDzygHyTDAkBl_MCeJ69FVtC?usp=sharing)

## Mevcut USB'yi güncelleme

0.7 paketi arşive eklendiğinde `VEDT-0.7-USB-GUNCELLEME.zip` dosyasını bilgisayara indirin ve tamamen çıkartın. `GUNCELLE.cmd` dosyasını çalıştırın; DTLIVE bölümünün harfini seçip doğru USB gösterildiğinde `EVET` yazın. Disk bilgilerini okuma yetkisi hatası çıkarsa Yönetici olarak çalıştır seçeneğini kullanın. Güncelleme sırasında gücü kesmeyin veya USB'yi çıkarmayın. Tam imajı yeniden yazmak gerekmez.

Paket doğrulanmış 0.5 ve 0.6 USB'lerini destekler. Test yazılımı, grafik açılış ayarı ve bunların SHA-256 listesi güncellenir. Önceki yazılım, açılış ayarı ve özet listesi bilgisayarın Belgeler/`VEDT-USB-Yedekleri` klasörüne yedeklenir. Kopyalama hatasında eski dosyalar geri yüklenir. Tamamen güncel USB'ye tekrar uygulanırsa yeniden kopyalama yapılmaz. Yarım kalmış ve tanınan dosyalardan oluşan bir güncelleme tekrar uygulanarak tamamlanabilir; tanınmayan/bozuk dosyada otomatik yazma yapılmaz.

**DTREPORTS raporları, VEDT numaratörü ve Windows kurulum dosyaları değiştirilmez.** Bilgisayarda paketin açılması ve yaklaşık 1 GB yazılım yedeği için yeterli alan bulunmalıdır. USB'yi Windows'un güvenli çıkarma işlemiyle çıkarın.

## Yeni görünüm

- Desteklenen ekranda 1920×1080 tercih edilir; daha düşük desteklenen çözünürlükte düzen ekrana oranlanır.
- Lacivert zemin, beyaz yazı ve ölçülü mavi vurgular kullanılır. Tamamlanan aşamalar yeşil, hata kırmızı, bekleyenler gridir.
- Altı aşama ilk andan itibaren listelenir. Henüz çalışmamış aşama başarılı gibi gösterilmez.
- Aktif aşamanın geçen süresi ve tahmini kalanı ayrı; bu diskteki altı aşamanın toplam geçen süresi ve tahmini kalanı ayrı gösterilir.
- Ana alan ve sondaki küçük parça aynı mantıksal aşamadır; son parçaya geçerken aşama saati sıfırlanmaz.
- Grafik ekran desteklenmezse büyük yazılı metin görünümü kullanılır. Görüntü hatası disk testinin yerine geçmez veya onu başarısız saydırmaz. Ctrl+C ile durdurma korunur.

## Süre tahminini okuma

**Toplam, yalnız o anda test edilen diskin altı aşamasını ifade eder.** Diğer diskler ve Windows kurulumu dahil değildir. Toplam geçen süre, başlangıç/SMART/boşta gözlem süresini de içerir.

İlk ölçümler yeterli değilse kalan süre `Ölçülüyor` olarak görünür. Kısa başlangıç okumasının hızı bütün diske doğrudan genellenmez. Tam geçişlerden yeterli veri geldikten sonra yakın dönem hızı kullanılır; henüz ölçülmemiş okuma/yazma türleri için tahmin geçicidir. Önbellek, sıcaklık ve disk hızı değişince süre tahmini de değişir. İlerleme, aşama sayısına eşit paylar verilerek değil, planlanan I/O baytları üzerinden hesaplanır; bu yüzden uzun tam kapasite geçişleri belirleyicidir.

Tahmini süre sağlık ölçümü veya bitiş garantisi değildir. Başarısız/iptal edilen testte sıfır kalan süreyle tamamlanmış izlenimi verilmez. Son SMART kontrolleri bitmeden genel sonuç üretilmez.

## Kontrol kapsamı

169 Windows kaynak testi geçti, Linux'a özel 7 test atlandı. Linux'ta yeni normal dosyalarda gerçek fio ve ilerleme hesaplarıyla 13 kontrol geçti. USB güncelleyicisi normal dosyalarda başarı, vazgeçme, bozuk paket, kök veya açılış ayarı kopya hatasında geri alma, tanınmayan açılış dosyası, yarım güncelleme onarımı ve tekrar uygulama kontrollerinden geçti. Bunlar fiziksel USB/donanım kabulü değildir.

Sürümün gerçek sanal açılış ve rapor doğrulama kapsamı [doğrulama kaydında](validation-0.7/acceptance.json) belirtilir. Windows ilk oturumu, AppXSvc, fiziksel donanım ve Secure Boot için önceki kabul sınırları sürer.

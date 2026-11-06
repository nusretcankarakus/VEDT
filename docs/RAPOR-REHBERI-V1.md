# VEDT rapor okuma kılavuzu — şema 1

0.5 geliştirme kaynaklarının rapor yapısı. Eski raporlarda DiskTest86 adı görülebilir. Önce `version`, `mode`, `status`, `error`, `warnings` ve `full_capacity_verified` alanlarını okuyun. Test gelecekte arıza olmayacağını garanti etmez.

## Genel değerlendirme

PDF/HTML'de genel özet ve sıcaklık özeti önce, teknik ayrıntılar sonra gelir. VEDT numarası USB'deki test kayıt numarasıdır; gerçek müşteri kimliği veya bütün servislerde tekil bir numara değildir.

- FAIL / Başarısız: hata kaydedildi; hata türü ve aşama incelenir. Tek başına “disk kesin bozuk” denemez.
- WARNING / Uyarılı: uyarıları okuyun. Fiziksel donanım kabulü eksik geliştirme sürümü de uyarı nedenidir.
- INCOMPLETE / Tamamlanamadı: bütün testler bitmedi; sağlamlık sonucu üretmeyin.
- CANCELLED / İptal: test durduruldu; eksik aşamaları başarılı saymayın.
- PASS / Başarılı: ilgili aşamada hata kaydedilmedi; bütün diskin veya gelecekteki kullanımın garantisi değildir.

`mode=raw-device` ham aygıt akışıdır; sanal mı fiziksel mi olduğunu ayrıca doğrulayın. Dosya demosu fiziksel sağlık testi değildir. Windows laboratuvarı örnek raporu tam kapasite test kanıtı değildir.

## Altı aşama

1. Örnek sıralı okuma: sınırlı alanda okuma/hız ölçümü; bütün diski taramaz.
2. Rastgele okuma: sınırlı sayıda küçük blok erişimi.
3. Tam kapasite yazma: hedefin tamamına doğrulanabilir veri yazar; eski verileri siler.
4. Tam kapasite doğrulama: okunan ve yazılan veriyi karşılaştırır.
5. Karma erişim: okuma/yazma erişimleri; tam disk taramasıyla eş tutulamaz.
6. Son tam kapasite doğrulama: veri tutarlılığı yeniden kontrol edilir.

Tam kapasite iddiası için aşama durumları, işlenen baytlar ve `full_capacity_verified` birlikte incelenir. Uyarıları/SMART'ı atlamayın.

## Hatalar ve SMART

Veri uyuşmazlığı FAIL'dir; ilk saptanan adres/uzunluk gibi ayrıntılar kaydedilir. I/O hatası da başarısızlıktır. Disk, kablo, denetleyici, bağlantı veya bellek etkili olabilir; rapor tek başına kök nedeni kanıtlamaz. İlerlemesizlik/süre aşımı tamamlanamayan test olarak ele alınabilir. Varsayılan ilerlemesizlik eşiği 30 saniyedir; rapor ayarlarını esas alın.

SMART desteklenmiyorsa bilinmiyor olarak kalır; bunu “sağlıklı” diye çevirmeyin. Test öncesi sayaçları ve test sırasındaki artışları ayırın. Eski hata sayacı yeni oluşan hata demek değildir. Olumlu SMART sonucu veri doğrulama testinin yerine geçmez.

## Sıcaklık ve hız

Boşta, yük altında, bütün test ve aşamalara göre ortalama/minimum/maksimum ve geçerli örnek sayıları verilir. Ortalama sensör örneklerinin aritmetik ortalamasıdır; sürekli veya zamana göre ağırlıklı ölçüm varsaymayın. Sensör yoksa veri üretmeyin. Sanal/sentetik sensör verisi fiziksel sıcaklık kanıtı değildir.

Varsayılan sıcaklık durdurma eşiği 70 °C'dir; gerçek ayarı rapordan okuyun. Sıcaklık nedeniyle durma kesin disk arızası kanıtı değildir; soğutma/ortam ve modelin üretici sınırları ayrıca değerlendirilir.

Hızlar MiB/sn'dir (1 MiB = 1.048.576 bayt). HDD/SATA SSD/NVMe aynı beklentiyle karşılaştırılmaz. Önbellek dolması, bağlantı, termal kısma ve sanal makine yükü etkilidir. Düşük hız tek başına otomatik FAIL nedeni değildir.

## Dosyalar ve Windows

`session.json` ayrıntıları, PDF/HTML okunabilir raporu, `manifest.json` SHA-256 dosya özetlerini taşır. Manifest kazara değişikliği saptar; dijital imza veya bağımsız gerçeklik kanıtı değildir. Zamanları saat dilimiyle değerlendirin; JSON'da UTC olabilir.

Test başarısı Windows'un kurulduğu, ilk oturumun açıldığı veya hedef rapor kopyasının oluştuğu anlamına gelmez. Bu adımlar ayrı doğrulanır. Birleşik Linux → Windows USB zinciri ve Secure Boot kabulü henüz tamamlanmadı.

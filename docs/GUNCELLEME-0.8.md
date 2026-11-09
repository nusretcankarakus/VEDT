# VEDT 0.8 — Grafikler, sağlık karşılaştırması ve rapor arşivi

## Mevcut USB’yi güncelleme

0.5, 0.6 veya 0.7 USB’den doğrudan güncellenebilir. `VEDT-0.8-USB-GUNCELLEME.zip` dosyasını bilgisayarınıza çıkarın; USB’yi takıp `GUNCELLE.cmd` dosyasını çalıştırın. DTLIVE bölümünün harfini seçin ve `EVET` yazın. Raporlar, numaratör ve Windows dosyaları korunur. Rufus ile yeniden yazılmaz. Eski yazılım bilgisayarda `Belgeler/VEDT-USB-Yedekleri` altında yedeklenir.

## Eklenenler

- PDF ve HTML raporlarında test boyunca disk hızı ve sıcaklık grafikleri. Grafik PNG’leri de aynı rapor klasöründe bulunur ve dosya özetine dahildir; raporu taşırken klasörün tamamını kopyalayın.
- Hız grafiğinde sık örneklenmiş kayıtlarda en az 5 saniyelik sıfır tamamlanan I/O dizileri kırmızıyla işaretlenir. Bu tek başına donanım arızası anlamına gelmez. Ölçüm boşlukları bağlanmaz; uzun testte hız örnekleri başlangıç korunarak seyreltilir. Çok kısa olaylar kayıtlarda görünmeyebilir.
- SMART önce / sonra / değişim / yorum tablosu. NVMe ortam hataları ve kritik uyarı maskesi; SATA yeniden eşleme, bekleyen/düzeltilemeyen sektör, zaman aşımı ve CRC sayaçları desteklendiği ölçüde gösterilir. Ham ATA değerleri üreticiye özgü olabilir. Eksik değer sıfır sayılmaz.
- Windows için disk testi kapısı: altı başarılı aşama, tam kapasite/bayt kapsamı, hata olmaması, başlangıç ve bitişte başarılı ve okunabilmiş SMART gerekir. İzlenen sayaç değişimi, kritik mevcut hata veya belirsiz SMART otomatik kurulumu engeller. Genel geliştirme sürümü uyarısı tek başına engellemez. Nedenler raporda ve hazırlık planında yazılır.
- Eski yarım Windows işi sürdürülmeden önce Linux tarafında güncel kural ve rapor bütünlüğü yeniden doğrulanır. Bu güncelleme mevcut Windows WIM’ini değiştirmez. Yeni oluşturulacak Windows medyasında WinPE de aynı sağlık kuralını tekrar kontrol eder.
- USB’nin rapor bölümünde `reports/index.html`: önceki işler dahil müşteri/test numarası, seri numarası, model, UTC tarih ve sonuç listesi; çevrimdışı arama ve sonuç filtresi. Eski raporların içerikleri değiştirilmez; yeni grafikler yalnız yeni testlerde oluşur.
- Raporda destekleniyorsa SATA etkin/en yüksek bağlantı hızı ve en yakın PCIe denetleyicisinin etkin/en yüksek hız ve hat sayısı. Bağlantı hızı gerçek aktarım hızı değildir; köprü/RAID ve güç yönetimi yorumu etkileyebilir. Eksik bilgi açıkça belirtilir.
- Genel özetin altında test kapsamı ve sınırları açıklanır. Yapay zekâ alıntısı bağlantı ve kurulum kararını da içerir.

Grafikler rapor içindir; test esnasındaki 0.7 koyu panel ve süre göstergeleri korunur. Tam kapasite yazma ve iki tam okuma doğrulaması değişmez.

## Sınırlar

Windows için uygun sonucu yalnız disk testi kapısını geçmeyi ifade eder; Windows kurulmuş veya ilk oturum tamamlanmış demek değildir. Önceki Windows AppXSvc, fiziksel donanım ve Secure Boot kabul sınırları sürer. Güncelleme paketi yerel hazırlanır; Drive’a ayrıca yüklenmelidir.

## Veri kaynakları

SATA JSON alanları smartmontools’un [resmî kaynak koduna](https://github.com/smartmontools/smartmontools/blob/main/src/ataprint.cpp), PCIe bağlantı alanları Linux’un [resmî sysfs kaynağına](https://github.com/torvalds/linux/blob/master/drivers/pci/pci-sysfs.c) dayanır. Bağlantı ve SMART yalnız okunur; bu özellikler ayrı bir disk yazma işlemi başlatmaz.

## Doğrulama

Windows üzerinde 183 kaynak testi geçti; Linux sysfs/fio kontrolleri dahil 8 test bu platformda atlandı. Linux’ta son sağlık/rapor/handoff kontrollerinde 22 test geçti; Windows’a özgü 3 kontrol atlandı. Aynı I/O akışında yeni geçici dosyalarda dört gerçek fio tam kapasite/son parça/bozulma senaryosu ayrıca geçti. PDF grafik ve SMART sayfaları görsel olarak incelendi. [Ayrıntılı kabul kaydı](validation-0.8/acceptance.json).

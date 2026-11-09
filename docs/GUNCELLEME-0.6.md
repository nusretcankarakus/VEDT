# VEDT 0.6 güncellemesi

Bu sürüm, yarım kalan testten sonra kullanıcı onayıyla baştan test başlatmayı ve tam kapasiteyi azaltmadan daha büyük I/O işlemlerini ekler.

**[Tüm sürümler ve güncelleme paketleri — Google Drive arşivi](https://drive.google.com/drive/folders/1jhm70ZRFvDzygHyTDAkBl_MCeJ69FVtC?usp=sharing)**

Bu yönerge için klasörden `VEDT-0.6-USB-GUNCELLEME.zip` dosyasını indirin.

## Mevcut USB'yi güncelleme

1. USB'yi Windows çalışan bir bilgisayara takın. ZIP paketini **bilgisayarın içine** tamamen çıkartın; USB'nin üzerine çıkartmayın.
2. Paket içindeki `GUNCELLE.cmd` dosyasını çalıştırın. Disk bilgilerini okuma yetkisi hatası çıkarsa sağ tıklayıp **Yönetici olarak çalıştır** seçin.
3. Listede görünen **DTLIVE** bölümünün sürücü harfini yazın; örneğin `E`. Bu bölümün Windows'ta sürücü harfi yoksa Disk Yönetimi'nden yalnız DTLIVE bölümüne harf atayın. Biçimlendirmeyin.
4. Doğru USB gösterildiğinde `EVET` yazın. Güncelleme sırasında USB'yi çıkarmayın, bilgisayarı kapatmayın.
5. Betik paket ve mevcut yazılımın SHA-256 değerlerini kontrol eder. Eski yazılımı bilgisayarın Belgeler/`VEDT-USB-Yedekleri` klasörüne alır; yeni yazılımı kopyalayıp tekrar doğrular. Hata halinde eski dosyaları geri yüklemeyi dener; yedek silinmez. Bilgisayarda yaklaşık 1 GB boş yedek alanı gerekir.
6. Tamamlandı mesajından sonra Windows'un **Donanımı güvenle kaldır** işlemiyle USB'yi çıkartın.

Bu paket yalnız tanınan 0.5 DTLIVE yazılımını günceller. DTREPORTS içindeki eski raporlar, iş kaydı ve VEDT numaratörü; Windows kurulum dosyaları korunur. Yanlış sürücü, farklı kaynak özeti veya bozuk paket varsa yazma yapılmaz. Paket bilgisayarı test etmez veya dahili diski silmez.

## Yarım testi baştan başlatma

Güncellenmiş USB ile açın. Eski iş bulunduğunda hedef disklerin listesi gösterilir:

- `R` + Enter: yeniden başlatmayı seçer.
- Ardından `SIL` + Enter: listedeki uygun dahili disklerin tüm verilerinin yeniden silinmesini onaylar.
- `N` + Enter, boş yanıt veya vazgeçme: yeniden silme yapılmaz.

**Bu işlem kaldığı bayttan devam etmez; uygun dahili disklerin tamamını baştan test eder.** Eski raporlar ve numaralar korunur; yeni iş yeni klasöre yazılır. Windows hazırlığı yarım kalmışsa yeniden test seçimi aynı şekilde açık onay gerektirir. USB'nin kendisi test hedefi yapılmaz.

## Süreyi nasıl kısaltıyor?

0.5 sürümü, kapasite büyük bloklara tam bölünmediğinde bütün diskte 4 KiB veya 512 baytlık küçük erişimlere düşebiliyordu. 0.6 sürümü ana alanı 1 MiB sıralı işlemler ve 16 bekleyen istekle işler; sondaki küçük bölümü ayrı ve tam uzunluğuyla sınar. SHA-256 doğrulama aralığı yazma/okuma/karma işlem arasında uyumludur. Son baytlar atlanmaz.

Altı aşama, bir tam kapasite yazma ve iki tam kapasite okuma doğrulaması korunur. Rastgele 4 KiB okuma ölçümü hâlâ QD1'dir. Raporda yöntem ve her aşamanın gerçek bayt sayısı bulunur; ekranda mevcut parçanın tahmini kalan süresi gösterilir. Tahmin hız değiştikçe değişir.

1 TB'yi 90 dakikada yazmak yaklaşık 185 MB/sn'dir. Donanımın sürdürülebilir hızı bu düzeydeyse tam tarama yine saatler sürebilir. Üç tam geçiş aynı hızda yaklaşık 4,5 saat eder; ölçümler, SMART kontrolleri ve Windows kurulumu ayrıca zaman alır. Gerçek 1 TB donanımda 0.6 süre kazancı henüz ölçülmedi; belirli dakika veya hızlanma oranı garanti edilmez.

## Kontrol kapsamı

Kaynak testleri, yeni oluşturulan normal dosyalarda gerçek fio ile tam alan/512 bayt ve 4 KiB son parça denemeleri ve son parçaya kontrollü bozulma eklenince başarısızlık tespiti kontrol edildi. Güncelleyicide başarı, vazgeçme, hatalı özet ve kopya hatasında geri alma yolları yalnız geçici normal dosyalarla sınandı; fiziksel USB kabulü değildir.

Önceki Windows ilk oturum/AppXSvc, fiziksel donanım ve Secure Boot kabulünün tamamlanmamış olması devam eder. Ayrıntılı sürüm doğrulaması `validation-0.6/acceptance.json` dosyasındadır.

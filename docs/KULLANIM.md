# VEDT kullanım kılavuzu

Bu belge birleşik geliştirme imajının kullanım akışını anlatır. İmajın kabul durumunu ve SHA-256 özetini beraberindeki build/validation dosyalarından kontrol edin. Fiziksel donanım kabulü tamamlanmış ürün olarak değerlendirmeyin.

## İndirme

**[VEDT birleşik USB imajını indir — Google Drive](https://drive.google.com/file/d/1NOxrlyXA1J8_HA6QbCUYt4iy1yqf5YO3/view?usp=sharing)**

Geliştirme adayı: `VEDT-combined-0.5-dev.img` · 13.692.305.408 bayt (yaklaşık 13,7 GB). Drive sayfasındaki **İndir** düğmesini kullanın. Bağlantı proje sahibi tarafından sağlanmıştır; Drive dosyasının içeriği ayrıca doğrulanmamıştır. İndirdiğiniz dosyanın SHA-256 değeri aşağıdakiyle eşleşmelidir:

```text
e21151d8259dd80c67dc1b7c5332e55987fec20115166277ab4c1133bd2aa9ff
```

**Uygun dahili disklerin bütün verileri silinir.** Yeni Windows ilk oturumu, fiziksel donanım ve Secure Boot kabulü tamamlanmadı. [USB'ye yazma ve kullanım](KULLANIM.md) · [Doğrulama kaydı](validation-0.5/acceptance.json).

[Kendi medyanızla oluşturma](GELISTIRME.md).

## 1. Başlamadan önce

**Açılış USB'si dışındaki uygun dahili HDD/SSD'lerin bütün verileri silinir.** Önemli verileri yedekleyin; test edilmeyecek dahili diskleri bilgisayardan çıkarın. USB'yi Rufus ile hazırlamak da seçtiğiniz USB'nin içini siler. USB modelini ve kapasitesini dikkatle kontrol edin.

En az 16 GB USB gerekir; 32 GB veya üzeri önerilir. x64 UEFI bilgisayar, Windows 11 Pro'ya uygun donanım ve her Windows hedefi için en az 64 GiB gerekir. Proje Windows lisansı veya etkinleştirme sağlamaz. İnternet çalışma sırasında gerekmez; donanımın yerleşik sürücü desteği gerekir. Secure Boot zinciri bu geliştirme imajı için henüz doğrulanmadı; açıkken başlatılabildiği varsayılmamalıdır.

## 2. İmajı USB'ye yazma

1. Yayımlanan dosyanın tam adı ve SHA-256 değerini kaydedin. Windows PowerShell'de `Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\VEDT-combined-0.5-dev.img'` komutunun çıktısını verilen değerle karşılaştırın. Yol örnektir.
2. Rufus'u açın. **Aygıt** alanında doğru USB'yi seçin.
3. **SEÇ** ile `.img` dosyasını açın. Dosya görünmüyorsa dosya türünü tüm dosyalar yapın.
4. **BAŞLAT** düğmesine basın. ISO/DD seçimi gösterilirse **DD imaj modu** kullanın. İmaj kendi GPT bölüm tablosunu ve dosya sistemlerini içerir; sonradan biçimlendirmeyin. USB'nin kalan kapasitesi ayrılmamış görünebilir.
5. Yazma tamamlanınca USB'yi güvenli çıkarın. Windows bazı bölümleri biçimlendirmeyi önerirse **iptal edin**; VEDT'nin Linux/EFI bölümlerini biçimlendirmeyin.

## 3. Test edilen bilgisayarı başlatma

USB'yi takın ve bilgisayarı USB'nin **UEFI** girdisinden başlatın. USB zaten açılış sıralamasında öndeyse tuşa gerek yoktur. Her bilgisayarın USB'den kendiliğinden açılması garanti değildir; ilk açılışta üreticinin açılış menüsünden USB seçmek veya açılış sırasını önceden ayarlamak gerekebilir. Legacy/CSM bu imajın hedefi değildir.

VEDT uygun dahili diskleri sabit bir listeye alır ve sırayla test eder. Türkçe ekranda aşama, ilerleme, hız ve destekleniyorsa sıcaklık görünür. Seri/model/kapasite kimliği doğrulanamayan veya korunması gereken aygıtlar atlanır. USB dışındaki her aygıtın mutlaka test edileceği varsayılmamalıdır.

Tam kapasite yazma ve iki tam kapasite doğrulama uzun sürebilir. Kapasiteye ve bağlantıya göre saatler sürebilir; beş dakikalık tam disk garantisi yoktur. Gücü kesmeyin. Testi durdurmak için Ctrl+C kullanılabilir; işlem yarım kalırsa otomatik olarak baştan silerek devam etmez.

## 4. Windows aşaması

Başarılı tam test kanıtı ve yeterli kapasitesi olan hedeflere, USB'deki Türkçe Windows 11 Pro imajı ayrı ayrı uygulanır. Başarısız hedefe Windows kurulmaz; bu durumda raporun USB nüshası korunur, hedefte masaüstü kopyası oluşmaz. Hedef kimliği ve USB korunması bölümlemeden hemen önce tekrar denetlenir.

Windows bölümü NTFS'dir. Tek bir görünür Windows bölümü yanında UEFI için FAT32 EFI, Microsoft ayrılmış alanı ve kurtarma bölümü bulunur; bunlar gerekli gizli sistem bölümleridir, ayrı bir kullanıcı rapor bölümü yoktur.

İlk hazırlanmış diskten Windows başlatılır; yerel `VEDT1`, `VEDT2`, … hesabı açılır. E-posta girişi istenmeden geçici test ortamı hazırlanması hedeflenir. Diğer disklere Windows uygulanmış olması, her birinin ilk oturumunun açılıp doğrulandığı anlamına gelmez. Her diskin bağımsız açılışı ayrıca kontrol edilmelidir. Bu hesap kişisel kullanım için hazırlanmış güvenli bir son kullanıcı kurulumu değildir. Kişisel kullanım öncesi diski silerek temiz Windows kurulumu yapın.

## 5. Raporlar

Örnek: oturum `VEDT54`, masaüstü klasörü `VEDT54`, raporlar `VEDT54_SERI-NUMARASI.pdf` ve `VEDT54_SERI-NUMARASI.html`.

USB'nin `DTREPORTS` bölümünde `reports/jobs/<iş-kimliği>/` altında `index.html` bütün disklerin sonucunu gösterir. Her oturumun iç rapor klasöründe numaralı PDF/HTML, `session.json` ve `manifest.json` bulunur. Dosya adında kullanılamayan seri karakterleri değiştirilir, uzun seriler kısaltılır; tam seri rapor içinde korunur. USB ve hedef raporları SHA-256 ile kontrol edilir. Windows ilk oturum sonucu ayrı `windows-first-logon.json` kaydıdır; sağlık test raporu değiştirilmez.

PDF önce genel özeti, sonra teknik ayrıntıları verir. Son bölümdeki **Yapay zekâ ile yorumla — hazır metin** alıntısını kopyalayıp yapıştırabilirsiniz. Alıntı test verisini ve GitHub kılavuzunu içerir. Kopyalamadan önce hata/uyarı metinlerini gözden geçirin. Yapay zekânın bağlantıları açması kullandığınız hizmetin internet erişimine bağlıdır.

## 6. Yeniden başlatma ve hata

USB'deki son iş kaydı, aynı bilgisayar ve aynı disklerle yeniden başlatıldığında yeniden silmeyi engeller; tamamlanan Windows hazırlığına yönlendirir. Son iş tamamlandıysa ve yeni bir dahili disk kimliği görülürse yeni numaralı test başlar. Yarım iş sırasında disk kimlikleri değişirse işlem durur. Yarım kalan bir test/kurulum varsa durur ve inceleme ister. **Hata çözmek için iş kayıtlarını gelişigüzel silmeyin.** Aynı bilgisayarı bilinçli olarak yeniden test etmek ayrı servis işlemi olmalıdır; normal yeniden başlatmayla otomatik yeni test başlatılmaz.

Numaratör USB'ye özeldir ve her disk testi için artar. USB yeniden imajlanırsa kayıtlar/sayaç kaybolur; farklı USB'lerin sayaçları ortak değildir. Raporları ve numaratör kayıtlarını düzenli arşivleyin.

Bir hata durumunda USB raporlarını, `windows-install.json`, komut günlüklerini ve varsa `VEDT-install-error.txt` dosyasını inceleyin. Disk hızının düşük olması tek başına arıza kanıtı değildir. Eksik test, bilinmeyen SMART veya ölçülemeyen sıcaklık “sağlam” diye yorumlanmaz.

[Şema 1 rapor kılavuzu](RAPOR-REHBERI-V1.md) · [Proje](https://github.com/nusretcankarakus/VEDT)


Koruma USB'nin son iş kaydı içindir. USB başka bilgisayarda yeni iş başlattıktan sonra önceki bilgisayarda tekrar USB'den açılması yeni bir test başlatabilir. USB'den her yeni başlatmayı veri silme işlemi olarak değerlendirin.

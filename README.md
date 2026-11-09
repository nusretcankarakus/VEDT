# VEDT — Vektron Elektronik Disk Test

Türkçe arayüz ve raporlarla HDD/SSD testi için geliştirilen açık kaynak teknik servis aracı. Önceki adı DiskTest86 idi; GitHub deposu VEDT olarak yeniden adlandırıldı; dahili `disktest` paket adı uyumluluk için korunuyor.

**Geliştirme sürümüdür. Ham disk testleri hedef diskin bütün verilerini siler.** Otomatik mod, açılış USB'si dışındaki uygun dahili diskleri sırayla seçer. Birleşik geliştirme imajı oluşturuldu; fiziksel donanım kabulü ve yeni Windows akışının tam kurulum kabulü henüz tamamlanmadı.

## 0.6 güncellemesi — 9 Kasım 2026

Yarım kalan işlerde `R` + Enter, ardından `SIL` + Enter ile açık onay vererek baştan test başlatılabilir. Eski raporlar ve numaratör korunur. Tam kapasite yazma, SHA-256 ve iki tam okuma korunarak büyük bloklu sıralı I/O eklendi; son parça ayrıca doğrulanır. [Mevcut USB’yi güncelleme ve süre açıklaması](docs/GUNCELLEME-0.6.md).

**Aşağıdaki Google Drive bağlantısı önceki 0.5 imajınadır; 0.6 düzeltmelerini içermez. Yeni imaj/güncelleme paketinin indirme bağlantısı henüz eklenmedi.**

## USB imajını indir — önceki 0.5

**[VEDT birleşik USB imajını indir — Google Drive](https://drive.google.com/file/d/1NOxrlyXA1J8_HA6QbCUYt4iy1yqf5YO3/view?usp=sharing)**

Geliştirme adayı: `VEDT-combined-0.5-dev.img` · 13.692.305.408 bayt (yaklaşık 13,7 GB). Drive sayfasındaki **İndir** düğmesini kullanın. Bağlantı proje sahibi tarafından sağlanmıştır; Drive dosyasının içeriği ayrıca doğrulanmamıştır. İndirdiğiniz dosyanın SHA-256 değeri aşağıdakiyle eşleşmelidir:

```text
e21151d8259dd80c67dc1b7c5332e55987fec20115166277ab4c1133bd2aa9ff
```

**Uygun dahili disklerin bütün verileri silinir.** Yeni Windows ilk oturumu, fiziksel donanım ve Secure Boot kabulü tamamlanmadı. [USB'ye yazma ve kullanım](docs/KULLANIM.md) · [Doğrulama kaydı](docs/validation-0.5/acceptance.json).

## Mevcut durum — 6 Kasım 2026

- SATA/NVMe kimlik denetimi ve açılış/rapor USB'sini koruma kontrolleri.
- Altı aşama: örnek sıralı okuma, rastgele okuma, tam kapasite yazma, tam kapasite doğrulama, karma erişim ve son tam kapasite doğrulama.
- SMART, desteklenen sensörlerden sıcaklık; boşta/yükte/aşama bazlı ortalama, en düşük ve en yüksek değerler.
- Renkli Türkçe konsol, genel özetin ardından teknik ayrıntılar içeren Türkçe PDF/HTML/JSON, SHA-256 manifesti ve verisi dahil hazır yapay zekâ yorumlama alıntısı.
- VEDT adı, Vektron logosu ve mavi-beyaz duvar kâğıdı/rapor tasarımı.
- USB'de saklanan numaratör: yeni disk testlerinde `VEDT1`, `VEDT2`, …; aynı rapor kimliğine aynı numara. Farklı USB'lerin sayaçları bağımsızdır; bu numara gerçek müşteri kaydı değildir.
- Oturum `VEDT54` ise rapor `VEDT54_SERI-NUMARASI.pdf`, masaüstü klasörü `VEDT54` olur.
- Windows hazırlık kodu: Türkçe Windows 11 Pro, numaralı yerel VEDT hesabı, masaüstüne rapor ve geçici kullanım uyarılı duvar kâğıdı.

**Birleşik akış Linux testlerini WinPE kurulumuna bağlar; üretim kabulü henüz verilmemiştir.** Ayrı QEMU laboratuvarında önceki `test` hesabıyla ilk oturum ve rapor kopyası doğrulandı. Yeni VEDT hesabı/numaratörü kod kontrollerinden geçti; yeni Windows ilk oturum kabulü yapılmadı. Windows laboratuvarında uygulama hizmeti çökme uyarıları da kaydedildi; sorun çözülmüş sayılmıyor.

Son Windows kaynak kontrolü: **151 başarılı, 3 Linux'a özgü test atlandı**. Yeni 0.5 birleşik imajında 64 MiB sanal SATA ve NVMe disklerinde altı aşama doğrulandı; Linux → WinPE geçişi ve geçersiz işin yazmadan reddedilmesi de kontrol edildi. Bunlar fiziksel disk veya son Linux → Windows zinciri kabulü yerine geçmez. ATTO dahil değildir.

## Güvenli dosya demosu

Python 3.11+ ile depo kökünde:

```sh
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -e ".[test]"
python -m disktest demo --reports reports
python -m pytest -q
```

`demo` yeni geçici normal dosya üzerinde çalışır; fiziksel disk sağlığını ölçmez. Ham aygıt/otomatik mod silme yetkisi gerektirir. Üretim bilgisayarında deneme amacıyla otomatik modu başlatmayın.

## Belgeler

- [USB hazırlama ve adım adım kullanım](docs/KULLANIM.md)

- [Türkçe rapor okuma kılavuzu — şema 1](docs/RAPOR-REHBERI-V1.md)
- [Yapay zekâ ile rapor yorumlama](docs/YAPAY-ZEKA-ILE-YORUMLAMA.md)
- [Derleme ve geliştirme](docs/GELISTIRME.md)
- [Kalan işler ve doğrulama sınırları](docs/DURUM.md)

Yapay zekânın bağlantıları kendiliğinden açacağı garanti edilmez. İnternet erişimi olan araca kılavuzu incelemesini isteyin; `session.json` sürümü ve belge bağlantılarını taşır. Paylaşmadan önce seri numarası gibi bilgileri gözden geçirin.

## Açık kaynak

Proje kodu [MIT lisanslıdır](LICENSE). Vektron logosu ve markası bu lisansla lisanslanmaz; haklar hak sahibinde kalır. [Üçüncü taraf notları](THIRD-PARTY-NOTICES.md).

Windows ISO/WIM ve üçüncü taraf ikilileri Git deposuna dahil değildir. Birleşik geliştirme imajı için yukarıdaki harici Google Drive bağlantısı kullanılır. Windows lisansı/etkinleştirme sağlanmaz; Windows ve diğer bileşenlerin kendi lisans koşulları geçerlidir.

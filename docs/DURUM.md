# Geliştirme durumu — 6 Kasım 2026

Kaynak: 0.5.0.dev0. VEDT marka değişikliği ve numaratör eklendi. Windows kaynak kontrolü: 144 başarılı, 3 Linux testi atlandı. Bu sayı donanım test sayısı değildir.

Önceki 0.4 Linux imajında 64 MiB sanal SATA/NVMe üzerinde altı aşama ve USB raporları doğrulandı. Yeni VEDT kaynakları henüz nihai USB imajına paketlenmedi.

Ayrı Windows laboratuvarında eski `test` hesabıyla çevrimdışı ilk oturum, rapor kopyası ve duvar kâğıdı doğrulandı; o laboratuvarda Linux tam kapasite testi yapılmadı. AppXSvc/Windows uygulama hazırlığı çökme uyarıları çözümlenmedi. VEDT numaralı hesap kod kontrolünden geçti; yeni ilk oturum kabulü yapılmadı.

## Kalan işler

- Linux → WinPE → başarılı hedeflere Windows kurulum zinciri.
- Yeniden başlatmada yeniden silmeyi önleyen kalıcı iş durumu ve kurtarma akışı.
- Numaralı hesaplarla ilk oturum ve iki rapor nüshasının uçtan uca kabulü.
- Nihai Rufus USB imajı, dosya özeti, paket lisans/kaynak envanteri.
- Fiziksel SATA/NVMe, güç kesintisi, donanım uygunluğu ve Secure Boot kabulü.

ATTO dahil değildir. Windows lisansı/etkinleştirme VEDT tarafından sağlanmaz.

# Geliştirme ve derleme

Python 3.11+ ile `python -m pip install -e ".[test]"` ve `python -m pytest -q`.
Paket `disktest86`, modül `disktest`, görünen ad VEDT'dir. Logo paket verisidir; Windows duvar kâğıdı betiğinde de gömülüdür.

## Linux Live

Ayrılmış Debian amd64 sanal makinesinde root olarak:

```sh
apt-get update
apt-get install live-build mtools dosfstools
sh scripts/build-live.sh /var/tmp/vedt-live-build
```

Çıktı dizini önceden var olmamalı. Betik paket kurar ve Live ağacı/ISO oluşturur; Windows eklemez. `scripts/make-usb-image.py` GPT USB dosyası üretir; vmtest bağımlılıkları ve mtools gerekir. `--help` çıktısını inceleyin. Otomatik imaj hedefleri siler; fiziksel aygıtları derleme VM'sine aktarmayın. Önce sahipli sanal disklerde deneyin.

`windows/lab_install.py` sabit kimlikli QEMU laboratuvarı içindir, genel kurulum değildir. Korumalarını kaldırmayın. `windows/handoff.py` test kanıtını ve medya/hedef ayrımını kontrol eden ön doğrulamadır. Genel Linux → Windows birleştirmesi henüz tamamlanmadı.

Windows ISO/WIM ve derleme anahtarlarını depoya eklemeyin. İmaj dağıtımı için paket lisansları, kaynak sağlama yükümlülükleri ve Windows dağıtım koşulları ayrıca değerlendirilmelidir.


## Kendi Windows ISO'nuzla birleşik imaj

Windows dosyaları depodan indirilmez. Microsoft'tan edindiğiniz Türkçe Windows 11 Pro x64 ISO, resmî CPython x64 gömülü dağıtımının çıkarılmış klasörü ve wimlib-imagex gerekir. Kaynakları ve sağlama toplamlarını kendi resmî dağıtımlarından doğrulayın.

Windows üzerinde VEDT depo kökünde (yollar örnektir):

```powershell
python -m pip install -e ".[vmtest]"
python scripts/prepare-windows-media.py "D:/Windows11-tr.iso" "D:/tools/python-embed" "D:/tools/wimlib-imagex.exe" "D:/vedt-media"
```

Betik Professional/tr-TR/amd64 indeksini metadata üzerinden seçer; index 4 olduğunu körlemesine varsaymaz. `sources/install.wim` içeren medya desteklenir; ESD/split-WIM bu akışta desteklenmez. WinPE başlangıç imajının Setup index 2 olması beklenir. ISO dosyası değiştirilmez.

Ayrılmış Linux derleyicide Live dosya ağacı ve hazırlanan yerel Windows dosyalarıyla, root olarak:

```sh
apt-get install mtools dosfstools ntfs-3g util-linux
python -m pip install -e ".[vmtest]"
python scripts/make-combined-image.py /build/live/binary /build/vedt-media/winpe /build/vedt-media/media/install.wim /build/vedt-media/windows-media.json /build/VEDT-combined-0.6-dev.img
```

Betik yalnız yeni düzenli imaj dosyası oluşturur. NTFS biçimleme için sadece bu dosyanın payload aralığına bağlı, backing dosyası kontrol edilen geçici loop aygıtı kullanır; kullanıcıdan fiziksel hedef yolu almaz. Mevcut imajın üzerine yazmaz. En az 35 GB boş derleme alanı ayırın. Rootfs/WinPE imajları ayrıca doğrulanmalıdır.

`--defer-host-verification` yalnız doğrulamayı ayrı ana bilgisayarda tamamlayan paketleme iş akışı içindir. Bu seçenekle oluşan dosya doğrulanmış sayılmaz; nihai imaj SHA-256, GPT/FAT yapıları ve içindeki WIM'in beklenen SHA-256 özeti doğrulanmadan kullanmayın/dağıtmayın.

Hazırlanan Windows medyası kendi lisans koşullarına tabidir. Bu yönerge Windows içeren imajın herkese açık yeniden dağıtım iznini vermez.

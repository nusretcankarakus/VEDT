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

#!/bin/sh
# Run in a disposable Debian amd64 VM as root. Produces the Live build tree.
# Produces an ISO FILE only; never writes a physical USB drive.
set -eu
if [ "$(uname -s)" != Linux ] || [ "$(id -u)" != 0 ]; then
    echo 'Debian amd64 Linux sanal makinesinde root olarak çalıştırın.' >&2
    exit 2
fi
if [ "$(dpkg --print-architecture)" != amd64 ]; then
    echo 'Yalnızca amd64 derleyici destekleniyor.' >&2
    exit 2
fi
if [ "$#" -ne 1 ]; then
    echo 'Kullanım: sh scripts/build-live.sh /yeni/bos/cikti-klasoru' >&2
    exit 2
fi
command -v lb >/dev/null || { echo 'Önce apt install live-build çalıştırın.' >&2; exit 2; }
src=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
# mkdir without -p deliberately refuses an existing directory.
mkdir -- "$1"
out=$(CDPATH= cd -- "$1" && pwd)
case "$out/" in "$src/"*) echo 'Çıktı kaynak klasörünün dışında olmalı.' >&2; exit 2 ;; esac
cd "$out"
extra_boot="disktest.unattended=1"
if [ "${DISKTEST_AUTOTEST:-0}" = 1 ]; then
    extra_boot="disktest.autotest=1"
fi
lb config --mode debian --distribution trixie --architectures amd64 \
    --debootstrap-options '--include=ca-certificates' \
    --mirror-bootstrap https://deb.debian.org/debian \
    --mirror-chroot https://deb.debian.org/debian \
    --mirror-binary https://deb.debian.org/debian \
    --mirror-chroot-security https://deb.debian.org/debian-security \
    --mirror-binary-security https://deb.debian.org/debian-security \
    --binary-images iso-hybrid --bootloaders grub-efi --debian-installer none \
    --archive-areas 'main non-free-firmware' \
    --bootappend-live "boot=live components locales=tr_TR.UTF-8 keyboard-layouts=tr console=tty1 console=ttyS0,115200 $extra_boot" \
    --apt-recommends false --apt-secure true
mkdir -p config/package-lists config/includes.chroot/opt/disktest86 \
    config/includes.chroot/etc/systemd/system/multi-user.target.wants \
    config/includes.chroot/etc/default
mkdir -p config/includes.binary/boot/grub
cp "$src/live/grub-config.cfg" config/includes.binary/boot/grub/config.cfg
cat > config/package-lists/disktest.list.chroot <<'EOF'
linux-image-amd64
live-boot
live-config
systemd-sysv
python3
python3-reportlab
python3-pil
fio
smartmontools
grub-common
fonts-dejavu-core
console-setup
kbd
locales
ca-certificates
EOF
tar -C "$src" --exclude='__pycache__' --exclude='*.pyc' -cf - disktest live | tar -C config/includes.chroot/opt/disktest86 -xf -
cp "$src/live/disktest.service" config/includes.chroot/etc/systemd/system/
ln -s ../disktest.service config/includes.chroot/etc/systemd/system/multi-user.target.wants/disktest.service
printf 'CHARMAP="UTF-8"\nCODESET="Uni2"\nFONTFACE="Terminus"\nFONTSIZE="16"\n' > config/includes.chroot/etc/default/console-setup
lb build
sha256sum live-image-amd64.hybrid.iso > live-image-amd64.hybrid.iso.sha256
echo "ISO dosyası: $out/live-image-amd64.hybrid.iso"

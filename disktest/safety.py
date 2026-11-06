"""Pure identity rules, supplemented by Linux ownership checks in device.py."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Identity:
    serial: str
    model: str
    size_bytes: int
    wwn: str


@dataclass(frozen=True)
class Authorization:
    target: Identity
    allow_destroy: bool = False


def validate_identity(auth: Authorization, candidates: list[Identity], *,
                      protected: list[Identity], in_use: bool, inventory_complete: bool) -> Identity:
    if not inventory_complete:
        raise ValueError("Disk/topoloji keşfi eksik; işlem kilitli.")
    if not auth.allow_destroy:
        raise ValueError("Veri silme yetkisi yok.")
    wanted = auth.target
    if not wanted.serial.strip() or not wanted.model.strip() or wanted.size_bytes <= 0 or not wanted.wwn.strip():
        raise ValueError("Otomatik mod için seri, model, kapasite ve WWN zorunlu.")
    # Matching duplicate serials are ambiguous even if other fields differ.
    same_serial = [c for c in candidates if c.serial.strip() == wanted.serial.strip()]
    if len(same_serial) != 1 or same_serial[0] != wanted:
        raise ValueError("Hedef kimliği eksik, belirsiz veya uyuşmuyor.")
    if any(c.serial == wanted.serial or c.wwn == wanted.wwn for c in protected):
        raise ValueError("Açılış/rapor diski test hedefi olamaz.")
    if in_use:
        raise ValueError("Hedef kullanımda; işlem kilitli.")
    return same_serial[0]

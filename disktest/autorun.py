"""Explicit, identity-bound unattended configuration stored on the report USB."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

from .dashboard import Dashboard, clean
from .raw import RawSettings, persistent_reports, run_raw
from .report import write_report
from .safety import Identity


NAME = 'disktest-autorun.json'


def save(reports, settings):
    settings.validate(settings.target.serial)
    if settings.laboratory or settings.inject_corruption:
        raise ValueError('Laboratuvar yapılandırması otomatik moda kaydedilemez.')
    payload = {'schema_version': 1, 'enabled': True,
               'accepted_data_loss_for_serial': settings.target.serial,
               'settings': asdict(settings)}
    path = Path(reports) / NAME
    temporary = path.with_suffix('.json.new')
    # Never overwrite an unrelated leftover file or follow its symlink.
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def load(reports):
    path = Path(reports) / NAME
    if path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError('Otomatik başlatma dosyası geçersiz.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if (set(data) != {'schema_version', 'enabled', 'accepted_data_loss_for_serial', 'settings'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['enabled'] is not True):
        raise ValueError('Otomatik başlatma kaydı etkin veya geçerli değil.')
    values = dict(data['settings'])
    values['target'] = Identity(**values['target'])
    settings = RawSettings(**values)
    settings.validate(data['accepted_data_loss_for_serial'])
    if settings.laboratory or settings.inject_corruption:
        raise ValueError('Otomatik mod laboratuvar/hata enjeksiyonu kabul etmez.')
    return settings


def remove(reports):
    path = Path(reports) / NAME
    path.unlink(missing_ok=True)
    os.sync()


def boot(reports):
    """Called once at boot. Missing record means no disk writes, no selection."""
    path = Path(reports) / NAME
    if not path.exists() and not path.is_symlink():
        return
    try:
        settings = load(reports)
        import reportlab
        persistent_reports(Path(reports))
        # Check topology and current users before the countdown, then let the
        # engine repeat all checks while acquiring its exclusive descriptor.
        from .device import active_users, inventory, select_target, settle
        from .safety import Authorization
        settle()
        active_users(select_target(inventory(), Authorization(settings.target, True)))
        print('\nKAYITLI OTOMATİK TEST — HEDEFİN TÜM VERİLERİ SİLİNECEK')
        print('Model:', clean(settings.target.model), '| Seri:', clean(settings.target.serial))
        print('İptal için 10 saniye içinde Enter tuşuna basın.', flush=True)
        if not sys.stdin.isatty():
            raise ValueError('Yerel konsol yok; otomatik test başlatılmadı.')
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([sys.stdin], [], [], max(0, min(1, deadline - time.monotonic())))[0]:
                sys.stdin.readline()
                print('Bu açılış için otomatik test iptal edildi.')
                return
        dashboard = Dashboard(settings.target, laboratory=False)
        session = run_raw(settings, settings.target.serial, Path(reports), dashboard,
                          accept_data_loss=True)
        dashboard.finish(session, write_report(session, Path(reports)))
    except KeyboardInterrupt:
        print('\nOtomatik başlatma iptal edildi.')
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print('Otomatik test başlatılamadı:', clean(exc))

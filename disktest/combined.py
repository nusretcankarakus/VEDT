"""Persistent Linux/WinPE handoff. Never repeat a started destructive job."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import uuid


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.new')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    os.sync()


def machine_id():
    value = Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()
    result = str(uuid.UUID(value))
    if result in {'00000000-0000-0000-0000-000000000000', 'ffffffff-ffff-ffff-ffff-ffffffffffff'}:
        raise ValueError('Bilgisayar kimliği doğrulanamadı.')
    return result


def next_boot(stage, esp_uuid=None):
    if stage not in {'winpe', 'windows'}:
        raise ValueError('Geçersiz açılış aşaması.')
    if stage == 'windows' and not re.fullmatch('[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}', esp_uuid or ''):
        raise ValueError('Windows EFI bölüm kimliği geçersiz.')
    medium = Path('/run/live/medium')
    env = medium / 'boot/grub/grubenv'
    if not env.is_file() or env.stat().st_size != 1024:
        raise ValueError('Tek seferlik açılış kaydı eksik.')
    subprocess.run(['mount', '-o', 'remount,rw', str(medium)], check=True)
    try:
        values = ['next_stage=' + stage]
        if esp_uuid:
            values.append('target_uuid=' + esp_uuid)
        subprocess.run(['grub-editenv', str(env), 'set', *values], check=True)
        subprocess.run(['sync'], check=True)
    finally:
        subprocess.run(['mount', '-o', 'remount,ro', str(medium)], check=True)
    print('VEDT: sonraki aşamaya geçiliyor: ' + stage, flush=True)
    subprocess.run(['systemctl', 'reboot'], check=True)



def current_targets():
    from dataclasses import asdict
    from .batch import plan
    from .device import inventory, settle
    settle()
    queue, _ = plan(inventory())
    return [asdict(target) for target in queue]


def target_change(active, current, windows_complete):
    previous = active.get('target_identities')
    if previous is None or previous == current:
        return False
    encode = lambda rows: {json.dumps(row, sort_keys=True) for row in rows}
    new_devices = encode(current) - encode(previous)
    completed = windows_complete or (active.get('phase') == 'finished-no-windows' and active.get('batch_complete') is True)
    if completed and new_devices:
        return True
    raise ValueError('Hedef diskler önceki işten farklı; yarım işi yeniden silerek sürdürme engellendi.')


def request_restart(reports, active, targets, read=None):
    """Explicit local opt-in only; keep all old jobs and number reservations."""
    if read is None:
        if not sys.stdin.isatty():
            return False
        read = input
    print('\033[1;33mÖnceki iş tamamlanmadı. Eski kayıtlar korunuyor.\033[0m', flush=True)
    print('R + Enter: bütün uygun dahili diskleri BAŞTAN test et. N + Enter: dur.', flush=True)
    for target in targets:
        print(f"  {target['serial']} | {target['model']} | {target['size_bytes'] / 10**9:.1f} GB", flush=True)
    try:
        if read('Seçim [N]: ').strip().upper() != 'R':
            return False
        if read('Bu disklerdeki TÜM VERİLER yeniden silinecek. Onay için SIL yazın: ').strip().upper() != 'SIL':
            return False
    except (EOFError, KeyboardInterrupt):
        return False
    if not targets:
        raise ValueError('Yeniden başlatılacak uygun dahili disk yok.')
    job = Path(reports) / 'jobs' / active['job_id']
    job.mkdir(parents=True, exist_ok=True)
    save(job / ('yeniden-baslatma-' + secrets.token_hex(6) + '.json'),
         {'previous_job': active, 'new_targets': targets, 'decision': 'operator-confirmed-retest-all'})
    return True


def run(reports):
    reports = Path(reports)
    root = reports.parent
    marker = root / 'VEDT-MEDIA.json'
    if not marker.is_file():
        return False
    media = json.loads(marker.read_text())
    if media.get('schema_version') != 1 or media.get('role') != 'reports' or not re.fullmatch('[0-9a-f]{32}', media.get('media_id', '')):
        raise ValueError('Birleşik USB kimliği geçersiz.')
    computer = machine_id()
    active_path = root / 'VEDT-ACTIVE.json'
    active = json.loads(active_path.read_text()) if active_path.exists() else None
    if active and active.get('machine_uuid') == computer:
        if active.get('media_id') != media['media_id'] or not re.fullmatch('[0-9a-f]{24}', active.get('job_id', '')):
            raise ValueError('Kalıcı iş kimliği geçersiz.')
        job = reports / 'jobs' / active['job_id']
        journal_path = job / 'windows-install.json'
        windows_complete = False
        completed = []
        if journal_path.is_file():
            journal = json.loads(journal_path.read_text(encoding='utf-8-sig'))
            completed = journal.get('targets', [])
            windows_complete = journal.get('complete') is True and bool(completed) and all(t.get('phase') == 'complete' for t in completed)
        targets = current_targets() if active.get('target_identities') is not None or active.get('phase') == 'testing' else []
        try:
            changed = target_change(active, targets, windows_complete) if active.get('target_identities') is not None else False
        except ValueError:
            if not request_restart(reports, active, targets):
                raise
            changed = True
        if changed:
            active = None
        elif windows_complete:
            next_boot('windows', completed[0]['esp_uuid'])
            return True
        elif active.get('phase') == 'windows-ready':
            if journal_path.is_file():
                if not request_restart(reports, active, targets):
                    print('Yarım Windows işi korunuyor; yeniden silme yapılmadı.', flush=True)
                    return True
            else:
                from .deployment import validate_installation_targets
                validate_installation_targets(job)
                next_boot('winpe')
                return True
        elif active.get('phase') == 'finished-no-windows':
            if not request_restart(reports, active, targets):
                print('Son iş kaydı korundu; yeniden silme yapılmadı. USB raporlarını inceleyin.', flush=True)
                return True
        elif active is not None:
            if not request_restart(reports, active, targets):
                raise ValueError('Önceki test yarım kaldı. Otomatik yeniden silme engellendi; yeniden başlatmak için R ve SIL onayını kullanın.')
    job_id = secrets.token_hex(12)
    job = reports / 'jobs' / job_id
    job.mkdir(parents=True)
    active = {'schema_version': 1, 'media_id': media['media_id'], 'machine_uuid': computer,
              'job_id': job_id, 'phase': 'testing', 'target_identities': current_targets()}
    save(active_path, active)
    from .batch import run_batch
    record = run_batch(job, boot_usb_verified=True, numbering_reports=reports)
    active['target_identities'] = record['queue']
    active['batch_complete'] = record.get('complete') is True and not record.get('stopped')
    plan_path = job / 'windows-hazirlik.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if record.get('complete') and plan['targets']:
        plan.update(enabled=True, media_id=media['media_id'], machine_uuid=computer, job_id=job_id)
        plan['note'] = 'Yalnız eşleşen USB ve bilgisayarda doğrulanmış hedeflere Windows hazırlığı.'
        save(plan_path, plan)
        active['phase'] = 'windows-ready'
        save(active_path, active)
        from .deployment import validate_installation_targets
        validate_installation_targets(job)
        next_boot('winpe')
    else:
        active['phase'] = 'finished-no-windows'
        save(active_path, active)
        print('Windows kurulabilecek başarılı hedef yok. USB raporlarını inceleyin.', flush=True)
    return True

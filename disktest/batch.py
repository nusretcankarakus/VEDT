"""Unattended sequential testing of a frozen inventory of internal disks."""
from dataclasses import asdict
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import subprocess

from .naming import report_stem
from .numbering import reserve_account
from .dashboard import Dashboard, clean
from .device import SafetyError, active_users, descendants, identity, inventory, select_target, settle
from .language import status_text
from .raw import RawSettings, persistent_reports, run_raw
from .report import write_report
from .safety import Authorization


def plan(data, physical_paths=None):
    candidates, skipped, seen = [], [], set()
    for root in data.get('blockdevices', []):
        for node in descendants(root):
            path = node.get('path')
            if node.get('type') != 'disk' or path in seen:
                continue
            seen.add(path)
            try:
                if node.get('rm') not in (False, 0) or node.get('tran') not in {'ata', 'sata', 'nvme', 'sas', 'scsi'}:
                    raise SafetyError('USB, çıkarılabilir veya dahili olduğu doğrulanamayan aygıt korunuyor.')
                physical = (physical_paths[path] if physical_paths is not None else
                            str((Path('/sys/dev/block') / node['maj:min']).resolve(strict=True)))
                if not physical.startswith('/sys/devices/pci') or any(p.startswith('usb') for p in physical.split('/')):
                    raise SafetyError('Dahili bağlantı yolu doğrulanamadı; aygıt korunuyor.')
                target = identity(node)
                if target.size_bytes < 64 * 1024**2:
                    raise SafetyError('Hedef kapasitesi desteklenmiyor.')
                select_target(data, Authorization(target, True))
                candidates.append(target)
            except (SafetyError, ValueError, KeyError, OSError) as exc:
                skipped.append({'path': path, 'reason': str(exc)})
    # Duplicate world-wide identities can denote aliases/multipath: fail closed.
    accepted = []
    for target in candidates:
        if sum(other.wwn == target.wwn for other in candidates) != 1:
            skipped.append({'serial': target.serial, 'reason': 'Aynı aygıt kimliği birden fazla hedefte görünüyor.'})
        else:
            accepted.append(target)
    return sorted(accepted, key=lambda t: (t.serial, t.wwn)), skipped


def checkpoint(reports, record):
    temporary = reports / 'toplu-sonuc.json.new'
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, reports / 'toplu-sonuc.json')
    rows = ''.join('<tr><td>' + escape(row['serial']) + '</td><td>' + escape(status_text(row['status'])) +
                   '</td><td><a href="' + escape(row['report'], quote=True) + '/' + escape(row.get('report_file_stem', 'report'), quote=True) + '.html">Raporu aç</a></td><td>' +
                   ('Doğrulandı' if row.get('target_copy', {}).get('verified') else
                    'Windows aşaması bekleniyor' if row.get('windows_eligible_test_result') else 'Windows kurulmayacak') + '</td></tr>'
                   for row in record['results'])
    skipped = ''.join('<li>' + escape(str(r.get('path', r.get('serial', 'Aygıt')))) + ': ' +
                      escape(r['reason']) + '</li>' for r in record['skipped'])
    (reports / 'index.html').write_text('<!doctype html><html lang="tr"><meta charset="utf-8">'
        '<title>VEDT toplu sonuç</title><style>body{font:18px system-ui;background:#0c1e32;color:#e3eef7;padding:30px}'
        'td{padding:12px;border-bottom:1px solid #3b5877}a{color:#51d6f5}h1{color:#73e7a3}</style>'
        '<h1>VEDT — Toplu test sonucu</h1><table><tr><th>Seri numarası</th><th>Test sonucu</th>'
        '<th>USB raporu</th><th>Hedefteki rapor</th></tr>' + rows + '</table><h2>Korunan / atlanan aygıtlar</h2>' +
        '<ul>' + skipped + '</ul></html>', encoding='utf-8')
    os.sync()


def run_batch(reports, *, boot_usb_verified=False, numbering_reports=None):
    if boot_usb_verified is not True:
        raise SafetyError('Kalıcı rapor alanının açılış USB’sinde olduğu doğrulanmalı.')
    import reportlab
    reports = Path(reports)
    persistent_reports(reports)
    for command in ('fio', 'smartctl'):
        import shutil
        if not shutil.which(command):
            raise SafetyError('Gerekli araç bulunamadı: ' + command)
    settle()
    queue, skipped = plan(inventory())
    record = {'started_at': datetime.now(timezone.utc).isoformat(), 'policy': 'all-internal-destroy',
              'queue': [asdict(t) for t in queue], 'skipped': skipped, 'results': [], 'complete': False}
    checkpoint(reports, record)
    for index, target in enumerate(queue, 1):
        print(f'\033[1;97;44m DİSK {index} / {len(queue)} — {clean(target.serial)} \033[0m', flush=True)
        persistent_reports(reports)  # Stop rather than erase without USB report capacity.
        settings = RawSettings(target, allow_destroy=True, laboratory=False, timeout_seconds=604800,
                               mixed_operations=4096, idle_observation_seconds=15)
        screen = Dashboard(target, laboratory=False)
        session = run_raw(settings, target.serial, reports, screen, accept_data_loss=True)
        session['report_copy_plan'] = ('Bu raporun USB nüshası kaydedildi. Hedefte ayrı rapor bölümü oluşturulmaz. '
            'Windows kurulum aşaması hazır olduğunda ikinci nüsha test kullanıcısının masaüstüne bırakılacaktır. '
            'Masaüstü nüshası Windows hazırlığı ve ilk oturum tamamlandıktan sonra kullanılabilir.')
        session['account_name'] = reserve_account(numbering_reports or reports, session['id'])
        directory = write_report(session, reports)
        os.sync()
        row = {'serial': target.serial, 'status': session['status'], 'report': directory.name,
               'full_capacity_verified': session['full_capacity_verified'], 'account_name': session['account_name'], 'report_file_stem': report_stem(session)}
        row['windows_eligible_test_result'] = (session.get('full_capacity_verified') is True and
            not session.get('error') and len(session['stages']) == 6 and
            all(stage['status'] == 'PASS' for stage in session['stages']))
        row['target_copy'] = {'verified': False, 'state': 'windows-pending' if row['windows_eligible_test_result'] else 'not-eligible'}
        record['results'].append(row)
        checkpoint(reports, record)
        screen.finish(session, directory)
        print('\033[33mUSB raporu kaydedildi. Windows ve masaüstü nüshası sonraki aşamada hazırlanacak.\033[0m', flush=True)
        if session['status'] == 'CANCELLED' or session.get('worker_may_still_be_running'):
            record['stopped'] = True
            break
    record['complete'] = len(record['results']) == len(queue)
    from .deployment import prepare_plan
    prepare_plan(reports, record)
    checkpoint(reports, record)
    print('\033[1;36mTOPLU TEST BİTTİ — USB’de index.html dosyasından bütün raporları açabilirsiniz.\033[0m' if queue else
          '\033[1;33mTeste uygun dahili disk bulunamadı; hiçbir diske test uygulanmadı.\033[0m')
    return record

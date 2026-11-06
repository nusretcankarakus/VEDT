"""Interactive destructive-test workflow. No target is selected implicitly."""
from pathlib import Path

from .dashboard import Dashboard, clean
from .device import (SafetyError, active_users, descendants, identity, inventory,
                     select_target, settle)
from .raw import RawSettings, run_raw
from .report import write_report
from .safety import Authorization


def choose_and_run(reports: Path, *, read=input, write=print):
    # Establish report storage before discovering protected mount ancestry.
    from .raw import persistent_reports
    persistent_reports(reports)
    import reportlab  # Require PDF support before any destructive work.
    settle()
    data = inventory()
    candidates = []
    seen = set()
    write('\nDisk seçimi — seçilen diskin TÜM verileri silinecek.')
    for root in data.get('blockdevices', []):
        for node in descendants(root):
            if node.get('type') != 'disk' or node.get('path') in seen:
                continue
            seen.add(node.get('path'))
            try:
                target = identity(node)
                selected = select_target(data, Authorization(target, True))
                active_users(selected)
            except (SafetyError, ValueError, OSError) as exc:
                write(f"KİLİTLİ {clean(node.get('path'))}: {clean(exc)}")
                continue
            candidates.append(target)
            write(f'{len(candidates)}. {clean(target.model)} | Seri: {clean(target.serial)} | '
                  f'{target.size_bytes / 1024**3:.2f} GiB | WWN: {clean(target.wwn)}')
    if not candidates:
        write('Teste uygun disk bulunamadı.')
        return
    choice = read('Disk numarası (iptal için Enter): ').strip()
    if not choice:
        return
    if not choice.isdecimal() or not 1 <= int(choice) <= len(candidates):
        write('Geçersiz seçim; test başlatılmadı.')
        return
    target = candidates[int(choice) - 1]
    write(f'HEDEF: {clean(target.model)} / {clean(target.serial)} / {target.size_bytes} bayt')
    write('Bu işlem bölümler dahil tüm verileri geri alınamaz biçimde siler.')
    write('Bu geliştirme sürümünün fiziksel donanım kabulü tamamlanmadı.')
    required = 'SİL ' + target.serial
    if read(f'Onaylamak için tam olarak "{clean(required)}" yazın: ') != required:
        write('Onay eşleşmedi; test başlatılmadı.')
        return
    settings = RawSettings(target, allow_destroy=True, laboratory=False,
                           timeout_seconds=604800, mixed_operations=4096)
    write('İsteğe bağlı: aynı diski sonraki USB açılışlarında da otomatik test et.')
    write('Bu seçenek her açılışta hedef diskin verilerini yeniden siler.')
    if read('Etkinleştirmek için OTOMATİK yazın; yalnız bu test için Enter: ') == 'OTOMATİK':
        from .autorun import save
        save(reports, settings)
        write('Otomatik test kaydedildi. Ana menüde 6 ile kaldırabilirsiniz.')
    else:
        from .autorun import remove
        remove(reports)
        write('Yalnız bu test çalışacak; varsa önceki otomatik test kaydı kaldırıldı.')
    dashboard = Dashboard(target, laboratory=False)
    session = run_raw(settings, target.serial, reports, dashboard, accept_data_loss=True)
    directory = write_report(session, reports)
    dashboard.finish(session, directory)

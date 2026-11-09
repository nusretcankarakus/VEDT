"""Navy graphical screen with a readable terminal fallback."""
from __future__ import annotations
import os
import shutil
import sys
import time
from .language import status_text, error_text
from .progress import Progress, STAGES, duration

_latest = None


def clean(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


class Dashboard:
    def __init__(self, target, stream=None, *, laboratory=True, keep_result=False):
        self.target = target
        self.laboratory = laboratory
        self.keep_result = keep_result
        self.stream = stream if stream is not None else sys.stdout
        self.terminal = self.stream.isatty()
        self.last = None
        self.last_paint = -1e30
        self.display = self.renderer = None
        self.graphics_attempted = False
        global _latest
        if _latest is not None:
            _latest.close()
        _latest = self

    def color(self, text, code):
        return f'\x1b[{code}m{text}\x1b[0m' if self.terminal else text

    def close(self):
        if self.display is not None:
            self.display.close()
            self.display = None

    def __call__(self, row):
        self.last = row
        now = time.monotonic()
        if row.get('event_kind') == 'update' and now-self.last_paint < 1:
            return
        self.last_paint = now
        if not self.graphics_attempted:
            self.graphics_attempted = True
            if self.terminal and sys.platform == 'linux' and os.environ.get('VEDT_FRAMEBUFFER') == '1':
                try:
                    from .graphics import PanelRenderer
                    from .framebuffer import Framebuffer
                    self.renderer = PanelRenderer(self.target, laboratory=self.laboratory)
                    self.display = Framebuffer()
                except Exception:
                    self.close()
        if self.display is not None:
            try:
                self.display.present(self.renderer.frame(row))
                return
            except Exception:
                self.close()  # A display failure must not abort the disk worker.
        self._text(row)

    def _text(self, row):
        stage = clean(row.get('stage', 'Başlangıç kontrolleri'))
        percent = row.get('percent')
        progress = f'%{percent:.1f}' if percent is not None else 'Ölçülüyor'
        elapsed = duration(row.get('elapsed_seconds', 0))
        stage_time = duration(row.get('stage_elapsed_seconds', 0))
        stage_eta = duration(row.get('stage_eta_seconds'))
        total_eta = duration(row.get('overall_eta_seconds'))
        speed = max(0, row.get('mib_per_s') or 0)
        temp = row.get('temperature_c')
        temperature = f'{temp:g} °C' if temp is not None else 'Alınamadı'
        if not self.terminal:
            self.stream.write(f'{elapsed} | {stage} | {progress} | {speed:.2f} MiB/sn | '
                              f'Aşama {stage_time} / kalan {stage_eta} | Toplam kalan {total_eta}\n')
            self.stream.flush()
            return
        size = shutil.get_terminal_size((100, 33))
        width = max(32, min(118, size.columns-1))
        line = lambda value: clean(value)[:width]
        states = row.get('stage_states') or [{'name': name, 'status': 'PENDING'} for name in STAGES]
        labels = {'PENDING':'Bekliyor', 'RUNNING':'Çalışıyor', 'PASS':'Tamamlandı',
                  'FAIL':'Başarısız', 'STOPPED':'Durduruldu'}
        lines = [self.color(line(' VEDT — Vektron Elektronik Disk Test'), '1;97;44'),
                 self.color('─'*width, '34'), line('Model: '+self.target.model),
                 line('Seri no: '+self.target.serial),
                 line(f'Kapasite: {self.target.size_bytes/1024**3:.1f} GiB'), '',
                 self.color(line(stage), '1;37'),
                 self.color(line('['+'█'*int((percent or 0)*.35)+'░'*(35-int((percent or 0)*.35))+'] '+progress), '34'),
                 line(f'Hız: {speed:.1f} MiB/sn    Sıcaklık: {temperature}'), '',
                 line(f'AŞAMA    Geçen: {stage_time}    Tahmini kalan: {stage_eta}'),
                 line(f'6 AŞAMA  Geçen: {elapsed}    Tahmini kalan: {total_eta}'), '',
                 self.color('TEST AŞAMALARI', '1;37')]
        for i, item in enumerate(states):
            status = item['status']
            color = {'PASS':'32','RUNNING':'1;37','FAIL':'31','STOPPED':'33'}.get(status,'90')
            lines.append(self.color(line(f"{i+1:02}  {item['name']} — {labels.get(status,status)}"), color))
        lines += ['', self.color(line('Ctrl+C: durdur · Kalan süreler tahminidir.'), '90')]
        self.stream.write('\x1b[H\x1b[2J'+'\n'.join(lines)+'\n')
        self.stream.flush()

    def finish(self, session, directory):
        tracker = Progress(self.target.size_bytes, session.get('settings',{}).get('mixed_operations',4096))
        rows = session.get('stages',[])
        current = rows[-1]['name'] if rows else None
        state = tracker.snapshot(rows, session.get('elapsed_seconds',0), current,
            rows[-1].get('bytes',0) if rows else 0,
            rows[-1].get('seconds',0) if rows else 0, final_status=session['status'])
        completed = session.get('full_capacity_verified') and not session.get('error') and session['status'] in ('PASS','WARNING')
        if completed:
            state.update(percent=100, overall_percent=100, stage_eta_seconds=0, overall_eta_seconds=0)
        state.update(temperature_c=session.get('temperature_c'), mib_per_s=0,
                     error_message=error_text(session) if session.get('error') else None,
                     event_kind='end')
        self(state)
        if not self.keep_result:
            self.close()
        label = self.color(status_text(session['status']),
                           {'FAIL':'31','WARNING':'33','PASS':'32'}.get(session['status'],'33'))
        self.stream.write(f'\nSonuç: {label}\n')
        if session.get('error'):
            self.stream.write('Hata: '+error_text(session)+'\n')
        self.stream.write('USB raporu: '+clean(directory.resolve())+'\n')
        self.stream.flush()


def wait_for_result():
    """Keep the final panel visible; an already queued Windows reboot still proceeds."""
    screen = _latest
    if screen is None or screen.display is None or not screen.last or not screen.last.get('final_status'):
        return
    try:
        final_image = screen.renderer.frame(screen.last)
        while True:
            screen.display.present(final_image)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        screen.close()

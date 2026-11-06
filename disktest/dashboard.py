"""Color display with Turkish text and plain redirected output."""
from __future__ import annotations
import shutil
import sys
from .language import status_text, error_text


def clean(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


def duration(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


class Dashboard:
    def __init__(self, target, stream=None, *, laboratory=True):
        self.target = target
        self.laboratory = laboratory
        self.stream = stream if stream is not None else sys.stdout
        self.terminal = self.stream.isatty()
        self.stages = []
        self.current_stage = None
        self.last = None

    def color(self, text, code):
        return f'\x1b[{code}m{text}\x1b[0m' if self.terminal else text

    def __call__(self, row):
        self.last = row
        stage = clean(row['stage'])
        if stage != self.current_stage:
            if self.current_stage is not None:
                self.stages.append(self.current_stage)
            self.current_stage = stage
        percent = row.get('percent')
        progress = f'%{percent:.1f}' if percent is not None else 'çalışıyor'
        temperature = row.get('temperature_c')
        temp_text = f'{temperature:g} °C' if temperature is not None else 'bilgi alınamadı'
        speed = max(0, row.get('mib_per_s') or 0)
        elapsed = duration(row.get('elapsed_seconds', 0))
        if not self.terminal:
            self.stream.write(f'{elapsed} | {stage} | {progress} | {speed:.2f} MiB/sn | {temp_text}\n')
            self.stream.flush()
            return
        width = max(40, min(100, shutil.get_terminal_size((80, 24)).columns - 1))
        filled = int(max(0, min(100, percent or 0)) * 35 / 100)
        text = lambda value: clean(value)[:width]
        lines = [self.color(' VEDT — Vektron Elektronik Disk Test  |  ' + ('SANAL DİSK DENEMESİ' if self.laboratory else 'OTOMATİK DİSK TESTİ'), '1;97;44'),
                 self.color('═' * width, '34'), text(f'Model     : {self.target.model}'),
                 text(f'Seri no   : {self.target.serial}'),
                 text(f'Kapasite  : {self.target.size_bytes / 1024**3:.2f} GiB'), '',
                 self.color(text('Aşama     : ' + stage), '1;36'),
                 self.color('[' + '█' * filled + '░' * (35 - filled) + '] ' + progress, '1;36'),
                 self.color(f'Hız       : {speed:.2f} MiB/sn', '36'),
                 self.color(f'Sıcaklık  : {temp_text}', '31;1' if temperature is not None and temperature >= 60 else '33'),
                 f'Geçen süre: {elapsed}', '', self.color('TAMAMLANAN AŞAMALAR', '1;34'),
                 *[self.color(text('  ✓ ' + item), '32') for item in self.stages[-6:]], '',
                 self.color('İşlemler otomatik yürütülüyor. Durdurmak için Ctrl+C.', '33')]
        self.stream.write('\x1b[H\x1b[2J' + '\n'.join(lines) + '\n')
        self.stream.flush()

    def finish(self, session, directory):
        if session.get('full_capacity_verified') and self.last:
            self({**self.last, 'stage': 'Bütün test aşamaları tamamlandı', 'percent': 100,
                  'elapsed_seconds': session.get('elapsed_seconds', 0)})
        status = session['status']
        label = self.color(status_text(status), {'FAIL': '1;97;41', 'WARNING': '1;30;43',
                           'INCOMPLETE': '1;33', 'CANCELLED': '1;33', 'PASS': '1;97;42'}.get(status, '37'))
        self.stream.write(f'\nSonuç: {label}\n')
        if session.get('error'):
            self.stream.write('Hata: ' + error_text(session) + '\n')
        self.stream.write('USB raporu: ' + clean(directory.resolve()) + '\n')
        self.stream.flush()

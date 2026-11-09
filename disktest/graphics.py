"""VEDT navy dashboard. Pure image rendering; no hardware or disk operations."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .progress import duration, STAGES

COLORS = {'bg': '#0B1423', 'card': '#122035', 'line': '#26364B',
          'text': '#EAF0F8', 'muted': '#9AAAC0', 'pending': '#7F8FA6',
          'accent': '#6AA3DE', 'track': '#24364D', 'active': '#1A3554',
          'success': '#65B49B', 'error': '#EE8585', 'warning': '#D5B778'}


def clean(value):
    return ''.join(c if c.isprintable() else ' ' for c in str(value))


class PanelRenderer:
    def __init__(self, target, font_dir=None, laboratory=False):
        self.target = target
        self.laboratory = laboratory
        self.font_dir = Path(font_dir) if font_dir else Path('/usr/share/fonts/truetype/dejavu')
        self.fonts = {}
        self.logo = Image.open(Path(__file__).parent/'assets/vektron-logo.png').convert('RGBA')
        self.logo.thumbnail((110, 98), Image.Resampling.LANCZOS)

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            candidates = [self.font_dir/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'),
                          Path('C:/Windows/Fonts')/('seguisb.ttf' if bold else 'segoeui.ttf')]
            found = next((p for p in candidates if p.is_file()), None)
            self.fonts[key] = (ImageFont.truetype(str(found), size) if found else
                              ImageFont.load_default(size=size))
        return self.fonts[key]

    def frame(self, row):
        c = COLORS
        im = Image.new('RGB', (1920, 1080), c['bg'])
        d = ImageDraw.Draw(im)

        def text(x, y, value, size=26, color=None, bold=False, width=None):
            value = clean(value)
            f = self.font(size, bold)
            if width:
                while value and d.textlength(value, font=f) > width:
                    value = value[:-2] + '…' if len(value) > 2 else ''
            d.text((x, y), value, font=f, fill=color or c['text'])

        def right(x, y, value, size=26, color=None, bold=False):
            value = clean(value)
            text(x-d.textlength(value, font=self.font(size, bold)), y, value, size, color, bold)

        def card(box):
            d.rounded_rectangle(box, radius=16, fill=c['card'], outline=c['line'], width=1)

        def label(x, y, value):
            text(x, y, value, 20, c['muted'], True)

        def bar(x, y, width, height, percent):
            d.rounded_rectangle((x, y, x+width, y+height), radius=height//2, fill=c['track'])
            filled = int(width*max(0, min(100, percent or 0))/100)
            if filled:
                d.rounded_rectangle((x, y, x+filled, y+height), radius=height//2, fill=c['accent'])

        d.rectangle((0, 0, 1920, 126), fill='#102746')
        im.paste(self.logo, (62, 14), self.logo)
        text(194, 12, 'VEDT', 57, '#FFFFFF', True)
        text(197, 79, 'Vektron Elektronik Disk Test', 25, '#C6D4E5')
        d.rounded_rectangle((1422, 36, 1856, 88), radius=26, fill='#1C3D65', outline='#365A82')
        text(1450, 47, 'SANAL DİSK DENEMESİ' if self.laboratory else 'OTOMATİK · TAM KAPASİTE',
             22, '#DAE7F7', True)
        card((64, 150, 1856, 255))
        label(92, 164, 'TEST EDİLEN DİSK')
        text(92, 191, self.target.model, 29, bold=True, width=455)
        text(578, 195, 'Seri no · '+self.target.serial, 24, c['muted'], width=480)
        for x in (1090, 1330, 1570):
            d.line((x, 175, x, 230), fill=c['line'])
        label(1124, 166, 'KAPASİTE')
        text(1124, 197, f'{self.target.size_bytes/1024**3:.1f} GiB', 27, bold=True)
        label(1364, 166, 'DURUM')
        text(1364, 197, 'Test ediliyor' if not row.get('final_status') else 'Test sona erdi', 24)
        label(1604, 166, 'SICAKLIK')
        temp = row.get('temperature_c')
        text(1604, 194, f'{temp:g} °C' if temp is not None else 'Alınamadı', 30,
             c['warning'] if temp is not None and temp >= 60 else c['text'], True)

        index = row.get('stage_index')
        status = row.get('final_status')
        verdict = {'PASS': 'Test tamamlandı', 'WARNING': 'Uyarılı tamamlandı',
                   'FAIL': 'Test başarısız', 'INCOMPLETE': 'Test tamamlanamadı',
                   'CANCELLED': 'Test durduruldu'}
        bad = status in ('FAIL', 'INCOMPLETE', 'CANCELLED')
        active_color = c['error'] if status == 'FAIL' else c['warning'] if status else c['accent']
        card((64, 279, 1176, 559))
        label(96, 299, 'TEST SONUCU' if status else f'AKTİF AŞAMA · {index+1:02} / 06' if index is not None else 'HAZIRLIK VE KONTROLLER')
        title = verdict.get(status, row.get('stage', 'Başlangıç kontrolleri'))
        text(96, 343, title, 34, active_color if status else None, True, width=830)
        detail = row.get('error_message') if bad else ('USB raporu kaydedildi.' if status else
                 'SHA-256 veri bütünlüğü · tam kapasite korunur')
        text(97, 398, detail or 'USB raporunu inceleyin.', 23, c['muted'], width=1048)
        percent = row.get('percent')
        right(1142, 326, f'%{percent:.0f}' if percent is not None else '—', 62, active_color, True)
        bar(96, 444, 1048, 18, percent)
        label(96, 488, 'ANLIK HIZ')
        text(266, 480, f"{max(0,row.get('mib_per_s') or 0):.1f} MiB/sn", 29, bold=True)
        done, expected = row.get('stage_bytes', 0), row.get('stage_expected_bytes', 0)
        if expected:
            right(1142, 485, f'İşlenen {done/10**9:.2f} / {expected/10**9:.2f} GB', 25, c['muted'])

        card((1200, 279, 1856, 559))
        label(1232, 299, 'AKTİF AŞAMANIN SÜRESİ')
        label(1232, 365, 'GEÇEN')
        label(1560, 365, 'TAHMİNİ KALAN')
        text(1232, 398, duration(row.get('stage_elapsed_seconds', 0)), 41, bold=True)
        text(1560, 398, '—' if bad else duration(row.get('stage_eta_seconds')), 41, c['accent'], True)
        d.line((1526, 367, 1526, 458), fill=c['line'])
        text(1232, 497, 'Yalnız şu an çalışan aşamaya aittir.', 22, c['muted'])

        card((64, 583, 1856, 714))
        label(96, 600, 'BU DİSKTE TÜM TEST · 6 AŞAMA')
        overall = row.get('overall_percent', 0)
        text(96, 635, f'Yaklaşık %{overall:.0f}', 30, bold=True)
        bar(330, 656, 558, 12, overall)
        d.line((934, 607, 934, 689), fill=c['line'])
        label(978, 600, 'TOPLAM GEÇEN')
        text(978, 635, duration(row.get('elapsed_seconds', 0)), 38, bold=True)
        label(1414, 600, 'TOPLAM TAHMİNİ KALAN')
        total_eta = '—' if bad else duration(row.get('overall_eta_seconds'))
        text(1414, 635, total_eta, 38, c['accent'], True)

        card((64, 738, 1856, 1022))
        label(96, 755, 'TEST AŞAMALARI')
        label(1382, 755, 'DURUM')
        right(1824, 755, 'AŞAMA SÜRESİ', 20, c['muted'], True)
        states = row.get('stage_states') or [{'name': name, 'status': 'PENDING'} for name in STAGES]
        labels = {'PENDING': 'BEKLİYOR', 'RUNNING': 'ÇALIŞIYOR', 'PASS': 'TAMAMLANDI',
                  'FAIL': 'BAŞARISIZ', 'STOPPED': 'DURDURULDU'}
        for i, item in enumerate(states):
            y = 794+i*34
            state = item['status']
            color = (c['success'] if state == 'PASS' else c['accent'] if state == 'RUNNING'
                     else c['error'] if state == 'FAIL' else c['warning'] if state == 'STOPPED'
                     else c['pending'])
            if state == 'RUNNING':
                d.rounded_rectangle((82, y-1, 1838, y+32), radius=8, fill=c['active'])
            cx, cy = 108, y+16
            if state == 'PASS':
                d.ellipse((cx-9, cy-9, cx+9, cy+9), fill=color)
                d.line((cx-4, cy, cx-1, cy+3, cx+5, cy-4), fill=c['card'], width=2)
            else:
                d.ellipse((cx-8, cy-8, cx+8, cy+8), outline=color, width=2)
                if state == 'RUNNING':
                    d.ellipse((cx-4, cy-4, cx+4, cy+4), fill=color)
                elif state in ('FAIL', 'STOPPED'):
                    text(cx-4, y-1, '!', 20, color, True)
            text(140, y+1, f'{i+1:02}', 23, color, True)
            text(202, y, item['name'], 23, c['pending'] if state == 'PENDING' else c['text'],
                 state == 'RUNNING', width=1145)
            text(1382, y+3, labels.get(state, state), 18, color, True)
            right(1824, y, '—' if state == 'PENDING' else duration(item.get('seconds', 0)),
                  23, c['pending'] if state == 'PENDING' else c['text'])
        text(64, 1039, 'USB raporu kaydedildi · Yeniden başlatmak için Ctrl+Alt+Del' if status else 'Ctrl+C · Testi durdur   |   Kalan süreler ölçülen hızla tahmin edilir.', 21, c['muted'])
        right(1856, 1041, 'VEDT · Türkçe disk testi', 20, c['muted'])
        return im

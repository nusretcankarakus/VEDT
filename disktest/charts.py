"""Offline raster charts shared by HTML and PDF; no fabricated measurements."""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont


def valid(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def points(session, kind):
    source = session.get('telemetry', []) if kind == 'speed' else session.get('temperature_samples', [])
    key = 'mib_per_s' if kind == 'speed' else 'temperature_c'
    return [(float(x['elapsed_seconds']), float(x[key]), x.get('stage') or x.get('phase') or '')
            for x in source if valid(x.get('elapsed_seconds')) and (valid(x.get(key)) if kind == 'speed' else type(x.get(key)) in (int, float) and math.isfinite(x[key]) and -90 <= x[key] <= 200)]


def render_chart(session, kind, path):
    data = points(session, kind)
    image = Image.new('RGB', (1400, 560), '#0b1423'); d = ImageDraw.Draw(image)
    candidates = [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('C:/Windows/Fonts/arial.ttf')]
    font = next((p for p in candidates if p.is_file()), None)
    def text(xy, value, size=23, fill='#dce7f4'):
        d.text(xy, value, font=ImageFont.truetype(str(font), size) if font else ImageFont.load_default(), fill=fill)
    title, unit = ('Disk hızı', 'MiB/sn') if kind == 'speed' else ('Disk sıcaklığı', '°C')
    text((35, 20), title + ' — test boyunca kaydedilen ölçümler', 30)
    left, top, right, bottom = 120, 100, 1350, 435
    max_x = max([1, session.get('elapsed_seconds', 0)] + [p[0] for p in data])
    min_y = min((p[1] for p in data), default=0)-5 if kind == 'temperature' else 0
    max_y = max(min_y+1, max((p[1] for p in data), default=1)*(1.15 if kind=='speed' else 1)+ (5 if kind=='temperature' else 0))
    def xy(t,v):return (left+(right-left)*t/max_x, bottom-(bottom-top)*(v-min_y)/(max_y-min_y))
    for i in range(5):
        y = top+(bottom-top)*i/4;d.line((left,y,right,y),fill='#26364b')
        text((15,y-12),f'{max_y-(max_y-min_y)*i/4:.1f}',20)
    for i in range(6):
        x=left+(right-left)*i/5;text((x-20,bottom+14),f'{max_x*i/5/60:.1f}',20)
    text((20,65),unit,21);text((560,490),'Test başlangıcından itibaren dakika',22)
    if not data:text((250,245),'Geçerli ölçüm yok — sensör / veri desteklenmiyor',27)
    if kind == 'speed':
        for event in pauses(session):
            x1 = xy(event['start_seconds'], min_y)[0]; x2 = xy(event['start_seconds']+event['seconds'], min_y)[0]
            d.rectangle((x1,top,max(x1+3,x2),bottom),fill='#512a35')
    previous = None
    for row in data:
        t,v,stage=row;pos=xy(t,v)
        # Missing periods and different stages are not interpolated.
        if previous and previous[2] == stage and 0 <= t-previous[0] <= 12:
            d.line((*xy(previous[0],previous[1]),*pos),fill='#6aa3de' if kind=='speed' else '#65b49b',width=3)
        d.ellipse((pos[0]-2,pos[1]-2,pos[0]+2,pos[1]+2),fill='#9bc4ef')
        previous=row
    note='Noktalar gerçek örneklerdir; boşluklar ölçüm yapılmayan süreleri gösterir.'
    if kind=='speed':note='Hız: tamamlanan aygıt I/O sayaçları. Kırmızı: gözlenen uzun sıfır I/O dizisi; tek başına arıza kanıtı değildir.'
    text((35,530),note,19,fill='#99abc1')
    image.save(path)
    return path


def pauses(session):
    """Report only observed runs of zero speed with dense samples in one stage."""
    result=[];start=None;prev=None
    for t,v,stage in points(session,'speed'):
        contiguous = prev and prev[2]==stage and 0<t-prev[0]<=2
        if v==0:
            if not contiguous or start is None:start=t
            if start is not None and t-start>=5:
                if result and result[-1]['start_seconds']==start:result[-1]['seconds']=round(t-start,1)
                else:result.append(dict(stage=stage,start_seconds=start,seconds=round(t-start,1)))
        else:start=None
        prev=(t,v,stage)
    return result

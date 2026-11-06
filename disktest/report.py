from __future__ import annotations
from html import escape
import base64
import hashlib
import json
import os
from pathlib import Path
from .report_content import sections, stage_rows, temperature_rows
from .project import references, PROJECT_URL, REPORT_GUIDE, AI_GUIDE


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def verify_manifest(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    errors = []
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if path.parent != root or name == 'manifest.json':
            errors.append(f'Geçersiz manifest yolu: {name}')
        elif not path.is_file() or digest(path) != expected:
            errors.append(f'Eksik veya değiştirilmiş dosya: {name}')
    if 'session.json' not in manifest['files'] or 'report.html' not in manifest['files']:
        errors.append('Zorunlu rapor dosyaları manifestte eksik.')
    return errors


def write_report(session, output, with_pdf=True):
    session = dict(session)
    session['documentation'] = references(session['version'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    directory = output / session['id']
    directory.mkdir()
    (directory / 'session.json').write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding='utf-8')
    summary, details = sections(session)
    if session.get('account_name'):
        summary.insert(0, ('Test kayıt numarası', [session['account_name']]))
    def paragraphs(items):
        return ''.join(f'<h2>{escape(title)}</h2>' + ''.join(f'<p>{escape(str(s))}</p>' for s in lines)
                       for title, lines in items)
    def table(rows):
        return '<table>' + ''.join('<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in r) + '</tr>' for r in rows) + '</table>'
    logo = base64.b64encode((Path(__file__).parent / 'assets/vektron-logo.png').read_bytes()).decode('ascii')
    html = ('<!doctype html><html lang="tr"><meta charset="utf-8"><title>VEDT test raporu</title>'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{font:16px system-ui,sans-serif;background:#edf2f7;color:#142438;margin:0;padding:30px}'
            'main{max-width:1000px;margin:auto;background:white;padding:30px;border-top:8px solid #18649e}'
            'h1,h2{color:#145581}table{border-collapse:collapse;width:100%;font-size:14px}'
            'td{padding:10px;border:1px solid #d3dfe9}tr:first-child{background:#dcebf7;font-weight:bold}'
            'p{overflow-wrap:anywhere}.technical{margin-top:40px;border-top:3px solid #18649e}'
            '@media print{body{padding:0;background:white}.technical{break-before:page}}</style>'
            '<main><div style="background:#145581;padding:20px"><img alt="Vektron" width="145" src="data:image/png;base64,' + logo + '"></div><h1>VEDT — Vektron Elektronik Disk Test</h1><p>Test sonuç raporu</p>' + paragraphs(summary) +
            '<section class="technical"><h1>Ayrıntılı teknik rapor</h1>' + paragraphs(details[:1]) +
            '<h2>Aşama sonuçları ve ölçümler</h2>' + table(stage_rows(session)) +
            '<h2>Aşamalara göre sıcaklık ölçümleri</h2>' + table(temperature_rows(session)) +
            paragraphs(details[1:]) + '</section><h2>Proje ve rapor okuma kılavuzu</h2>' +
            ''.join('<p><a href="' + escape(url, quote=True) + '">' + escape(label) + '</a></p>'
                    for label, url in [('VEDT açık kaynak projesi', PROJECT_URL),
                                       ('Türkçe rapor okuma kılavuzu (şema 1)', REPORT_GUIDE),
                                       ('Yapay zekâ ile rapor yorumlama', AI_GUIDE)]) + '</main></html>')
    (directory / 'report.html').write_text(html, encoding='utf-8')
    if with_pdf:
        _pdf(session, directory / 'report.pdf')
    files = {p.name: digest(p) for p in sorted(directory.iterdir()) if p.is_file()}
    (directory / 'manifest.json').write_text(json.dumps({'algorithm': 'SHA-256', 'files': files}, indent=2), encoding='utf-8')
    for file in directory.iterdir():
        with file.open('r+b') as stream:
            os.fsync(stream.fileno())
    return directory


def _pdf(session, path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    candidates = [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/arial.ttf',
                  Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font = next((p for p in candidates if p.is_file()), None)
    if font is None:
        raise RuntimeError('PDF için Türkçe destekli font bulunamadı.')
    pdfmetrics.registerFont(TTFont('DiskTest', str(font)))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = 'DiskTest'
    styles['Normal'].fontSize = 9
    styles['Normal'].leading = 13
    styles['Heading2'].textColor = colors.HexColor('#145581')
    summary, details = sections(session)
    if session.get('account_name'):
        summary.insert(0, ('Test kayıt numarası', [session['account_name']]))
    from reportlab.lib.styles import ParagraphStyle
    brand_style = ParagraphStyle('VEDTBrand', parent=styles['Title'], textColor=colors.white, fontSize=22, leading=29)
    logo = Image(str(Path(__file__).parent / 'assets/vektron-logo.png'), width=116, height=103)
    header = Table([[logo, Paragraph('VEDT<br/>Vektron Elektronik Disk Test', brand_style)]], colWidths=[140, 355])
    header.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#145581')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    styles['Title'].textColor = colors.white
    story = [header, Spacer(1, 18), Paragraph('Test sonuç raporu', styles['Heading1'])]
    styles['Title'].textColor = colors.HexColor('#145581')
    def paragraphs(items):
        for title, lines in items:
            story.append(Paragraph(escape(title), styles['Heading2']))
            for line in lines:
                story.extend([Paragraph(escape(str(line)), styles['Normal']), Spacer(1, 7)])
    def table(rows, widths):
        data = [[Paragraph(escape(str(cell)), styles['Normal']) for cell in row] for row in rows]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dcebf7')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd9e5')),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        story.extend([item, Spacer(1, 12)])
    paragraphs(summary)
    story.extend([PageBreak(), Paragraph('Ayrıntılı teknik rapor', styles['Title'])])
    paragraphs(details[:1])
    story.append(Paragraph('Aşama sonuçları ve ölçümler', styles['Heading2']))
    table(stage_rows(session), [185, 80, 75, 65, 90])
    story.append(Paragraph('Aşamalara göre sıcaklık ölçümleri', styles['Heading2']))
    table(temperature_rows(session), [185, 50, 85, 90, 85])
    paragraphs(details[1:])
    story.append(Paragraph('Proje ve rapor okuma kılavuzu', styles['Heading2']))
    for label, url in [('VEDT açık kaynak projesi', PROJECT_URL),
                       ('Türkçe rapor okuma kılavuzu (şema 1)', REPORT_GUIDE),
                       ('Yapay zekâ ile rapor yorumlama', AI_GUIDE)]:
        story.extend([Paragraph('<link href="' + escape(url, quote=True) + '">' + escape(label) +
                                '</link>', styles['Normal']), Spacer(1, 7)])
    story.append(Paragraph(escape(PROJECT_URL), styles['Normal']))
    def footer(canvas, doc):
        canvas.setFont('DiskTest', 8)
        canvas.drawRightString(A4[0] - 48, 23, f'Sayfa {doc.page}')
    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=48, leftMargin=48,
                       topMargin=35, bottomMargin=40, title='VEDT test sonuç raporu').build(
                           story, onFirstPage=footer, onLaterPages=footer)

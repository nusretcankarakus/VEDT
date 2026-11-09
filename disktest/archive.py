"""USB-wide offline report index, including nested jobs and previous runs."""
from html import escape
import json
import os
from pathlib import Path
from urllib.parse import quote
from .language import status_text
from .naming import report_stem


def build_index(root):
    root=Path(root).resolve();rows=[];unreadable=0
    for f in sorted(root.rglob('session.json')):
        try:
            if f.is_symlink() or not f.resolve().is_relative_to(root):continue
            s=json.loads(f.read_text(encoding='utf-8'));identity=s.get('target',{}).get('identity',{})
            report=f.parent/(report_stem(s)+'.html')
            if not report.is_file():continue
            label=status_text(s.get('status','UNKNOWN'))
            cells=[s.get('account_name') or 'Numarasız',identity.get('serial') or 'Bilgi yok',
                   identity.get('model') or 'Bilgi yok',s.get('started_at') or 'Bilgi yok',label]
            href=quote(report.relative_to(root).as_posix(),safe='/')
            rows.append('<tr data-status="'+escape(s.get('status','UNKNOWN'),quote=True)+'">'+
                ''.join('<td>'+escape(str(x))+'</td>' for x in cells)+'<td><a href="'+href+'">Raporu aç</a></td></tr>')
        except (OSError,ValueError,TypeError,KeyError):unreadable+=1
    html="""<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VEDT — USB rapor arşivi</title><style>body{font:17px system-ui;background:#0b1423;color:#eaf0f8;padding:28px}main{max-width:1500px;margin:auto}h1{color:#9bc4ef}input,select{font:inherit;padding:12px;background:#122035;color:#eaf0f8;border:1px solid #526780;border-radius:6px;margin:8px}table{width:100%;border-collapse:collapse}td,th{padding:14px;text-align:left;border-bottom:1px solid #26364b}a{color:#9bc4ef}small{color:#a5b5c9}.scroll{overflow:auto}</style>
<main><h1>VEDT — USB rapor arşivi</h1><p>Bu USB’deki eski ve yeni test kayıtları. Tarihler UTC’dir. Bu sayfa disk testini veya kurulumu başlatmaz.</p>
<label>Ara <input id="search" placeholder="VEDT54, seri numarası, model veya tarih"></label>
<label>Sonuç <select id="status"><option value="">Tüm sonuçlar</option><option value="PASS">Başarılı</option><option value="WARNING">Uyarılı</option><option value="FAIL">Başarısız</option><option value="CANCELLED">İptal</option><option value="INCOMPLETE">Tamamlanmadı</option></select></label>
<p id="count"></p><div class="scroll"><table><thead><tr><th>Müşteri / test no</th><th>Seri numarası</th><th>Model</th><th>Başlangıç (UTC)</th><th>Sonuç</th><th>Rapor</th></tr></thead><tbody>"""+''.join(rows)+"""</tbody></table></div><small>Arşiv kaydı garanti belgesi değildir. Rapor içindeki test kapsamı ve uyarıları okuyun.</small>
<script>const rows=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;const q=document.querySelector('#search').value.toLocaleLowerCase('tr'),s=document.querySelector('#status').value;for(const r of rows){const show=r.textContent.toLocaleLowerCase('tr').includes(q)&&(!s||r.dataset.status===s);r.hidden=!show;if(show)n++;}document.querySelector('#count').textContent=n+' / '+rows.length+' kayıt gösteriliyor';}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#status').addEventListener('change',filter);filter();</script></main></html>"""
    if unreadable:html=html.replace('<p id="count">',f'<p>{unreadable} okunamayan kayıt arşive alınamadı.</p><p id="count">')
    tmp=root/'index.html.new';tmp.write_text(html,encoding='utf-8');os.replace(tmp,root/'index.html')
    return len(rows)

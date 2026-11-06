"""Persistent per-USB VEDT reservations; a reservation is never reused."""
import json
import os
from pathlib import Path
import re


def reserve_account(reports, report_id):
    if not isinstance(report_id, str) or not re.fullmatch('[0-9a-f]{24}', report_id):
        raise ValueError('Geçersiz test kimliği.')
    directory = Path(reports) / 'vedt-numaralar'
    directory.mkdir(exist_ok=True)
    if directory.is_symlink():
        raise ValueError('Numaratör klasörü bağlantı olamaz.')
    # Single reservation writer. A crash leaves a lock and stops further allocation
    # rather than risking a duplicate customer number after an incomplete write.
    lock = directory / '.kilit'
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError('VEDT numaratörü kilitli; USB kaydı incelenmeli.') from exc
    try:
        highest = 0
        existing = None
        for path in directory.glob('VEDT*.json'):
            match = re.fullmatch(r'VEDT([1-9][0-9]{0,14})\.json', path.name)
            if not match or path.is_symlink():
                raise ValueError('Numaratör kaydı geçersiz.')
            number = int(match[1])
            highest = max(highest, number)
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('account_name') != f'VEDT{number}' or not re.fullmatch('[0-9a-f]{24}', str(data.get('report_id', ''))):
                raise ValueError('Numaratör kaydı bozuk; numara sıfırlanmadı.')
            if data['report_id'] == report_id:
                if existing is not None:
                    raise ValueError('Test kimliği için birden fazla numara var.')
                existing = data['account_name']
        if existing:
            return existing
        number = highest + 1
        if number > 999999999999999:
            raise ValueError('VEDT numara sınırına ulaşıldı.')
        name = f'VEDT{number}'
        with (directory / (name + '.json')).open('x', encoding='utf-8') as stream:
            json.dump({'account_name': name, 'report_id': report_id}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        return name
    finally:
        lock.rmdir()

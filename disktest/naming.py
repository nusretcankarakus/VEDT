"""Portable report filenames; complete hardware serial stays inside the report."""
import re


def report_stem(session):
    account = session.get('account_name')
    if account is None:
        return 'report'
    if not isinstance(account, str) or not re.fullmatch(r'VEDT[1-9][0-9]{0,14}', account):
        raise ValueError('Rapor hesap numarası geçersiz.')
    serial = str(session.get('target', {}).get('identity', {}).get('serial', 'SERI-YOK'))
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', serial).strip('._')[:48] or 'SERI-YOK'
    return account + '_' + safe

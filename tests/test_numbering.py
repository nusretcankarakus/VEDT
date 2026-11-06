import json
import pytest
from disktest.numbering import reserve_account


def test_usb_numbers_increase_and_existing_test_keeps_its_number(tmp_path):
    assert reserve_account(tmp_path, 'a' * 24) == 'VEDT1'
    assert reserve_account(tmp_path, 'b' * 24) == 'VEDT2'
    assert reserve_account(tmp_path, 'a' * 24) == 'VEDT1'
    assert reserve_account(tmp_path, 'c' * 24) == 'VEDT3'


def test_broken_or_locked_counter_does_not_reset_to_one(tmp_path):
    reserve_account(tmp_path, 'a' * 24)
    path = tmp_path / 'vedt-numaralar' / 'VEDT1.json'
    path.write_text('{}')
    with pytest.raises(ValueError):
        reserve_account(tmp_path, 'b' * 24)
    path.write_text(json.dumps({'account_name': 'VEDT1', 'report_id': 'a' * 24}))
    (path.parent / '.kilit').mkdir()
    with pytest.raises(ValueError, match='kilitli'):
        reserve_account(tmp_path, 'b' * 24)


@pytest.mark.parametrize('value', ['../a', '', 'a' * 23])
def test_counter_rejects_invalid_report_ids(tmp_path, value):
    with pytest.raises(ValueError):
        reserve_account(tmp_path, value)

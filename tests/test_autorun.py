from dataclasses import asdict
import json

import pytest

from disktest.autorun import NAME, load
from disktest.raw import RawSettings
from disktest.safety import Identity


def record():
    settings = RawSettings(Identity('TARGET-123', 'Test', 128 * 1024**2, 'wwn-test'),
                           allow_destroy=True, laboratory=False)
    return {'schema_version': 1, 'enabled': True,
            'accepted_data_loss_for_serial': 'TARGET-123', 'settings': asdict(settings)}


def test_saved_configuration_preserves_whole_identity(tmp_path):
    (tmp_path / NAME).write_text(json.dumps(record()))
    settings = load(tmp_path)
    assert settings.target == Identity('TARGET-123', 'Test', 128 * 1024**2, 'wwn-test')


@pytest.mark.parametrize('case', ['wrong-consent', 'disabled', 'lab', 'fault', 'extra-key'])
def test_invalid_automatic_consent_is_rejected(tmp_path, case):
    data = record()
    if case == 'wrong-consent':
        data['accepted_data_loss_for_serial'] = 'OTHER'
    elif case == 'disabled':
        data['enabled'] = False
    elif case == 'lab':
        data['settings']['laboratory'] = True
    elif case == 'fault':
        data['settings']['inject_corruption'] = True
    else:
        data['command'] = 'not permitted'
    (tmp_path / NAME).write_text(json.dumps(data))
    with pytest.raises((ValueError, RuntimeError)):
        load(tmp_path)

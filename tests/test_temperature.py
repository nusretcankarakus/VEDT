from disktest.temperature import summarize


def test_sensor_samples_are_grouped_without_cached_display_values():
    samples = [{'temperature_c': 30, 'phase': 'boşta', 'stage': None},
               {'temperature_c': 32, 'phase': 'boşta', 'stage': None},
               {'temperature_c': 40, 'phase': 'yük', 'stage': 'Yazma'},
               {'temperature_c': 50, 'phase': 'yük', 'stage': 'Yazma'},
               {'temperature_c': None, 'phase': 'yük', 'stage': 'Okuma'}]
    result = summarize(samples)
    assert result['idle']['average_c'] == 31
    assert result['load']['average_c'] == 45
    assert result['overall']['minimum_c'] == 30
    assert result['overall']['maximum_c'] == 50
    assert result['stages']['Yazma']['count'] == 2
    assert result['stages']['Okuma']['average_c'] is None


def test_unavailable_sensor_never_creates_fake_temperature():
    result = summarize([{'temperature_c': None, 'phase': 'boşta', 'stage': None}])
    assert result['overall'] == {'count': 0, 'minimum_c': None, 'maximum_c': None, 'average_c': None}

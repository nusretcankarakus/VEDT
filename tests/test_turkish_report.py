from io import StringIO
from disktest.dashboard import Dashboard
from disktest.language import conclusion
from disktest.report import write_report, verify_manifest
from disktest.safety import Identity


def session():
    return {'id': 'turkish-report', 'version': '0.4.0', 'status': 'WARNING', 'mode': 'raw-device',
            'target': {'bytes': 67108864, 'identity': {'serial': 'SERIAL', 'model': 'Model', 'wwn': 'wwn'}},
            'settings': {'scenario': 'raw-device'}, 'started_at': '2026-11-05T10:00:00Z',
            'elapsed_seconds': 10, 'error': None, 'warnings': [], 'full_capacity_verified': True,
            'stages': [{'name': 'Tam kapasite yazma', 'status': 'PASS', 'bytes': 67108864,
                        'seconds': 1, 'mib_per_s': 64}]}


def test_readable_report_is_turkish_and_summary_precedes_technical_details(tmp_path):
    folder = write_report(session(), tmp_path, with_pdf=False)
    html = (folder / 'report.html').read_text(encoding='utf-8')
    assert html.index('Genel değerlendirme') < html.index('Ayrıntılı teknik rapor')
    assert '>Başarılı<' in html and '>PASS<' not in html and '>WARNING<' not in html
    assert 'Sıcaklık özeti' in html and 'Ölçülemedi' in html
    assert verify_manifest(folder) == []


def test_late_smart_failure_does_not_get_successful_general_summary():
    value = session()
    value['status'] = 'FAIL'
    assert 'sağlamdır denilemez' in conclusion(value)


def test_colored_screen_sanitizes_device_text_and_finishes_at_100_percent(tmp_path):
    class Terminal(StringIO):
        def isatty(self):
            return True
    stream = Terminal()
    target = Identity('SERIAL\x1b[31m', 'Model', 67108864, 'wwn')
    screen = Dashboard(target, stream, laboratory=False)
    screen({'stage': 'Yazma', 'percent': 40, 'temperature_c': 45, 'elapsed_seconds': 2, 'mib_per_s': 15})
    screen.finish(session(), tmp_path)
    output = stream.getvalue()
    assert '\x1b[1;97;44m' in output and '%100.0' in output and 'Uyarılı' in output
    assert 'SERIAL\x1b' not in output

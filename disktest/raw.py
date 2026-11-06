"""Block-device engine with separate laboratory and operator-authorized modes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import secrets
import re
import shutil
import subprocess
import time

from . import __version__
from .device import PinnedDevice, SafetyError, require_lab
from .engine import DeadlineExceeded
from .fio import FioError, FioDataMismatch, _stop, parse_result
from .safety import Authorization, Identity
from .smart import read_smart


class ThermalLimit(RuntimeError):
    pass


@dataclass(frozen=True)
class RawSettings:
    target: Identity
    allow_destroy: bool = False
    laboratory: bool = False
    timeout_seconds: float = 300
    stall_seconds: float = 30
    maximum_temperature_c: float = 70
    mixed_operations: int = 256
    inject_corruption: bool = False
    idle_observation_seconds: float = 0

    def validate(self, confirmation):
        if any(type(value) is not str or not value.strip() for value in
               (self.target.serial, self.target.model, self.target.wwn)) or type(self.target.size_bytes) is not int:
            raise ValueError('Hedefin seri/model/WWN/kapasite alanları eksik veya türü geçersiz.')
        if self.allow_destroy is not True or type(self.laboratory) is not bool:
            raise SafetyError('Veri silme yetkisi açıkça gerekli.')
        if confirmation != self.target.serial or not confirmation:
            raise SafetyError('Seri numarası onayı eşleşmiyor.')
        if self.laboratory and self.target.serial not in {'DT-RAW-SATA1', 'DT-RAW-NVME1'}:
            raise SafetyError('Bu sürüm yalnızca iki dosya tabanlı QEMU hedefini kabul eder.')
        if self.laboratory and self.target.size_bytes != 64 * 1024**2:
            raise SafetyError('Laboratuvar hedefi tam 64 MiB olmalı.')
        if self.target.size_bytes < 64 * 1024**2 or self.target.size_bytes % 512:
            raise SafetyError('Hedef en az 64 MiB ve sektör hizalı olmalı.')
        if self.inject_corruption and not self.laboratory:
            raise SafetyError('Kontrollü bozulma yalnızca laboratuvarda kullanılabilir.')
        for value, low, high in [(self.timeout_seconds, 1, 604800), (self.stall_seconds, 2, 120),
                                  (self.idle_observation_seconds, 0, 120),
                                  (self.maximum_temperature_c, 30, 90)]:
            if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Geçersiz laboratuvar süre/sıcaklık sınırı.')
        if type(self.mixed_operations) is not int or not 1 <= self.mixed_operations <= 4096:
            raise ValueError('Karışık işlem sayısı 1-4096 olmalı.')
        if type(self.inject_corruption) is not bool:
            raise ValueError('Hata enjeksiyonu yalnızca boolean olabilir.')


def load_settings(path):
    data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    try:
        data['target'] = Identity(**data['target'])
        return RawSettings(**data)
    except (TypeError, KeyError) as exc:
        raise ValueError('Laboratuvar yapılandırması geçersiz.') from exc


def persistent_reports(path):
    path.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['findmnt', '--json', '--evaluate', '--target', str(path.resolve()),
                             '--output', 'SOURCE,FSTYPE'], capture_output=True,
                            text=True, timeout=10, check=True)
    fs = json.loads(result.stdout)['filesystems'][0]
    if fs['fstype'] not in {'ext4', 'xfs', 'vfat', 'exfat', 'ntfs3'} or not fs['source'].startswith('/dev/'):
        raise SafetyError('Ham test için kalıcı, yerel blok aygıtındaki rapor alanı gerekli.')
    if shutil.disk_usage(path).free < 16 * 1024**2:
        raise SafetyError('Rapor alanında boş yer yetersiz.')


def smart_delta(before, after):
    changes = {}
    warnings = []
    for key in ('media_errors', 'num_err_log_entries', 'critical_warning'):
        old = before.get('raw', {}).get('nvme_smart_health_information_log', {}).get(key)
        new = after.get('raw', {}).get('nvme_smart_health_information_log', {}).get(key)
        if type(old) is int and type(new) is int:
            changes[key] = {'before': old, 'after': new, 'delta': new - old}
            if new < old:
                warnings.append('SMART sayacı geriledi: ' + key)
    def ata(raw):
        return {row['id']: row.get('raw', {}).get('value')
                for row in raw.get('ata_smart_attributes', {}).get('table', []) if 'id' in row}
    old_ata = ata(before.get('raw', {}))
    new_ata = ata(after.get('raw', {}))
    for code in (5, 187, 188, 197, 198):
        old, new = old_ata.get(code), new_ata.get(code)
        if type(old) is int and type(new) is int:
            changes[f'ata_{code}'] = {'before': old, 'after': new, 'delta': new - old}
            if new < old:
                warnings.append(f'SMART sayacı geriledi: ATA {code}')
    return changes, warnings


def run_raw(settings, confirmation, reports, event=lambda _: None, *, accept_data_loss=False):
    settings.validate(confirmation)
    if settings.laboratory:
        require_lab()
    elif accept_data_loss is not True:
        raise SafetyError('Operatörün açık veri silme onayı gerekli.')
    persistent_reports(reports)
    executable = shutil.which('fio')
    if not executable:
        raise RuntimeError('fio kurulu değil.')
    fio_version = subprocess.run([executable, '--version'], capture_output=True,
                                 text=True, timeout=10, check=True).stdout.strip()
    if not fio_version.startswith('fio-'):
        raise RuntimeError('Bulunan program Flexible I/O Tester değil.')
    started = time.monotonic()
    session = {
        'schema_version': 1, 'version': __version__, 'id': secrets.token_hex(12),
        'started_at': datetime.now(timezone.utc).isoformat(), 'mode': 'lab-raw' if settings.laboratory else 'raw-device',
        'physical_hardware_tested': False, 'virtual_block_target_tested': False,
        'identity_authorized': False, 'full_capacity_verified': False,
        'target': {'kind': 'qemu-block-device' if settings.laboratory else 'block-device', 'bytes': settings.target.size_bytes,
                   'identity': asdict(settings.target)},
        'settings': {**asdict(settings), 'scenario': 'lab-data-mismatch' if settings.inject_corruption else 'lab-raw'},
        'status': 'RUNNING', 'stages': [], 'fio_results': [], 'telemetry': [],
        'fio_version': fio_version, 'temperature_c': None, 'error': None,
        'warnings': ['LAB: Yalnızca 64 MiB dosya tabanlı QEMU blok aygıtı sınandı.',
                     'Hedef sanal diskin verileri silinir; fiziksel donanım kabulü yapılmadı.',
                     'Anlık I/O, Linux tamamlanan aygıt sayaçlarından alınır; başka aygıt I/O işlemleri ölçümü etkileyebilir.'],
    }
    if not settings.laboratory:
        session['settings']['scenario'] = 'raw-device'
        session['warnings'] = ['Geliştirme sürümü: fiziksel donanım kabulü henüz tamamlanmadı.',
                               'Test hedefinin tüm verileri silinir.']
    authorization = Authorization(settings.target, settings.allow_destroy)
    temperature_samples = []

    def check_time():
        if time.monotonic() - started >= settings.timeout_seconds:
            raise DeadlineExceeded('Toplam test süresi aşıldı.')

    def smart(device, phase='kontrol', stage=None):
        check_time()
        try:
            data = read_smart(device.path, timeout=3)
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
            data = {'health': 'UNKNOWN', 'temperature_c': None, 'acquisition_ok': False,
                    'raw': {}, 'messages': [str(exc)]}
        value = data['temperature_c']
        session['temperature_c'] = value
        temperature_samples.append({'elapsed_seconds': round(time.monotonic() - started, 3),
                                    'phase': phase, 'stage': stage, 'temperature_c': value})
        if value is not None and value >= settings.maximum_temperature_c:
            raise ThermalLimit(f'Sıcaklık sınırı: {value} C')
        if data['health'] == 'FAIL':
            raise FioError('SMART güncel arıza/eşik hatası bildiriyor.')
        return data

    try:
        with PinnedDevice(authorization, laboratory=settings.laboratory) as device:
            session['identity_authorized'] = True
            session['device_path'] = str(device.path)
            session['logical_sector_bytes'] = device.logical_sector
            session['native_ids'] = device.native_ids()
            before = smart(device)
            session['smart_before'] = before
            if settings.idle_observation_seconds and before['temperature_c'] is not None:
                smart(device, 'boşta')
                idle_end = time.monotonic() + settings.idle_observation_seconds
                while time.monotonic() < idle_end:
                    check_time()
                    time.sleep(max(0, min(5, idle_end - time.monotonic())))
                    smart(device, 'boşta')
            size = settings.target.size_bytes
            block = 65536 if size % 65536 == 0 else 4096 if size % 4096 == 0 else device.logical_sector
            if block < device.logical_sector:
                raise SafetyError('Blok boyutu mantıksal sektörden küçük.')

            def stage(name, options, workload_size=size, bs=block, verify_only=False,
                      require_bytes=None, direction='both'):
                check_time()
                device.boundary()
                smart(device, 'aşama öncesi', name)
                row = {'name': name, 'status': 'RUNNING', 'bytes': 0, 'seconds': 0, 'mib_per_s': 0}
                session['stages'].append(row)
                since = time.monotonic()
                baseline = device.stats()
                previous = baseline
                previous_time = since
                last_progress = since
                last_smart = since - 5
                process = None
                stdout = stderr = ''
                command = [executable, '--name=disktest-raw', f'--filename=/proc/self/fd/{device.fd}',
                           f'--size={workload_size}', f'--bs={bs}', '--ioengine=psync', '--iodepth=1',
                           '--numjobs=1', '--direct=1', '--allow_file_create=0', '--eta=never',
                           '--output-format=json', '--verify_state_save=0', '--verify_state_load=0',
                           '--verify_fatal=1', '--end_fsync=1'] + options
                try:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               text=True, start_new_session=True, pass_fds=(device.fd,))
                    while True:
                        check_time()
                        device.check_fd()
                        try:
                            stdout, stderr = process.communicate(timeout=0.5)
                            break
                        except subprocess.TimeoutExpired:
                            now = time.monotonic()
                            current = device.stats()
                            if current[0] < previous[0] or current[1] < previous[1]:
                                raise SafetyError('Aygıt sayaçları sıfırlandı; kimlik/güncellik belirsiz.')
                            delta = tuple(current[i] - baseline[i] for i in (0, 1))
                            completed = delta[0] if direction == 'read' else delta[1] if direction == 'write' else sum(delta)
                            if current != previous:
                                last_progress = now
                            if now - last_progress >= settings.stall_seconds:
                                raise DeadlineExceeded('Süre sınırı boyunca tamamlanan I/O görülmedi.')
                            if now - last_smart >= 5:
                                smart(device, 'yük', name)
                                last_smart = time.monotonic()
                            speed = sum(current[i] - previous[i] for i in (0, 1)) / 1024**2 / max(now - previous_time, 1e-9)
                            sample = {'stage': name, 'elapsed_seconds': now - started,
                                      'source': 'linux-completed-device-io', 'read_bytes': delta[0],
                                      'write_bytes': delta[1], 'mib_per_s': speed,
                                      'percent': min(100, completed * 100 / require_bytes) if require_bytes else None,
                                      'temperature_c': session['temperature_c']}
                            session['telemetry'].append(sample)
                            if len(session['telemetry']) > 4096:
                                del session['telemetry'][:1024]
                                session['telemetry_samples_omitted'] = session.get('telemetry_samples_omitted', 0) + 1024
                            event(sample)
                            previous, previous_time = current, now
                    result, count = parse_result(stdout, process.returncode, verify_only=verify_only)
                    smart(device, 'aşama sonrası', name)
                    session['fio_results'].append({'stage': name, 'argv': command, 'result': result,
                                                   'stderr': stderr, 'phantom_writes_excluded': verify_only})
                    if require_bytes is not None and count != require_bytes:
                        raise FioError(f'Aşama eksik: {count}/{require_bytes} bayt.')
                    row['bytes'] = count
                    job = result['jobs'][0]
                    row['mib_per_s'] = (job.get('read', {}).get('bw_bytes', 0) +
                        (0 if verify_only else job.get('write', {}).get('bw_bytes', 0))) / 1024**2
                    device.boundary()
                    row['status'] = 'PASS'
                except BaseException as exc:
                    if process is not None:
                        try:
                            _stop(process)
                        except subprocess.TimeoutExpired:
                            session['worker_may_still_be_running'] = process.pid
                    row['status'] = 'STOPPED' if isinstance(exc, KeyboardInterrupt) else 'FAIL'
                    session['failure_diagnostics'] = {'stdout': stdout[-30000:], 'stderr': stderr[-6000:]}
                    if isinstance(exc, FioDataMismatch):
                        match = re.search(r'at file .+ offset (\d+), length (\d+)', stderr)
                        if match:
                            offset, length = map(int, match.groups())
                            session['verification_failure_range'] = {'offset_bytes': offset, 'length_bytes': length}
                            exc.args = (f'Veri uyuşmazlığı: {offset} bayt adresinden başlayan {length} baytlık blok.',)
                    raise
                finally:
                    row['seconds'] = time.monotonic() - since

            bench = min(size, 32 * 1024**2)
            stage('Sıralı okuma ölçümü', ['--rw=read', '--readonly'], workload_size=bench,
                  require_bytes=bench, direction='read')
            session['virtual_block_target_tested'] = settings.laboratory
            stage('4 KiB rastgele okuma / QD1', ['--rw=randread', '--readonly', '--io_size=4194304',
                  '--number_ios=1024'], bs=4096, require_bytes=4194304, direction='read')
            stage('Tam kapasite yazma / SHA-256', ['--rw=write', '--verify=sha256', '--do_verify=0'],
                  require_bytes=size, direction='write')
            if settings.inject_corruption:
                device.boundary()
                offset = block + 17
                original = os.pread(device.fd, 1, offset)
                if len(original) != 1:
                    raise FioError('Hata enjeksiyonu adresi okunamadı.')
                if os.pwrite(device.fd, bytes([original[0] ^ 255]), offset) != 1:
                    raise FioError('Hata enjeksiyonu yazılamadı.')
                os.fsync(device.fd)
                session['injected_fault'] = {'kind': 'controlled-data-mismatch', 'offset_bytes': offset}
                session['warnings'].append('LAB: Kontrollü veri bozulması özellikle uygulandı; gerçek cihaz arızası değildir.')
            verify = ['--rw=write', '--verify=sha256', '--verify_only=1', '--do_verify=1']
            stage('Tam kapasite geri okuma doğrulaması', verify, verify_only=True,
                  require_bytes=size, direction='read')
            # Keep this bounded workload within one address-space pass. fio
            # stops at the device range boundary on small targets even when
            # number_ios requests more operations.
            mixed_operations = min(settings.mixed_operations, size // block)
            mixed_bytes = mixed_operations * block
            session['effective_mixed_operations'] = mixed_operations
            stage('Karışık okuma/yazma', ['--rw=randrw', '--rwmixread=50', '--verify=sha256',
                  '--do_verify=0', '--verify_header_seed=0', '--verify_write_sequence=0',
                  f'--number_ios={mixed_operations}', f'--io_size={mixed_bytes}'],
                  require_bytes=mixed_bytes)
            stage('Karışık test sonrası tam doğrulama', verify, verify_only=True,
                  require_bytes=size, direction='read')
            session['full_capacity_verified'] = True
            after = smart(device)
            session['smart_after'] = after
            session['smart_changes'], warnings = smart_delta(before, after)
            session['warnings'].extend(warnings)
            if any(c['delta'] > 0 for name, c in session['smart_changes'].items()
                   if name in {'media_errors', 'critical_warning', 'ata_5', 'ata_187', 'ata_188', 'ata_197', 'ata_198'}):
                raise FioError('Test sırasında kritik SMART sayacı yükseldi.')
            if before['health'] != 'PASS' or after['health'] != 'PASS':
                session['warnings'].append('SMART verisinin tamamı doğrulanamadı.')
            session['status'] = 'WARNING'  # laboratory evidence, not a physical health certificate
    except KeyboardInterrupt:
        session['status'] = 'CANCELLED'
        session['error'] = {'kind': 'cancelled', 'message': 'Operatör durdurdu.'}
    except (SafetyError, DeadlineExceeded, ThermalLimit, FioError, OSError, subprocess.SubprocessError) as exc:
        session['status'] = 'INCOMPLETE' if isinstance(exc, DeadlineExceeded) else 'FAIL'
        session['error'] = {'kind': type(exc).__name__, 'message': str(exc)}
    session['elapsed_seconds'] = time.monotonic() - started
    from .temperature import summarize
    session['temperature_samples'] = temperature_samples
    session['temperature_summary'] = summarize(temperature_samples)
    session['finished_at'] = datetime.now(timezone.utc).isoformat()
    return session

"""Progress and estimates for the six stages on ONE disk; no device I/O."""
from collections import deque
import math

STAGES = (
    'Sıralı okuma ölçümü',
    '4 KiB rastgele okuma / QD1',
    'Tam kapasite yazma / SHA-256',
    'Tam kapasite geri okuma doğrulaması',
    'Karışık okuma/yazma',
    'Karışık test sonrası tam doğrulama',
)


def duration(value):
    if value is None or not math.isfinite(value):
        return 'Ölçülüyor'
    seconds = max(0, math.ceil(value))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


class Progress:
    def __init__(self, size, mixed_operations):
        body = size // 1048576 * 1048576
        self.expected = [min(size, 32*1048576), 4194304, size, size,
                         min(mixed_operations, body//65536)*65536, size]
        self.history = [deque() for _ in STAGES]
        self.rates = {}

    def snapshot(self, actual, elapsed, current=None, completed=0,
                 stage_elapsed=0, phase=None, final_status=None):
        index = STAGES.index(current) if current in STAGES else None
        by_name = {row['name']: row for row in actual}
        states = []
        for i, name in enumerate(STAGES):
            source = by_name.get(name, {})
            state = {'name': name, 'status': source.get('status', 'PENDING'),
                     'bytes': source.get('bytes', 0), 'seconds': source.get('seconds', 0)}
            if i == index:
                state['bytes'] = min(self.expected[i], max(state['bytes'], completed))
                state['seconds'] = max(state['seconds'], stage_elapsed)
            states.append(state)
        current_rate = None
        if index is not None:
            history = self.history[index]
            value = states[index]['bytes']
            if history and (elapsed < history[-1][0] or value < history[-1][1]):
                history.clear()
            if not history or elapsed > history[-1][0]:
                history.append((elapsed, value))
            while len(history) > 2 and history[1][0] < elapsed - 15:
                history.popleft()
            threshold = min(32*1048576, self.expected[index]*0.1)
            if stage_elapsed >= 3 and value >= threshold and len(history) > 1:
                seconds = history[-1][0] - history[0][0]
                amount = history[-1][1] - history[0][1]
                if seconds > 0 and amount > 0:
                    current_rate = amount / seconds
                    self.rates[index] = current_rate
            if states[index]['status'] == 'PASS' and states[index]['seconds'] > 0:
                self.rates.setdefault(index, value / states[index]['seconds'])

        failed = any(row['status'] in ('FAIL', 'STOPPED') for row in states)
        failed = failed or final_status in ('FAIL', 'INCOMPLETE', 'CANCELLED')
        passed = all(row['status'] == 'PASS' for row in states)
        stage_eta = None
        if index is not None and not failed:
            remaining = max(0, self.expected[index] - states[index]['bytes'])
            if states[index]['status'] == 'PASS':
                stage_eta = 0
            elif current_rate:
                stage_eta = remaining / current_rate

        # Short QD1 benchmarks must never be extrapolated to terabytes. Full
        # passes provide the estimate; unmeasured directions are provisional.
        full_rates = {i: rate for i, rate in self.rates.items() if i in (2, 3, 5) and rate > 0}
        fallback = (current_rate if index in (2, 3, 5) and current_rate else
                    next(reversed(full_rates.values()), None))
        overall_eta = None
        provisional = False
        if not failed and fallback:
            remaining_time = 0
            for i, row in enumerate(states):
                if row['status'] == 'PASS':
                    continue
                remaining = max(0, self.expected[i] - row['bytes'])
                if i == index and current_rate:
                    rate = current_rate
                elif i in (3, 5) and (5 in full_rates or 3 in full_rates):
                    rate = full_rates.get(5, full_rates.get(3))
                    provisional = True
                elif i in full_rates:
                    rate = full_rates[i]
                    provisional = True
                else:
                    rate = fallback
                    provisional = True
                remaining_time += remaining / rate
            overall_eta = remaining_time
        if passed:
            overall_eta = 0 if final_status in ('PASS', 'WARNING') else None
        if failed:
            overall_eta = stage_eta = None
        done = sum(min(self.expected[i], max(0, row['bytes'])) for i, row in enumerate(states))
        total = sum(self.expected)
        return {'stage': current or phase or 'Başlangıç kontrolleri',
                'stage_index': index, 'stage_states': states,
                'stage_elapsed_seconds': stage_elapsed,
                'stage_eta_seconds': stage_eta, 'eta_seconds': stage_eta,
                'overall_eta_seconds': overall_eta,
                'overall_eta_provisional': provisional,
                'overall_percent': min(100, done*100/total),
                'elapsed_seconds': elapsed,
                'percent': (min(100, states[index]['bytes']*100/self.expected[index])
                            if index is not None else None),
                'stage_bytes': states[index]['bytes'] if index is not None else 0,
                'stage_expected_bytes': self.expected[index] if index is not None else 0,
                'final_status': final_status}

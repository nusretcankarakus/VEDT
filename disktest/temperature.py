"""Summaries use only real sensor acquisitions, never cached display samples."""
def statistics(samples):
    values = [s['temperature_c'] for s in samples if type(s.get('temperature_c')) in (int, float)]
    return {'count': len(values), 'minimum_c': min(values) if values else None,
            'maximum_c': max(values) if values else None,
            'average_c': round(sum(values) / len(values), 2) if values else None}


def summarize(samples):
    names = dict.fromkeys(s['stage'] for s in samples if s.get('stage'))
    return {'overall': statistics(samples),
            'idle': statistics([s for s in samples if s['phase'] == 'boşta']),
            'load': statistics([s for s in samples if s['phase'] == 'yük']),
            'stages': {name: statistics([s for s in samples if s.get('stage') == name]) for name in names},
            'method': 'Gerçek sensör okumalarının aritmetik ortalaması; ekranda yinelenen değerler sayılmaz.'}

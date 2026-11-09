"""Read-only link metadata from smartctl and the pinned device sysfs path."""
from pathlib import Path
import re


def connection_info(path, smart, sys_root=Path('/sys')):
    raw = smart.get('raw', {})
    result = {'protocol': raw.get('device', {}).get('protocol') or 'Bilgi alınamadı',
              'sata_current': None, 'sata_maximum': None, 'pcie_current_speed': None,
              'pcie_current_width': None, 'pcie_maximum_speed': None, 'pcie_maximum_width': None,
              'source': 'smartctl / Linux sysfs (salt okunur)',
              'note': 'Bağlantı hızı gerçek disk aktarım hızı değildir. PCIe bilgisi en yakın denetleyiciye aittir; RAID/köprü arkasındaki diski tek başına tanımlamaz.'}
    speed = raw.get('interface_speed', {})
    for src, dst in [('current', 'sata_current'), ('max', 'sata_maximum')]:
        value = speed.get(src, {})
        if isinstance(value, dict) and isinstance(value.get('string'), str):result[dst] = value['string'][:120]
    try:
        name = Path(path).name
        if not re.fullmatch(r'[A-Za-z0-9_.!-]+', name): return result
        device = (Path(sys_root)/'class/block'/name/'device').resolve(strict=True)
        root = Path(sys_root).resolve()
        if not device.is_relative_to(root):return result
        for node in [device, *device.parents]:
            if node == root:break
            if re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]', node.name):
                result['pcie_controller'] = node.name
                for src, dst in [('current_link_speed','pcie_current_speed'),('current_link_width','pcie_current_width'),
                                 ('max_link_speed','pcie_maximum_speed'),('max_link_width','pcie_maximum_width')]:
                    try:
                        value = (node/src).read_text(encoding='utf-8').strip()[:120]
                        if dst.endswith('width'):
                            if value in {'1','2','4','8','12','16','32'}:result[dst] = value
                        elif re.fullmatch(r'[0-9]+(?:\.[0-9]+)? GT/s(?: PCIe)?', value) and float(value.split()[0]) > 0:
                            result[dst] = value
                    except (OSError, ValueError):pass
                break
    except (OSError, RuntimeError, ValueError):pass
    return result

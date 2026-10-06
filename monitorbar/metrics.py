"""Read Linux counters without root. Missing readings are None, never fake zeroes."""
import csv
import io
import json
import math
from pathlib import Path
import shutil
import subprocess


def percent(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and 0 <= result <= 100 else None
    except (ValueError, TypeError):
        return None


def cpu_ticks(text):
    line = next(line for line in text.splitlines() if line.startswith('cpu '))
    ticks = [int(x) for x in line.split()[1:9]]  # guest already included in user/nice
    if len(ticks) < 4 or min(ticks) < 0:
        raise ValueError('Invalid CPU counters')
    return sum(ticks), ticks[3] + (ticks[4] if len(ticks) > 4 else 0)


def ram_percent(text):
    fields = {line.split(':')[0]: int(line.split(':')[1].split()[0])
              for line in text.splitlines() if ':' in line}
    total = fields.get('MemTotal', 0)
    available = fields.get('MemAvailable')
    if not total or available is None:
        return None
    return percent((total - available) * 100 / total)


class SystemMetrics:
    def __init__(self, proc=Path('/proc')):
        self.proc = Path(proc)
        self.previous = None

    def sample(self):
        cpu = ram = None
        try:
            current = cpu_ticks((self.proc / 'stat').read_text())
            if self.previous:
                total = current[0] - self.previous[0]
                idle = current[1] - self.previous[1]
                if total > 0 and 0 <= idle <= total:
                    cpu = percent(100 * (total - idle) / total)
            self.previous = current
        except (OSError, ValueError, StopIteration):
            self.previous = None
        try:
            ram = ram_percent((self.proc / 'meminfo').read_text())
        except (OSError, ValueError, IndexError):
            pass
        return {'CPU': cpu, 'RAM': ram}


def run(command, timeout=1.5):
    return subprocess.run(command, capture_output=True, text=True,
                          timeout=timeout, check=False)


def discover_gpus(drm=Path('/sys/class/drm')):
    devices = []
    if shutil.which('nvidia-smi'):
        try:
            result = run(['nvidia-smi', '--query-gpu=uuid,name', '--format=csv,noheader'])
            if result.returncode == 0:
                for row in csv.reader(io.StringIO(result.stdout)):
                    if len(row) == 2 and row[0].strip().startswith('GPU-'):
                        devices.append({'id': row[0].strip(), 'name': row[1].strip(),
                                        'backend': 'nvidia'})
        except (OSError, subprocess.TimeoutExpired):
            pass
    for card in sorted(Path(drm).glob('card[0-9]*')):
        if not card.name[4:].isdigit():
            continue
        try:
            vendor = (card / 'device/vendor').read_text().strip()
            busy = card / 'device/gpu_busy_percent'
            if busy.exists():
                devices.append({'id': str(card), 'name': f'{card.name} (GPU sysfs)',
                                'backend': 'sysfs', 'path': str(busy)})
            elif vendor == '0x8086':
                devices.append({'id': str(card), 'name': f'Intel {card.name}',
                                'backend': 'intel', 'device': f'/dev/dri/{card.name}'})
        except OSError:
            continue
    return devices


def intel_percent(output):
    """intel_gpu_top may end mid-JSON when its sampling timeout expires."""
    decoder = json.JSONDecoder()
    readings = []
    pos = 0
    while pos < len(output):
        start = output.find('{', pos)
        if start < 0:
            break
        try:
            item, end = decoder.raw_decode(output[start:])
            pos = start + end
        except ValueError:
            pos = start + 1
            continue
        if isinstance(item, dict) and isinstance(item.get('engines'), dict):
            values = [percent(engine.get('busy')) for engine in item['engines'].values()
                      if isinstance(engine, dict)]
            values = [value for value in values if value is not None]
            if values:
                readings.append(max(values))
    return readings[-1] if readings else None


def gpu_sample(device):
    if not device:
        return None, 'Aucun GPU compatible détecté. Voir README : pilotes GPU.'
    try:
        if device['backend'] == 'sysfs':
            value = percent(Path(device['path']).read_text().strip())
        elif device['backend'] == 'nvidia':
            result = run(['nvidia-smi', '-i', device['id'], '--query-gpu=utilization.gpu',
                          '--format=csv,noheader,nounits'])
            value = percent(result.stdout.strip()) if result.returncode == 0 else None
        else:
            if not shutil.which('intel_gpu_top'):
                return None, 'Intel : installer intel-gpu-tools (voir README).'
            command = ['intel_gpu_top', '-J', '-s', '500', '-d',
                       'drm:' + device['device'], '-o', '-']
            try:
                result = run(command, timeout=1.7)
                output = result.stdout
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout or b''
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='replace')
            value = intel_percent(output)
        if value is None:
            return None, device['name'] + ' : mesure indisponible (pilote ou permissions).'
        suffix = ' — moteur le plus occupé' if device['backend'] == 'intel' else ''
        return value, device['name'] + suffix
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return None, device.get('name', 'GPU') + ' : mesure indisponible.'

"""Validated, atomic per-user preferences."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile

KEYS = ['CPU', 'RAM', 'GPU']
DEFAULTS = dict(scale=1.0, spacing=16, opacity=.35, background=False, locked=False,
                snap=True, load_colors=False, icons=False, neon=False, layout=0,
                indicators=KEYS, graphs=[], colors={key: '#34c759' for key in KEYS},
                position=None, gpu=None)


def normalize(raw):
    result = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return result
    for key in ('background', 'locked', 'snap', 'load_colors', 'icons', 'neon'):
        if isinstance(raw.get(key), bool):
            result[key] = raw[key]
    for key, low, high in [('scale', .6, 2.5), ('spacing', 0, 80), ('opacity', 0, 1)]:
        value = raw.get(key)
        if type(value) in (int, float) and math.isfinite(value):
            result[key] = max(low, min(high, value))
    if type(raw.get('layout')) is int and raw['layout'] in (0, 1, 2):
        result['layout'] = raw['layout']
    for key in ('indicators', 'graphs'):
        if isinstance(raw.get(key), list):
            value = list(dict.fromkeys(v for v in raw[key] if isinstance(v, str) and v in KEYS))
            if value or key == 'graphs':
                result[key] = value
    if isinstance(raw.get('colors'), dict):
        for key in KEYS:
            value = raw['colors'].get(key)
            if isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                result['colors'][key] = value
    position = raw.get('position')
    if isinstance(position, list) and len(position) == 2 and all(type(v) is int and abs(v) < 100000 for v in position):
        result['position'] = position
    if isinstance(raw.get('gpu'), str):
        result['gpu'] = raw['gpu']
    return result


def config_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'monitorbar/settings.json'


def load(path=None):
    try:
        return normalize((json.loads((path or config_path()).read_text())))
    except (OSError, ValueError):
        return normalize({})


def save(settings, path=None):
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(normalize(settings), stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()

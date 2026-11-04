"""The application taxonomy is the only permitted technical label vocabulary."""
import json
import re
from functools import lru_cache

from .local_model import model_directory


@lru_cache(maxsize=4)
def _read(path, modified):
    with open(path, encoding='utf-8') as source:
        return tuple(value[0] for value in json.load(source)['technical'])


def allowed_technical_fields():
    path = model_directory()/'taxonomy.json'
    return _read(str(path), path.stat().st_mtime_ns)


def selection(value):
    names = list(dict.fromkeys(v.strip() for v in re.split(r'[·,;\n]', value or '') if v.strip()))
    if not names or names == ['미분류']:
        return []
    if len(names) > 3 or any(name not in allowed_technical_fields() for name in names):
        raise ValueError('INVALID_TECHNICAL_SELECTION')
    return names


def validate_row_fields(row):
    """Validate at every import/reanalysis DB boundary, including explicit cells."""
    allowed = allowed_technical_fields()
    if row.technical_field not in ('', None, '미분류') and row.technical_field not in allowed:
        raise ValueError('INVALID_TECHNICAL_SELECTION')
    names = [v.get('name') for v in row.technical_fields]
    if len(names) > 3 or len(names) != len(set(names)) or any(name not in allowed for name in names):
        raise ValueError('INVALID_TECHNICAL_SELECTION')
    if names and row.technical_field != names[0]:
        raise ValueError('TECHNICAL_PRIMARY_MISMATCH')

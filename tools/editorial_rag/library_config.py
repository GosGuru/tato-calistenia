"""Public, bounded library configuration; no environment or credential discovery."""
import re
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from .supabase_reader import PROJECT_REF, _json, _uuid
else:
    from supabase_reader import PROJECT_REF, _json, _uuid

PROJECT_URL = 'https://' + PROJECT_REF + '.supabase.co'
DEFAULT_PATH = Path('C:/Users/Maxim/AppData/Local/TatoEditorialRag/library-config.json')
MAX_BYTES = 8192


class ConfigError(RuntimeError):
    """Content-free configuration failure."""


@dataclass(frozen=True, repr=False)
class LibraryConfig:
    version: int
    project_url: str
    publishable_key: str
    owner_id: str

    def __post_init__(self):
        if (type(self.version) is not int or self.version != 1
                or self.project_url != PROJECT_URL
                or type(self.publishable_key) is not str
                or not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{1,256}', self.publishable_key)):
            raise ValueError('Invalid public configuration')
        _uuid(self.owner_id)


def _load(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError
    obj = _json(data.decode('utf-8'))
    if type(obj) is not dict or set(obj) != {'version', 'project_url', 'publishable_key', 'owner_id'}:
        raise ValueError
    return LibraryConfig(**obj)


def load_config(path=DEFAULT_PATH):
    """Trusted path only. Sanitize traceback retention, not secure memory erasure."""
    try:
        return _load(path)
    except Exception:
        del path
    raise ConfigError('Editorial library configuration unavailable or rejected')

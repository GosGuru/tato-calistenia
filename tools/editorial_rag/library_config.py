"""Public, bounded library configuration from explicit local or injected sources."""
import os
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
# Managed deployment injection. These hold the same bounded public fields as the file.
ENV_PUBLISHABLE_KEY = 'TATO_LIBRARY_PUBLISHABLE_KEY'
ENV_OWNER_ID = 'TATO_LIBRARY_OWNER_ID'
ENV_MAX_CHARS = 512


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


def env_config():
    """Explicit managed-deployment source; the local file stays the only default.

    Absent or invalid variables fail closed instead of falling back. No user
    credential is read here: the publishable key is public by design and the
    owner is an opaque project UUID, both bounded before validation.
    """
    publishable_key = str(os.environ.get(ENV_PUBLISHABLE_KEY, ''))[:ENV_MAX_CHARS].strip()
    owner_id = str(os.environ.get(ENV_OWNER_ID, ''))[:ENV_MAX_CHARS].strip()
    try:
        return LibraryConfig(version=1, project_url=PROJECT_URL,
                             publishable_key=publishable_key, owner_id=owner_id)
    except Exception:
        del publishable_key, owner_id
    raise ConfigError('Editorial library configuration unavailable or rejected')

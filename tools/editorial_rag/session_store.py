"""Opt-in current-user DPAPI store. No default path or import-time I/O."""
import ctypes
import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from .library_config import LibraryConfig
from .supabase_reader import _json

MAX_BYTES = 32768


def valid_refresh(token):
    return (type(token) is str and 1 <= len(token) <= 4096
            and all(33 <= ord(char) <= 126 for char in token))


def _dpapi(data, decrypt=False):
    if os.name != 'nt' or type(data) is not bytes or not 1 <= len(data) <= MAX_BYTES:
        raise ValueError('Session protection unavailable')
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    try:
        # UI forbidden; deliberately no CRYPTPROTECT_LOCAL_MACHINE flag.
        if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise ValueError('Session protection unavailable')
        if not 1 <= target.size <= MAX_BYTES:
            raise ValueError('Session protection unavailable')
        return ctypes.string_at(target.data, target.size)
    finally:
        if target.data:
            kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class SessionStore:
    """Trusted explicit path and binding; public methods expose no file/secret errors."""
    def __init__(self, path, config, *, protect=None, unprotect=None):
        if type(config) is not LibraryConfig:
            raise ValueError('Validated configuration required')
        config.__post_init__()
        self.path, self.config = Path(path), config
        self.protect = protect or _dpapi
        self.unprotect = unprotect or (lambda data: _dpapi(data, decrypt=True))

    def _safe_path(self):
        # Refuse symlinks/junctions, including any redirected ancestor.
        return self.path.is_absolute() and self.path.resolve() == self.path.absolute()

    def save(self, token):
        temporary = None
        try:
            if not valid_refresh(token) or not self._safe_path():
                return False
            data = json.dumps({'version': 1, 'project': self.config.project_url,
                               'owner': self.config.owner_id, 'refresh': token}, separators=(',', ':')).encode()
            encrypted = self.protect(data)
            if type(encrypted) is not bytes or not 1 <= len(encrypted) <= MAX_BYTES:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.session-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return True
        except Exception:
            return False
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)

    def load(self):
        try:
            if not self._safe_path():
                return None
            with self.path.open('rb') as stream:
                encrypted = stream.read(MAX_BYTES + 1)
            if not 1 <= len(encrypted) <= MAX_BYTES:
                return None
            data = self.unprotect(encrypted)
            if type(data) is not bytes or not 1 <= len(data) <= MAX_BYTES:
                return None
            payload = _json(data)
            if (type(payload) is not dict or set(payload) != {'version', 'project', 'owner', 'refresh'}
                    or type(payload['version']) is not int or payload['version'] != 1
                    or payload['project'] != self.config.project_url or payload['owner'] != self.config.owner_id
                    or not valid_refresh(payload['refresh'])):
                return None
            return payload['refresh']
        except Exception:
            return None

    def clear(self):
        try:
            if not self._safe_path():
                return False
            self.path.unlink(missing_ok=True)
            return True
        except Exception:
            return False


class EnvSessionStore:
    """In-memory equivalent of the persisted session for a deployment credential.

    Implements the same ``config``/``load``/``save``/``clear`` surface as
    ``SessionStore`` so ``AppAuth`` composes unchanged and every owner, project
    and authenticated RLS check still runs. It never touches disk: the
    deployment environment supplies the seed credential and rotation is held in
    memory for the life of the process only. No credential value is logged,
    printed, returned or placed in an exception message; failures stay fixed and
    content-free.
    """
    def __init__(self, config, token=None):
        if type(config) is not LibraryConfig:
            raise ValueError('Validated configuration required')
        config.__post_init__()
        if token is not None and not valid_refresh(token):
            raise ValueError('Validated refresh credential required')
        self.config = config
        self._token = token

    def load(self):
        return self._token if valid_refresh(self._token) else None

    def save(self, token):
        if not valid_refresh(token):
            return False
        self._token = token
        return True

    def clear(self):
        self._token = None
        return True

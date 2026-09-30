"""Editorial session with optional explicitly injected current-user persistence."""
import threading

from . import supabase_auth
from .editorial_library import read_library
from .library_config import load_config
from .supabase_auth import sign_in
from .supabase_reader import _claims


class AppAuth:
    def __init__(self, store=None):
        self._store = store
        self._lock = threading.RLock()
        self._login_lock = threading.Lock()
        self._revision = 0
        self._jwt = None
        self._config = None
        self._count = 0
        self._expired = False
        self._refresh = None
        self._remembered = False
        self._problem = False
        self._restore_attempted = False

    def persistence(self):
        with self._lock:
            return {'enabled': self._store is not None,
                    'remembered': self._remembered, 'problem': self._problem}

    def _clear(self):
        self._jwt = self._config = None
        self._count = 0
        self._expired = False

    def _forget(self):
        self._refresh = None
        self._remembered = False
        if self._store is not None:
            try:
                self._problem = not self._store.clear()
            except Exception:
                self._problem = True

    def _expire(self):
        if self._jwt is not None:
            try:
                config = self._config
                if config is None or _claims(self._jwt, config.project_url) != config.owner_id:
                    raise ValueError
                return
            except Exception:
                self._clear()
                self._expired = True

    def _accept(self, revision, jwt, config, refresh):
        if _claims(jwt, config.project_url) != config.owner_id:
            return False
        rows = read_library(jwt, config)
        # Supabase's authenticated RLS read verifies signatures, unlike local claims.
        if _claims(jwt, config.project_url) != config.owner_id:
            return False
        with self._lock:
            if revision != self._revision:
                return False
            self._jwt, self._config, self._count = jwt, config, len(rows)
            self._expired = False
            self._refresh = refresh
            if self._store is not None:
                try:
                    self._remembered = bool(self._store.save(refresh))
                except Exception:
                    self._remembered = False
                self._problem = not self._remembered
                if not self._remembered:
                    # Do not leave a previous refresh credential eligible for restore.
                    self._forget()
                    self._problem = True
            return True

    def login(self, email, password):
        if not self._login_lock.acquire(blocking=False):
            return False
        try:
            with self._lock:
                self._revision += 1
                revision = self._revision
                self._clear()
                self._forget()
            config = self._store.config if self._store is not None else load_config()
            if self._store is None:
                jwt, refresh = sign_in(email, password, config=config), None
            else:
                jwt, refresh = supabase_auth.sign_in_session(email, password, config=config)
            return self._accept(revision, jwt, config, refresh)
        except Exception:
            return False
        finally:
            self._login_lock.release()

    def restore(self):
        """At most one startup attempt. File presence never implies authentication."""
        with self._lock:
            if self._store is None or self._restore_attempted:
                return False
            self._restore_attempted = True
        return self._renew(startup=True)

    def _renew(self, startup=False):
        store = self._store
        if store is None or not self._login_lock.acquire(blocking=False):
            return False
        revision = None
        accepted = False
        try:
            with self._lock:
                self._revision += 1
                revision = self._revision
                self._clear()
                refresh = store.load() if startup else self._refresh
                self._refresh = None
                self._remembered = False
            if refresh is None:
                return False
            config = store.config
            jwt, rotated = supabase_auth.refresh_session(refresh, config=config)
            accepted = self._accept(revision, jwt, config, rotated)
            return accepted
        except Exception:
            return False
        finally:
            with self._lock:
                if not accepted and revision == self._revision:
                    self._forget()
            self._login_lock.release()

    def logout(self):
        with self._lock:
            self._revision += 1
            self._restore_attempted = True
            self._clear()
            self._forget()

    def snapshot(self):
        with self._lock:
            self._expire()
            renew = self._expired and self._refresh is not None
        # Only an explicit generation snapshot can renew an expired session.
        # Passive status never waits for network or starts a refresh/model call.
        if renew:
            self._renew()
        with self._lock:
            state = 'connected' if self._jwt is not None else 'expired' if self._expired else 'off'
            return self._revision, state, self._jwt, self._config

    def current(self, revision, require_connected=False):
        with self._lock:
            self._expire()
            return revision == self._revision and (not require_connected or self._jwt is not None)

    def status(self):
        with self._lock:
            self._expire()
            connected = self._jwt is not None
            return {'connected': connected, 'empty': connected and self._count == 0,
                    'count': self._count, 'revision': self._revision}

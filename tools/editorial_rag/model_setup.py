"""Explicit, pinned asset setup. Importing this module never downloads.

``TATO_LIBRARY_MODEL_DIR`` (optional, single override) points at the models
root under which the pinned ``<model>/<revision>`` assets live; ``CACHE``
resolves to ``<root>/<model>/<revision>``. When the variable is unset or not a
non-empty string, ``CACHE`` keeps the original Windows default and local runs
are unchanged. ``SPEC`` and ``verify_cache`` keep their pinned semantics: every
asset is still checked against its manifest size and hash and setup still
fails closed when any asset is absent or mismatched. The value is a plain path
string and is never logged or printed.

Each asset download is retried a bounded number of times because a long
transfer can be cut by a transient network failure; every attempt is verified
against the pinned size and hash before publishing, so retries can never
introduce unverified bytes.

Public errors stay fixed and content-free. So a failed build can say what broke,
one extra JSON line goes to stderr before each failure and each retry: the
manifest-relative asset name and the check that failed, plus small facts such
as sizes, an HTTP status or an errno. That line never carries a URL, a redirect
target, a token, the model-directory value or any exception message.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

try:
    SPEC = json.loads((Path(__file__).parent / 'embedding_node/model_manifest.json').read_text(encoding='utf-8'))
except (OSError, ValueError):
    raise RuntimeError('model_manifest_unavailable') from None
ENV_MODEL_DIR = 'TATO_LIBRARY_MODEL_DIR'
DEFAULT_MODEL_DIR = Path('C:/Users/Maxim/AppData/Local/TatoEditorialRag/models')
DOWNLOAD_ATTEMPTS = 3
RETRY_BACKOFF = (3.0, 7.0)


def model_root(environ=os.environ):
    """Models root from the single optional override; default behaviour unchanged."""
    value = environ.get(ENV_MODEL_DIR)
    if type(value) is not str or not value:
        return DEFAULT_MODEL_DIR
    return Path(value)


CACHE = model_root() / SPEC['model'] / SPEC['revision']


class SetupError(RuntimeError):
    """Fixed, content-free setup failure."""

    reported = False
    check: str = ''
    facts: tuple = ()


class UnsafeRedirect(Exception):
    """A redirect left HTTPS and the TLS-only handler rejected it."""


# The only values the diagnostic line may carry besides the asset name.
SAFE_FACTS = ('check', 'hash_kind', 'expected_size', 'actual_size', 'http_status', 'errno',
              'error', 'found', 'attempt', 'attempts', 'failed')


def detail(asset, **facts):
    """One safe stderr line: asset name, check kind and small facts only."""
    payload = {'type': 'setup_detail', 'asset': str(asset)}
    payload.update({key: value for key, value in facts.items() if key in SAFE_FACTS})
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _error(message, check, **facts) -> SetupError:
    """Fixed error carrying only its safe check identity for the retry policy."""
    error = SetupError(message)
    error.check = check
    error.facts = tuple((key, value) for key, value in facts.items() if key in SAFE_FACTS)
    return error


def fail(message, asset=None, **facts) -> NoReturn:
    """Report the failing asset and check, then raise the fixed error."""
    if asset is not None:
        detail(asset, **facts)
    error = SetupError(message)
    error.reported = True
    raise error


def file_check(path, spec):
    """``'ok'`` or the pinned check this file fails; a name, never file content."""
    try:
        if path.is_symlink():
            return 'symlink'
        if not path.is_file():
            return 'missing'
        if path.stat().st_size != spec['size']:
            return 'size_mismatch'
        # Git publishes SHA-1 blob IDs for these three small metadata files.
        # This is identity compatibility over pinned TLS assets, not password hashing.
        # The tokenizer and weights use their published SHA-256 digests.
        digest = hashlib.sha256() if spec['hash_kind'] == 'sha256' else hashlib.new('sha1', usedforsecurity=False)
        if spec['hash_kind'] == 'git_blob_sha1':
            digest.update(b'blob ' + str(spec['size']).encode('ascii') + b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return 'ok' if digest.hexdigest() == spec['hash'] else 'hash_mismatch'
    except OSError:
        return 'unreadable'


def valid_file(path, spec):
    return file_check(path, spec) == 'ok'


class TLSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise UnsafeRedirect
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_download(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), TLSRedirect())
    return opener.open(url, timeout=30)


def download_once(target, spec) -> int:
    """One full attempt: download into a partial file, verify, then publish."""
    partial = target.with_name(target.name + '.partial')
    owned = False
    try:
        with partial.open('xb') as output:
            owned = True
            url = f"https://huggingface.co/{SPEC['model']}/resolve/{SPEC['revision']}/{spec['path']}"
            started = time.monotonic()
            total = 0
            with open_download(url) as response:
                while True:
                    if time.monotonic() - started > 600:
                        raise _error('model_setup_failed', 'download_time_budget', actual_size=total)
                    block = response.read(min(1024 * 1024, spec['size'] - total + 1))
                    if not block:
                        break
                    total += len(block)
                    if total > spec['size']:
                        raise _error('model_setup_failed', 'size_overflow',
                                     expected_size=spec['size'], actual_size=total)
                    output.write(block)
        state = file_check(partial, spec)
        if state != 'ok':
            try:
                actual = partial.stat().st_size
            except OSError:
                actual = -1
            raise _error('model_setup_failed', state, hash_kind=spec['hash_kind'],
                         expected_size=spec['size'], actual_size=actual)
        os.replace(partial, target)
        return total
    except SetupError:
        raise
    except UnsafeRedirect:
        raise _error('model_setup_failed', 'redirect_not_https') from None
    except urllib.error.HTTPError as exc:
        raise _error('model_setup_failed', 'download_http_error', http_status=exc.code) from None
    except urllib.error.URLError as exc:
        raise _error('model_setup_failed', 'download_transport_error',
                     error=type(exc.reason).__name__) from None
    except TimeoutError:
        raise _error('model_setup_failed', 'download_timeout') from None
    except OSError as exc:
        raise _error('model_setup_failed', 'io_error', errno=exc.errno) from None
    except Exception as exc:
        raise _error('model_setup_failed', 'download_error', error=type(exc).__name__) from None
    finally:
        if owned and partial.exists():
            partial.unlink()


def install_file(root, spec) -> int:
    target = root / spec['path']
    state = file_check(target, spec)
    if state == 'ok':
        return 0
    # Never load or overwrite corrupt existing assets silently.
    if target.exists() or target.is_symlink():
        fail('model_setup_failed', spec['path'], check='existing_asset_invalid', found=state)
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            return download_once(target, spec)
        except SetupError as error:
            if attempt >= DOWNLOAD_ATTEMPTS:
                fail('model_setup_failed', spec['path'], check=error.check,
                     attempts=attempt, **dict(error.facts))
            detail(spec['path'], check='download_retry', attempt=attempt, failed=error.check)
            time.sleep(RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)])
    # Unreachable: the last attempt either publishes or fails above.
    fail('model_setup_failed', spec['path'], check='attempts_exhausted', attempts=DOWNLOAD_ATTEMPTS)


def verify_cache(root=CACHE):
    for item in SPEC['files']:
        state = file_check(root / item['path'], item)
        if state != 'ok':
            fail('model_assets_unavailable', item['path'], check=state, hash_kind=item['hash_kind'],
                 expected_size=item['size'])


def main():
    try:
        downloaded = sum(install_file(CACHE, item) for item in SPEC['files'])
        verify_cache()
        print(json.dumps({'type': 'setup', 'downloaded_bytes': downloaded, 'asset_bytes': 135392183, 'revision': SPEC['revision']}))
        return 0
    except Exception as exc:
        if not getattr(exc, 'reported', False):
            detail('model_setup', check='unclassified_error', error=type(exc).__name__)
        print('{"type":"error","code":"model_setup_failed"}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())

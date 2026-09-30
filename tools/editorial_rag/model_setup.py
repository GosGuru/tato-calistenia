"""Explicit, pinned asset setup. Importing this module never downloads."""
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

try:
    SPEC = json.loads((Path(__file__).parent / 'embedding_node/model_manifest.json').read_text(encoding='utf-8'))
except (OSError, ValueError):
    raise RuntimeError('model_manifest_unavailable') from None
CACHE = Path('C:/Users/Maxim/AppData/Local/TatoEditorialRag/models') / SPEC['model'] / SPEC['revision']


class SetupError(RuntimeError):
    """Fixed, content-free setup failure."""


def valid_file(path, spec):
    try:
        if path.is_symlink() or path.stat().st_size != spec['size']:
            return False
        # Git publishes SHA-1 blob IDs for these three small metadata files.
        # This is identity compatibility over pinned TLS assets, not password hashing.
        # The tokenizer and weights use their published SHA-256 digests.
        digest = hashlib.sha256() if spec['hash_kind'] == 'sha256' else hashlib.new('sha1', usedforsecurity=False)
        if spec['hash_kind'] == 'git_blob_sha1':
            digest.update(b'blob ' + str(spec['size']).encode('ascii') + b'\0')
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest() == spec['hash']
    except OSError:
        return False


class TLSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise SetupError('model_setup_failed')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_download(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), TLSRedirect())
    return opener.open(url, timeout=30)


def install_file(root, spec):
    target = root / spec['path']
    if valid_file(target, spec):
        return 0
    # Never load or overwrite corrupt existing assets silently.
    if target.exists() or target.is_symlink():
        raise SetupError('model_setup_failed')
    target.parent.mkdir(parents=True, exist_ok=True)
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
                        raise SetupError('model_setup_failed')
                    block = response.read(min(1024 * 1024, spec['size'] - total + 1))
                    if not block:
                        break
                    total += len(block)
                    if total > spec['size']:
                        raise SetupError('model_setup_failed')
                    output.write(block)
        if not valid_file(partial, spec):
            raise SetupError('model_setup_failed')
        os.replace(partial, target)
        return total
    except Exception:
        raise SetupError('model_setup_failed') from None
    finally:
        if owned and partial.exists():
            partial.unlink()


def verify_cache(root=CACHE):
    if not all(valid_file(root / item['path'], item) for item in SPEC['files']):
        raise SetupError('model_assets_unavailable')


def main():
    try:
        downloaded = sum(install_file(CACHE, item) for item in SPEC['files'])
        verify_cache()
        print(json.dumps({'type': 'setup', 'downloaded_bytes': downloaded, 'asset_bytes': 135392183, 'revision': SPEC['revision']}))
        return 0
    except Exception:
        print('{"type":"error","code":"model_setup_failed"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

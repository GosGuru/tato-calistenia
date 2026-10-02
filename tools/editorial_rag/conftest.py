"""Pytest bootstrap for tools/editorial_rag; replaces the previously hand-rolled invocation.

The repository has no ``pytest.ini`` and this directory mixes three import styles
(package-relative, ``tools.editorial_rag.*`` and bare ``prototype``), while
``api_runner.test_provider_connection`` is a production helper that pytest mis-collects
because ``test_api_runner.py`` imports it by name. This conftest makes a plain

    python -m pytest tools/editorial_rag

work like the old hand-rolled command:

- puts the repository root, this directory and the venv site-packages (``fastapi``) on
  ``sys.path``, then pre-imports ``prototype`` so ``from prototype import ...`` resolves;
- forces ``--import-mode=importlib`` with ``consider_namespace_packages`` so the existing
  relative imports in the test modules resolve; both are required by the mixed styles
  above and override any conflicting flag. This conftest is itself first imported in
  prepend mode, which leaves this directory on ``sys.path``; that would make pytest
  resolve the test modules as top-level names, so the forced mode also drops this
  directory from ``sys.path`` again. The repository root stays, so
  ``tools.editorial_rag.*`` keeps working;
- drops only the mis-collected node ``test_api_runner.py::test_provider_connection``,
  the same scope as the old ``--deselect``. Production code is never modified.

No test, source or dependency is changed by this file.
"""
import importlib
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_VENV_SITE = _HERE / '.venv' / 'Lib' / 'site-packages'
_MISCOLLECTED = 'test_provider_connection'


def _bootstrap_paths():
    sys.path.insert(0, str(_VENV_SITE))
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_HERE))
    importlib.import_module('prototype')
    sys.path.remove(str(_HERE))


_bootstrap_paths()


def _force_import_mode(config):
    # config.getoption("--import-mode") resolves dest "importmode" at import time;
    # config.getini("consider_namespace_packages") reads the cached ini value first.
    config.option.importmode = 'importlib'
    config._inicache['consider_namespace_packages'] = True
    # Prepend-mode conftest import leaves this directory on sys.path, which makes the
    # namespace resolution pick top-level names and breaks the tests' relative imports.
    sys.path[:] = [entry for entry in sys.path if entry != str(_HERE)]


def pytest_configure(config):
    _force_import_mode(config)


def pytest_collectstart(collector):
    # Fallback for runs that collect this directory without passing it as an argument.
    _force_import_mode(collector.config)


def pytest_collection_modifyitems(items):
    items[:] = [item for item in items
                if not (item.name == _MISCOLLECTED
                        and Path(str(item.path)).name == 'test_api_runner.py')]

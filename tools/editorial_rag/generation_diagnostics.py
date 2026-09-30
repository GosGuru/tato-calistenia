"""Bounded request-local metadata; never retain exception or input objects."""
import math
import subprocess
import time
from contextlib import contextmanager

STAGES = ('retrieval', 'rules', 'packet', 'login', 'exec', 'stream', 'raw_result')
OUTCOMES = frozenset(('ok', 'not_run', 'timeout', 'unavailable', 'rejected',
                      'nonzero', 'invalid', 'internal'))


class GenerationDiagnostics:
    def __init__(self):
        self.started = time.monotonic()
        self.values = {name: ['not_run', 0] for name in STAGES}
        self.exec_attempts = 0

    def outcome(self, stage, outcome):
        if stage not in STAGES or outcome not in OUTCOMES:
            raise ValueError('Invalid diagnostic enum')
        self.values[stage][0] = outcome

    def attempt_exec(self):
        if self.exec_attempts:
            raise ValueError('Exec already attempted')
        self.exec_attempts = 1

    @staticmethod
    def milliseconds(start):
        value = (time.monotonic() - start) * 1000
        return round(min(max(value, 0), 86400000), 3) if math.isfinite(value) else 0

    @contextmanager
    def stage(self, name):
        self.outcome(name, 'ok')
        start = time.monotonic()
        try:
            yield
        except subprocess.TimeoutExpired:
            self.outcome(name, 'timeout')
            raise
        except Exception:
            if self.values[name][0] == 'ok':
                self.outcome(name, 'invalid' if name in ('packet', 'stream', 'raw_result') else 'internal')
            raise
        finally:
            self.values[name][1] = min(86400000, self.values[name][1] + self.milliseconds(start))

    def headers(self, fallback='ok'):
        if fallback not in OUTCOMES:
            raise ValueError('Invalid diagnostic enum')
        total = next((value[0] for value in self.values.values()
                      if value[0] not in ('ok', 'not_run')), fallback)
        headers = {'X-Tato-Diagnostics': '1', 'X-Tato-Exec-Attempts': str(self.exec_attempts),
                   'X-Tato-Total-Outcome': total,
                   'X-Tato-Total-Ms': str(self.milliseconds(self.started))}
        for stage, (outcome, duration) in self.values.items():
            prefix = 'X-Tato-' + stage.replace('_', '-').title()
            headers[prefix + '-Outcome'] = outcome
            headers[prefix + '-Ms'] = str(duration)
        return headers

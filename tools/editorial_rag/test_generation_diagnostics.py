"""Content-free, request-local diagnostics contracts."""
import unittest
from tools.editorial_rag.generation_diagnostics import GenerationDiagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_closed_values_and_finite_timings(self):
        record = GenerationDiagnostics()
        with record.stage('retrieval'):
            pass
        record.attempt_exec()
        headers = record.headers()
        self.assertEqual(headers['X-Tato-Exec-Attempts'], '1')
        self.assertEqual(headers['X-Tato-Retrieval-Outcome'], 'ok')
        self.assertEqual(headers['X-Tato-Login-Outcome'], 'not_run')
        with self.assertRaises(ValueError):
            record.attempt_exec()
        with self.assertRaises(ValueError):
            record.outcome('login', 'secret sentinel')
        with self.assertRaises(ValueError):
            record.outcome('secret sentinel', 'ok')
        self.assertNotIn('secret sentinel', str(record.headers()))

    def test_failure_has_only_closed_outcome(self):
        record = GenerationDiagnostics()
        with self.assertRaises(ValueError):
            with record.stage('raw_result'):
                raise ValueError('secret sentinel')
        self.assertEqual(record.headers()['X-Tato-Raw-Result-Outcome'], 'invalid')
        self.assertNotIn('secret sentinel', str(vars(record)))

import json
import tempfile
import unittest
from pathlib import Path

if __package__:
    from .library_config import PROJECT_URL, ConfigError, LibraryConfig, load_config
else:
    from library_config import PROJECT_URL, ConfigError, LibraryConfig, load_config

OWNER = '11111111-1111-4111-8111-111111111111'

class ConfigTests(unittest.TestCase):
    def test_rejected_content_is_absent_from_loader_traceback(self):
        marker = 'fictional-accidental-secret'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'public.json'
            path.write_text(json.dumps({'password': marker}), encoding='utf-8')
            try:
                load_config(path)
            except ConfigError as exc:
                self.assertIsNone(exc.__context__)
                self.assertIsNone(exc.__cause__)
                tb = exc.__traceback__
                while tb:
                    if tb.tb_frame.f_code.co_name != 'test_rejected_content_is_absent_from_loader_traceback':
                        self.assertNotIn(marker, repr(tb.tb_frame.f_locals))
                    tb = tb.tb_next
            else:
                self.fail('Rejected configuration accepted')

    def test_bounded_strict_public_config(self):
        valid = {'version': 1, 'project_url': PROJECT_URL,
                 'publishable_key': 'sb_publishable_test', 'owner_id': OWNER}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'public.json'
            path.write_text(json.dumps(valid), encoding='utf-8')
            self.assertEqual(load_config(path), LibraryConfig(**valid))
            for text in ['{}', json.dumps(valid)[:-1] + ',"version":1}', json.dumps({**valid, 'extra': 1}), json.dumps({**valid, 'version': True}), json.dumps({**valid, 'project_url': PROJECT_URL+'/'}), json.dumps({**valid, 'publishable_key': 'secret'}), json.dumps({**valid, 'owner_id': 'bad'}), ' '*8193]:
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ConfigError):
                    load_config(path)

"""Pruebas de gobernanza sin escrituras ni fuentes privadas."""

import copy
import unittest
from unittest.mock import patch

import runtime_governance as g


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.sources = g.load_json(g.ROOT / g.SOURCES)
        self.ledger = {"version": 1, "records": []}
        self.fixtures = {"change", "no-change"}

    def record(self, key="rule-one"):
        return {
            "id": key,
            "status": "candidate",
            "kind": "general_rule",
            "owner": g.OWNERS["voz"],
            "principle": "Evitar conectores repetidos.",
            "scope": "Continuidades simples.",
            "exception": "Claridad necesaria.",
            "replaces": "Preferencia anterior por un conector uniforme.",
            "contrast": "Variar según intención, no sustituir sinónimos.",
            "change_case": "change",
            "no_change_case": "no-change",
            "previous": None,
            "replacement": None,
            "approval": None,
        }

    def validate(self):
        return g.validate(self.sources, self.ledger, self.fixtures)

    def test_repository_and_empty_ledger(self):
        self.assertEqual(self.validate(), [])
        self.assertEqual(g.validate_repository(), [])

    def test_candidate_and_promoted_states(self):
        r = self.record()
        self.ledger["records"] = [r]
        for status in ("candidate", "rejected"):
            r["status"] = status
            self.assertEqual(self.validate(), [])
        for status in ("approved", "applied", "reverted"):
            r["status"] = status
            self.assertTrue(self.validate())
            r["approval"] = {
                "by": "user",
                "decision": "explicit",
                "principle": r["principle"],
            }
            self.assertEqual(self.validate(), [])
            r["approval"] = None

    def test_malformed_fields_fail_closed(self):
        for field, value in (
            ("status", []),
            ("status", "active"),
            ("kind", "praise"),
            ("principle", " "),
            ("scope", 3),
            ("owner", "README.md"),
            ("previous", []),
            ("approval", True),
            ("extra", "x"),
            ("change_case", "missing"),
            ("no_change_case", "change"),
        ):
            with self.subTest(field=field, value=value):
                r = self.record()
                r[field] = value
                self.ledger["records"] = [r]
                self.assertTrue(self.validate())

    def test_exact_approval_not_praise(self):
        r = self.record()
        r.update(
            status="approved",
            approval={
                "by": "user",
                "decision": "explicit",
                "principle": "Otro principio",
            },
        )
        self.ledger["records"] = [r]
        self.assertTrue(self.validate())

    def test_links_pairs_and_cycles(self):
        a, b = self.record(), self.record("rule-two")
        a["replacement"], b["previous"] = b["id"], a["id"]
        self.ledger["records"] = [a, b]
        self.assertEqual(self.validate(), [])
        b["previous"] = None
        self.assertTrue(self.validate())
        b["previous"] = a["id"]
        b["replacement"], a["previous"] = a["id"], b["id"]
        self.assertTrue(self.validate())
        self.ledger["records"] = [a, a]
        self.assertTrue(self.validate())

    def test_path_guards(self):
        for path in (
            "/etc/passwd",
            "C:/private",
            "../outside",
            "a/../b",
            "a\\b",
            "a//b",
            "./README.md",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                g.safe_file(path)
        with (
            patch.object(g.Path, "is_symlink", return_value=True),
            self.assertRaises(ValueError),
        ):
            g.safe_file("README.md")
        with self.assertRaises(ValueError):
            g.safe_file("missing-governance-owner.md")

    def test_unknown_source_shapes_and_duplicates(self):
        original = copy.deepcopy(self.sources)
        for mutate in (
            lambda d: d.update(version=True),
            lambda d: d.update(extra=1),
            lambda d: d["owners"].update(voz="README.md"),
            lambda d: d["sources"].append(d["sources"][0]),
            lambda d: d["sources"][0].update(status="active"),
            lambda d: d["summaries"].append(d["summaries"][0]),
        ):
            self.sources = copy.deepcopy(original)
            mutate(self.sources)
            self.assertTrue(self.validate())
        for malformed in (None, [], {"version": 1, "records": [None]}):
            self.ledger = malformed
            self.assertTrue(self.validate())

    def test_json_duplicate_keys_and_constants_rejected(self):
        for raw in ('{"version":1,"version":1}', '{"value":NaN}', "[]"):
            with (
                self.subTest(raw=raw),
                patch.object(g.Path, "read_text", return_value=raw),
                self.assertRaises(ValueError),
            ):
                g.load_json(g.ROOT / g.SOURCES)


if __name__ == "__main__":
    unittest.main()

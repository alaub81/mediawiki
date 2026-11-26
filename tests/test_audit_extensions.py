"""Exercise audit completeness and conservative candidate decisions without a live wiki."""

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from audit_extensions import AuditError, Client, audit, batches


class FakeClient:
    def __init__(self, slots=None, hidden=False):
        self.calls = []
        self.slots = slots or {"main": {"contentmodel": "wikitext", "content": "Plain text"}}
        self.hidden = hidden

    def query(self, **params):
        self.calls.append(params)
        if "meta" in params:
            return {
                "query": {
                    "extensions": [
                        {"name": n}
                        for n in [
                            "Math",
                            "Cite",
                            "Elastica",
                            "Unknown",
                            "SyntaxHighlight_GeSHi",
                            "intersection",
                            "Cite",
                        ]
                    ],
                    "namespaces": {str(n): {"id": n} for n in [-2, -1, 0, 10, 828]},
                }
            }
        if "list" in params:
            n = params["apnamespace"]
            if n == 10 and "apcontinue" not in params:
                return {
                    "query": {"allpages": []},
                    "continue": {"continue": "-||", "apcontinue": "Next"},
                }
            return {"query": {"allpages": [{"pageid": n + 1}]}}
        page = {"pageid": int(params["pageids"]), "title": "Template:Example"}
        if not self.hidden:
            page["revisions"] = [{"slots": self.slots}]
        return {"query": {"pages": [page]}}


class AuditTests(unittest.TestCase):
    def run_audit(self, client, confirmed=True):
        with redirect_stderr(io.StringIO()):
            return audit(client, confirmed)

    def test_all_namespaces_empty_continuation_and_candidates(self):
        client = FakeClient()
        result = self.run_audit(client)
        self.assertEqual(result["pages_scanned"], 3)
        self.assertEqual(result["namespaces"], [0, 10, 828])
        rows = {r["extension"]: r for r in result["extensions"]}
        self.assertEqual(rows["Math"]["status"], "Möglicher Kandidat")
        self.assertEqual(rows["Elastica"]["status"], "Manuell prüfen")
        self.assertEqual(rows["Unknown"]["status"], "Manuell prüfen")
        self.assertEqual(len(rows), len(result["extensions"]))
        self.assertTrue(all(p["rvslots"] == "*" for p in client.calls if "rvslots" in p))

    def test_aliases_tag_function_and_secondary_slots(self):
        result = self.run_audit(
            FakeClient(
                {
                    "main": {"contentmodel": "wikitext", "content": "<REF name='x'>x</REF>"},
                    "extra": {
                        "contentmodel": "wikitext",
                        "content": "{{#tag:math|x}} <source>code</source> <DynamicPageList>",
                    },
                }
            )
        )
        rows = {r["extension"]: r for r in result["extensions"]}
        for name in ["Cite", "Math", "SyntaxHighlight_GeSHi", "intersection"]:
            self.assertEqual(rows[name]["status"], "Quelltext-Beleg")
            self.assertEqual(rows[name]["pages"], 3)

    def test_no_candidates_without_confirmed_visibility(self):
        result = self.run_audit(FakeClient(), confirmed=False)
        self.assertFalse(any(r["status"] == "Möglicher Kandidat" for r in result["extensions"]))

    def test_dynamic_lua_and_computed_tags_suppress_candidates(self):
        for content, model in [
            ("return {}", "Scribunto"),
            ("{{#invoke:X|main}}", "wikitext"),
            ("{{#tag:{{{tag}}}|x}}", "wikitext"),
        ]:
            with self.subTest(content=content):
                result = self.run_audit(
                    FakeClient({"main": {"contentmodel": model, "content": content}})
                )
                self.assertTrue(result["dynamic_content_detected"])
                self.assertFalse(
                    any(r["status"] == "Möglicher Kandidat" for r in result["extensions"])
                )

    def test_hidden_revision_or_slot_aborts(self):
        for client in [FakeClient(hidden=True), FakeClient({"main": {"texthidden": True}})]:
            with self.assertRaises(AuditError):
                self.run_audit(client)

    def test_missing_pages_abort(self):
        client = FakeClient()
        original = client.query
        client.query = lambda **p: {"query": {"pages": []}} if "prop" in p else original(**p)
        with self.assertRaises(AuditError):
            self.run_audit(client)

    def test_repeated_continuation_aborts(self):
        client = FakeClient()
        client.query = lambda **p: {"continue": {"apcontinue": "same"}}
        with self.assertRaises(AuditError):
            list(batches(client, list="allpages"))

    def test_transport_only_sends_query_get(self):
        client = Client("https://example.org/api.php", delay=0)
        response = io.StringIO('{"query": {}}')
        with patch.object(client.opener, "open", return_value=response) as opener:
            client.query(meta="siteinfo")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("action=query", request.full_url)
        with self.assertRaises(AuditError):
            client.query(action="edit")

    def test_api_warning_or_error_aborts(self):
        for payload in [
            '{"warnings": {"revisions": "truncated"}}',
            '{"error": {"code": "permissiondenied"}}',
        ]:
            client = Client("https://example.org/api.php", delay=0)
            with patch.object(client.opener, "open", return_value=io.StringIO(payload)):
                with self.assertRaises(AuditError):
                    client.query(meta="siteinfo")

    def test_cookies_require_https_and_url_has_no_credentials(self):
        for url in ["http://example.org/api.php", "https://user:pass@example.org/api.php"]:
            with self.assertRaises(AuditError):
                Client(url, cookie_file="unused")


if __name__ == "__main__":
    unittest.main()

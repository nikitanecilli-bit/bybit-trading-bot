"""Tests for fail-closed Bybit announcement content validation."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.validate_bybit_announcement_content import validate_inventory


def article_html(content_html: str) -> bytes:
    payload = {
        "props": {
            "pageProps": {
                "articleDetail": {
                    "title": "Risk limit adjustment for BTCUSDT",
                    "date": "2026-11-20T08:00:00Z",
                    "categoryConnection": {"edges": []},
                    "content_html": content_html,
                }
            }
        }
    }
    encoded = json.dumps(payload).replace("</", "<\\/")
    return ('<html><script id="__NEXT_DATA__" type="application/json">' + encoded + '</script></html>').encode()


class ContentValidationTests(unittest.TestCase):
    def run_fixture(self, body: bytes):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "articles").mkdir()
        rel = "articles/test.html"
        (root / rel).write_bytes(body)
        inventory = {
            "complete": True,
            "article_count_unique": 1,
            "article_records": [{
                "title": "Risk limit adjustment for BTCUSDT",
                "url": "https://announcements.bybit.com/en/article/test",
                "body_file": rel,
                "body_bytes": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
            }],
        }
        (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
        return root

    def test_nonempty_content_is_semantically_complete(self):
        root = self.run_fixture(article_html("<p>BTCUSDT risk limit changed.</p>"))
        inventory, failures = validate_inventory(root)
        self.assertEqual(failures, [])
        self.assertTrue(inventory["complete"])
        self.assertEqual(inventory["content_validation"]["nonempty_article_bodies"], 1)

    def test_empty_content_fails_closed_even_when_raw_body_is_valid(self):
        root = self.run_fixture(article_html(""))
        inventory, failures = validate_inventory(root)
        self.assertFalse(inventory["complete"])
        self.assertEqual(inventory["content_validation"]["failed_article_bodies"], 1)
        self.assertEqual(failures[0]["kind"], "empty_article_content")

    def test_hash_mismatch_fails_closed(self):
        root = self.run_fixture(article_html("<p>Valid body.</p>"))
        (root / "articles/test.html").write_text("tampered", encoding="utf-8")
        inventory, failures = validate_inventory(root)
        self.assertFalse(inventory["complete"])
        self.assertEqual(failures[0]["kind"], "article_body_integrity_mismatch")


if __name__ == "__main__":
    unittest.main()

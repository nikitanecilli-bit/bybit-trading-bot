"""Offline tests for candidate Bybit listing/delisting event extraction."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.extract_bybit_lifecycle_events import extract_events


def build_fixture(title: str, published_at: str, body_text: str):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    (root / "articles").mkdir()
    payload = {
        "props": {
            "pageProps": {
                "articleDetail": {
                    "title": title,
                    "date": published_at,
                    "categoryConnection": {"edges": []},
                    "content_html": f"<p>{body_text}</p>",
                    "content": {"json": None},
                }
            }
        }
    }
    encoded = json.dumps(payload).replace("</", "<\\/")
    body = ('<html><script id="__NEXT_DATA__" type="application/json">' + encoded + '</script></html>').encode()
    relative = "articles/test.html"
    (root / relative).write_bytes(body)
    inventory = {
        "article_records": [{
            "title": title,
            "url": "https://announcements.bybit.com/en/article/test",
            "body_file": relative,
            "body_bytes": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest(),
        }]
    }
    (root / "inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    return tmp, root


class LifecycleExtractionTests(unittest.TestCase):
    def test_linear_delisting_extracts_exact_effective_time(self):
        tmp, root = build_fixture(
            "Delisting of TMXUSDT Perpetual Contract",
            "2026-10-28T09:04:42Z",
            "Bybit will be delisting the TMXUSDT Perpetual Contract at Oct 30, 2026, 9:00AM UTC.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual(len(result["events"]), 1)
        event = result["events"][0]
        self.assertEqual(event["symbol"], "TMXUSDT")
        self.assertEqual(event["product_class_candidate"], "linear_usdt_perpetual_candidate")
        self.assertEqual(event["effective_at_utc"], "2026-10-30T09:00:00Z")

    def test_usdc_delisting_symbol_does_not_need_usdc_suffix(self):
        tmp, root = build_fixture(
            "Delisting of IPPERP USDC Perpetual Contract",
            "2026-06-25T11:19:44Z",
            "Bybit will be delisting the IPPERP USDC Perpetual Contract at Jun 26, 2026, 7AM UTC.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        event = result["events"][0]
        self.assertEqual(event["symbol"], "IPPERP")
        self.assertEqual(event["product_class_candidate"], "usdc_perpetual")
        self.assertEqual(event["effective_at_utc"], "2026-06-26T07:00:00Z")

    def test_multi_symbol_pre_ipo_listing_does_not_invent_effective_time(self):
        tmp, root = build_fixture(
            "New listing: OPENAIUSDT and ANTHROPICUSDT Pre-IPO Perpetual Contracts with up to 20x Leverage",
            "2026-11-25T10:00:00+08:00",
            "Bybit has listed the OPENAIUSDT and ANTHROPICUSDT Pre-IPO Perpetual Contracts. Trading is now open.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual({e["symbol"] for e in result["events"]}, {"OPENAIUSDT", "ANTHROPICUSDT"})
        for event in result["events"]:
            self.assertEqual(event["product_class_candidate"], "pre_ipo_perpetual")
            self.assertIsNone(event["effective_at_utc"])
            self.assertEqual(event["effective_time_source"], "publication_confirms_open_but_not_exact_start")
            self.assertEqual(event["availability_confirmed_at_utc"], "2026-11-25T02:00:00.000Z")

    def test_delist_wording_on_without_minutes_is_supported(self):
        tmp, root = build_fixture(
            "Delisting of WIFUSD Inverse Perpetual Contract",
            "2026-04-29T08:00:00Z",
            "Bybit will delist the WIFUSD Inverse Perpetual Contract on May 1, 2026, 10AM UTC.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual(result["events"][0]["effective_at_utc"], "2026-05-01T10:00:00Z")

    def test_single_character_base_asset_perpetual_symbols_are_supported(self):
        tmp, root = build_fixture(
            "New listing: OUSDT Perpetual Contract, with up to 20x leverage",
            "2026-11-25T10:00:00Z",
            "Trading is now open for OUSDT Perpetual Contract.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual(result["events"][0]["symbol"], "OUSDT")

    def test_alpha_token_delisting_is_retained_as_out_of_scope_not_perpetual(self):
        tmp, root = build_fixture(
            "Bybit Alpha: Delisting of ARENA",
            "2026-11-25T10:00:00Z",
            "Bybit Alpha will delist ARENA.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual(result["events"], [])
        self.assertEqual(len(result["out_of_scope_articles"]), 1)
        self.assertEqual(result["out_of_scope_articles"][0]["reason"], "alpha_spot_or_token_notice")
    def test_spot_pair_with_usdt_ticker_is_not_classified_as_perpetual(self):
        tmp, root = build_fixture(
            "New listing: ABCUSDT spot trading pair",
            "2026-11-25T10:00:00Z",
            "ABCUSDT spot trading is now open.",
        )
        self.addCleanup(tmp.cleanup)
        result, failures = extract_events(root)
        self.assertEqual(failures, [])
        self.assertEqual(result["events"], [])
        self.assertEqual(result["out_of_scope_articles"][0]["reason"], "product_scope_not_explicitly_perpetual")
        self.assertEqual(result["out_of_scope_articles"][0]["symbols"], ["ABCUSDT"])
    def test_raw_body_hash_mismatch_fails_closed(self):
        tmp, root = build_fixture(
            "Delisting of TMXUSDT Perpetual Contract",
            "2026-10-28T09:04:42Z",
            "Bybit will be delisting the TMXUSDT Perpetual Contract at Oct 30, 2026, 9:00AM UTC.",
        )
        self.addCleanup(tmp.cleanup)
        (root / "articles/test.html").write_text("tampered", encoding="utf-8")
        result, failures = extract_events(root)
        self.assertEqual(result["events"], [])
        self.assertEqual(failures[0]["kind"], "article_body_integrity_mismatch")


if __name__ == "__main__":
    unittest.main()

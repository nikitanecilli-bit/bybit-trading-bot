"""Offline safety and parser tests for the public Bybit announcement inventory."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.collect_bybit_announcements import canonical_url, parse_page, classify, page_url, HOST, extract_article_payload

class AnnouncementCollectorTests(unittest.TestCase):
    def test_page_parser_extracts_article_and_page_numbers(self):
        html = b'''<a href="/en/article/listing-foo/?category=new_crypto">FooUSDT Perpetual listing</a>
        <ul class="ant-pagination">
        <li title="1" class="ant-pagination-item ant-pagination-item-1"><a>1</a></li>
        <li title="5" class="ant-pagination-item ant-pagination-item-5"><a>5</a></li>
        <li title="25" class="ant-pagination-item ant-pagination-item-25"><a>25</a></li>
        </ul>'''
        pages, articles = parse_page(html, page_url("new_crypto", 1))
        self.assertEqual(pages, 25)
        self.assertIn("https://announcements.bybit.com/en/article/listing-foo", articles)
    def test_canonical_url_rejects_external_hosts(self):
        with self.assertRaises(ValueError):
            canonical_url("https://example.com/en/article/not-bybit")
    def test_event_classification_keeps_product_candidate_separate(self):
        product, event = classify("Risk limit adjustment", "USDT Perpetual Contract risk limit adjustment", "x")
        self.assertEqual(product, "linear_candidate")
        self.assertEqual(event, "RISK_LIMIT_CHANGE")
        product, event = classify("Stock split", "TradFi Perpetual contract split", "x")
        self.assertEqual(product, "tradfi_candidate")
        product, _ = classify("Generic perpetual listing", "Perpetual contract", "x")
        self.assertEqual(product, "perpetual_product_unknown")
        product, _ = classify("Inverse perpetual listing", "Inverse perpetual contract", "x")
        self.assertEqual(product, "inverse_candidate")
    def test_archive_page_baseline_is_explicit(self):
        from scripts.collect_bybit_announcements import EXPECTED_PAGES
        self.assertEqual(EXPECTED_PAGES, {"new_crypto": 25, "delistings": 11, "maintenance_updates": 19, "latest_bybit_news": 11})
    def test_article_payload_uses_structured_body_not_site_chrome(self):
        body = b'''<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"articleDetail":{"title":"Tick size change for BTCUSDT","date":"2026-11-20T09:00:00Z","categoryConnection":{"edges":[{"node":{"key":"latest_bybit_news"}}]},"content_html":"<p>BTCUSDT tick size changes from 0.1 to 0.01.</p>"}}}}</script><footer>TradFi delisting notices</footer></html>'''
        payload = extract_article_payload(body)
        self.assertEqual(payload["title"], "Tick size change for BTCUSDT")
        self.assertEqual(payload["published_at"], "2026-11-20T09:00:00Z")
        self.assertEqual(payload["category_keys"], ["latest_bybit_news"])
        self.assertIn("BTCUSDT tick size", payload["content_text"])
        self.assertEqual(payload["content_source"], "content_html")
        self.assertNotIn("TradFi", payload["content_text"])
    def test_article_payload_falls_back_to_rich_content_json(self):
        body = b'''<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"articleDetail":{"title":"Risk tiers for BTCUSDT","date":"2026-11-20T09:00:00Z","content_html":"","content":{"json":{"type":"doc","children":[{"type":"p","children":[{"text":"BTCUSDT risk tier "},{"text":"changes at 08:00 UTC"}]},{"type":"table","children":[{"type":"tr","children":[{"type":"td","children":[{"text":"100000"}]}]}]}]}}}}}}</script></html>'''
        payload = extract_article_payload(body)
        self.assertEqual(payload["content_source"], "content.json")
        self.assertIn("BTCUSDT risk tier changes at 08:00 UTC 100000", payload["content_text"])
    def test_html_extractor_ignores_style_and_script_text(self):
        import json
        payload_data = {"props": {"pageProps": {"articleDetail": {
            "title": "HTML body",
            "content_html": "<style>td { color: red; }</style><p>Only article text.</p><script>noise()</script>",
        }}}}
        encoded = json.dumps(payload_data).replace("</", "<\\/")
        body = ('<html><script id="__NEXT_DATA__" type="application/json">' + encoded + '</script></html>').encode()
        payload = extract_article_payload(body)
        self.assertIn("Only article text.", payload["content_text"])
        self.assertNotIn("color: red", payload["content_text"])
        self.assertNotIn("noise()", payload["content_text"])

    def test_empty_article_body_remains_empty(self):
        body = b'''<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"articleDetail":{"title":"No body","content_html":"","content":{"json":{"type":"doc","children":[{"type":"p","children":[{"text":""}]}]}}}}}}</script></html>'''
        payload = extract_article_payload(body)
        self.assertEqual(payload["content_text"], "")
        self.assertEqual(payload["content_source"], "none")
    def test_symbol_set_is_47_and_host_is_official(self):
        from scripts.collect_bybit_announcements import SYMBOLS
        self.assertEqual(len(SYMBOLS), 47)
        self.assertEqual(HOST, "announcements.bybit.com")

if __name__ == "__main__":
    unittest.main()

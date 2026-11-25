"""Offline safety and parser tests for the public Bybit announcement inventory."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.collect_bybit_announcements import canonical_url, parse_page, classify, page_url, HOST

class AnnouncementCollectorTests(unittest.TestCase):
    def test_page_parser_extracts_article_and_page_numbers(self):
        html = b'''<a href="/article/listing-foo/">FooUSDT Perpetual listing</a>
        <ul class="ant-pagination">
        <li title="1" class="ant-pagination-item ant-pagination-item-1"><a>1</a></li>
        <li title="5" class="ant-pagination-item ant-pagination-item-5"><a>5</a></li>
        <li title="25" class="ant-pagination-item ant-pagination-item-25"><a>25</a></li>
        </ul>'''
        pages, articles = parse_page(html, page_url("new_crypto", 1))
        self.assertEqual(pages, 25)
        self.assertIn("https://announcements.bybit.com/article/listing-foo", articles)
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
    def test_symbol_set_is_47_and_host_is_official(self):
        from scripts.collect_bybit_announcements import SYMBOLS
        self.assertEqual(len(SYMBOLS), 47)
        self.assertEqual(HOST, "announcements.bybit.com")

if __name__ == "__main__":
    unittest.main()

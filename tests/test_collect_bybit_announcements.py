"""Offline safety and parser tests for the public Bybit announcement inventory."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.collect_bybit_announcements import canonical_url, parse_page, classify, page_url, HOST

class AnnouncementCollectorTests(unittest.TestCase):
    def test_page_parser_extracts_article_and_page_numbers(self):
        html = b'''<a href="/en/article/listing-foo/">FooUSDT Perpetual listing</a>
        <a href="/en/?category=new_crypto&amp;page=2">2</a>
        <a href="/en/?category=new_crypto&amp;page=25">25</a>'''
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
    def test_symbol_set_is_47_and_host_is_official(self):
        from scripts.collect_bybit_announcements import SYMBOLS
        self.assertEqual(len(SYMBOLS), 47)
        self.assertEqual(HOST, "announcements.bybit.com")

if __name__ == "__main__":
    unittest.main()

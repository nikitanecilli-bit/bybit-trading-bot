#!/usr/bin/env python3
"""Read-only inventory of Bybit's public announcement archive.

Only requests https://announcements.bybit.com/en/ category and article pages.
No market API, account API, credentials, trading endpoints, or off-domain redirects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from collections import defaultdict

BASE = "https://announcements.bybit.com"
HOST = "announcements.bybit.com"
CATEGORIES = {
    "new_crypto": "new_crypto",
    "delistings": "delistings",
    "maintenance_updates": "maintenance_updates",
    "latest_bybit_news": "latest_bybit_news",
}
EXPECTED_PAGES = {"new_crypto": 25, "delistings": 11, "maintenance_updates": 19, "latest_bybit_news": 11}
SYMBOLS = (
    "AAVEUSDT ADAUSDT ALGOUSDT APTUSDT ARBUSDT ASTERUSDT ATOMUSDT AVAXUSDT "
    "BCHUSDT BNBUSDT BTCUSDT CAKEUSDT DASHUSDT DOGEUSDT DOTUSDT ENAUSDT "
    "ETCUSDT ETHUSDT GMXUSDT HBARUSDT ICPUSDT JSTUSDT LINKUSDT LTCUSDT "
    "MINAUSDT MORPHOUSDT NEARUSDT ONDOUSDT PAXGUSDT PEPEUSDT POLUSDT "
    "PUMPUSDT QNTUSDT RAYUSDT RENDERUSDT SHIBUSDT SKYUSDT SOLUSDT SUIUSDT "
    "TAOUSDT TRXUSDT UNIUSDT WLDUSDT WLFIUSDT XLMUSDT XRPUSDT ZECUSDT"
).split()
MAX_BODY = 8 * 1024 * 1024

class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlparse(newurl)
        if target.scheme != "https" or target.hostname != HOST:
            raise RuntimeError("blocked redirect outside official announcements host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.page_titles = set()
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.lower() == "li":
            classes = values.get("class", "")
            title = values.get("title", "")
            if "ant-pagination-item" in classes and title.isdigit():
                self.page_titles.add(int(title))
        if tag.lower() == "a":
            self._href = values.get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(" ".join(self._text).split())))
            self._href = None
            self._text = []

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

def rich_content_text(value):
    """Extract ordered text nodes from Bybit's Contentstack rich-text JSON."""
    parts = []
    def visit(node):
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(" ".join(text.split()))
            for key, child in node.items():
                if key != "text":
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return " ".join(parts)

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def canonical_url(url):
    p = urlparse(urljoin(BASE, url))
    if p.scheme != "https" or p.hostname != HOST:
        raise ValueError("non-official URL rejected")
    path = re.sub(r"/+", "/", p.path).rstrip("/")
    return urlunparse(("https", HOST, path, "", "", ""))

def request_bytes(opener, url, delay, timeout):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != HOST:
        raise ValueError("request outside official host rejected")
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; PublicAnnouncementResearch/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }, method="GET")
    time.sleep(delay)
    with opener.open(req, timeout=timeout) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname != HOST:
            raise RuntimeError("final URL outside official host")
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise RuntimeError("response exceeded 8 MiB safety limit")
        headers = {k.lower(): v for k, v in response.headers.items()
                   if k.lower() in {"date", "content-type", "content-length", "last-modified", "etag"}}
        return body, int(response.status), headers, response.geturl()

def write_capture(root, relative, body, *, url, status, headers, retrieved):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()
    path.write_bytes(body)
    return {
        "url": url, "retrieved_at_utc": retrieved, "http_status": status,
        "response_headers": headers, "body_file": relative.as_posix(),
        "body_bytes": len(body), "body_sha256": digest,
    }

def page_url(category, page):
    query = {"category": category}
    if page > 1:
        query["page"] = str(page)
    return f"{BASE}/en/?{urlencode(query)}"

def article_slug(url):
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or hashlib.sha256(url.encode()).hexdigest()[:16]

def parse_page(body, category_url):
    parser = Anchors()
    parser.feed(body.decode("utf-8", errors="replace"))
    page_numbers = {1} | parser.page_titles
    articles = {}
    for href, label in parser.links:
        if not href:
            continue
        full = urljoin(category_url, href)
        p = urlparse(full)
        if p.scheme == "https" and p.hostname == HOST:
            q = parse_qs(p.query)
            if "page" in q and q["page"][0].isdigit() and (not q.get("category") or q["category"][0] in CATEGORIES):
                page_numbers.add(int(q["page"][0]))
            if re.match(r"^/(?:en/)?article/[^/]+/?$", p.path):
                clean = canonical_url(full)
                if label:
                    articles[clean] = label
    return max(page_numbers), articles

def extract_article_payload(body):
    match = re.search(
        rb"""<script[^>]+id=["']__NEXT_DATA__["'][^>]*>(.*?)</script>""",
        body, flags=re.DOTALL
    )
    if not match:
        raise ValueError("article page has no __NEXT_DATA__ payload")
    data = json.loads(match.group(1).decode("utf-8"))
    detail = data.get("props", {}).get("pageProps", {}).get("articleDetail")
    if not isinstance(detail, dict):
        raise ValueError("article page has no articleDetail object")
    title = detail.get("title") or ""
    content_html = detail.get("content_html") or ""
    content_parser = VisibleText()
    content_parser.feed(content_html)
    content_text = " ".join(content_parser.parts)
    content_source = "content_html"
    if not content_text.strip():
        rich = detail.get("content") or {}
        rich_json = rich.get("json") if isinstance(rich, dict) else None
        content_text = rich_content_text(rich_json)
        content_source = "content.json" if content_text.strip() else "none"
    category_keys = []
    connection = detail.get("categoryConnection") or {}
    for edge in connection.get("edges") or []:
        node = (edge or {}).get("node") or {}
        key = node.get("key")
        if key:
            category_keys.append(key)
    return {
        "title": title,
        "published_at": detail.get("date"),
        "category_keys": sorted(set(category_keys)),
        "content_text": content_text,
        "content_source": content_source,
    }

def classify(title, text, category):
    sample = (title + " " + text[:12000]).lower()
    if re.search(r"\btradfi\b|\bstock\b|\bpre-ipo\b", sample):
        product = "tradfi_candidate"
    elif re.search(r"\b(usdt|usdc)\s+perpetual\b|\blinear contract\b", sample):
        product = "linear_candidate"
    elif re.search(r"\binverse perpetual\b|\bxbtusd\b", sample):
        product = "inverse_candidate"
    elif re.search(r"\bperpetual contract\b", sample):
        product = "perpetual_product_unknown"
    elif re.search(r"\bspot\b|\btrading pair\b", sample):
        product = "spot_or_token_candidate"
    else:
        product = "unknown"
    event = "OTHER"
    rules = [
        ("DELIST", r"delist|delisting|last trading"),
        ("LIST", r"new listing|listing of|perpetual contract.*available|now live"),
        ("HALT_RESUME_OR_ADJUSTMENT", r"temporary suspension|trading suspension|halt|resume|contract size adjustment|split and rename"),
        ("TICK_CHANGE", r"tick size"),
        ("ORDER_SIZE_CHANGE", r"max(?:imum)?\.?\s*order size"),
        ("RISK_LIMIT_CHANGE", r"risk limit|position tier|maximum leverage"),
        ("FUNDING_RULE_CHANGE", r"funding rate|funding interval|funding formula"),
    ]
    for name, pattern in rules:
        if re.search(pattern, sample):
            event = name
            break
    return product, event

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--max-pages-per-category", type=int, default=100)
    args = ap.parse_args()
    if args.delay < 0.5 or args.delay > 10:
        ap.error("--delay must be between 0.5 and 10 seconds")
    if not 1 <= args.max_pages_per_category <= 100:
        ap.error("--max-pages-per-category must be between 1 and 100")

    root = Path(args.output)
    if root.exists() and any(root.iterdir()):
        raise SystemExit("output directory must be new/empty; refusing overwrite")
    root.mkdir(parents=True, exist_ok=True)
    opener = build_opener(SameHostRedirect())
    run = {
        "schema_version": 1, "source": BASE, "started_at_utc": utc_now(),
        "scope": {"categories": list(CATEGORIES), "symbols": SYMBOLS,
                  "max_pages_per_category": args.max_pages_per_category,
                  "expected_pages_from_2026_11_25_observation": EXPECTED_PAGES,
                  "delay_seconds_minimum": args.delay,
                  "article_pages": "all unique article links found in selected archive pages"},
        "categories": {}, "article_count_unique": 0, "failures": [],
    }
    article_index = {}
    for category in CATEGORIES:
        first_url = page_url(category, 1)
        try:
            body, status, headers, final_url = request_bytes(opener, first_url, args.delay, args.timeout)
            retrieved = utc_now()
            page_capture = write_capture(root, Path("archive_pages") / category / "page-001.html",
                                          body, url=final_url, status=status, headers=headers, retrieved=retrieved)
            total_pages, found = parse_page(body, first_url)
            if total_pages != EXPECTED_PAGES[category]:
                raise RuntimeError(f"pagination changed or was not fully exposed: parsed {total_pages}, expected observed baseline {EXPECTED_PAGES[category]}; refusing to claim complete inventory")
            if total_pages > args.max_pages_per_category:
                raise RuntimeError(f"archive reports {total_pages} pages; configured safety cap is {args.max_pages_per_category}")
            pages = [{"page": 1, **page_capture, "article_links_found": len(found)}]
            for url, title in found.items():
                article_index[url] = title
            for page in range(2, total_pages + 1):
                url = page_url(category, page)
                try:
                    b, st, h, fu = request_bytes(opener, url, args.delay, args.timeout)
                    retrieved = utc_now()
                    cap = write_capture(root, Path("archive_pages") / category / f"page-{page:03d}.html",
                                        b, url=fu, status=st, headers=h, retrieved=retrieved)
                    _, links = parse_page(b, url)
                    pages.append({"page": page, **cap, "article_links_found": len(links)})
                    for article, title in links.items():
                        article_index[article] = title
                except Exception as exc:
                    run["failures"].append({"kind": "archive_page", "category": category,
                                            "page": page, "url": url, "error": f"{type(exc).__name__}: {exc}"})
            run["categories"][category] = {
                "reported_pages": total_pages, "retrieved_pages": len(pages),
                "page_numbers": [p["page"] for p in pages],
                "page_inventory": pages, "complete": len(pages) == total_pages,
            }
        except Exception as exc:
            run["failures"].append({"kind": "archive_first_page", "category": category,
                                    "url": first_url, "error": f"{type(exc).__name__}: {exc}"})
            run["categories"][category] = {"reported_pages": None, "retrieved_pages": 0, "complete": False}

    symbol_hits = defaultdict(list)
    article_records = []
    for index, (url, title) in enumerate(sorted(article_index.items()), start=1):
        try:
            body, status, headers, final_url = request_bytes(opener, url, args.delay, args.timeout)
            retrieved = utc_now()
            slug = article_slug(url)
            cap = write_capture(root, Path("articles") / f"{slug}.html",
                                body, url=final_url, status=status, headers=headers, retrieved=retrieved)
            payload = extract_article_payload(body)
            article_title = payload["title"] or title
            text = payload["content_text"]
            matched = [s for s in SYMBOLS if re.search(rf"(?<![A-Z0-9]){re.escape(s)}(?![A-Z0-9])", (article_title + " " + text).upper())]
            product, event = classify(article_title, text, "mixed")
            record = {"title": article_title, "url": url, "symbols": matched,
                      "published_at": payload["published_at"],
                      "category_keys": payload["category_keys"],
                      "content_extraction": payload["content_source"],
                      "content_text_chars": len(text),
                      "product_class_candidate": product, "event_type_candidate": event, **cap}
            article_records.append(record)
            for symbol in matched:
                symbol_hits[symbol].append({
                    "url": url, "title": article_title, "product_class_candidate": product,
                    "event_type_candidate": event, "body_sha256": cap["body_sha256"],
                })
        except Exception as exc:
            run["failures"].append({"kind": "article", "url": url,
                                    "error": f"{type(exc).__name__}: {exc}"})
        if index % 100 == 0:
            print(f"Fetched {index}/{len(article_index)} unique article pages", flush=True)

    run["article_count_unique"] = len(article_index)
    run["article_count_captured"] = len(article_records)
    run["symbol_hit_counts"] = {s: len(symbol_hits.get(s, [])) for s in SYMBOLS}
    run["symbol_hits"] = dict(symbol_hits)
    run["article_records"] = article_records
    run["finished_at_utc"] = utc_now()
    run["complete"] = (
        not run["failures"]
        and all(v.get("complete") for v in run["categories"].values())
        and run["article_count_captured"] == run["article_count_unique"]
    )
    (root / "inventory.json").write_text(
        json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "complete": run["complete"], "category_pages": {
            k: {"reported": v.get("reported_pages"), "retrieved": v.get("retrieved_pages")}
            for k, v in run["categories"].items()
        }, "unique_articles": run["article_count_unique"],
        "captured_articles": run["article_count_captured"],
        "failure_count": len(run["failures"]),
        "symbols_with_hits": sum(bool(v) for v in symbol_hits.values()),
    }, ensure_ascii=False), flush=True)
    return 0 if run["complete"] else 2

if __name__ == "__main__":
    sys.exit(main())

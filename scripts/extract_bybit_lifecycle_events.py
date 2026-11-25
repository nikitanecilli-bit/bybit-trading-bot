#!/usr/bin/env python3
"""Extract candidate Bybit listing/delisting lifecycle events from a captured archive.

Offline only: reads captured HTML and inventory.json; makes no network requests.
Listing publication time is not silently treated as the exact listing effective time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.collect_bybit_announcements import SYMBOLS, extract_article_payload

SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z0-9]{2,30}(?:USDT|USDC|USD))(?![A-Z0-9])")
EFFECTIVE_PATTERN = re.compile(
    r"(?:will be delisting|will delist|will be delisted)[^.!?]{0,240}?\b(?:at|on)\s+"
    r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4},\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*UTC)",
    re.IGNORECASE,
)


def normalize_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("published_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_effective_utc(text: str) -> str | None:
    match = EFFECTIVE_PATTERN.search(text)
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip()
    for fmt in ("%b %d, %Y, %I:%M%p UTC", "%b %d, %Y, %I%p UTC"):
        try:
            parsed = datetime.strptime(value.upper(), fmt).replace(tzinfo=timezone.utc)
            return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        except ValueError:
            continue
    return None


def classify_product(title: str, symbol: str) -> str:
    lower = title.lower()
    if "tradfi" in lower:
        return "tradfi_perpetual"
    if "pre-ipo" in lower:
        return "pre_ipo_perpetual"
    if "inverse" in lower:
        return "inverse_perpetual"
    if "usdc" in lower or symbol.endswith("USDC"):
        return "usdc_perpetual"
    if symbol.endswith("USDT") and "perpetual contract" in lower:
        return "linear_usdt_perpetual_candidate"
    if symbol.endswith("USD"):
        return "inverse_or_usd_perpetual_candidate"
    return "unknown"


def extract_underlying_asset(text: str) -> str | None:
    match = re.search(
        r"Underlying asset\s+(.+?)\s+(?:Settlement asset|Tick size|Maximum leverage|Capped funding rate)",
        text, re.IGNORECASE,
    )
    return " ".join(match.group(1).split()) if match else None


def extract_events(root: Path) -> tuple[dict, list[dict]]:
    manifest_path = root / "inventory.json"
    inventory = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    events = []
    checked = 0
    proxy = set(SYMBOLS)

    for record in inventory.get("article_records", []):
        title = str(record.get("title") or "")
        is_listing = bool(re.search(r"^New listing:", title, re.IGNORECASE))
        is_delisting = bool(re.search(r"\bdelist(?:ing|ed)?\b", title, re.IGNORECASE))
        if not (is_listing or is_delisting):
            continue
        checked += 1
        relative = Path(record.get("body_file", ""))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            failures.append({"kind": "unsafe_article_path", "url": record.get("url")})
            continue
        path = root / relative
        if not path.is_file():
            failures.append({"kind": "missing_article_body", "url": record.get("url"), "body_file": str(relative)})
            continue
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        if len(body) != record.get("body_bytes") or digest != record.get("body_sha256"):
            failures.append({"kind": "article_body_integrity_mismatch", "url": record.get("url"), "body_file": str(relative)})
            continue
        try:
            payload = extract_article_payload(body)
        except Exception as exc:
            failures.append({"kind": "article_payload_parse_error", "url": record.get("url"), "error": f"{type(exc).__name__}: {exc}"})
            continue

        article_title = payload.get("title") or title
        text = payload.get("content_text") or ""
        full_text = article_title + " " + text
        symbols = sorted(set(SYMBOL_PATTERN.findall(article_title.upper())))
        if not symbols and is_delisting:
            title_symbol = re.search(r"^Delisting of\s+([A-Z0-9]+)", article_title, re.IGNORECASE)
            if title_symbol:
                symbols = [title_symbol.group(1).upper()]
        if not symbols:
            symbols = sorted(set(SYMBOL_PATTERN.findall(text.upper())))
        if not symbols:
            failures.append({"kind": "lifecycle_article_without_symbol", "url": record.get("url"), "title": article_title})
            continue

        try:
            published_utc = normalize_utc(payload["published_at"])
        except Exception as exc:
            failures.append({"kind": "invalid_published_at", "url": record.get("url"), "error": str(exc)})
            published_utc = None

        effective_utc = parse_effective_utc(text) if is_delisting else None
        now_open = bool(is_listing and re.search(r"trading is now open", text, re.IGNORECASE))
        event_type = "listing" if is_listing else "delisting"
        for symbol in symbols:
            events.append({
                "event_type": event_type,
                "symbol": symbol,
                "product_class_candidate": classify_product(article_title, symbol),
                "published_at_source": payload.get("published_at"),
                "published_at_utc": published_utc,
                "effective_at_utc": effective_utc,
                "availability_confirmed_at_utc": published_utc if now_open else None,
                "effective_time_source": "article_body_explicit" if effective_utc else (
                    "publication_confirms_open_but_not_exact_start" if now_open else "unknown"
                ),
                "underlying_asset_candidate": extract_underlying_asset(text),
                "matched_47_symbol_proxy": symbol in proxy,
                "category_keys": payload.get("category_keys", []),
                "title": article_title,
                "url": record.get("url"),
                "body_file": relative.as_posix(),
                "body_bytes": len(body),
                "body_sha256": digest,
            })

    summary = {
        "candidate_article_records_checked": checked,
        "event_symbol_rows": len(events),
        "unique_symbols": len({event["symbol"] for event in events}),
        "listing_rows": sum(event["event_type"] == "listing" for event in events),
        "delisting_rows": sum(event["event_type"] == "delisting" for event in events),
        "delistings_with_explicit_effective_time": sum(
            event["event_type"] == "delisting" and event["effective_at_utc"] is not None
            for event in events
        ),
        "listings_confirmed_open_at_publication": sum(
            event["event_type"] == "listing" and event["availability_confirmed_at_utc"] is not None
            for event in events
        ),
        "proxy_matched_rows": sum(event["matched_47_symbol_proxy"] for event in events),
        "failures": len(failures),
    }
    output = {
        "schema_version": 1,
        "source": "official Bybit public announcement HTML captured in inventory.json",
        "scope": "candidate listing/delisting events; product class and event times require review",
        "summary": summary,
        "events": sorted(events, key=lambda event: (
            event["symbol"], event["event_type"], event["published_at_utc"] or ""
        )),
        "failures": failures,
        "complete": not failures,
    }
    return output, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="directory containing inventory.json and captured bodies")
    parser.add_argument("--output", required=True, help="output JSON path")
    args = parser.parse_args()
    output, failures = extract_events(Path(args.input))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"] | {"complete": output["complete"]}, ensure_ascii=False), flush=True)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())

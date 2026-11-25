#!/usr/bin/env python3
"""Fail-closed semantic validation for captured Bybit announcement article bodies."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts.collect_bybit_announcements import extract_article_payload


def validate_inventory(root: Path) -> tuple[dict, list[dict]]:
    manifest_path = root / "inventory.json"
    inventory = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    checked = 0
    nonempty = 0
    for record in inventory.get("article_records", []):
        checked += 1
        relative = Path(record.get("body_file", ""))
        if relative.is_absolute() or ".." in relative.parts:
            failures.append({"kind": "unsafe_body_path", "url": record.get("url")})
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
        text = payload.get("content_text", "").strip()
        if not text:
            failures.append({"kind": "empty_article_content", "url": record.get("url"), "title": record.get("title"), "body_file": str(relative), "body_sha256": digest})
            record["content_text_chars"] = 0
            continue
        nonempty += 1
        record["content_text_chars"] = len(text)

    inventory["content_validation"] = {
        "checked_article_records": checked,
        "nonempty_article_bodies": nonempty,
        "failed_article_bodies": len(failures),
        "semantic_complete": not failures and checked == inventory.get("article_count_unique"),
    }
    # Keep collection failures and semantic validation failures distinct.
    inventory["content_validation_failures"] = failures
    if failures or checked != inventory.get("article_count_unique"):
        inventory["complete"] = False
    manifest_path.write_text(json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return inventory, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inventory, failures = validate_inventory(Path(args.output))
    summary = inventory["content_validation"]
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["semantic_complete"] else 2


if __name__ == "__main__":
    sys.exit(main())

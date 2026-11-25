"""Content-addressed evidence helpers for public Bybit GET snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def capture_response(
    raw_body: bytes, *, base_url: str, endpoint: str, params: dict[str, Any],
    http_status: int, response_headers: dict[str, Any],
    evidence_dir: str | Path, records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist exact response bytes and an immutable audit record."""
    if not isinstance(raw_body, bytes):
        raise TypeError("raw response body must be bytes")
    root = Path(evidence_dir)
    digest = hashlib.sha256(raw_body).hexdigest()
    body_relative = f"bodies/{digest}.json"
    request = {
        "method": "GET", "base_url": base_url.rstrip("/"),
        "endpoint": endpoint, "params": params,
    }
    identity = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + digest.encode("ascii")
    ).hexdigest()
    retrieved = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    request_id = identity
    audit_relative = f"requests/{request_id}.json"
    record = {
        "schema_version": 1, "request_id": request_id, "request": request,
        "retrieved_at_utc": retrieved, "http_status": int(http_status),
        "response_headers": response_headers, "body_bytes": len(raw_body),
        "body_sha256": digest, "body_file": body_relative,
        "audit_file": audit_relative,
    }
    body_path = root / body_relative
    if body_path.exists() and hashlib.sha256(body_path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("existing raw response body failed its content-addressed hash")
    if not body_path.exists():
        _atomic_write(body_path, raw_body)
    audit_path = root / audit_relative
    if audit_path.exists():
        try:
            previous = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("existing raw response audit record is invalid") from exc
        if previous != record:
            request_id = hashlib.sha256(
                (identity + retrieved).encode("utf-8")
            ).hexdigest()
            record["request_id"] = request_id
            record["audit_file"] = f"requests/{request_id}.json"
            audit_path = root / record["audit_file"]
    _atomic_write(
        audit_path,
        (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    records.append(record)
    return record


def write_evidence_manifest(
    manifest_path: str | Path, *, source: str, category: str,
    normalized_output: str | Path, records: list[dict[str, Any]],
    collection_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    path = Path(manifest_path)
    output = Path(normalized_output)
    if not output.is_file():
        raise FileNotFoundError(output)
    manifest = {
        "schema_version": 1,
        "source": source,
        "category": category,
        "normalized_output": {
            "path": os.path.relpath(output, path.parent).replace(os.sep, "/"),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "bytes": output.stat().st_size,
        },
        "collection_pages": collection_pages,
        "records": records,
    }
    _atomic_write(
        path,
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    report = validate_evidence_manifest(path)
    if not report["ok"]:
        raise RuntimeError(f"raw evidence validation failed: {report['errors']}")
    return manifest


def validate_evidence_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    errors: list[str] = []
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "errors": ["manifest_missing_or_invalid"], "records": 0}
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("records"), list):
        return {"ok": False, "errors": ["manifest_schema_invalid"], "records": 0}
    root = path.parent.resolve()
    records_by_id: dict[str, dict[str, Any]] = {}
    for record in manifest["records"]:
        if not isinstance(record, dict):
            errors.append("record_invalid")
            continue
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            errors.append("request_id_missing")
        else:
            records_by_id[request_id] = record
        if record.get("http_status") != 200:
            errors.append("http_status_not_200")
        if not isinstance(record.get("request"), dict) or record["request"].get("method") != "GET":
            errors.append("request_identity_invalid")
        for key in ("body_file", "audit_file"):
            relative = record.get(key)
            if not isinstance(relative, str) or not relative:
                errors.append(f"{key}_missing")
                continue
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append(f"{key}_escapes_manifest_root")
                continue
            if not target.is_file():
                errors.append(f"{key}_not_found")
                continue
            if key == "body_file":
                body = target.read_bytes()
                if hashlib.sha256(body).hexdigest() != record.get("body_sha256"):
                    errors.append("raw_body_hash_mismatch")
                if len(body) != record.get("body_bytes"):
                    errors.append("raw_body_size_mismatch")
            else:
                try:
                    audit = json.loads(target.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    errors.append("audit_record_invalid")
                    continue
                if audit != record:
                    errors.append("audit_record_content_mismatch")
    pages = manifest.get("collection_pages")
    if not isinstance(pages, list):
        errors.append("collection_pages_missing")
    else:
        for page in pages:
            if not isinstance(page, dict):
                errors.append("collection_page_invalid")
                continue
            request_id = page.get("raw_response_request_id")
            body_hash = page.get("raw_response_body_sha256")
            record = records_by_id.get(request_id) if isinstance(request_id, str) else None
            if record is None:
                errors.append("collection_page_raw_record_missing")
            elif record.get("body_sha256") != body_hash:
                errors.append("collection_page_raw_hash_mismatch")
    output = manifest.get("normalized_output")
    if not isinstance(output, dict) or not isinstance(output.get("path"), str):
        errors.append("normalized_output_missing")
    else:
        target = (root / output["path"]).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            errors.append("normalized_output_escapes_manifest_root")
        else:
            if not target.is_file():
                errors.append("normalized_output_not_found")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != output.get("sha256"):
                errors.append("normalized_output_hash_mismatch")
            elif target.stat().st_size != output.get("bytes"):
                errors.append("normalized_output_size_mismatch")
    return {"ok": not errors, "errors": errors, "records": len(manifest["records"])}

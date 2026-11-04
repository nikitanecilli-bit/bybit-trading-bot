"""Safe serialization for generated research reports."""
from __future__ import annotations

import json
from pathlib import Path


def write_json_report(path: Path, report: dict) -> None:
    """Create a JSON report without ever replacing an existing artifact."""
    payload = json.dumps(report, indent=2) + "\n"
    created = False
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(payload)
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise

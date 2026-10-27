#!/usr/bin/env python3
"""Heuristic local secret scanner. Prints file/line/type, never the matched value."""
from pathlib import Path
import re
import sys

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
}
SKIP_FILES = {".env.example"}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz",
    ".parquet", ".feather", ".pkl", ".pickle",
}
MAX_FILE_SIZE = 2_000_000

PATTERNS = [
    ("private key", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    )),
    ("possible credential assignment", re.compile(
        r"""(?i)\b(?:BYBIT_API_KEY|BYBIT_API_SECRET|api[_-]?secret|api[_-]?key|"""
        r"""secret[_-]?key|access[_-]?token|refresh[_-]?token|client_secret|"""
        r"""telegram[_-]?bot[_-]?token|bot[_-]?token|password|passwd)\b"""
        r"""\s*[:=]\s*["']?([A-Za-z0-9_./+=:-]{12,})"""
    )),
    ("credential in URL", re.compile(r"(?i)https?://[^/\s:@]+:[^/\s@]+@")),
    ("known token prefix", re.compile(
        r"\b(?:ghp_|github_pat_|xox[baprs]-|AKIA[0-9A-Z]{16})[A-Za-z0-9_-]{8,}"
    )),
]

def main() -> int:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_FILES:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in PATTERNS:
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                findings.append((str(rel), line, label))
    if findings:
        print("Potential secrets found; matched values are deliberately hidden:")
        for filename, line, label in findings:
            print(f"  {filename}:{line}: {label}")
        print("Do not commit until every finding is understood.")
        return 1
    print("No obvious secret patterns found. Manual review is still required.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

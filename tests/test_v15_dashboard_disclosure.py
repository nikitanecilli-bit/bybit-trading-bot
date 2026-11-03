#!/usr/bin/env python3
"""Guardrails for the archived v15 demo dashboard and its downloadable mirror."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "dashboards/v15/Bybit Profit Dashboard v15 (Чистый HTML).html"
GUIDE = ROOT / "dashboards/v15/📥 СКАЧАТЬ HTML БЕЗ ОШИБКИ (Откройте эту карточку).md"


def main():
    html = HTML.read_text(encoding="utf-8")
    guide = GUIDE.read_text(encoding="utf-8")

    required_disclosures = (
        "ЭТО НЕ ВАЛИДИРОВАННЫЙ BACKTEST",
        "заранее заложенным направленным преимуществом",
        "отдельном виртуальном капитале 10 000 USDT",
        "не shared-capital",
        "не независимый holdout",
        "не доказательство доходности",
    )
    for text in required_disclosures:
        assert text in html, f"HTML disclosure missing: {text}"
    assert "synthetic fallback" in guide.lower() or "синтетическому fallback" in guide.lower()
    assert guide.index("не использовать как доказательство доходности") < guide.index("```html")

    # The downloadable source must be byte-for-byte identical to the maintained HTML.
    match = re.search(r"```html\n([\s\S]*?)\n```", guide)
    assert match, "download guide has no complete HTML source block"
    assert match.group(1) == html.rstrip(), "downloadable HTML mirror has drifted"

    # Guard against the original false claims returning.
    forbidden = (
        "v15.0 (Чистый Профит)",
        "Запустить прибыльный бэктест",
        "Комиссии снижены на 96%",
        "Почему бот теперь в плюсе",
    )
    for text in forbidden:
        assert text not in html, f"misleading claim reintroduced: {text}"

    # Confirm the key reasons for the warning remain visible in source.
    assert "function generateCalibratedCandles" in html
    assert "const hasEdge" in html and "edgeStrength" in html
    assert "const keep = st.net > 0 && st.pf >= 1.15" in html
    assert "portTrades.push(...tr)" in html
    assert "if (!candles.length) { usedOffline = true;" in html
    assert "не сравним с Python engine" in html

    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, re.IGNORECASE)
    assert scripts, "no inline JavaScript found"
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(scripts[-1])
        script_path = handle.name
    result = subprocess.run(["node", "--check", script_path], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    Path(script_path).unlink(missing_ok=True)
    print("PASS: v15 demo disclosures, mirrored source, synthetic/selection guardrails, and JavaScript syntax")


if __name__ == "__main__":
    main()

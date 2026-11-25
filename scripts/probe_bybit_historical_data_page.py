#!/usr/bin/env python3
"""Inspect Bybit's official public historical market-data page for dataset catalog metadata."""
import hashlib, json, re, urllib.request
from pathlib import Path
from html.parser import HTMLParser

URL = "https://www.bybit.com/en/derivative-activity/history-data"
req = urllib.request.Request(URL, headers={"User-Agent":"Mozilla/5.0 (compatible; bybit-public-data-research/1.0)","Accept":"text/html"})
with urllib.request.urlopen(req, timeout=45) as response:
    status = response.status
    html = response.read().decode("utf-8", errors="replace")

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts=[]
        self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=="script" and a.get("src"): self.scripts.append(a["src"])
        if tag=="a" and a.get("href"): self.links.append(a["href"])

p=Tags(); p.feed(html)
terms=("funding","mark price","mark_price","premium","history-data","data product","download")
matches=[]
for term in terms:
    for m in list(re.finditer(re.escape(term),html,re.I))[:12]:
        matches.append({"term":term,"offset":m.start(),"context":html[max(0,m.start()-180):m.start()+360]})
result={
 "url":URL,"http_status":status,"html_bytes":len(html),
 "sha256":hashlib.sha256(html.encode()).hexdigest(),
 "title":(re.search(r"<title[^>]*>(.*?)</title>",html,re.I|re.S).group(1) if re.search(r"<title[^>]*>(.*?)</title>",html,re.I|re.S) else None),
 "scripts":p.scripts,"links":p.links[:120],"matches":matches[:80],
}
Path("bybit_history_page_probe").mkdir(exist_ok=True)
Path("bybit_history_page_probe/result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

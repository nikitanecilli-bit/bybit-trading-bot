#!/usr/bin/env python3
"""Inspect Bybit's official public historical market-data page and its own page bundle."""
import hashlib, json, re, urllib.request
from pathlib import Path
from html.parser import HTMLParser

BASE = "https://www.bybit.com"
URL = BASE + "/en/derivative-activity/history-data"
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; bybit-public-data-research/1.1)","Accept":"text/html,application/javascript,*/*"}

def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=60) as response:
        return response.status,response.read()

status,raw=get(URL)
html=raw.decode("utf-8",errors="replace")

class Tags(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts=[]; self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="script" and a.get("src"): self.scripts.append(a["src"])
        if tag=="a" and a.get("href"): self.links.append(a["href"])

p=Tags(); p.feed(html)
page_scripts=[x for x in p.scripts if "pages/history-data-" in x]
bundles=[]
for path in page_scripts:
    js_status,js_raw=get(BASE+path)
    js=js_raw.decode("utf-8",errors="replace")
    patterns=(r'["\']([^"\']{0,180}(?:/api/|/v[0-9]/|historyData|history-data|dataProduct|download)[^"\']{0,180})["\']')
    strings=[]
    for pat in patterns:
        for m in re.finditer(pat,js,re.I):
            value=m.group(1)
            if value not in strings: strings.append(value)
    bundles.append({"path":path,"status":js_status,"bytes":len(js_raw),"sha256":hashlib.sha256(js_raw).hexdigest(),"matches":strings[:300],"snippet":js[:1200]})

terms=("funding","mark price","mark_price","premium","history-data","data product","download")
matches=[]
for term in terms:
    for m in list(re.finditer(re.escape(term),html,re.I))[:8]:
        matches.append({"term":term,"offset":m.start(),"context":html[max(0,m.start()-140):m.start()+260]})
result={"url":URL,"http_status":status,"html_bytes":len(raw),"html_sha256":hashlib.sha256(raw).hexdigest(),"scripts":p.scripts,"page_scripts":page_scripts,"links":p.links[:120],"matches":matches,"bundles":bundles}
Path("bybit_history_page_probe").mkdir(exist_ok=True)
Path("bybit_history_page_probe/result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

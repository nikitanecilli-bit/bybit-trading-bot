#!/usr/bin/env python3
"""Inspect Bybit's official public historical market-data catalog and list-products API."""
import hashlib, json, re, urllib.request
from pathlib import Path
from html.parser import HTMLParser

BASE="https://www.bybit.com"
URL=BASE+"/en/derivative-activity/history-data"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; bybit-public-data-research/1.3)","Accept":"text/html,application/javascript,application/json,*/*","Referer":URL,"Origin":BASE}

def get(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=60) as response:
        return response.status,response.read(),dict(response.headers)

status,raw,_=get(URL)
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
    js_status,js_raw,_=get(BASE+path)
    js=js_raw.decode("utf-8",errors="replace")
    strings=[]
    contexts=[]
    for m in re.finditer(r'"([^"]{1,400})"',js):
        value=m.group(1)
        if re.search(r'api/|/v[0-9]/|history.?data|data.?product|download|funding|mark.?price|premium',value,re.I) and value not in strings:
            strings.append(value)
    for endpoint in ("/quote/public/support/download/list-products","/quote/public/support/download/list-options","/quote/public/support/download/list-files"):
        pos=js.find(endpoint)
        if pos>=0: contexts.append({"endpoint":endpoint,"context":js[max(0,pos-1400):pos+1800]})
    bundles.append({"path":path,"status":js_status,"bytes":len(js_raw),"sha256":hashlib.sha256(js_raw).hexdigest(),"matches":strings[:400],"contexts":contexts})

api_probe=[]
for path in ("/quote/public/support/download/list-products","/quote/public/support/download/list-options","/quote/public/support/download/list-files"):
    try:
        st,data,headers=get(BASE+path)
        api_probe.append({"path":path,"status":st,"headers":{k:v for k,v in headers.items() if k.lower() in ("content-type","content-length","server")},"body":data.decode("utf-8",errors="replace")[:5000]})
    except Exception as e:
        api_probe.append({"path":path,"error":repr(e)})

core_probe=[]
for path in ("/static/data-core/data-core.latest.min.js",):
    try:
        st,data,_=get(BASE+path)
        js=data.decode("utf-8",errors="replace")
        hits=[]
        for m in re.finditer(r'"([^"]{1,300})"',js):
            v=m.group(1)
            if re.search(r'api\\.bybit|api2|baseURL|quote/public|api\\.bytick|api\\.bybit',v,re.I) and v not in hits:
                hits.append(v)
        core_probe.append({"path":path,"status":st,"bytes":len(data),"matches":hits[:300]})
    except Exception as e:
        core_probe.append({"path":path,"error":repr(e)})
shared_script_hits=[]
for path in p.scripts:
    if not path.endswith(".js") or "history-data-" in path or "monitor" in path:
        continue
    try:
        st,data,_=get(BASE+path)
        js=data.decode("utf-8",errors="replace")
        snippets=[]
        for term in ("api.bybit.com","api2.bybit.com","api.bytick.com","baseURL","getApiHost","serviceDomainList","serviceHost","apiHost","10831:","ml:function","ml:"):
            pos=js.find(term)
            if pos>=0: snippets.append({"term":term,"context":js[max(0,pos-250):pos+650]})
        if snippets:
            shared_script_hits.append({"path":path,"status":st,"bytes":len(data),"snippets":snippets})
    except Exception as e:
        shared_script_hits.append({"path":path,"error":repr(e)})
result={"url":URL,"http_status":status,"html_bytes":len(raw),"html_sha256":hashlib.sha256(raw).hexdigest(),"scripts":p.scripts,"page_scripts":page_scripts,"links":p.links[:120],"bundles":bundles,"api_probe":api_probe,"core_probe":core_probe,"shared_script_hits":shared_script_hits}
Path("bybit_history_page_probe").mkdir(exist_ok=True)
Path("bybit_history_page_probe/result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

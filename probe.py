import json, urllib.request, http.cookiejar
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept-Language": "cs-CZ,cs;q=0.9", "Accept": "application/json, text/plain, */*"}
def go(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={**H, **({"Content-Type": "application/json"} if body else {})})
    try:
        with op.open(req, timeout=30) as r:
            t = r.read().decode("utf-8", "replace"); print(url, r.status, len(t)); return t
    except Exception as e:
        print(url, "ERR", e, getattr(e, "read", lambda: b"")()[:300]); return None
go("https://www.tipsport.cz/")
print("cookies:", [c.name for c in cj])
t = go("https://www.tipsport.cz/rest/offer/v2/offer?limit=75", {"results": False, "highlightAnyTime": False, "limit": 75, "order": "DATESTART", "type": "COMPETITION", "id": 118, "matchViewFilters": [], "withLive": True})
if t:
    print(t[:1500])

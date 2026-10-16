"""临时：在 runner 上读网页正文（合并前删除）。"""
import json, re, sys, urllib.request, html
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
for u in open(sys.argv[1]):
    u=u.strip()
    if not u: continue
    print("\n######",u,flush=True)
    try:
        s=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30).read().decode('utf-8','replace')
    except Exception as e:
        print("ERR",e); continue
    try:
        d=json.loads(s); t=d.get('body') or d.get('content') or json.dumps(d)[:20000]
        print('TITLE',d.get('title'),'DATE',d.get('date') or d.get('publishFrom'))
        s=t if isinstance(t,str) else json.dumps(t)
    except Exception: pass
    s=re.sub(r'<script.*?</script>|<style.*?</style>','',s,flags=re.S)
    s=html.unescape(re.sub(r'<[^>]+>','\n',s))
    s=re.sub(r'\n\s*\n+','\n',s)
    print(s[:12000])

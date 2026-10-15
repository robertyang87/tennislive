"""封面候选第五轮：Unsplash napi、Flickr 搜索页（CC），找「球压在网带上」的高清实拍。"""
import json, os, re, time, urllib.parse, urllib.request
OUT="research/let-not-net-2026/cover_cands5"; os.makedirs(OUT,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
def fetch(u): return urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60).read()
rows=[]
for q in ["tennis ball net","tennis net ball","tennis ball on net","tennis ball net tape","tennis let","ball net tennis court"]:
    try:
        d=json.loads(fetch("https://unsplash.com/napi/search/photos?"+urllib.parse.urlencode({"query":q,"per_page":30})))
        for r in d.get("results",[]):
            if not isinstance(r,dict): continue
            u=r.get("urls") or {}
            rows.append({"src":"unsplash","q":q,"id":r.get("id"),"w":r.get("width"),"h":r.get("height"),"desc":r.get("alt_description") or r.get("description") or "","author":(r.get("user") or {}).get("name"),"page":(r.get("links") or {}).get("html"),"full":u.get("raw"),"thumb":u.get("small"),"premium":r.get("premium")})
        print("unsplash",q,len(d.get("results",[])))
    except Exception as e: print("ERR unsplash",q,str(e)[:100])
    time.sleep(2)
for q in ["net cord tennis","tennis ball net","tennis let"]:
    try:
        html=fetch("https://www.flickr.com/search/?"+urllib.parse.urlencode({"text":q,"license":"2,3,4,5,6,9,10"})).decode("utf-8","ignore")
        print("flickr",q,len(html))
        for m in re.finditer(r'"id":"(\d{8,12})","secret":"(\w+)","server":"(\d+)".{0,400}?"title":"([^"]*)"',html):
            pid,sec,srv,title=m.groups()
            rows.append({"src":"flickr","q":q,"id":pid,"desc":title,"page":f"https://www.flickr.com/photo.gne?id={pid}","thumb":f"https://live.staticflickr.com/{srv}/{pid}_{sec}_n.jpg"})
    except Exception as e: print("ERR flickr",q,str(e)[:100])
    time.sleep(2)
seen=set(); keep=[]
for n,r in enumerate(rows):
    if r["id"] in seen or not r.get("thumb"): continue
    seen.add(r["id"])
    fn=f"{OUT}/{r['src'][0]}{n:03d}.jpg"
    try: open(fn,"wb").write(fetch(r["thumb"])); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",r["id"],str(e)[:80])
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

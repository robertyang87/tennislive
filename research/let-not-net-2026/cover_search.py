"""封面候选第三轮：Getty 搜索页（职业赛「球压网带」）＋ Unsplash，存缩略图和元数据。"""
import json, os, re, time, urllib.parse, urllib.request
OUT="research/let-not-net-2026/cover_cands3"; os.makedirs(OUT,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60).read()
rows=[]
for q in ["net cord tennis","tennis ball net cord","tennis ball on net","tennis let serve","tennis ball clips net","net cord sensor tennis","umpire let tennis"]:
    u="https://www.gettyimages.com/search/2/image?"+urllib.parse.urlencode({"phrase":q,"sort":"best","family":"editorial"})
    try:
        html=fetch(u).decode("utf-8","ignore")
        print("getty",q,len(html))
        ids=re.findall(r'/detail/news-photo/([a-z0-9-]+)/(\d{6,12})',html)
        seen=set()
        for slug,i in ids:
            if i in seen: continue
            seen.add(i); rows.append({"src":"getty","q":q,"id":i,"slug":slug,"thumb":f"https://media.gettyimages.com/id/{i}/photo/{slug}.jpg?s=612x612&w=0&k=20"})
            if len(seen)>=24: break
    except Exception as e: print("ERR getty",q,e)
    time.sleep(2)
for q in ["tennis ball net","tennis net ball","tennis ball on net tape"]:
    u="https://unsplash.com/napi/search/photos?"+urllib.parse.urlencode({"query":q,"per_page":30})
    try:
        d=json.loads(fetch(u))
        for r in d.get("results",[]):
            rows.append({"src":"unsplash","q":q,"id":r["id"],"w":r.get("width"),"h":r.get("height"),"desc":r.get("alt_description") or r.get("description"),"author":(r.get("user") or {}).get("name"),"page":(r.get("links") or {}).get("html"),"full":(r.get("urls") or {}).get("raw"),"thumb":(r.get("urls") or {}).get("small")})
        print("unsplash",q,len(d.get("results",[])))
    except Exception as e: print("ERR unsplash",q,e)
    time.sleep(2)
keep=[]
for n,r in enumerate(rows):
    fn=f"{OUT}/{r['src'][0]}{n:03d}.jpg"
    try: open(fn,"wb").write(fetch(r["thumb"])); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",r.get("id"),e)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

"""封面候选第二轮：Commons 搜索 + 分类，按 Let 场景（球压网带、主裁、网前裁判）找 ≥2400px 实拍。"""
import json, os, time, urllib.parse, urllib.request
UA={"User-Agent":"tennislive-cover-search/1.0 (github.com/robertyang87/tennislive; contact via repo)"}
OUT="research/let-not-net-2026/cover_cands2"; os.makedirs(OUT,exist_ok=True)
Q=["net cord tennis","netcord","tennis ball net tape","tennis ball net match","ball net Wimbledon","ball net Roland Garros","ball net US Open tennis","tennis ball top of net","chair umpire tennis","tennis umpire microphone","net judge tennis","tennis umpire chair Wimbledon","tennis service let","tennis ball net Australian Open","tennis net sensor"]
CATS=["Category:Tennis nets","Category:Tennis umpires","Category:Chair umpires (tennis)","Category:Line judges (tennis)","Category:Net judges"]
def get(u,tries=5):
    for t in range(tries):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60))
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(8*(t+1)); continue
            raise
    raise RuntimeError("429 x5")
def add(rows,pages,q):
    for p in pages:
        ii=(p.get("imageinfo") or [{}])[0]
        if ii.get("width",0)<2400 or ii.get("mime","image/jpeg") not in ("image/jpeg",): continue
        md=ii.get("extmetadata",{})
        rows[p["title"]]={"q":q,"title":p["title"],"w":ii["width"],"h":ii["height"],"url":ii["url"],"thumb":ii.get("thumburl"),"desc":md.get("ImageDescription",{}).get("value","")[:300],"license":md.get("LicenseShortName",{}).get("value",""),"artist":md.get("Artist",{}).get("value","")[:160],"date":md.get("DateTimeOriginal",{}).get("value","")[:40],"page":ii.get("descriptionurl")}
rows={}
base={"action":"query","format":"json","prop":"imageinfo","iiprop":"url|size|mime|extmetadata","iiurlwidth":640}
for q in Q:
    try: d=get("https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({**base,"generator":"search","gsrsearch":f"filetype:bitmap {q}","gsrnamespace":6,"gsrlimit":50}))
    except Exception as e: print("ERR",q,e); continue
    add(rows,(d.get("query",{}).get("pages") or {}).values(),q); time.sleep(3)
for c in CATS:
    try: d=get("https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({**base,"generator":"categorymembers","gcmtitle":c,"gcmtype":"file","gcmlimit":200}))
    except Exception as e: print("ERR",c,e); continue
    add(rows,(d.get("query",{}).get("pages") or {}).values(),c); time.sleep(3)
print(len(rows),"candidates")
keep=[]
for i,(k,r) in enumerate(rows.items()):
    if not r.get("thumb"): continue
    fn=f"{OUT}/{i:03d}.jpg"
    for t in range(4):
        try:
            open(fn,"wb").write(urllib.request.urlopen(urllib.request.Request(r["thumb"],headers=UA),timeout=60).read()); r["file"]=fn; keep.append(r); break
        except Exception as e: time.sleep(5*(t+1))
    time.sleep(0.5)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

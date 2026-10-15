"""封面候选：Commons 搜索 + 转载 AP 原图的新闻站 WordPress 媒体库，找「Fault 的场景」（司线喊失误、脚误、发球）。"""
import json, os, re, time, urllib.parse, urllib.request
OUT="research/fault-not-out-2026/cover_cands"; os.makedirs(OUT,exist_ok=True)
UA={"User-Agent":"tennislive-cover-search/1.0 (github.com/robertyang87/tennislive)"}
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def get(u,h=UA): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=h),timeout=60).read())
rows={}
for q in ["tennis line judge","line judge Wimbledon","tennis linesman","line umpire tennis","tennis foot fault","tennis serve baseline foot","tennis service line judge","tennis line judge signal out","line judge US Open","line judge Australian Open"]:
    u="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","format":"json","generator":"search","gsrsearch":f"filetype:bitmap {q}","gsrnamespace":6,"gsrlimit":50,"prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":640})
    try: d=get(u)
    except Exception as e: print("ERR commons",q,e); continue
    for p in (d.get("query",{}).get("pages") or {}).values():
        ii=(p.get("imageinfo") or [{}])[0]
        if ii.get("width",0)<2000: continue
        md=ii.get("extmetadata",{})
        rows[p["title"]]={"q":q,"src":"commons","title":p["title"],"w":ii["width"],"h":ii["height"],"url":ii["url"],"thumb":ii.get("thumburl"),"desc":re.sub("<[^>]+>","",md.get("ImageDescription",{}).get("value",""))[:300],"license":md.get("LicenseShortName",{}).get("value",""),"artist":re.sub("<[^>]+>","",md.get("Artist",{}).get("value",""))[:120],"date":md.get("DateTimeOriginal",{}).get("value","")[:40]}
    time.sleep(1)
print("commons",len(rows))
SITES=["wtop.com","www.kxan.com","www.wfla.com","www.kron4.com","www.wate.com","www.pix11.com","www.ktla.com","www.wkrg.com","www.8newsnow.com","www.mynorthwest.com"]
for s in SITES:
    ok=0
    for q in ["line judge","foot fault","double fault","line umpire","linesman","electronic line calling","line judges","service line"]:
        u=f"https://{s}/wp-json/wp/v2/media?"+urllib.parse.urlencode({"search":q,"per_page":50})
        try: d=get(u,H); ok+=1
        except Exception as e:
            print("ERR",s,q,str(e)[:80])
            if ok==0: break
            continue
        for m in d if isinstance(d,list) else []:
            if not isinstance(m,dict): continue
            def _r(x): return str((x or {}).get("rendered","") if isinstance(x,dict) else (x or ""))
            cap=re.sub("<[^>]+>","",_r(m.get("caption"))+" "+_r(m.get("title")))
            if not re.search("tennis|open|wimbledon",cap,re.I): continue
            md=m.get("media_details") or {}
            if not isinstance(md,dict): continue
            src=m.get("source_url","") or ""
            orig=re.sub(r"-scaled(\.\w+)$",r"\1",src)
            sizes=md.get("sizes") or {}
            th=((sizes.get("medium") or sizes.get("thumbnail") or {}) if isinstance(sizes,dict) else {}).get("source_url") or src
            rows[orig]={"src":"wp:"+s,"q":q,"w":md.get("width",0),"h":md.get("height",0),"url":orig,"thumb":th,"desc":cap.strip()[:500],"date":m.get("date")}
        time.sleep(1)
    print(s,ok,len(rows))
keep=[]
for n,(k,r) in enumerate(rows.items()):
    if not r.get("thumb"): continue
    fn=f"{OUT}/{n:03d}.jpg"
    try: open(fn,"wb").write(urllib.request.urlopen(urllib.request.Request(r["thumb"],headers=H),timeout=40).read()); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",k,e)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

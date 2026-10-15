"""封面候选第二轮：AP 原图转载站 WP 媒体库，找司线做判罚手势的大图、以及同一张 AP 图更高分辨率的版本。"""
import json, os, re, time, urllib.parse, urllib.request
OUT="research/fault-not-out-2026/cover_cands2"; os.makedirs(OUT,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def get(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=40).read())
def _r(x): return str((x or {}).get("rendered","") if isinstance(x,dict) else (x or ""))
SITES=["wtop.com","www.kxan.com","www.wfla.com","www.kron4.com","www.wate.com","www.pix11.com","www.ktla.com","www.wkrg.com","www.8newsnow.com","www.mynorthwest.com","www.wsls.com","www.ksat.com","www.clickondetroit.com","www.news4jax.com","www.local10.com","www.click2houston.com"]
QS=["line judge makes a call","linesman gestures","line judge signals","line judge calls","linesman calls","line judge gestures","calls a fault","foot fault","Pavliuchenkova Zheng line judge","line judge reacts","serve line judge"]
rows={}
for s in SITES:
    ok=0
    for q in QS:
        try: d=get(f"https://{s}/wp-json/wp/v2/media?"+urllib.parse.urlencode({"search":q,"per_page":50})); ok+=1
        except Exception as e:
            print("ERR",s,q,str(e)[:60])
            if ok==0: break
            continue
        for m in d if isinstance(d,list) else []:
            if not isinstance(m,dict): continue
            cap=re.sub("<[^>]+>","",_r(m.get("caption"))+" "+_r(m.get("title")))
            if not re.search(r"line ?judge|linesman|lineswoman|line umpire|foot fault",cap,re.I): continue
            md=m.get("media_details") or {}
            if not isinstance(md,dict): continue
            src=str(m.get("source_url","") or ""); orig=re.sub(r"-scaled(\.\w+)$",r"\1",src)
            sizes=md.get("sizes") or {}
            th=((sizes.get("medium") or sizes.get("thumbnail") or {}) if isinstance(sizes,dict) else {}).get("source_url") or src
            k=os.path.basename(orig)
            if k in rows and rows[k]["w"]>=md.get("width",0): continue
            rows[k]={"src":"wp:"+s,"q":q,"w":md.get("width",0),"h":md.get("height",0),"url":orig,"thumb":th,"desc":cap.strip()[:500],"date":m.get("date")}
        time.sleep(0.5)
    print(s,ok,len(rows))
keep=[]
for n,(k,r) in enumerate(rows.items()):
    fn=f"{OUT}/{n:03d}.jpg"
    try: open(fn,"wb").write(urllib.request.urlopen(urllib.request.Request(r["thumb"],headers=H),timeout=40).read()); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",k,e)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

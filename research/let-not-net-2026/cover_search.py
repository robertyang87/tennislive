"""封面候选第四轮：转载 AP 原图的新闻站 WordPress 媒体库（WP REST 搜说明），找「Let 场景」。"""
import json, os, re, time, urllib.parse, urllib.request
OUT="research/let-not-net-2026/cover_cands4"; os.makedirs(OUT,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITES=["wtop.com","www.kxan.com","www.wfla.com","www.pix11.com","www.ktla.com","www.kron4.com","www.wate.com","www.wkrg.com","www.8newsnow.com","fox8.com","www.wgnradio.com","www.boston.com","www.mynorthwest.com"]
QS=["net cord","netcord","hits the net","hit the net","clips the net","let serve","net judge","net umpire","ball on the net","tennis net","chair umpire","umpire Wimbledon","umpire Open tennis"]
def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=40).read())
rows={}
for s in SITES:
    ok=0
    for q in QS:
        u=f"https://{s}/wp-json/wp/v2/media?"+urllib.parse.urlencode({"search":q,"per_page":50})
        try: d=get(u); ok+=1
        except Exception as e:
            print("ERR",s,q,str(e)[:80]); 
            if ok==0: break
            continue
        if not isinstance(d,list): continue
        for m in d:
            if not isinstance(m,dict): continue
            c=m.get("caption"); t=m.get("title"); cap=re.sub("<[^>]+>","",(c.get("rendered","") if isinstance(c,dict) else str(c or ""))+" "+(t.get("rendered","") if isinstance(t,dict) else str(t or "")))
            if "tennis" not in cap.lower() and "open" not in cap.lower() and "wimbledon" not in cap.lower(): continue
            md=m.get("media_details") or {}
            w,h=md.get("width",0),md.get("height",0)
            src=m.get("source_url","")
            orig=re.sub(r"-scaled(\.\w+)$",r"\1",src)
            sizes=md.get("sizes") or {}
            th=(sizes.get("medium") or sizes.get("thumbnail") or {}).get("source_url") or src
            rows[orig]={"site":s,"q":q,"w":w,"h":h,"url":orig,"src":src,"thumb":th,"caption":cap.strip()[:500],"date":m.get("date")}
        time.sleep(1)
    print(s,"ok queries",ok,"rows",len(rows))
keep=[]
for n,(k,r) in enumerate(rows.items()):
    fn=f"{OUT}/{n:03d}.jpg"
    try: open(fn,"wb").write(urllib.request.urlopen(urllib.request.Request(r["thumb"],headers=H),timeout=40).read()); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",k,e)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

"""封面候选：Commons / Openverse 搜「Let 的场景」实拍大图，存缩略图和元数据供挑选。"""
import json, os, urllib.parse, urllib.request
UA={"User-Agent":"tennislive-cover-search/1.0 (github.com/robertyang87/tennislive)"}
OUT="research/let-not-net-2026/cover_cands"; os.makedirs(OUT,exist_ok=True)
Q=["tennis net cord","tennis ball net cord","tennis ball hitting net","tennis ball on net","net cord judge tennis","net judge Wimbledon","tennis umpire let","tennis serve net","tennis net tape ball","Wimbledon net cord","tennis ball touches net","tennis net close up ball"]
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60))
rows={}
for q in Q:
    u="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","format":"json","generator":"search","gsrsearch":f"filetype:bitmap {q}","gsrnamespace":6,"gsrlimit":40,"prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":640})
    try: d=get(u)
    except Exception as e: print("ERR commons",q,e); continue
    for p in (d.get("query",{}).get("pages") or {}).values():
        ii=(p.get("imageinfo") or [{}])[0]
        if ii.get("width",0)<2400: continue
        md=ii.get("extmetadata",{})
        rows[p["title"]]={"q":q,"src":"commons","title":p["title"],"w":ii["width"],"h":ii["height"],"url":ii["url"],"thumb":ii.get("thumburl"),"desc":(md.get("ImageDescription",{}).get("value","")[:300]),"license":md.get("LicenseShortName",{}).get("value",""),"artist":md.get("Artist",{}).get("value","")[:120],"date":md.get("DateTimeOriginal",{}).get("value","")[:40]}
    u="https://api.openverse.org/v1/images/?"+urllib.parse.urlencode({"q":q,"page_size":40})
    try: d=get(u)
    except Exception as e: print("ERR openverse",q,e); continue
    for r in d.get("results",[]):
        if (r.get("width") or 0)<2400: continue
        rows[r["url"]]={"q":q,"src":"openverse:"+str(r.get("source")),"title":r.get("title"),"w":r.get("width"),"h":r.get("height"),"url":r["url"],"thumb":r.get("thumbnail"),"desc":"","license":f'{r.get("license")} {r.get("license_version")}',"artist":r.get("creator"),"date":"","landing":r.get("foreign_landing_url")}
print(len(rows),"candidates ≥2400px")
keep=[]
for i,(k,r) in enumerate(rows.items()):
    if not r.get("thumb"): continue
    fn=f"{OUT}/{i:03d}.jpg"
    try:
        data=urllib.request.urlopen(urllib.request.Request(r["thumb"],headers=UA),timeout=60).read()
        open(fn,"wb").write(data); r["file"]=fn; keep.append(r)
    except Exception as e: print("thumb fail",k,e)
json.dump(keep,open(f"{OUT}/index.json","w"),ensure_ascii=False,indent=1)
print(len(keep),"thumbs")

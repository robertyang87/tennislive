"""临时：在 runner 上翻 ATP Media 照片接口，挑福基纳上海（及成都）实拍，缩到 2400 长边存进分支。"""
import io, json, os, urllib.request
from datetime import datetime, timezone
from PIL import Image
API="https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/?pageSize=100&page={}"
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out="research/fokina-story-2026/photos"; os.makedirs(out,exist_ok=True)
since=datetime(2026,9,20,tzinfo=timezone.utc).timestamp()*1000
rows=[]
for p in range(0,40):
    d=json.load(urllib.request.urlopen(urllib.request.Request(API.format(p),headers=UA),timeout=60))
    items=d.get("content") or []
    if not items: break
    for it in items:
        url=str(it.get("imageUrl") or "").split("?")[0]; t=str(it.get("title") or "")
        hay=(t+" "+url).lower()
        if "davidovich" in hay or "fokina" in hay:
            rows.append({"id":it.get("id"),"title":t,"url":url,"pub":it.get("publishFrom"),"orig":it.get("originalDetails")})
    last=items[-1].get("publishFrom") or 0
    print("page",p,len(items),datetime.fromtimestamp(last/1000,timezone.utc),flush=True)
    if last<since: break
print(len(rows),"hits")
for r in rows: print(r["id"],r["title"],r["url"].rsplit('/',1)[-1],r["orig"],datetime.fromtimestamp((r["pub"] or 0)/1000,timezone.utc))
keep=[]
for r in rows[:60]:
    try:
        b=urllib.request.urlopen(urllib.request.Request(r["url"],headers=UA),timeout=90).read()
        im=Image.open(io.BytesIO(b)); ex=im.getexif(); dto=""
        try: dto=im._getexif().get(36867,"")
        except Exception: pass
        r["exif"]=str(dto); r["size"]=im.size
        im=im.convert("RGB"); im.thumbnail((2400,2400))
        fn=f'{r["id"]}.jpg'; im.save(f"{out}/{fn}",quality=88); r["file"]=fn; keep.append(r)
        print("saved",fn,r["size"],dto,flush=True)
    except Exception as e: print("ERR",r["url"],e)
json.dump(keep,open(f"{out}/index.json","w"),ensure_ascii=False,indent=1,default=str)

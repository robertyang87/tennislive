"""临时：①ATP Media 官方图库里梅德韦杰夫名场面的高清图（按标签查，再翻页兜底）②美网图片接口 ③YouTube 官方源片检索。合并前删除。"""
import io, json, os, subprocess, urllib.request, urllib.parse
from PIL import Image
OUT = "research/medvedev-not-villain-2026/probe2"; os.makedirs(OUT+"/th", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def get(u, raw=False):
    b = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read()
    return b if raw else json.loads(b)
log = open(OUT+"/log.txt", "w")
def p(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.write(s+"\n"); log.flush()
BASE = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/"
rows = {}
def add(items, how):
    for it in items:
        t = it.get("title") or ""; url = it.get("imageUrl") or ""
        if "medvedev" not in (t+url+json.dumps(it.get("tags") or [])).lower(): continue
        od = it.get("originalDetails") or {}
        rows[it.get("id")] = {"title": t, "url": url, "w": od.get("width"), "h": od.get("height"), "date": it.get("date") or it.get("publishFrom"), "desc": (it.get("description") or "")[:200], "tags": [x.get("label") for x in (it.get("tags") or [])][:12], "how": how}
try:
    d = get(BASE+"?pageSize=1&page=0"); it = d["content"][0]
    p("SAMPLE KEYS", sorted(it.keys())); p("SAMPLE TAGS", json.dumps(it.get("tags"))[:800]); p("PAGEINFO", d.get("pageInfo"))
except Exception as e: p("ERR sample", e)
for q in ["tagNames=Daniil%20Medvedev", "tagNames=Medvedev", "q=Medvedev", "searchTerm=Medvedev", "title=Medvedev", "tagExpression=%22Daniil%20Medvedev%22"]:
    for page in range(0, 40):
        try: d = get(BASE+f"?pageSize=100&page={page}&{q}")
        except Exception as e: p("ERR", q, page, e); break
        items = d.get("content") or []
        n0 = len(rows); add(items, q)
        if page == 0: p("QUERY", q, "pageInfo", d.get("pageInfo"), "first", [x.get("title") for x in items[:3]])
        if not items or len(rows) == n0 and page > 2: break
    p("after", q, len(rows))
json.dump(list(rows.values()), open(OUT+"/atpmedia.json", "w"), ensure_ascii=False, indent=1)
KEYS = ["madrid", "cincinnati", "shanghai", "monte", "winston", "us open", "rome", "paris", "finals", "halle", "beijing", "miami", "indian", "toronto", "montreal", "dubai", "doha"]
cands = sorted(rows.values(), key=lambda r: str(r["date"]), reverse=True)
p("TOTAL medvedev", len(cands))
for r in cands: p(r["date"], r["w"], r["h"], "|", r["title"], "|", r["desc"][:120], "|", r["url"])
# 缩略图墙：按年份分组，每组最多 60 张
from collections import defaultdict
grp = defaultdict(list)
for r in cands: grp[str(r["date"])[:4]].append(r)
for y, rs in grp.items():
    ims = []
    for i, r in enumerate(rs[:60]):
        try:
            im = Image.open(io.BytesIO(get(r["url"]+"?width=360" if "?" not in r["url"] else r["url"], raw=True))).convert("RGB"); im.thumbnail((360, 240))
            c = Image.new("RGB", (360, 260), "black"); c.paste(im, (0, 0))
            from PIL import ImageDraw; ImageDraw.Draw(c).text((4, 242), f"{y}-{i} {str(r['date'])[:10]} {r['w']}x{r['h']}", fill="yellow")
            ims.append(c); r["sheet"] = f"{y}-{i}"
        except Exception as e: p("thumb ERR", r["url"], e)
    for s in range(0, len(ims), 20):
        part = ims[s:s+20]; W = Image.new("RGB", (360*5, 260*((len(part)+4)//5)))
        for k, c in enumerate(part): W.paste(c, ((k % 5)*360, (k//5)*260))
        W.save(f"{OUT}/th/{y}_{s//20}.jpg", quality=80)
json.dump(cands, open(OUT+"/atpmedia.json", "w"), ensure_ascii=False, indent=1)
# 美网图片接口：梅德韦杰夫 tag
try:
    cfg = get("https://www.usopen.org/en_US/json/gen/config_web.json"); p("USO cfg keys sample", [k for k in json.dumps(cfg).split('"') if "relatedcontent" in k][:5])
    for pid in ["atpmm58"]:
        d = get(f"https://www.usopen.org/relatedcontent/rest/v2/uso_v1/en/tag?tags={pid}&type=photo&count=200")
        for c in (d.get("content") or [])[:200]:
            p("USO", c.get("date"), "|", c.get("title"), "|", json.dumps(c.get("images") or c.get("image") or "")[:200])
except Exception as e: p("USO ERR", e)
# YouTube 官方源片检索
for q in ["US Open Medvedev Bonzi photographer", "Medvedev Bonzi US Open 2025 highlights", "Medvedev photographer match point US Open crowd", "Medvedev Tien Shanghai 2025 highlights", "Medvedev cramp shirt Shanghai 2025", "Medvedev ball girl shirt Shanghai", "Medvedev rubs balls Shanghai 2024", "Medvedev heat US Open 2023 Rublev someone is going to die"]:
    p("\n###### YT", q)
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", f"ytsearch12:{q}"], capture_output=True, text=True)
    try:
        for e in json.loads(r.stdout).get("entries", []): p(f"{e.get('id')} | {e.get('channel')} | {e.get('duration')} | {e.get('title')}")
    except Exception: p("ERR", r.stderr[-300:])

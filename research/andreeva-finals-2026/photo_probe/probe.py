"""临时：在 runner 上翻 WTA 照片接口里安德烈耶娃（331809）的 2026 照片，拼缩略图墙。用完删。"""
import io, json, sys, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
API = "https://api.wtatennis.com/content/wta/photo/EN/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
def get(url, n=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read() if n is None else r.read(n)
rows = []
for page in range(12):
    d = json.loads(get(f"{API}?pageSize=100&page={page}&references=TENNIS_PLAYER:331809"))
    c = d.get("content") or []
    for it in c:
        od = it.get("originalDetails") or {}
        rows.append({"id": it.get("id"), "title": it.get("title"), "url": str(it.get("imageUrl") or "").split("?")[0],
                     "w": od.get("width"), "h": od.get("height"), "publish": it.get("publishFrom"),
                     "credit": (it.get("metadata") or {}).get("credit")})
    print("page", page, len(c), flush=True)
    if not c: break
print("total", len(rows))
(out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
keep = [r for r in rows if (r["w"] or 0) >= 2000 and str(r["publish"] or "") and "2026" in str(r["title"] or "") + "2026"]
thumbs = []
for i, r in enumerate(keep[:120]):
    try:
        im = Image.open(io.BytesIO(get(r["url"] + "?width=480"))).convert("RGB")
    except Exception as e:
        print("skip", r["url"], e); continue
    im.thumbnail((320, 320)); thumbs.append((i, r, im))
cols = 8; W = 330; H = 360
for sheet in range(0, len(thumbs), 48):
    part = thumbs[sheet:sheet + 48]
    canvas = Image.new("RGB", (cols * W, ((len(part) + cols - 1) // cols) * H), "white")
    d = ImageDraw.Draw(canvas)
    for k, (i, r, im) in enumerate(part):
        x, y = (k % cols) * W, (k // cols) * H
        canvas.paste(im, (x + 5, y + 5)); d.text((x + 5, y + 330), f"#{i} {r['w']}x{r['h']} {str(r['title'])[:38]}", fill="black")
    canvas.save(out / f"sheet-{sheet // 48}.jpg", quality=85)
(out / "keep.json").write_text(json.dumps(keep[:120], ensure_ascii=False, indent=1))

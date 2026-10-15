"""临时第三趟：查封面候选 GettyImages-2270362315 的 Getty 说明（四要素），原图由工作流 fetch 步骤下载。合并前删除。"""
import re, urllib.request, os
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "en-US"}
os.makedirs("research/medvedev-not-villain-2026/probe3", exist_ok=True)
out = open("research/medvedev-not-villain-2026/probe3/getty.txt", "w")
for gid in ["2270362315"]:
    try:
        html = urllib.request.urlopen(urllib.request.Request(f"https://www.gettyimages.com/detail/{gid}", headers=H), timeout=60).read().decode("utf-8", "replace")
        for pat in [r'<meta property="og:description" content="([^"]+)"', r'<meta name="description" content="([^"]+)"', r'"caption":"([^"]+)"', r'<title>([^<]+)</title>']:
            for m in re.findall(pat, html)[:2]: print(gid, pat[:30], m, file=out)
    except Exception as e: print(gid, "ERR", e, file=out)
out.close(); print(open("research/medvedev-not-villain-2026/probe3/getty.txt").read())

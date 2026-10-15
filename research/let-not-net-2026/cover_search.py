"""封面候选第六轮：保存 Flickr 搜索页（CC 授权）原始 HTML，本地解析。"""
import os, time, urllib.parse, urllib.request
OUT="research/let-not-net-2026/cover_cands6"; os.makedirs(OUT,exist_ok=True)
H={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
for i,q in enumerate(["net cord tennis","tennis ball net","tennis let","tennis net cord ball","wimbledon net cord"]):
    try:
        html=urllib.request.urlopen(urllib.request.Request("https://www.flickr.com/search/?"+urllib.parse.urlencode({"text":q,"license":"2,3,4,5,6,9,10"}),headers=H),timeout=60).read()
        open(f"{OUT}/flickr{i}.html","wb").write(html); print(q,len(html))
    except Exception as e: print("ERR",q,e)
    time.sleep(2)

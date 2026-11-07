import datetime,hashlib,json,urllib.request
from pathlib import Path
r=Path('/workspace/jodar-finals-production/final');m=json.loads((r/'published-metadata/render.json').read_text());u=m['video_url'];h=hashlib.sha256();n=0
with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'tennislive-publication-verification'}),timeout=90) as resp:
 status=resp.status
 while True:
  b=resp.read(1048576)
  if not b:break
  h.update(b);n+=len(b)
a={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':u,'http_status':status,'bytes':n,'sha256':h.hexdigest(),'method':'EntirepublicReleasefilestreamedonceandhashed,noseconddiskcopy','expected_sha256':m['film_sha256']}
assert status==200 and n==m['film_bytes'] and h.hexdigest()==m['film_sha256'],a
(r/'publication/release-entire-file-verification.json').write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n');print(json.dumps(a))

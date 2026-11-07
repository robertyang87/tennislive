import concurrent.futures,datetime,hashlib,json,unicodedata,urllib.request,re
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path('/workspace/tiafoe-finals-production');D=ROOT/'final/publication/freshness';D.mkdir(parents=True,exist_ok=True)
old=json.loads((ROOT/'research/race/data-canonical.json').read_text())
urls={'race':old['sources']['live_race'],'singles':old['sources']['official_qualification'],'qualification':old['sources']['tiafoe_qualification']}
def get(kv):
 k,u=kv
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as r:
  b=r.read();v={'url':u,'http_status':r.status,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'headers':{x:r.headers.get(x) for x in ('Date','Age','Last-Modified')}}
 (D/(k+'.html')).write_bytes(b);return k,b,v
results=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(get,urls.items()));raw={k:b for k,b,v in results};ev={k:v for k,b,v in results}
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c)).casefold().strip()
soup=BeautifulSoup(raw['race'],'html.parser');rows=[]
for tr in soup.select('tr'):
 if tr.find('tr'):continue
 cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
 if len(cells)>5 and re.fullmatch(r'\d+',cells[0]) and 1<=int(cells[0])<=15:
  name=re.sub('[✓✗✔✘]','',cells[2]).strip();pts=int(re.sub('[^0-9]','',cells[5]));rows.append({'rank':int(cells[0]),'player':name,'points':pts})
assert len(rows)==15,rows
mismatches=[{'old':o,'now':n} for o,n in zip(old['rows'],rows) if o['rank']!=n['rank'] or norm(o['player'])!=norm(n['player']) or o['points']!=n['points']]
soup=BeautifulSoup(raw['singles'],'html.parser');qualified=sorted({a.get('href','').rstrip('/').split('/')[-1] for a in soup.select('a[href^="/en/players/singles/"]') if a.get('href','').rstrip('/')!='/en/players/singles'})
assert len(qualified)==8,qualified
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshot_sha256':hashlib.sha256((ROOT/'research/race/data-canonical.json').read_bytes()).hexdigest(),'sources':ev,'latest_rows':rows,'qualified_profiles':qualified,'row_mismatches':mismatches,'status':'PASS_CURRENT_SNAPSHOT_UNCHANGED' if not mismatches else 'REVIEW_NEW_POINTS','basis':'Normal public HTTP GET; original film explicitly dates snapshot Nov7 before Paris semifinals.'}
(D/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))

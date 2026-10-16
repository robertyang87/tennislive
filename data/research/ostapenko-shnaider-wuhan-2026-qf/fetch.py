import requests,pathlib,concurrent.futures,json,datetime
p=pathlib.Path('/workspace/scratch/osta-facts');base='https://api.wtatennis.com/tennis'
urls={'stats.json':base+'/tournaments/1075/2026/matches/LS007/stats','pbp.json':base+'/tournaments/1075/2026/matches/LS007/point-by-point','rankings.json':base+'/players/ranked?page=0&pageSize=100&type=rankSingles&sort=asc&name=&metric=SINGLES','draw.pdf':'https://wtafiles.wtatennis.com/pdf/draws/2026/1075/MDS.pdf','oop.pdf':'https://wtafiles.wtatennis.com/pdf/draws/2026/1075/OP.pdf','news.json':'https://api.wtatennis.com/content/wta/news/en/?page=0&pageSize=30&sort=desc','fs-today.raw':'https://global.flashscore.ninja/2/x/feed/f_2_0_0_en_1'}
def one(k,u):
 try:
  r=requests.get(u,timeout=25,headers={'x-fsign':'SW9D1eZo','Referer':'https://www.flashscore.com/'} if k.startswith('fs') else {});p.joinpath(k).write_bytes(r.content);return k,r.status_code,len(r.content)
 except Exception as e:return k,str(e)
print(list(concurrent.futures.ThreadPoolExecutor(7).map(lambda x:one(*x),urls.items())))
p.joinpath('sources.json').write_text(json.dumps({'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'urls':urls},indent=2))

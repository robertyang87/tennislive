"""临时：WTA 官方图库里找斯瓦泰克与赫瓦林斯卡（合并前删除）。"""
import json, urllib.request, datetime
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36","Accept":"application/json"}
def get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
def show(r):
    refs=[x.get('sid') for x in r.get('references',[]) if x.get('type')=='TENNIS_PLAYER']
    t=datetime.datetime.utcfromtimestamp((r.get('publishFrom') or 0)/1000).strftime('%Y-%m-%d')
    od=r.get('originalDetails') or {}
    print(t, r.get('id'), f"{od.get('width')}x{od.get('height')}", refs, (r.get('title') or '')[:90],'|',(r.get('description') or '')[:260].replace('\n',' '),'|',r.get('onDemandUrl') or r.get('imageUrl'),flush=True)
B="https://api.wtatennis.com/content/wta/photo/EN/?pageSize=100"
for q in ["&references=TENNIS_PLAYER:325639","&referenceExpression=TENNIS_PLAYER:325639","&tagNames=Maja%20Chwalinska"]:
    print("\n######",q,flush=True)
    try:
        for page in range(6):
            d=get(B+q+f"&page={page}")
            rows=d.get('content',[])
            if page==0: print('pageInfo',d.get('pageInfo'))
            for r in rows:
                txt=json.dumps(r).lower()
                both='swiatek' in txt or '326408' in txt
                if both or page==0: print('BOTH' if both else '    ',end=' '); show(r)
            if len(rows)<100: break
    except Exception as e: print('ERR',e)

"""拍线集原创数据·稳健性检验：同 mcp_serve_volley_trend.py 的口径，按年代统计不同发球人数、前 3 人占比、去掉前 3 人后的发球上网比例、每人等权平均（≥200 分的发球人）、零发球上网的场次比例。

    python3 -I mcp_serve_volley_robust.py <Match Charting Project 数据目录>
"""
import csv,sys,collections
D=sys.argv[1]
meta={}
for r in csv.DictReader(open(f"{D}/charting-m-matches.csv",encoding='utf-8',errors='replace')):
    meta[r['match_id']]=(r['Date'][:4],r['Player 1'],r['Player 2'])
def period(y):
    y=int(y)
    for lo,hi,lab in [(0,1990,'1970-89'),(1990,2000,'1990-99'),(2000,2005,'2000-04'),(2005,2010,'2005-09'),(2010,2015,'2010-14'),(2015,2020,'2015-19'),(2020,3000,'2020-26')]:
        if lo<=y<hi: return lab
bysrv=collections.defaultdict(lambda:[0,0])   # (period,server)->[nonace pts, sv]
match_sv=collections.defaultdict(lambda:[0,0])
for f in ['charting-m-points-to-2009.csv','charting-m-points-2010s.csv','charting-m-points-2020s.csv']:
    for r in csv.DictReader(open(f"{D}/{f}",encoding='utf-8',errors='replace')):
        m=meta.get(r['match_id'])
        if not m or not m[0].isdigit(): continue
        s=(r['2nd'] or r['1st']).lstrip('c')
        if not s or s[0] not in '0456': continue
        i=1
        while i<len(s) and s[i] in '0123456789': i+=1
        rest=s[i:]
        if rest.startswith('*') or rest.startswith('+*'): continue
        sv=rest.startswith('+')
        svr=m[1] if r['Svr']=='1' else m[2]
        p=period(m[0]); a=bysrv[(p,svr)]; a[0]+=1; a[1]+=sv
        b=match_sv[(p,r['match_id'])]; b[0]+=1; b[1]+=sv
order=['1970-89','1990-99','2000-04','2005-09','2010-14','2015-19','2020-26']
print('年代      不同发球人  前3人占分数%  去掉前3人后发球上网%  每人等权平均%  零发球上网的场次%')
for p in order:
    rows=[(k[1],v) for k,v in bysrv.items() if k[0]==p]
    tot=sum(v[0] for _,v in rows)
    top=sorted(rows,key=lambda x:-x[1][0])[:3]
    rest=[v for n,v in rows if n not in {t[0] for t in top}]
    rp=sum(v[0] for v in rest); rs=sum(v[1] for v in rest)
    eq=[v[1]/v[0] for _,v in rows if v[0]>=200]
    ms=[v for k,v in match_sv.items() if k[0]==p]
    zero=sum(1 for v in ms if v[1]==0)/len(ms)
    print(f'{p:9} {len(rows):6}      {100*sum(t[1][0] for t in top)/tot:5.1f}        {100*rs/rp:5.1f}             {100*sum(eq)/len(eq):5.1f} (n={len(eq)})     {100*zero:5.1f}   前3：{", ".join(t[0] for t in top)}')

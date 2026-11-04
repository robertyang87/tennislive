"""拍线集原创数据：Match Charting Project 男子逐分（志愿者逐拍标注，不是官方统计，CC BY-NC-SA 4.0，2026-11-04 下载）。
按年代统计：发球上网占比（去掉 ACE，同 Tennis Abstract 口径；「+」跟在发球后表示发球上网，见 MCP Quick Start Guide）与平均每分拍数；温网单列。

    python3 -I mcp_serve_volley_trend.py <放 charting-m-matches.csv 和 charting-m-points-{to-2009,2010s,2020s}.csv 的目录>

数据：https://github.com/JeffSackmann/tennis_MatchChartingProject
"""
import csv,sys,collections,re
D=sys.argv[1]
SHOTS=set('fbrsvzopuylmhijktq')
meta={}
for r in csv.DictReader(open(f"{D}/charting-m-matches.csv",encoding='utf-8',errors='replace')):
    meta[r['match_id']]=(r['Date'][:4],r['Surface'],r['Tournament'])
def period(y):
    y=int(y)
    for lo,hi,lab in [(0,1990,'1970-89'),(1990,2000,'1990-99'),(2000,2005,'2000-04'),(2005,2010,'2005-09'),(2010,2015,'2010-14'),(2015,2020,'2015-19'),(2020,3000,'2020-26')]:
        if lo<=y<hi: return lab
agg=collections.defaultdict(lambda:[0,0,0,set()])
for f in ['charting-m-points-to-2009.csv','charting-m-points-2010s.csv','charting-m-points-2020s.csv']:
    for r in csv.DictReader(open(f"{D}/{f}",encoding='utf-8',errors='replace')):
        m=meta.get(r['match_id'])
        if not m or not m[0].isdigit(): continue
        s=(r['2nd'] or r['1st']).lstrip('c')
        if not s or s[0] not in '0456': continue
        i=1
        while i<len(s) and s[i] in '0123456789': i+=1
        rest=s[i:]
        ace = rest.startswith('*') or rest.startswith('+*')
        sv = rest.startswith('+')
        nshots=1+sum(1 for ch in s[1:] if ch in SHOTS)
        wim = m[2].startswith('Wimbledon')
        keys=[(period(m[0]),'ALL')]
        if wim: keys.append((period(m[0]),'Wimbledon'))
        for k in keys:
            a=agg[k]
            if not ace: a[0]+=1; a[1]+=sv
            a[2]+=nshots; a[3].add(r['match_id'])
        for k in keys: agg[k+('n',)]=agg.get(k+('n',),0)+1
order=['1970-89','1990-99','2000-04','2005-09','2010-14','2015-19','2020-26']
for surf in ('ALL','Wimbledon'):
    print(f'== {surf}（去掉 ACE 的发球分里，发球上网的占比）')
    for p in order:
        a=agg.get((p,surf)); n=agg.get((p,surf,'n'),0)
        if not a: continue
        flag='' if n>=5000 else '  ← 样本少'
        print(f'{p:9} 场数{len(a[3]):5}  分数{n:7}  发球上网 {100*a[1]/a[0]:5.1f}%  平均拍数 {a[2]/n:4.2f}{flag}')

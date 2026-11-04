"""EP07 原创数据：用 Match Charting Project（志愿者逐拍标注，tennisabstract.com，CC BY-NC-SA 4.0）
验证「发外角和发中路，一发得分率被拉平」和「换边换得太勤」。

    python3 -I mcp_nash.py <放 charting-{m,w}-points-2020s.csv 和 charting-{m,w}-matches.csv 的目录>

数据：https://github.com/JeffSackmann/tennis_MatchChartingProject（2026-11-04 下载）
口径：
- 只看一发；方向取一发记录的第一位：4=外角（wide）、5=追身（body）、6=中路（T）；let（c 开头）去掉 c
- 不管一发进没进，发球方最终赢下这一分就算赢（同 Walker & Wooders 2001 的口径）
- 平分区／占先区按这一局已打的分数奇偶判；抢七按整数比分之和
- 「换边」只看外角和中路（去掉追身），同一场、同一发球人、同一半区的相邻两个一发；
  期望值 = 这个半区里他外角占比 p 时，独立随机的换边概率 2p(1-p)；只算 ≥8 个一发的半区
"""
import csv,sys,collections,json
D=sys.argv[1]
IDX={'0':0,'15':1,'30':2,'40':3,'AD':4}
def court(pts,tb):
    a,b=pts.split('-')
    if tb: s=int(a)+int(b)
    else: s=IDX[a]+IDX[b]
    return 'deuce' if s%2==0 else 'ad'
def load(tour):
    names={}
    for r in csv.DictReader(open(f"{D}/charting-{tour}-matches.csv",encoding='utf-8',errors='replace')):
        names[r['match_id']]=(r['Player 1'],r['Player 2'],r['Date'])
    rows=[]
    for r in csv.DictReader(open(f"{D}/charting-{tour}-points-2020s.csv",encoding='utf-8',errors='replace')):
        f=r['1st'].lstrip('c')
        if not f or f[0] not in '456': continue
        try:
            pts=r['Pts']; a,b=pts.split('-')
            # 抢七里比分是 1-0、3-2 这类整数；出现 0/15/30/40/AD 以外的数就按抢七算（0-0 两种算法都是平分区，不影响）
            tb = not (a in IDX and b in IDX)
            c=court(pts,tb)
        except Exception: continue
        mid=r['match_id']
        if mid not in names: continue
        svr=names[mid][int(r['Svr'])-1]
        rows.append(dict(mid=mid,pt=int(r['Pt']),svr=svr,date=names[mid][2],court=c,d=f[0],win=r['PtWinner']==r['Svr']))
    return rows
def agg(rows,label):
    out={}
    for c in ('deuce','ad'):
        n=collections.Counter(); w=collections.Counter()
        for x in rows:
            if x['court']!=c: continue
            n[x['d']]+=1; w[x['d']]+=x['win']
        tot=sum(n.values())
        out[c]={k:(n[k],round(n[k]/tot,3),round(w[k]/n[k],3)) for k in '456' if n[k]}
    print(label,json.dumps(out))
def serial(rows,label):
    g=collections.defaultdict(list)
    for x in sorted(rows,key=lambda x:(x['mid'],x['pt'])):
        if x['d']=='5': continue
        g[(x['mid'],x['svr'],x['court'])].append(x['d'])
    sw=tot=0; exp=0.0; same_after_T=[0,0]
    for k,seq in g.items():
        if len(seq)<8: continue
        p=seq.count('4')/len(seq)
        for i in range(1,len(seq)):
            tot+=1; sw+= seq[i]!=seq[i-1]; exp+=2*p*(1-p)
    print(label,'consecutive pairs',tot,'observed switch',round(sw/tot,3),'expected if random',round(exp/tot,3),'point games',sum(1 for s in g.values() if len(s)>=8))
for tour in ('m','w'):
    rows=load(tour)
    recent=[x for x in rows if x['date']>='20230101']
    print(tour,'first serves 2020s',len(rows),'since2023',len(recent),'matches',len({x['mid'] for x in recent}))
    agg(recent,f'{tour} ALL 2023+')
    serial(recent,f'{tour} serial 2023+')
    for who in (['Jannik Sinner','Carlos Alcaraz','Novak Djokovic','Alexander Zverev'] if tour=='m' else ['Aryna Sabalenka','Iga Swiatek','Coco Gauff','Qinwen Zheng']):
        rr=[x for x in recent if x['svr']==who]
        print(' ',who,'n',len(rr),'matches',len({x['mid'] for x in rr})); agg(rr,'   '+who); serial(rr,'   '+who)

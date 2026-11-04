"""破发点 vs 其他分：发球方向占比和得分率；朝接发人反手方向的占比（只算右手接发人）。"""
import csv,sys,collections,json
D=sys.argv[1]; IDX={'0':0,'15':1,'30':2,'40':3,'AD':4}
def parse(pts):
    a,b=pts.split('-')
    if a in IDX and b in IDX: return IDX[a],IDX[b],False
    return int(a),int(b),True
def run(tour):
    meta={}
    for r in csv.DictReader(open(f"{D}/charting-{tour}-matches.csv",encoding='utf-8',errors='replace')):
        meta[r['match_id']]=r
    st=collections.defaultdict(lambda: collections.Counter())
    for r in csv.DictReader(open(f"{D}/charting-{tour}-points-2020s.csv",encoding='utf-8',errors='replace')):
        m=meta.get(r['match_id']); 
        if not m or m['Date']<'20230101': continue
        try: s,rcv,tb=parse(r['Pts'])
        except Exception: continue
        if tb: continue
        # Pts 是「发球方-接发方」？MCP 的 Pts 按发球方在前记分
        bp = rcv>=3 and rcv>s   # 接发方 40 且领先（含 AD-接发）→ 破发点
        court='deuce' if (s+rcv)%2==0 else 'ad'
        rh = (m['Pl 2 hand'] if r['Svr']=='1' else m['Pl 1 hand'])=='R'
        win=r['PtWinner']==r['Svr']
        for serve,code in (('1st',r['1st'].lstrip('c')),('2nd',r['2nd'].lstrip('c'))):
            if not code or code[0] not in '456': continue
            if serve=='2nd' and not r['2nd']: continue
            d=code[0]; k=('BP' if bp else 'other',serve)
            st[k]['n']+=1; st[k][d]+=1; st[k]['w'+d]+=win
            if rh and d in '46':
                bh = (court=='deuce' and d=='6') or (court=='ad' and d=='4')
                st[k]['rh']+=1; st[k]['bh']+=bh
            if serve=='1st' and not (len(r['2nd'])>0): pass
    for k,c in sorted(st.items()):
        n=c['n']; print(tour,k,'n',n, {d:(round(c[d]/n,3),round(c['w'+d]/max(c[d],1),3)) for d in '456'}, 'toBackhand(RH recv, wide/T only)',round(c['bh']/max(c['rh'],1),3))
for t in ('m','w'): run(t)

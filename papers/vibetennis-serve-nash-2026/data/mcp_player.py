"""EP07：现役球员个例——一发外角／中路的比例与得分率（2023-01-01 以后，按半区，所有接发人合并）。"""
import csv,sys,collections,math
D=sys.argv[1]; IDX={'0':0,'15':1,'30':2,'40':3,'AD':4}
def p_chi1(x): return math.erfc(math.sqrt(x/2))
meta={r['match_id']:r for r in csv.DictReader(open(f"{D}/charting-m-matches.csv",encoding='utf-8',errors='replace'))}
st=collections.defaultdict(collections.Counter); mt=collections.defaultdict(set)
for r in csv.DictReader(open(f"{D}/charting-m-points-2020s.csv",encoding='utf-8',errors='replace')):
    m=meta.get(r['match_id'])
    if not m or m['Date']<'20230101': continue
    a,b=r['Pts'].split('-') if '-' in r['Pts'] else ('x','x')
    if not(a in IDX and b in IDX): continue
    f=r['1st'].lstrip('c')
    if not f or f[0] not in '456': continue
    svr=m['Player 1'] if r['Svr']=='1' else m['Player 2']; court='deuce' if (IDX[a]+IDX[b])%2==0 else 'ad'
    k=(svr,court); st[k]['n']+=1; st[k][f[0]]+=1; st[k]['w'+f[0]]+=r['PtWinner']==r['Svr']; mt[svr].add(r['match_id'])
for who in ['Jannik Sinner','Carlos Alcaraz','Novak Djokovic','Alexander Zverev','Taylor Fritz','Daniil Medvedev']:
    for c in ('deuce','ad'):
        x=st[(who,c)]; n=x['n']; w4,n4,w6,n6=x['w4'],x['4'],x['w6'],x['6']; p=(w4+w6)/(n4+n6)
        chi=sum((o-e)**2/e for o,e in ((w4,n4*p),(n4-w4,n4*(1-p)),(w6,n6*p),(n6-w6,n6*(1-p))))
        print(f"{who:18s} {len(mt[who]):3d}场 {c:5s} 一发{n:5d} 外角{n4/n:5.1%}({n4}) 中路{n6/n:5.1%}({n6}) | 得分率 外角{w4/n4:5.1%} 中路{w6/n6:5.1%} p={math.erfc(math.sqrt(chi/2)):.3f}")

"""EP07：关键分（局点／破发点／盘点／赛点）上，一发外角和中路的得分率是否仍然相等（均衡理论的直接检验）。
Match Charting Project，2023-01-01 以后；不含抢七。外角=4、追身=5、中路=6；发球方最终赢下这一分算赢。
另做「发球局面」级检验：同一发球人对同一接发人、同一半区（2023–26 合并），外角、中路各 ≥30 个一发，
Pearson 卡方检验两边得分率相等；理论成立时，5% 水平下应约有 5% 被拒绝。"""
import csv,sys,collections,math
D=sys.argv[1]; IDX={'0':0,'15':1,'30':2,'40':3,'AD':4}
def p_chi1(x): return math.erfc(math.sqrt(x/2))
def chi(w1,n1,w2,n2):
    if min(n1,n2)==0: return float('nan'),float('nan')
    p=(w1+w2)/(n1+n2)
    if p in (0,1): return 0,1
    x=sum((o-e)**2/e for o,e in ((w1,n1*p),(n1-w1,n1*(1-p)),(w2,n2*p),(n2-w2,n2*(1-p)))); return x,p_chi1(x)
def run(tour):
    meta={r['match_id']:r for r in csv.DictReader(open(f"{D}/charting-{tour}-matches.csv",encoding='utf-8',errors='replace'))}
    cat=collections.defaultdict(collections.Counter); pg=collections.defaultdict(collections.Counter)
    for r in csv.DictReader(open(f"{D}/charting-{tour}-points-2020s.csv",encoding='utf-8',errors='replace')):
        m=meta.get(r['match_id'])
        if not m or m['Date']<'20230101': continue
        try:
            a,b=r['Pts'].split('-')
            if not(a in IDX and b in IDX): continue
            sp,rp=IDX[a],IDX[b]; sv=int(r['Svr'])
            gs,gr=(int(r['Gm1']),int(r['Gm2'])) if sv==1 else (int(r['Gm2']),int(r['Gm1']))
            ss_,sr=(int(r['Set1']),int(r['Set2'])) if sv==1 else (int(r['Set2']),int(r['Set1']))
            need=3 if m['Best of'].strip()=='5' else 2
        except Exception: continue
        f=r['1st'].lstrip('c')
        if not f or f[0] not in '456': continue
        d=f[0]; win=r['PtWinner']==r['Svr']; court='deuce' if (sp+rp)%2==0 else 'ad'
        gp=sp>=3 and sp>rp; bp=rp>=3 and rp>sp
        setS=gp and gs+1>=6 and gs+1-gr>=2; setR=bp and gr+1>=6 and gr+1-gs>=2
        mpS=setS and ss_==need-1; mpR=setR and sr==need-1
        cats=['all']+(['game point (server)'] if gp else [])+(['break point'] if bp else [])+(['set point (server)'] if setS else [])+(['set point (receiver)'] if setR else [])+(['match point (server)'] if mpS else [])+(['match point (receiver)'] if mpR else [])+(['set point (either)'] if (setS or setR) else [])+(['match point (either)'] if (mpS or mpR) else [])
        if not gp and not bp: cats.append('other')
        for c in cats: cat[c]['n']+=1; cat[c][d]+=1; cat[c]['w'+d]+=win
        if d in '46':
            svr=m['Player 1'] if sv==1 else m['Player 2']; rcv=m['Player 2'] if sv==1 else m['Player 1']
            k=(svr,rcv,court); pg[k][d]+=1; pg[k]['w'+d]+=win
    print(f'== {tour} (2023+) 一发')
    for c in ['all','other','game point (server)','break point','set point (server)','set point (receiver)','match point (server)','match point (receiver)','set point (either)','match point (either)']:
        x=cat[c]; n=x['n']
        if not n: continue
        ww,nw,wt,nt=x['w4'],x['4'],x['w6'],x['6']; chi_,p=chi(ww,nw,wt,nt)
        print(f"{c:24s} n={n:6d} 外角{nw/n:5.1%} 追身{x['5']/n:5.1%} 中路{nt/n:5.1%} | 得分率 外角 {ww/nw:5.1%}({nw}) 中路 {wt/nt:5.1%}({nt}) 追身 {x['w5']/max(x['5'],1):5.1%} | 外角vs中路 p={p:.3f}")
    rej=tot=0
    for k,x in pg.items():
        if x['4']>=30 and x['6']>=30:
            tot+=1; _,p=chi(x['w4'],x['4'],x['w6'],x['6']); rej+=p<0.05
    print(f"发球局面检验（同一发球人×接发人×半区，外角/中路各≥30）：{tot} 个，5% 水平拒绝 {rej} 个 = {rej/max(tot,1):.1%}（理论成立时约 5%）")
    return pg
pgm=run('m'); run('w')
x=pgm  # 个例：辛纳占先区（所有接发人合并）

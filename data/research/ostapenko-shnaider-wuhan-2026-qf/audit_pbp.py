import json,collections
from pathlib import Path
p=Path('/workspace/scratch/osta-facts');payload=json.load(open(p/'pbp.json'));points=payload['points'];stats={r['setnum']:r for r in json.load(open(p/'stats.json'))}
def norm(v):return 'AD' if str(v) in ['A','AD'] else str(v)
def advance(s,w):
 a,b=s
 if s==('40','40'):return ('AD','40') if w=='A' else ('40','AD')
 if s==('AD','40'):return ('G','40') if w=='A' else ('40','40')
 if s==('40','AD'):return ('40','40') if w=='A' else ('40','G')
 idx=0 if w=='A' else 1;t=list(s);t[idx]={'0':'15','15':'30','30':'40','40':'G'}[t[idx]];return tuple(t)
groups=collections.OrderedDict()
for r in points:groups.setdefault((r['setNumber'],r['gameNumber']),[]).append(r)
errs=[];games=[];tot=collections.Counter();sets={};opps=[];setwins={'A':0,'B':0};tb=[]
for (sn,gn),rows in groups.items():
 if gn==1:gc={'A':0,'B':0};st=collections.Counter()
 before=dict(gc);server=rows[0]['server'];prev=('0','0');seq=[];is_tb=(gc=={'A':6,'B':6})
 for r in rows:
  sc=r['scoreAfterPoint']['gameScore'];cur=tuple(norm(sc[k]) for k in ['teamAScore','teamBScore'])
  if is_tb:
   delta=[int(cur[i])-int(prev[i]) for i in [0,1]];valid=['A'] if delta==[1,0] else ['B'] if delta==[0,1] else []
  else:valid=[w for w in ['A','B'] if advance(prev,w)==cur]
  if len(valid)!=1:raise RuntimeError((r['pointNumber'],prev,cur,valid))
  w=valid[0]
  if w!=r['pointWinner']:errs.append({'point':r['pointNumber'],'raw':r['pointWinner'],'score_derived':w})
  for who in ['A','B']:
   other='B' if who=='A' else 'A';i=0 if who=='A' else 1
   if is_tb:gp=int(prev[i])+1>=7 and int(prev[i])+1-int(prev[1-i])>=2;sp=gp
   else:
    gp='G' in advance(prev,who);sp=gp and gc[who]+1>=6 and gc[who]+1-gc[other]>=2
   if gp and (is_tb or who!=server or sp):opps.append({'point':r['pointNumber'],'set':sn,'game':gn,'type':'match_point' if sp and setwins[who]==1 else 'set_point' if sp else 'break_point','player':who,'before':prev,'converted':who==w,'timestamp':r['timestamp']})
  if is_tb:tb.append({'point':r['pointNumber'],'before':prev,'after':cur,'winner':w,'timestamp':r['timestamp']})
  tot[w]+=1;st[w]+=1;seq.append(w);prev=cur
 gw=('A' if int(prev[0])>int(prev[1]) else 'B') if is_tb else ('A' if prev[0]=='G' else 'B');gc[gw]+=1
 games.append({'set':sn,'game':gn,'server':server or 'TB rule order only; API blank','winner':gw,'break':not is_tb and server!=gw,'after_AB':[gc['A'],gc['B']],'before_AB':[before['A'],before['B']],'points_AB':[seq.count('A'),seq.count('B')],'point_numbers':[rows[0]['pointNumber'],rows[-1]['pointNumber']],'first_timestamp':rows[0]['timestamp'],'last_timestamp':rows[-1]['timestamp'],'score_sequence_AB':[[norm(r['scoreAfterPoint']['gameScore'][k]) for k in ['teamAScore','teamBScore']] for r in rows]})
 sets[sn]=dict(st)
 if is_tb or (gc[gw]>=6 and gc[gw]-gc['B' if gw=='A' else 'A']>=2):setwins[gw]+=1
out={'source':'https://api.wtatennis.com/tennis/tournaments/1075/2026/matches/LS007/point-by-point','mapping':{'A':'Diana Shnaider','B':'Jelena Ostapenko'},'points':len(points),'first_point_utc':points[0]['timestamp'],'last_point_utc':points[-1]['timestamp'],'raw_pointWinner_disagreements':errs,'score_derived_total_AB':[tot['A'],tot['B']],'official_total_AB':[stats[0]['totptswona'],stats[0]['totptswonb']],'totals_agree':[tot['A'],tot['B']]==[stats[0]['totptswona'],stats[0]['totptswonb']],'set_totals_AB':sets,'games':games,'opportunities':opps,'tiebreak_points':tb,'limits':'Derived from scoreAfterPoint with legal transitions and whole match point totals. PBP cannot verify stroke type, ball path, psychology, source speech or actual visible frames. API sets arrays hold final set score for every point; never use these as live game score.'}
p.joinpath('pbp-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('TOTAL',out['score_derived_total_AB'],out['totals_agree'],'RAW ERRORS',errs)
for g in games:print(g['set'],g['game'],g['server'],g['after_AB'],'break',g['break'])
print('OPPS',[(r['type'],r['player'],r['point'],r['before'],r['converted']) for r in opps]);print('TB',[r['after'] for r in tb])

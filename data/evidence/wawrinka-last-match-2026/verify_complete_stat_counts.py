import pathlib,json,re,hashlib
P=pathlib.Path(__file__).parent;d=json.loads((P/'tnns-complete-decoded.json').read_text());periods=d['data']['data']
def rows(period):return {r['key']:r for g in periods[period] for r in g.get('data',[]) if isinstance(r,dict) and 'key'in r}
# Renderer group key varies; use the shared decoder traversal rather than assuming it.
import sys;sys.path.insert(0,'/workspace/tennislive/tools');import tnns_stats as t
m={r['key']:r for r in t._rows(periods['Match'])}
def fraction(key,i):
 v=m[key]['values'][i];match=re.search(r'\((\d+)/(\d+)\)',v);assert match,(key,v);return tuple(map(int,match.groups()))
fields=[];checks=[]
for i in range(2):
 first_in,total=fraction('1st_serve_in',i);first_won,first_den=fraction('1st_serve_win',i);second_won,second_total=fraction('2nd_serve_win',i);bp_conv,bp_chances=fraction('bp_won',i);pts_won,pts_total=fraction('total_points_won',i);serve_won,serve_total=fraction('service_points_won',i);return_won,return_total=fraction('return_points_won',i)
 assert first_in==first_den and first_in+second_total==total==serve_total
 assert first_won+second_won==serve_won and serve_won+return_won==pts_won and pts_total==147
 x=dict(aces=m['aces']['values'][i],df=m['double_faults']['values'][i],first_in=first_in,first_total=total,first_won=first_won,second_total=second_total,second_won=second_won,bp_conv=bp_conv,bp_chances=bp_chances,pts_won=pts_won,winners=m['winners']['values'][i],ue=m['unforced_errors']['values'][i]);fields.append(x)
 for key in ['aces','double_faults','winners','unforced_errors','1st_serve_in','1st_serve_win','2nd_serve_win','bp_won','total_points_won']:
  whole=m[key]['values'][i];values=[]
  for period in ['Set 1','Set 2']:
   rm={r['key']:r for r in t._rows(periods[period])};values.append(rm[key]['values'][i])
  if isinstance(whole,int):assert sum(values)==whole
  else:
   f=lambda v:tuple(map(int,re.search(r'\((\d+)/(\d+)\)',v).groups()))
   assert tuple(sum(v[j] for v in map(f,values)) for j in [0,1])==f(whole),(key,whole,values)
 checks.append('Column'+str(i)+': per-set sums for9raw rows + serve,return,total count identities passed')
assert fields[0]['pts_won']+fields[1]['pts_won']==147
out={'status':'pass','source_url':'https://tnnslive.com/match/75991580','actual_stats_api':'https://api.tnnslive.com/v1/web?id=UyyzQKM4yiJpnxGZw6NI&mode=match_info&submode=stats&web=true','run':'https://github.com/robertyang87/tennislive/actions/runs/40604537455','job_id':122540634027,'player_order':t.players_of(d),'a':fields[0],'b':fields[1],'raw_sha256':hashlib.file_digest((P/'tnns-complete-raw.json').open('rb'),'sha256').hexdigest(),'decoded_sha256':hashlib.file_digest((P/'tnns-complete-decoded.json').open('rb'),'sha256').hexdigest(),'raw_api_rows':list(m.values()),'checks':checks,'not_inferred_from_percentages':True};(P/'stat-card-inputs-verified.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:out[k] for k in ['status','player_order','a','b','checks']},ensure_ascii=False))

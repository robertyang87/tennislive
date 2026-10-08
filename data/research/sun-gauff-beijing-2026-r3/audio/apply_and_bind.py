from pathlib import Path
import json,sys,hashlib
root=Path('/workspace/tennislive');sys.path.insert(0,str(root/'tools'))
import foreground_audio_gate
p=root/'specs/reels/sun-gauff-beijing-2026-r3.json';spec=json.loads(p.read_text());folder=root/'data/research/sun-gauff-beijing-2026-r3/audio';rows=json.loads((folder/'selected-windows-quotes.json').read_text());inv=json.loads((folder/'commentary-inventory.json').read_text())
entries=[]
for i,s in enumerate(spec['segments']):
 if 'start' not in s or 'end' not in s or s.get('image'):continue
 r=next(r for r in rows if r['start']==s['start'] and r['end']==s['end'])
 assert r['status']=='complete',r
 if r['quote']:s['quote']=r['quote']
 else:s.pop('quote',None)
 path=root/r['transcript_path'];packet=json.loads(path.read_text())
 packet['sentence_groups']=[x for x in inv.get('sentence_groups',[]) if x['status']=='resolved' and x['end']>s['start'] and x['start']<s['end']]
 path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n');r['transcript_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 entries.append({'index':i,'transcript_path':r['transcript_path'],'transcript_sha256':r['transcript_sha256']})
spec['_hit_data']=[{'label':'二发赢分25%对64%','detail':'官方全场孙心然二发8/32，高芙14/22；旁白与统计卡已经采用，非仅凭百分比推因果。','source_url':'https://api.wtatennis.com/tennis/tournaments/1020/2026/matches/LS020/stats'}]
p.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
(folder/'selected-windows-quotes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
review={'schema':foreground_audio_gate.SCHEMA,'plan_sha256':foreground_audio_gate.plan_hash(spec),'segments':entries}
reviewpath=root/'data/audio_reviews/sun-gauff-beijing-2026-r3.json';reviewpath.parent.mkdir(exist_ok=True);reviewpath.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
required=foreground_audio_gate.require(spec,sources={'main':Path('/workspace/scratch/sun-gauff/Wg6m85wS3Ps.mp4')})
print('Validated cues',len(required),'segments',len(entries),'plan_sha256',review['plan_sha256'])

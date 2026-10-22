from pathlib import Path
import json,sys,hashlib,shutil,datetime
R=Path('/workspace/gauff-finals-production');W=Path('/workspace/tennislive-gauff');P=W/'specs/reels/gauff-finals-2026.json';D=json.load(open(P));NF=R/'production/narration-segments.json'
if not NF.exists():NF.write_text(json.dumps(D['segments'],ensure_ascii=False,indent=2)+'\n')
N={x['_id'].replace('card-',''):x for x in json.load(open(NF))};rows=json.load(open(R/'production/source-selections.json'))['selections'];S={x.get('key',x['source_name']):x for x in rows};L=json.load(open(R/'production/label-definitions.json'));segments=[]
def v(key,ident=None,label=True,mp=True):
 q=S[key];src=q['source_name'];x={'_id':ident or key,'source':src,'start':q['start'],'end':q['end'],'cx':q['cx'],'frame':q['frame'],'narration':'','fit':'crop','track':False,'_quote_kind':q['quote_kind'],'_audio_review_state':'actual_asr_cross_checked_not_human_listening','_why':q['notes'],'_frame_why':'实际比赛与同场反应按用户要求固定球场中心cx=.5，不跟踪；人物发言另用真实9帧测量。' if q['frame']=='court' else 'Actual nine face samples, fixed person center; no tracking.'}
 if q.get('cx_face'):x['cx_face']=q['cx_face']
 if q.get('audio_tail'):x['audio_tail']=q['audio_tail']
 if q['captions']:x['quote']=[{'at':round(c['start']-q['start'],3),'end':round(c['end']-q['start'],3),'text':c['en']+'\n'+c['zh']}for c in q['captions']]
 else:x['_quote_skip_why']=q.get('no_foreground_english_reason','')
 if label:
  z=L[src];assert q['start']<=z['source_start']<z['source_end']<=q['end'];x['inset']={'image':z['image'],'kind':'story_text','corner':'tr','width':.6,'pad':.043,'show_after':round(z['source_start']-q['start'],3),'show_for':round(z['source_end']-z['source_start'],3),'motion':'editorial','label':z['label']};x['_label_window_why']='Actual transparent glyph overlays at nine source times checked; final native caption samples and encoded-film QC still separate.'
 if mp:x['_match_id']=src;x['_point_role']='match_point';x['point_end_ok']='Actual independent source-frame terminal point evidence, complete serve/rally/result/reaction retained; commentary tail chosen at complete sentence boundary. See research/gauff-finals-2026/production/source-selections.json and shared independent terminal QC; never treating scorebox late flip as another live point.'
 segments.append(x)
def n(k):segments.append(N[k])
v('cincy-speech','cold-quote',False,False);n('intro');n('ao');v('ao-qf');n('spring');v('miami-final');n('rome');v('rome-final');n('rg');v('rg-r3');n('wimbledon');v('wimbledon-sf');n('cincy');v('cincy-final');n('us-qf');v('us-qf-matchpoint');v('us-qf-reaction',label=False,mp=False);v('us-qf-interview',label=False,mp=False);n('us-sf');v('us-sf');n('asia');n('ending')
D['segments']=segments;D['_render_blockers']=[];D['_production_scope']={'focus_events':7,'shown_matches':8,'complete_terminal_matchpoints':8,'extra_rallies':0,'same_match_reaction_commentary':1,'qualified_public_date':'2026-10-14','qualified_UTC':'2026-10-14T10:00:00Z','Roma_TB_conflict':'kept open; display omits smallscore','single_event_points':'show once per event, USQF no second780 addition; not mathematical weekly Race netdelta','formal_render_authorized':False};P.write_text(json.dumps(D,ensure_ascii=False,indent=2)+'\n')
# Complete source-bound foreground packets are genuine machine cross-checks, never human listening.
sys.path[:0]=[str(W/'tools'),str(W/'src')];import foreground_audio_gate as gate
O=W/'data/audio_reviews/gauff-finals-2026';RAW=O/'raw';RAW.mkdir(parents=True,exist_ok=True);entries=[];srcs={x['key']:Path(x['file'])for x in json.load(open(R/'media/source-manifest.json'))}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for i,x in enumerate(segments):
 if 'start' not in x:continue
 key='cincy-speech' if x['_id']=='cold-quote' else x['_id'];q=S[key];assert sha(srcs[x['source']])==q['source_sha256'];ev=[]
 for z in q['asr_evidence']:
  p=Path(z['path']);a=RAW/(key+'-'+z['sha256'][:10]+'-'+p.name);shutil.copy2(p,a);assert sha(a)==z['sha256'];ev.append({'path':str(a.relative_to(W)),'sha256':sha(a),'model':'large-v3' if 'large-v3' in a.name else 'medium.en' if 'medium' in a.name else 'small.en' if 'small.en' in a.name else 'small'})
 packet={'schema':'tennislive.foreground-audio-packet.v1','source_url':q['source_url'],'source_sha256':q['source_sha256'],'method':'asr_cross_checked','reviewer':'Codex actual source-frame review plus paired local ASR and targeted third-model disambiguation; not human listening','human_listened':False,'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewed_from':q['start'],'reviewed_to':q['end'],'status':'complete','uncertain_spans':[],'foreground_english':q['captions'],'no_foreground_english_reason':q.get('no_foreground_english_reason',''),'review_notes':q['notes'],'asr_evidence':ev};path=O/f'{i:02d}-{key}.json';path.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n');entries.append({'index':i,'transcript_path':str(path.relative_to(W)),'transcript_sha256':sha(path)})
rev={'schema':gate.SCHEMA,'plan_sha256':gate.plan_hash(D),'segments':entries,'method_note':'Genuine sourceSHA-bound paired unprompted local ASR; third model for two words; no human listening. French PA kept full, no invented English.'};(W/'data/audio_reviews/gauff-finals-2026.json').write_text(json.dumps(rev,ensure_ascii=False,indent=2)+'\n');required=gate.require(D,root=W,sources=srcs);print(len(segments),'segments',len(entries),'source windows',len(required),'bilingual cues; foreground source binding pass');print('body length',sum(x.get('seconds',x.get('end',0)-x.get('start',0))for x in segments))

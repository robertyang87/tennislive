from pathlib import Path
from copy import deepcopy
import json
R=Path('/workspace/pegula-finals-production/production');out={}

def normalized(row,key):
 r=deepcopy(row);r['source_name']=r.get('source_name') or r.get('source_key') or r.get('source')
 r['captions']=r.get('captions') or r.get('captions_absolute') or r.get('caption_candidates_absolute') or []
 r['audio_review_packet']=r.get('audio_review_packet') or r.get('foreground_packet') or r.get('foreground_audio_review')
 if not r.get('method'):r['method']=r.get('audio_review_method','asr_cross_checked')
 if r.get('audio_tail')!='silence':r.pop('audio_tail',None)
 if not r.get('cx_face'):r.pop('cx_face',None)
 if r.get('quote_kind')=='commentary':r['quote_kind']='broadcast'
 if r['source_name']=='cincy-runnerup':r['quote_kind']='ceremony'
 r['visual_review']=str(r.get('visual_evidence') or r.get('visual_limitations') or r.get('visual_review_status') or r.get('notes','Actual same-match source.'))
 if r['audio_review_packet']:
  packet=json.loads(Path(r['audio_review_packet']).read_text())
  r['asr_evidence']=packet.get('asr_evidence') or packet.get('evidence') or r.get('asr_evidence',[])
  r['no_foreground_english_reason']=packet.get('no_foreground_english_reason','')
  r['captions']=packet.get('foreground_english',r['captions'])
 window=r.get('label_safe_window') or r.get('live_label_window') or r.get('live_label')
 if isinstance(window,dict):
  lo=window.get('source_start',window.get('start'));hi=window.get('source_end',window.get('end'))
  if lo is not None and hi is not None:r['label_safe_window']=[lo,hi]
  else:r.pop('label_safe_window',None)
 if r.get('label_safe_window') is None:r.pop('label_safe_window',None)
 r['_original_selection_key']=row.get('key',row.get('selection_id',row.get('source_name')))
 return r
p=R/'early-selections.json'
if p.exists():
 for row in json.loads(p.read_text())['selections']:
  name=row['source_name'];key={'ao-sf':'ao','dubai-champion-speech':'dubai-speech'}.get(name,name)
  out[key]=normalized(row,key)
p=R/'north-selections.json'
if p.exists():
 mapping={'cold_cincy_speech':'cold-quote','dc_final':'dc-final','toronto_r16':'toronto-r16','cincy_sf':'cincy-sf','cincy_final':'cincy-final','us_qf_bp_save':'us-qf','us_qf_reaction':'us-qf-reaction','us_qf_interview':'us-qf-interview','us_sf_bp_save':'us-sf'}
 for row in json.loads(p.read_text())['selections']:
  key=mapping[row['key']];out[key]=normalized(row,key)
p=R/'wuhan-selections.json'
if p.exists():
 for row in json.loads(p.read_text())['primary_selections']:
  key={'wuhan_third_match_point':'wuhan-mp3','wuhan_final_point':'wuhan-final'}[row['key']];out[key]=normalized(row,key)
p=R/'middle-selections.json'
if p.exists():
 d=json.loads(p.read_text());rs=d.get('selections',d.get('primary_selections',[]))
 for row in rs:
  name=row.get('source_name',row.get('source_key',row.get('source')));key=row.get('key') or {'iw':'iw-qf','miami':'miami-qf'}.get(name,name);out[key]=normalized(row,key)
p=R/'label-overrides.json'
if p.exists():
 for key,fields in json.loads(p.read_text()).items():
  if key in out:out[key].update(fields)
p=R/'caption-edits.json'
if p.exists():
 for key,edits in json.loads(p.read_text()).items():
  if key not in out:continue
  out[key]['translation_edits']=edits
  for edit in edits:
   cue=next(c for c in out[key]['captions'] if c['start']==edit['start'] and c['end']==edit['end'])
   assert cue['en']==edit['en'] and cue['zh']==edit['from_zh']
   cue['zh']=edit['to_zh']
(R/'selections.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('merged',len(out),sorted(out))

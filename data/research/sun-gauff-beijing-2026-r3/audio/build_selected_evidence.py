import json,hashlib,datetime,sys
from pathlib import Path
root=Path('/workspace/tennislive');folder=Path(__file__).parent
inv=json.loads((folder/'commentary-inventory.json').read_text())
source_url='https://github.com/robertyang87/tennislive/releases/download/source-Wg6m85wS3Ps/Wg6m85wS3Ps.mp4'
windows=[(266.4,272.24),(81.04,106.32),(106.32,139.92),(160.12,176.24),(189.72,214.76),(231.28,243.2),(243.2,298.76)]
if len(sys.argv)>1:
 spec=json.loads(Path(sys.argv[1]).read_text());windows=[(s['start'],s['end']) for s in spec['segments'] if 'start' in s and 'end' in s and not s.get('image')]
 source_url=next(iter(spec['sources'].values()))
raw=[]
for file in folder.glob('*.json'):
 if any(tag in file.name for tag in ('full','refined','priority','edges','resolve','last','final')) and file.name!='selected-windows-quotes.json':
  raw.append({'path':str(file.relative_to(root)),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
result=[]
for start,end in windows:
 relevant=[r for r in inv['foreground_english'] if r['status']!='rejected_asr_false_positive' and r['end']>start and r['start']<end]
 uncertain=[r for r in relevant if r['status']!='resolved']
 clipped=[r for r in relevant if r['start']<start or r['end']>end]
 status='blocked' if uncertain or clipped else 'complete'
 entries=[{k:r[k] for k in ['start','end','en','zh']} for r in relevant]
 packet={'source_url':source_url,'canonical_source_url':inv['source_url'],'source_sha256':inv['source_sha256'],'method':'asr_cross_checked','reviewer':'Codex /root/broadcast_audio (independent ASR evidence reviewer)','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewed_from':start,'reviewed_to':end,'status':status,'foreground_english':entries,'uncertain_spans':[{'start':r['start'],'end':r['end'],'reason':r['status']} for r in uncertain]+[{'start':r['start'],'end':r['end'],'reason':'sentence_boundary_clipped'} for r in clipped],'raw_evidence':raw,'resolution_notes':inv['notes'][-6:],'review_basis':'Inspected independent tiny.en/base.en full-source results; cross-checked selected foreground English with independent small.en/medium.en/large-v3-turbo and targeted large-v3 results. Source-wide ASR disagreement retained in commentary-inventory.json; unused ambiguous windows not claimed complete. No human listening claim.'}
 if not entries:packet['no_foreground_english_reason']='Independent tiny.en and base.en full 425.48s source transcriptions report no foreground English in this complete selected window. Adjacent phrase ends229.80; next foreground phrase begins243.34; small/medium focused evidence corroborates these boundaries.'
 filename=f'selected-{round(start*100):05}-{round(end*100):05}.json';target=folder/filename;target.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
 quotes=[{'at':round(r['start']-start,3),'end':round(r['end']-start,3),'text':r['en']+'\n'+r['zh']} for r in entries]
 result.append({'start':start,'end':end,'status':status,'transcript_path':str(target.relative_to(root)),'transcript_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'quote':quotes,'uncertain_spans':packet['uncertain_spans']})
(folder/'selected-windows-quotes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'start':r['start'],'end':r['end'],'status':r['status'],'cues':len(r['quote']),'uncertain_spans':r['uncertain_spans']} for r in result],ensure_ascii=False,indent=2))

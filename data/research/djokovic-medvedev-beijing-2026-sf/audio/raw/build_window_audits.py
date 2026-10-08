from pathlib import Path
import json,hashlib
root=Path('/workspace/scratch/lgrd3-audio')
master=json.loads((root/'transcript-master.json').read_text())
windows=[('cold_open',360.5,368.0),('first_break',31.74,46.28),('chinese_narration',46.28,76.58),('response',76.58,95.32),('opening_set',135,165.88),('second_set_defence',165.88,199.08),('depth_and_break',233.16,273.2),('collapse',273.2,314.52),('break_back',314.52,339.22),('final_break_and_default',339.22,379.96)]
out=[]
for label,start,end in windows:
    packet={k:master[k] for k in ['source_url','source_sha256','official_provenance_url','method','reviewer','reviewed_at','method_details','name_corrections']}
    packet.update(reviewed_from=start,reviewed_to=end,status='complete',uncertain_spans=[r for r in master['uncertain_spans'] if r['end']>start and r['start']<end],foreground_english=[r for r in master['foreground_english'] if r['end']>start and r['start']<end])
    cut=[r for r in packet['foreground_english'] if r['start']<start or r['end']>end]
    if cut or packet['uncertain_spans']:packet['status']='incomplete'
    if not packet['foreground_english']:
        packet['no_foreground_english_reason']='Complete window cross-checked against source captions, full-source small.en VAD, local no-VAD small.en coverage, and targeted medium.en VAD; no stable lexical foreground English. Nonlexical court/exertion noises are not English sentences. See raw evidence and method_details; no claim of human listening.'
    packet['raw_evidence_bindings']={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in master['evidence_files']}
    quotes=[{'at':round(r['start']-start,3),'end':round(r['end']-start,3),'text':r['en']+'\n'+r['zh']} for r in packet['foreground_english']]
    f=root/f'packet-{label}.json';f.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    out.append({'label':label,'start':start,'end':end,'status':packet['status'],'packet_path':str(f),'packet_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'cut_utterances':cut,'quote':quotes})
(root/'window-audits.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('\n'.join(f"{r['label']} {r['start']}–{r['end']} {r['status']} {len(r['quote'])} cues" for r in out))

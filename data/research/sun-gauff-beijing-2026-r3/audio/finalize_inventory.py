import json,datetime
from pathlib import Path
p=Path(__file__).parent/'commentary-inventory-draft.json'
d=json.loads(p.read_text());rows=d['foreground_english']
updates={
8:dict(start=81.64,end=85.62),
9:dict(start=103.88,end=105.66),
10:dict(status='rejected_asr_false_positive',en='',zh=''),
11:dict(start=131.48,end=133.86,status='resolved'),
12:dict(start=134.62,end=136.44,en='I mean, just continue to watch.',zh='我是说，继续看下去。',status='resolved'),
13:dict(start=136.88,end=139.86,en='And Sun is back on the lettering on the court.',zh='孙心然又退到了场地上的字母标志处。',status='resolved'),
15:dict(start=160.24,end=163.58,en='But here, it’s all right in front of her.',zh='而现在，机会就在她眼前。',status='resolved'),
16:dict(start=184.84,end=188.88),
17:dict(start=194.26,end=199.9),
18:dict(start=202.28,end=203.68),
19:dict(start=204.24,end=205.56),
20:dict(start=205.66,end=211.68,status='resolved'),
21:dict(start=211.84,end=214.94),
22:dict(start=215.04,end=217.72,en='I said, good on you, Billie Jean.',zh='我说，比利·简，干得好。',status='uncertain_initial_clause'),
23:dict(start=226.48,end=229.8,status='resolved'),
24:dict(start=243.34,end=246.6),
25:dict(start=266.56,end=272.14),
26:dict(start=276.24,end=278.75),
27:dict(start=279.04,end=281.54),
28:dict(start=282.11,end=285.49),
29:dict(start=285.83,end=291.62),
30:dict(start=291.94,end=298.8),
}
for r in rows:
 if r['id'] in updates:r.update(updates[r['id']])
d['evidence']+=['small.en-edges.json','medium.en-edges.json','large-v3-turbo-resolve.json','large-v3-turbo-final.json','large-v3-last.json']
d['notes']+=[
'Nice at105.98–106.68 appears only in low-confidence base narrow-window output; independent small, medium and large-v3-turbo agree no English there, so rejected as ASR false positive rather than preserved as speech.',
'131s interjections Oh/Well/Wow disagree with one another and have probabilities0.1067/0.2385/0.1141. Independent small(128s) and large-v3-turbo(128s), as well as tiny full-source, agree the foreground sentence starts She; rejected unstable low-confidence insertion. Source sentence retained without trimming the action.',
'Names Sun and Sun Xinran normalized against official source identity from repeated phonetic Suin/Sueann/Swin-Sinaran variants. 206.98–208.2 are the full name, not a new sentence She ran.',
'Previous source speech around184–189 is an incomplete source-highlight fragment, excluded from retained window starting189.72; independent small and medium exact-window ASR starts foreground English only at194.32/194.46.',
'No human listening or aural inspection claim. Model disagreement resolution is documented, and selected-window packets remain blocked if a material unresolved wording span intersects them.',
]
d['reviewed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
d['uncertain_spans']=[{'start':r['start'],'end':r['end'],'id':r['id'],'reason':r['status']} for r in rows if r['status'].startswith('uncertain')]
(Path(__file__).parent/'commentary-inventory.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

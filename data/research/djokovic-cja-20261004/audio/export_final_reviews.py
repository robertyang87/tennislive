from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
p=Path(__file__).resolve().parent;root=p.parents[3];specpath=root/'specs/reels/zverev-djokovic.json';spec=json.loads(specpath.read_text());candidate=json.loads((p/'candidate-cues.json').read_text());now=datetime.now(timezone.utc).isoformat();rows=[]
for i,s in enumerate(spec['segments']):
 if 'start'not in s or s.get('image')or s.get('stat_card')or s.get('title_card'):continue
 start,end=s['start'],s['end'];utterances=[c for c in candidate['cues']if c['end']>start and c['start']<end];uncertain=[c for c in candidate['uncertain_spans']if c['end']>start and c['start']<end];cut=[c for c in utterances if c['start']<start or c['end']>end]
 utterances=[dict(c)for c in utterances]
 for c in utterances:
  matching=[q for q in s.get('quote',[])if isinstance(q,dict)and q.get('text','').split('\n',1)[0]==c['en']]
  if matching:
   zh=matching[0]['text'].split('\n',1)[1]
   allowed={'opening_name':'兹维列夫很快抓住了机会。','firstset_verdict':'头号种子兹维列夫拿下首盘。'}
   if zh!=c['zh'] and allowed.get(c['id'])!=zh:raise ValueError('Unreviewed Chinese quote change '+c['id'])
   c['zh']=zh
 status='incomplete'if uncertain or cut else 'complete'
 if i==24 and s.get('audio_tail')!='silence':status='waiting_audio_tail_policy'
 tail=end+.18 if i<len(spec['segments'])-1 else end
 tail_cues=[c for c in candidate['cues']if c['end']>end and c['start']<tail]
 notes=list(candidate['coverage_notes'])
 notes+=['Two compact Chinese translations were independently accepted for subtitle width: opening wastes very little time→很快抓住了机会; firstsetverdict the set goes to our top seed→头号种子兹维列夫拿下首盘. Same verified context, no added unspoken tactical claim.']
 notes +=['All foreground English enumerated for the entire nominal retained window. Transcription based on actual source audio, not narration/news text; no human listening attestation.','Packet source SHA binds unchanged exact official source; final audio_review plan hash binds the selected windows, quotes, narration and tail policy separately.']
 if tail_cues:
  notes.append('This native0.18s dissolve tail intersects the opening of a confirmed utterance. The following same-source segment begins at the same source end, and its full timed bilingual quote covers the continued utterance. No additional/source-only utterance is introduced. '+str([(c['id'],c['start'],c['end'])for c in tail_cues]))
 if i==24:
  notes +=['The sole unresolved broadcast phrase266.44–268.56 is outside this nominal window, which ends266.44 after the ball has died (story50fps mp1-boundary native6frames). Source video remains unchanged and the native audio_tail=silence policy must zero-pad the0.18s outgoing audio tail; no lexical guess, false silent-source claim, or global narrated-mode replacement.','Retained245.8–266.44 contains rally, crowd and nonlexical cheering. Cross-offset ASR tests produce incompatible Thank you/Oh my God/Ah/Let us go suggestions; none establishes a stable foreground broadcast-English sentence. Do not print hallucinated captions. This is actual-ASR counterevidence, not an invented listening result.']
 if i==23:
  notes +=['Base fullsource imagined two repetitions of I am going to take a nap at230–235; small.en and medium.en fullsource do not reproduce them, and third turbo on229.2–266.4 does not reproduce them. Treat inconsistent generic phrases over rally/crowd as raw-model hallucinations, not broadcast speech.']
 doc=dict(schema='tennislive.foreground-audio-transcript.v1',source_url=candidate['source_url'],source_sha256=candidate['source_sha256'],source_path=candidate['source_path'],method='asr_cross_checked',reviewer=candidate['reviewer'],reviewed_at=now,status=status,reviewed_from=start,reviewed_to=end,actual_listening_performed=False,review_scope='Entire retained nominal window. Complete means actual-source ASR crosscheck scope; human listening was unavailable and is not claimed.',uncertain_spans=uncertain+[dict(start=c['start'],end=c['end'],reason='Selected window cuts confirmed utterance')for c in cut],raw_evidence=candidate['raw_evidence'],foreground_english=[{k:c[k]for k in ['start','end','en','zh']}for c in utterances],crosscheck_notes=notes,native_dissolve_tail=dict(video_from=end,video_to=tail,audio_policy=s.get('audio_tail','source'),foreground_continuation=[c['id']for c in tail_cues]))
 if i==24 and s.get('audio_tail')=='silence':
  proofpath=p/'audio-tail/actual-source-audio-tail.json';proof=json.loads(proofpath.read_text());new=next(x for x in proof['outputs']if x['audio_tail']=='silence')
  if proof['source_sha256']!=candidate['source_sha256']or proof['source_window']!=[start,end]or new['tail_nonzero_samples']!=0 or new['tail_samples_actual']!=new['tail_samples_expected']:raise ValueError('Native audio tail proof does not match selected window')
  doc['native_audio_tail_proof']=dict(path=str(proofpath.relative_to(root)),sha256=hashlib.sha256(proofpath.read_bytes()).hexdigest(),method=proof['method'],sample_rate=proof['sample_rate'],channels=proof['channels'],body_samples=new['body_samples'],zero_tail_samples_per_channel=new['tail_samples_actual'],nonzero_tail_samples=new['tail_nonzero_samples'])
 if not utterances:doc['no_foreground_english_reason']='Independent actual-source Whisper small.en and medium.en fullsource/targeted passes, base/small auto-language corroboration and applicable third-turbo targets found no stable recognizable foreground broadcast-English utterance in this selected nominal interval. Ball impacts and crowd/cheering remain; no claim of silence or no human voice, and no manual listening claim.'
 path=p/f'selected-{i:02d}.json';path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n');sha=hashlib.sha256(path.read_bytes()).hexdigest();rows.append(dict(index=i,transcript_path=str(path.relative_to(root)),transcript_sha256=sha,status=status))
 print(i,start,end,status,len(utterances),s.get('audio_tail'))
(p/'selected-export-manifest.json').write_text(json.dumps(dict(schema='tennislive.selected-audio-export.v1',slug=spec['slug'],exported_at=now,spec_sha256=hashlib.sha256(specpath.read_bytes()).hexdigest(),source_sha256=candidate['source_sha256'],segments=rows),ensure_ascii=False,indent=2)+'\n')
if '--bind'in sys.argv:
 if any(x['status']!='complete'for x in rows):raise SystemExit('Refusing final binding: incomplete packets')
 sys.path.insert(0,str(root/'tools'));from foreground_audio_gate import plan_hash,require
 target=root/'data/audio_reviews/zverev-djokovic.json';target.parent.mkdir(parents=True,exist_ok=True);packet=dict(schema='tennislive.foreground-audio-review.v1',slug=spec['slug'],plan_sha256=plan_hash(spec),spec_sha256=hashlib.sha256(specpath.read_bytes()).hexdigest(),method='asr_cross_checked',reviewer=candidate['reviewer'],reviewed_at=now,actual_listening_performed=False,source_sha256=candidate['source_sha256'],segments=[{k:r[k]for k in ['index','transcript_path','transcript_sha256']}for r in rows],excluded_uncertain_spans=candidate['uncertain_spans'],notes=['Only the sole uncertain phrase is excluded using reviewed complete-rally cut plus silence on outgoing native dissolve audio tail. Original source SHA unchanged.','Each retained original-English sentence has exact timed English/Chinese quote; Chinese narration occupies the gaps and nativecards; actual-listening false is explicit.']);target.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
 cues=require(spec,root=root,sources={'':Path(candidate['source_path'])});print('FINAL_BINDING_OK',len(rows),'video windows',len(cues),'timed bilingual utterances',packet['plan_sha256'])

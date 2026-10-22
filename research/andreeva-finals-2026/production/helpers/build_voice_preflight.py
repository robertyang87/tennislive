from pathlib import Path
import sys,json,tempfile,hashlib
P=Path('/workspace/tennislive-andreeva');R=Path('/workspace/andreeva-finals-production');sys.path[:0]=[str(P/'tools'),str(P/'src')]
import voice_auto_review as v
from faster_whisper import WhisperModel,decode_audio
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
rows=[];bundle=R/'production/narration/tts_bundle.zip';bundle_identity=hashlib.sha256(bundle.read_bytes()).hexdigest();previous_path=R/'production/voice-preflight.json';previous={x['audio_sha256']:x for x in json.load(open(previous_path))['entries']}if previous_path.exists()else{};model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=1,num_workers=1)
with tempfile.TemporaryDirectory()as tmp:
 entries=v.load_bundle(bundle,Path(tmp))
 for e in entries:
  if e['audio_sha256'] in previous:
   prior=previous[e['audio_sha256']];assert prior['request']==e['request']
   if not prior['pass'] and not prior['completeness']['ok']:
    second=WhisperModel('medium.en' if False else 'large-v3',device='cpu',compute_type='int8',cpu_threads=1,num_workers=1);segs,_=second.transcribe(decode_audio(str(e['mp3']),sampling_rate=16000),language='zh',beam_size=5,condition_on_previous_text=False);text2=''.join(x.text for x in segs);compare2=v.compare_transcript(e['request']['text'],text2);prior['transcript_large_v3_turbo']=text2;prior['second_completeness']=compare2
    if compare2['ok']:prior['completeness']=compare2;prior['pass']=prior['pause_and_speed']['pause_ok'] and prior['pause_and_speed']['speed_ok'] and all(v.poly_ok(x)for x in prior['polyphone_measurements'])
    del second
   rows.append(prior);print('Verified same-audio cached preflight',prior['pass'],e['request']['text'][:18],flush=True);continue
  segs,_=model.transcribe(decode_audio(str(e['mp3']),sampling_rate=16000),language='zh',beam_size=5,condition_on_previous_text=False)
  transcript=''.join(s.text for s in segs);comp=v.compare_transcript(e['request']['text'],transcript);ps=v.pause_and_speed(e,v._names(json.load(open(P/'specs/reels/andreeva-finals-2026.json'))));poly=[]
  for target in v.poly_targets(e['request']['text']):poly.append(v.measure_target(e,target))
  z={'text':e['request']['text'],'request':e['request'],'audio_sha256':e['audio_sha256'],'actual_duration':e['duration'],'transcript_small':transcript,'completeness':comp,'pause_and_speed':ps,'polyphone_measurements':poly,'pass':comp['ok']and ps['pause_ok']and ps['speed_ok']and all(v.poly_ok(x)for x in poly)};rows.append(z);print(z['pass'],e['request']['text'][:18],transcript,flush=True)
 evidence={'schema':'andreeva.actual-tts-preflight.v1','scope':'Actual frozen local TTS bytes preflight only, not final-movie approval. Native final automated_voice_suite still required.','bundle_sha256':bundle_identity,'entries':rows,'pass':all(x['pass']for x in rows),'sentence_splits':v.split_sentences({'segments':[{'narration':x['text']}for x in json.load(open(R/'production/narration-plan.json'))]})};(R/'production/voice-preflight.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n');print('VOICES PREFLIGHT',evidence['pass'],flush=True)

from pathlib import Path
import json,hashlib,datetime,subprocess
R=Path('/workspace/shelton-finals-production/research/audio')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=Path('/dev/shm/shelton-sources/sh26montmp.mp4');s=sha(p)
assert s=='59667371f40df7f125a4ba6d4f10cb00a04c2883ca0f160c7862b99009101cf8'
url='https://www.tennistv.com/videos/4559432/montreal-2026-final-match-point'
archive='https://github.com/robertyang87/tennislive/releases/download/source-sh26montmp/sh26montmp.mp4'
u=[{'start':16.38,'end':20.04,'en':'Ben Shelton delivers a masterful performance in Montreal,','zh':'谢尔顿在蒙特利尔打出大师级表现，'},{'start':20.04,'end':23.18,'en':'that will yield the most glittering of prizes.','zh':'赢得最耀眼的奖赏。'}]
ev=[]
for f in [R/'raw/sh26montmp/small.en.json',R/'raw/sh26montmp/medium.en.json',R/'raw/refined/sh26montmp/small.en.json',R/'raw/refined/sh26montmp/medium.en.json']:
 d=json.loads(f.read_text());assert d['source_sha256']==s
 ev.append({'path':str(f),'research_path':str(f),'sha256':sha(f),'source_sha256':s,'model':d['model'],'clip':d['clip'],'parameters':d['parameters'],'script_path':str(R/'asr_selected_sources.py'),'script_sha256':sha(R/'asr_selected_sources.py')})
q=[{'at':x['start'],'end':x['end'],'text':x['en']+'\n'+x['zh']} for x in u]
geo=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_type,width,height,r_frame_rate,sample_rate,channels','-of','json',str(p)]))
packet={'schema':'tennislive.foreground-audio-transcript.v1','source_url':url,'archive_url':archive,'source_sha256':s,'method':'asr_cross_checked','reviewer':'Codex shelton_audio_race; actual local two-model ASR, refined-window word timings and local activity reviewed; no human auditory listening claimed','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewed_from':0.0,'reviewed_to':29.0,'status':'complete','human_listening_performed':False,'foreground_english':u,'uncertain_spans':[],'review_notes':['Both actual small.en and medium.en, in full-source and tight15–24.5 contexts, agree on the complete retained sentence. Two readable clauses preserve every lexical word, with punctuation-only comma at the clause division.','Ben onset16.38 from full small.en word; Shelton16.62–17.2 agrees across all4 runs. Medium15.68 and tight15/15.82 Ben starts are broad leading envelopes, explicitly not accepted as precise onset. Local strong speech activity16.464 supports late onset. Sentence end23.18 includes final prizes word.','Rejected small.en Here we go candidate0–14.76: Here has zero duration/probability0 and we spans11.78s; no medium/tight agreement. Rejected That\'s what it is23.10–23.30: zero-duration weak words, absent other3 runs. These are unsupported ASR hallucination candidates, not claimed spoken English.','No consistent foreground English after23.18. Visual reviewed source is continuous final point then title reaction and handshake/hug. Source0–29.0 plus native0.5 tail ends29.5 within clean29.52 source.'],'source_identity':{'source_path':str(p),'actual_ffprobe':geo},'asr_evidence':ev,'timing_support':{'path':str(R/'montreal-speech-activity.json'),'sha256':sha(R/'montreal-speech-activity.json'),'scope':'Local Silero activity support, not human hearing or precise quiet-syllable/sample boundary proof.'},'native_quote':q}
dest=R/'transcripts/montreal-final.json';dest.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
h={'source_key':'montreal-final','source_id':'sh26montmp','source_url':url,'archive_url':archive,'source_sha256':s,'source_path':str(p),'window':[0.0,29.0],'packet_path':str(dest),'packet_sha256':sha(dest),'quote':q,'absolute_utterances':u,'status':'complete','native_tail':29.5}
(R/'montreal-native-handoff.json').write_text(json.dumps(h,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'packet':str(dest),'sha256':sha(dest),'handoff':str(R/'montreal-native-handoff.json')},ensure_ascii=False))

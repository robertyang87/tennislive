import pathlib,json,sys,subprocess
from faster_whisper import WhisperModel
r=pathlib.Path('/workspace/scratch');mode=sys.argv[1];m=WhisperModel(mode,device='cpu',compute_type='int8',cpu_threads=2);out=[]
for n,a,b in [(1,117.5,132.4),(4,74,103)]:
 p=r/'rna10-effects'/f's{n}.wav';w=r/f'extra-effects-{n}.wav';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(a),'-i',str(p),'-t',str(b-a),'-ar','16000','-ac','1',str(w)],check=True)
 ss,info=m.transcribe(str(w),beam_size=5,vad_filter=True,condition_on_previous_text=False,word_timestamps=True);meta=next(x for x in json.loads((p.parent/'processing.json').read_text()) if x['source']==f's{n}')
 row={'source':f's{n}','start':a,'end':b,'model':mode,'effects_sha256':meta['effects_sha256'],'language':info.language,'language_probability':info.language_probability,'segments':[{'start':s.start+a,'end':s.end+a,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':x.start+a,'end':x.end+a,'word':x.word,'probability':x.probability} for x in s.words]} for s in ss]};out.append(row);(r/f'rna10-effects-context-{mode}-asr.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(row,flush=True)

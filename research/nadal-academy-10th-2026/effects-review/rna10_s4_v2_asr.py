import pathlib,json,sys,subprocess
from faster_whisper import WhisperModel
r=pathlib.Path('/workspace/scratch');mode=sys.argv[1];m=WhisperModel(mode,device='cpu',compute_type='int8',cpu_threads=2);out=[];meta=json.loads((r/'rna10-effects/s4-v2-processing.json').read_text())
for a,b in [(74,103),(79.7,81.1),(98.7,99.9)]:
 w=r/f's4v2-{a}.wav';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(a),'-i',str(r/'rna10-effects/s4-v2.wav'),'-t',str(b-a),'-ar','16000','-ac','1',str(w)],check=True)
 ss,info=m.transcribe(str(w),beam_size=5,vad_filter=True,condition_on_previous_text=False,word_timestamps=True);row={'source':'s4','start':a,'end':b,'model':mode,'effects_sha256':meta['output_sha256'],'language':info.language,'language_probability':info.language_probability,'segments':[{'start':s.start+a,'end':s.end+a,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':x.start+a,'end':x.end+a,'word':x.word,'probability':x.probability} for x in s.words]} for s in ss]};out.append(row);(r/f'rna10-effects-s4v2-{mode}-asr.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(row,flush=True)

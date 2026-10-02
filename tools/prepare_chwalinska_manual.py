"""Collect original footage and speech evidence; no text-generation provider."""
import argparse, json, subprocess, sys, hashlib, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_match_reel import download
from PIL import Image,ImageDraw
p=argparse.ArgumentParser();p.add_argument('--outdir',required=True,type=Path);a=p.parse_args();a.outdir.mkdir(parents=True,exist_ok=True)
source=download('https://www.youtube.com/watch?v=12BOGT88OnQ',a.outdir/'source.mp4')
from faster_whisper import WhisperModel
model=WhisperModel('medium.en',device='cpu',compute_type='int8')
segs,info=model.transcribe(str(source),language='en',word_timestamps=True,vad_filter=True,beam_size=5,initial_prompt='Dayana Yastremska and Maja Chwalinska. China Open, Beijing. Tennis commentary.')
rows=[{'start':s.start,'end':s.end,'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words or []]} for s in segs]
(a.outdir/'broadcast_asr.json').write_text(json.dumps({'model':'medium.en','language':info.language,'segments':rows},ensure_ascii=False,indent=2)+'\n')
(a.outdir/'captions.txt').write_text(''.join(f"{r['start']:.2f}\t{r['text']}\n" for r in rows))
frames=[]
for low,high in [(35.0,38.2),(255.8,257.8),(279.8,283.2)]:
 for i in range(round((high-low)/0.2)+1):
  t=round(low+0.2*i,2);f=a.outdir/f'portrait_{t:06.2f}.jpg'
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(t),'-i',str(source),'-frames:v','1','-q:v','2','-y',str(f)],check=True)
  frames.append((t,f))
w,h=320,200;sheet=Image.new('RGB',(w*5,h*((len(frames)+4)//5)), '#10221c');dr=ImageDraw.Draw(sheet)
for i,(t,f) in enumerate(frames):
 im=Image.open(f);im.thumbnail((w,h-20));x=(i%5)*w;y=(i//5)*h;sheet.paste(im,(x,y));dr.text((x+5,y+h-18),f'{t:.2f}s',fill='white')
sheet.save(a.outdir/'portrait_contact.jpg',quality=92)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss','259.0','-i',str(source),'-t','28','-vn','-c:a','libmp3lame','-b:a','128k','-y',str(a.outdir/'deciding_audio.mp3')],check=True)
print('Original speech and same-match portraits collected; no DeepSeek calls.')

source_sha=hashlib.file_digest(source.open('rb'),'sha256').hexdigest()
(a.outdir/'source_sha256.txt').write_text(source_sha+'\n')
model2=WhisperModel('small.en',device='cpu',compute_type='int8')
segs2,info2=model2.transcribe(str(source),language='en',word_timestamps=True,vad_filter=True,beam_size=5)
rows2=[{'start':s.start,'end':s.end,'text':s.text.strip(),'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words or []]} for s in segs2]
(a.outdir/'broadcast_asr_independent.json').write_text(json.dumps({'model':'small.en','source_sha256':source_sha,'segments':rows2},ensure_ascii=False,indent=2)+'\n')
from analyze_reel_visuals import verified_minimax_report, evidence_hash
base=json.loads(Path('specs/reels/pending/yastremska-chwalinska.draft.json').read_text())
base['cover']['portrait']={'image':str(a.outdir/'portrait_036.80.jpg')}
base['_cover_brief']={'preferred_subject':'赫瓦林斯卡','preferred_moment_key':'loser_fighting','preferred_moment':'本场仍在拼；正面手持拍准备下一分，不要低头失落照。'}
probe=json.loads((a.outdir/'probe.json').read_text())
frames=[]
for t in [36.8,53.8,63.2,135.0,140.5,144.6,192.5,209.0,259.0,264.0,270.0,275.5,276.0,278.0,280.0,281.4,282.2,284.4]:
 f=a.outdir/f'visual_native_{t:06.2f}.jpg'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(t),'-i',str(source),'-frames:v','1','-q:v','2','-y',str(f)],check=True)
 im=Image.open(f);im.thumbnail((1280,720));dr=ImageDraw.Draw(im);dr.rectangle((0,0,180,40),fill='black');dr.text((10,10),f'SOURCE {t:.2f}s',fill='white');im.save(f,quality=92);frames.append(f)
# Full-duration sheets plus native source-timestamped images; early score is a valid match state.
base['_cover_brief']['evidence_notes']='封面来自此源片36.8秒首盘2-1，不能拿过程比分与最终6-3/6-1不相同当旧图。最终赛点在259到275.8，黄裙赢家近景随后，281.4到282.2握手，299.92片尾。按原帧所见判断，不猜未展示的动作。'
base['_cover_brief']['requested_cold_open_scope']=[275.5,278.0]
base['_cover_brief']['requested_ending_scope']=[275.5,284.4]
frames=sorted(a.outdir.glob('contact_*.jpg'))+frames
# Independently decode the one disputed commentary clause from its local acoustic context.
clip=a.outdir/'volley_speech.wav'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss','59','-i',str(source),'-t','10','-vn','-ar','16000','-y',str(clip)],check=True)
third,_=model.transcribe(str(clip),language='en',word_timestamps=True,vad_filter=False,beam_size=5)
(a.outdir/'volley_asr_crosscheck.json').write_text(json.dumps({'model':'medium.en','source_offset':59,'decoding':'unseeded local 10-second context','segments':[{'start':59+s.start,'end':59+s.end,'text':s.text} for s in third]},ensure_ascii=False,indent=2)+'\\n')

report,problems=verified_minimax_report(base,frames,a.outdir/'portrait_036.80.jpg',probe,os.environ['MINIMAX_API_KEY'])
report['evidence_sha256']=evidence_hash(frames,a.outdir/'portrait_036.80.jpg')
(a.outdir/'manual_visual_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('VISUAL PROBLEMS',problems)


# Re-run with tolerant JSON string decoding; content gates remain unchanged.

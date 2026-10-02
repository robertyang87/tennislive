"""Collect original footage and speech evidence; no text-generation provider."""
import argparse, json, subprocess, sys
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

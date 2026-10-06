#!/usr/bin/env python3
"""Read-only actual Edge speech and acoustic review; never publishes."""
import argparse, hashlib, json, shutil, subprocess, sys, time, re
from difflib import SequenceMatcher
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from check_polyphones import reel_texts
from tennislive.video.explainer import speakable
import measure_polyphone as mp
from pypinyin import Style,pinyin
# Common competing pronunciations; rare dictionary variants are not useful controls.
PAIRS={'场':['chang2','chang3'],'冠':['guan1','guan4'],'分':['fen1','fen4'],'发':['fa1','fa4'],'还':['hai2','huan2'],'打':['da3','da2'],'得':['de5','de2','dei3'],'看':['kan4','kan1'],'更':['geng4','geng1'],'都':['dou1','du1'],'重':['chong2','zhong4'],'差':['cha1','cha4','chai1'],'好':['hao3','hao4'],'为':['wei4','wei2'],'没':['mei2','mo4'],'单':['dan1','shan4','chan2'],'给':['gei3','ji3'],'强':['qiang2','qiang3','jiang4'],'六':['liu4','lu4'],'抢':['qiang3','qiang1'],'当':['dang1','dang4'],'中':['zhong1','zhong4'],'先':['xian1'],'字':['zi4']}
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--spec',default='specs/reels/noskova-alexandrova.json');ap.add_argument('--out',default='audio-review');a=ap.parse_args()
 sp=ROOT/a.spec;spec=json.loads(sp.read_text());out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 mp.CACHE=out/'cache'
 from faster_whisper import WhisperModel
 model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4,download_root=str(out/'asr-models'))
 report={'spec_sha256':hashlib.sha256(sp.read_bytes()).hexdigest(),'voice':'zh-CN-YunjianNeural','rate':'+6%','method':'actual full utterance Edge TTS; MFCC+F0 DTW contrasting references; no claimed human listening','cover_narration':bool(spec.get('cover',{}).get('narration')),'lines':[],'status':'pending'}
 for row in reel_texts(spec):
  text=speakable(row.text);line={'label':row.label,'screen_text':row.text,'tts_text':text,'rate':row.rate,'measurements':[],'lexical_review':'pending ASR/manual: numbers, cutting and player proper names; acoustic polyphone result alone does not verify these'};report['lines'].append(line)
  try:
   wav,marks=mp.synth(text,report['voice'],row.rate);target=out/(str(len(report['lines'])).zfill(2)+'.mp3');shutil.copyfile(wav,target);line['audio']=str(target);line['word_boundaries']=marks
   segs,info=model.transcribe(str(wav),language='zh',beam_size=5,word_timestamps=True,vad_filter=True,condition_on_previous_text=False)
   segs=list(segs);transcript=''.join(s.text for s in segs)
   def phonetic(t):
    t=re.sub(r'[^\u4e00-\u9fff]','',t)
    return [x[0] for x in pinyin(t,style=Style.NORMAL)]
   expected,observed=phonetic(text),phonetic(transcript)
   score=SequenceMatcher(a=expected,b=observed,autojunk=False).ratio()
   line['asr']={'model':'faster-whisper small int8 zh','transcript':transcript,'phonetic_similarity':score,'expected_phonemes':expected,'observed_phonemes':observed,'segments':[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words]} for s in segs]}
   line['lexical_review']='ASR exact phonetic sequence matched (tones still require acoustic controls)' if expected==observed else 'pending: ASR phonetic mismatch; inspect aligned audio, no human listening claimed'
   line['duration']=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(wav)],text=True).strip())
   readings=pinyin(text,style=Style.TONE3,neutral_tone_with_five=True)
   for i,c in enumerate(text):
    if c not in PAIRS or len(PAIRS[c])<2:continue
    intended=readings[i][0]
    if c=='差' and text[max(0,i-1):i+1]=='时差':intended='cha1'
    ok,_=mp.suggest_homophones(intended,exclude=c,k=3)
    for wrong in [r for r in PAIRS[c] if r!=intended]:
     result={'position':i,'char':c,'intended':intended,'wrong':wrong}
     bad,_=mp.suggest_homophones(wrong,exclude=c,k=3)
     if not ok or not bad:result.update(verdict='pending',why='No unambiguous control characters')
     else:
      try:result.update(mp.measure(c,text,ok,bad,report['voice'],row.rate,char=c,at=i))
      except Exception as e:result.update(verdict='pending',why=f'{type(e).__name__}: {e}')
     line['measurements'].append(result);dump(out/'report.json',report);print(row.label,c,intended,wrong,result.get('verdict'),flush=True)
  except Exception as e:line['error']=f'{type(e).__name__}: {e}'
  dump(out/'report.json',report)
 report['status']='pending lexical review and any uncertain/unreliable/misread controls';dump(out/'report.json',report)
 print('Read-only QC complete; inspect report, status intentionally pending until lexical review.',flush=True)
if __name__=='__main__':main()

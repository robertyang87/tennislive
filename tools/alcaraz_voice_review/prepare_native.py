import argparse,hashlib,json,os,subprocess,sys,zipfile,shutil,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(os.environ['ALCARAZ_VOICE_REVIEW_DIR']);sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
os.environ['TENNISLIVE_TTS_BACKEND']='edge'
from tennislive.localca import trust_local_proxy_ca
from tennislive.video import tts
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
import check_polyphones as cp
from pypinyin import pinyin,Style
ap=argparse.ArgumentParser();ap.add_argument('--spec',required=True);ap.add_argument('--only-id',action='append');a=ap.parse_args();specpath=Path(a.spec);spec=json.loads(specpath.read_text());trust_local_proxy_ca();rows=[];items=[]
assert not spec.get('cover',{}).get('narration'),'Cover narration unauthorized'
assert spec.get('outro') is False,'Brand outro unauthorized'
cover=spec.get('cover')or{}
if cover.get('narration')and not a.only_id:items.append(('封面',cover['narration'],'cover',None,float(cover.get('seconds',0))or None,{}))
for i,s in enumerate(spec['segments']):
 if s.get('narration')and (not a.only_id or s.get('_edit_id')in a.only_id):items.append((f'第 {i+1} 段',s['narration'],s.get('_edit_id')or str(i),i,float(s['seconds'])if'seconds'in s else float(s['end'])-float(s['start']),s.get('voice')or{}))
if spec.get('outro',True)and not a.only_id:items.append(('片尾',NARRATION,'outro',None,None,{}))
for label,text,edit_id,index,window,v in items:
 voice='zh-CN-YunjianNeural';rate=v.get('rate')or'+6%';pitch=v.get('pitch')or'+0Hz';style=v.get('style')or'';degree=v.get('styledegree')or'';lead=float(v.get('lead_pause')or 0)
 assert rate=='+6%'and pitch=='+0Hz'and not style and not degree and lead==0,'Only authorized standard production voice/rate; do not silently change parameters'
 spoken=speakable(text);key=tts.tts_content_key(spoken,voice,rate,pitch,style,degree,lead);p=OUT/'native-speech'/f'{key}.mp3';p.parent.mkdir(exist_ok=True,parents=True);marks=tts.tts_one(spoken,p,voice,rate,pitch,style,degree,lead);m=p.with_suffix('.marks.json');m.write_text(json.dumps(marks,ensure_ascii=False,indent=2)+'\n')
 cache=Path(os.environ.get('TENNISLIVE_TTS_CACHE',str(Path.home()/'.cache/tennislive-tts')))/f'{key}-edge-v2.zip'
 zip_snapshot=p.with_suffix('.native.zip');shutil.copy2(cache,zip_snapshot)
 with zipfile.ZipFile(zip_snapshot)as z:assert z.read('audio.mp3')==p.read_bytes();paired=json.loads(z.read('marks.json'));assert paired==marks;raw_marks_sha=hashlib.sha256(z.read('marks.json')).hexdigest()
 duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)]));r,w,_,_=cp._readings(spoken);poly=[{'at':i,'char':c,'word':w[i],'intended_lexical_reading':r[i],'all_dictionary_readings':pinyin(c,style=Style.TONE3,heteronym=True,neutral_tone_with_five=True)[0]}for i,c in enumerate(spoken)if '\u4e00'<=c<='\u9fff' and len(pinyin(c,style=Style.TONE3,heteronym=True,neutral_tone_with_five=True)[0])>1]
 b={'label':label,'index':index,'edit_id':edit_id,'display_text':text,'text':spoken,'voice':voice,'rate':rate,'pitch':pitch,'cache_key':key,'actual_mp3_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bound_snapshot_path':str(p),'marks_snapshot_path':str(m),'mp3_duration_seconds':duration,'window_seconds':window,'headroom_seconds':window-duration if window else None,'native_cache_path':str(cache),'native_zip_snapshot_path':str(zip_snapshot),'native_zip_sha256':hashlib.sha256(zip_snapshot.read_bytes()).hexdigest(),'native_zip_marks_raw_sha256':raw_marks_sha,'actual_marks_sha256':hashlib.sha256(m.read_bytes()).hexdigest(),'word_boundary_tokens':[x['text']for x in marks],'enumerated_polyphones':poly,'tts_only_substitution_changed_text':spoken!=text};rows.append(b)
 print(json.dumps({k:b[k]for k in ['label','edit_id','mp3_duration_seconds','window_seconds','headroom_seconds','actual_mp3_sha256','word_boundary_tokens','enumerated_polyphones']},ensure_ascii=False),flush=True)
result={'schema':'tennislive.native-prepared-speech.v1','prepared_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'spec_sha256_at_preparation':hashlib.sha256(specpath.read_bytes()).hexdigest(),'bindings':rows,'outro_enabled':spec.get('outro',True),'scope_status':'partial_requested_ids_only'if a.only_id else'all_current_actual_spec_tts','excluded_brand':{'status':'excluded_by_actual_spec','reason':'Current authorized spec has no brand outro; no brand evidence from another episode is included.'}if not spec.get('outro',True)else None,'human_listening_claimed':False}
p=OUT/('native-bindings-'+('-'.join(a.only_id))+'.json'if a.only_id else'native-bindings.json');p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

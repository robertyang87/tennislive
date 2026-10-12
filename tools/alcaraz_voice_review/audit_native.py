import argparse,json,os,sys,subprocess,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from pypinyin import pinyin,Style
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(os.environ['ALCARAZ_VOICE_REVIEW_DIR'])
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
import check_polyphones as cp
import measure_polyphone as mp
ap=argparse.ArgumentParser();ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--names',required=True);a=ap.parse_args()
bindings=json.loads((OUT/'native-bindings.json').read_text())['bindings']; targets=[]; unresolved=[]; coverage=[]
names=json.loads(Path(a.names).read_text())
special={'fa1':['發','発'],'fa4':['髮','珐'],'de2':['锝'],'chang3':['敞','昶','氅'],'er4':['贰','貳'],'liang3':['魉','両'],'san1':['叁','毵'],'si4':['肆','饲'],'ling2':['灵','玲'],'yi1':['衣','依'],'yi2':['姨','移'],'yi4':['义','亦','亿'],'wu3':['伍','侮','午'],'wu4':['勿','误','悟'],'bai3':['佰','摆'],'ba1':['巴','疤'],'shi2':['实','时']}
def refs(reading,char):
 if reading in special:return [x for x in special[reading]if x!=char], 'Provisional declared nonoriginal controls; context-sensitive/traditional/rare controls require fresh self-calibration.'
 rs,note=mp.suggest_homophones(reading,exclude=char,k=8)
 strict=[c for c in rs if pinyin(c,style=Style.TONE3,heteronym=True,neutral_tone_with_five=True)[0]==[reading]]
 return strict[:3], 'Only dictionary single-reading nonoriginal references selected; '+note
def add(b,ch,i,intended,wrong,kind,notes=None):
 A,an=refs(intended,ch);B,bn=refs(wrong,ch)
 item={'label':b['label'],'edit_id':b['edit_id'],'word':ch,'char':ch,'at':i,'sentence':b['text'],'intended':intended,'wrong':wrong,'actual_binding':b,'check_kind':kind,'context_notes':notes or[]}
 if not A or not B:
  unresolved.append({**item,'status':'no_valid_independent_reference','why':f'No finite independent reference set: intended={A}; wrong={B}. ASR/tokenizer/dictionary do not fill this evidence gap.'});return
 targets.append({**item,'ok_refs':A,'bad_refs':B,'reference_notes':[an,bn],'reference_validity_limited':intended=='fa1' or len(A)<2 or len(B)<2})
num={'一':('yi1','yi4'),'二':('er4','er3'),'三':('san1','san4'),'四':('si4','si1'),'五':('wu3','wu4'),'六':('liu4','liu2'),'七':('qi1','qi2'),'八':('ba1','ba4'),'九':('jiu3','jiu4'),'十':('shi2','shi1'),'千':('qian1','qian2'),'百':('bai3','bai4'),'零':('ling2','ling4'),'两':('liang3','liang4')}
def yi_reading(text,i,rs):
 prev=text[i-1]if i else'';nxt=text[i+1]if i+1<len(text)else''
 if prev in ['第','十']or nxt in ['比','，','。','、']or not nxt:return 'yi1'
 next_r=rs[i+1]if i+1<len(rs)else None
 if next_r and next_r.endswith('4'):return 'yi2'
 if next_r:return 'yi4'
 return 'yi1'
for b in bindings:
 text=b['text']; rs,words,_,_=cp._readings(text); seen=set(); c={'edit_id':b['edit_id'],'text':text,'polyphone_occurrences':[],'numeral_occurrences':[],'proper_name_occurrences':[],'ascii_letter_occurrences':[],'actual_word_boundary_tokens':b['word_boundary_tokens']}
 for name,readings in names.items():
  start=0
  while (at:=text.find(name,start))>=0:
   for j,reading in enumerate(readings):rs[at+j]=reading
   start=at+len(name)
 for i,ch in enumerate(text):
  if ch=='一':rs[i]=yi_reading(text,i,rs)
  if ch=='不'and i+1<len(rs)and rs[i+1]and rs[i+1].endswith('4'):rs[i]='bu2'
 for i,ch in enumerate(text):
  common_yes,default,common_live=cp.poly_info(ch)
  live=tuple(dict.fromkeys(pinyin(ch,style=Style.TONE3,heteronym=True,neutral_tone_with_five=True)[0])) if '\u4e00'<=ch<='\u9fff' else ()
  yes=len(live)>1
  if yes:
   c['polyphone_occurrences'].append({'at':i,'char':ch,'lexical_intended':rs[i],'word':words[i],'live':live,'common_polyphone_inventory':common_yes,'common_live':common_live})
   for wrong in live:
    if wrong!=rs[i]:add(b,ch,i,rs[i],wrong,'polyphone',['Lexical dictionary intended reading is a declared hypothesis; calibration evaluates actual audio.']);seen.add((i,wrong))
  if ch in num:
   intended,wrong=num[ch];notes=[]
   if ch=='一':
    intended=rs[i];wrong='yi4'if intended=='yi1'else'yi1';notes=['Contextual 一 hypothesis includes ordinal/score citation and next-tone sandhi; calibrated relative result is not an exhaustive realization claim.']
   if ch in ['五','两']:notes+=['Lexical third tone may realize contextual sandhi; the fourth-tone negative is outside valid third/second-tone realizations.']
   c['numeral_occurrences'].append({'at':i,'char':ch,'intended':intended,'context_notes':notes})
   if (i,wrong)not in seen:add(b,ch,i,intended,wrong,'numeral',notes);seen.add((i,wrong))
  if ch.isascii() and ch.isalpha():c['ascii_letter_occurrences'].append({'at':i,'char':ch,'status':'letter_recognition_requires_actual_whole_utterance_support_not_tone_claim'})
 for match in re.finditer(r'\d+(?:\.\d+)?',text):c['numeral_occurrences'].append({'at':match.start(),'text':match.group(),'status':'numeric_normalization_requires_actual_whole_utterance_support'})
 for name,readings in names.items():
  start=0
  while (at:=text.find(name,start))>=0:
   c['proper_name_occurrences'].append({'name':name,'at':at,'length':len(name),'declared_readings':readings})
   assert len(readings)==len(name)
   for j,(ch,intended) in enumerate(zip(name,readings)):
    syllable=intended[:-1];tone=intended[-1]; wrong=syllable+('4'if tone!='4' else '1')
    if (at+j,wrong)not in seen:add(b,ch,at+j,intended,wrong,'proper_name',[f'Every occurrence of proper name {name}.']);seen.add((at+j,wrong))
   start=at+len(name)
 coverage.append(c)
job={'schema':'tennislive.finite-actual-speech-audit.v1','targets':targets,'unresolved_no_valid_reference':unresolved,'coverage':coverage,'output_dir':str(OUT/'native-targets'),'method':'Fresh frozen full-utterance native edge Yunjian +6%/+0Hz baseline, MP3+paired native ZIP WordBoundary. Finite same-utterance nonoriginal correct/wrong homophone MFCC+F0 contrasts with LOO calibration. Low/uncertain/unreliable/no-reference remain limitations. No historical sentence pass, ASR tone proof, or human listening claimed.','exclusions':{'brand_outro':False,'cover_narration':False}}
j=OUT/'native-job.json';j.write_text(json.dumps(job,ensure_ascii=False,indent=2)+'\n');print('TARGET_COUNT',len(targets),'UNRESOLVED_WITHOUT_CONTROLS',len(unresolved),flush=True)
if a.prepare_only:sys.exit(0)
def run(i):
 p=Path(job['output_dir'])/f'target-{i:03}.json'
 if p.exists():
  r=json.loads(p.read_text());t=targets[i]
  if r['sentence']==t['sentence']and r['at']==t['at']and r['wrong']==t['wrong']and r['actual_binding']['actual_mp3_sha256']==t['actual_binding']['actual_mp3_sha256']:return
 e=dict(os.environ);e.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',POLYPHONE_CACHE=str(OUT/'fresh-reference-cache'))
 q=subprocess.run([sys.executable,str(Path(__file__).with_name('run_target.py')),str(j),str(i)],env=e,capture_output=True,text=True);print(q.stdout.strip()or q.stderr[-600:],flush=True)
with ThreadPoolExecutor(max_workers=4)as pool:list(pool.map(run,range(len(targets))))

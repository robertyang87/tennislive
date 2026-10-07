import json,hashlib,datetime,shutil
from pathlib import Path
out=Path('/workspace/tennislive/data/research/zheng-charaeva-beijing-2026-r4/pronunciation');m=json.loads((out/'final-text-manifest.json').read_text());bindings=json.loads((out/'native-final-audio/bindings.json').read_text());default=json.loads((out/'native-acoustic-results.json').read_text());matrix=[];used=[]
bind_by={b['text_sha256']:b for b in bindings}
def evidence(p,txt,binding):
 r=json.loads(p.read_text());assert r['sentence']==txt,(p,'different full utterance')
 orig=Path(r['audio']['ORIG']);sha=hashlib.sha256(orig.read_bytes()).hexdigest();assert sha==binding['mp3_sha256'],(p,'different production audio')
 assert r['verdict']=='correct',(p,r['verdict'])
 used.append(p)
 return {'verdict':'correct','confidence':r.get('confidence') or 'medium','score':r.get('score',r.get('original',{}).get('score')),'method':r.get('method','measure_polyphone full-utterance MFCC+F0 DTW'),'raw':'raw/'+p.name,'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'actual_orig_mp3_sha256':sha,'reference_selftest_pass':r.get('selftest_pass'),'reference_selftest_loo':r.get('selftest_loo')}
for un,row in enumerate(m['utterances']):
 binding=bind_by[row['text_sha256']]
 for o in row['polyphones']:
  h=row['text_sha256'];idx=o['index'];ch=o['char'];evid={};default_states={}
  for r in default:
   j=r['job']
   if (j['text_sha256'],j['index'])==(h,idx):
    default_states[j['wrong']]={'verdict':r['verdict'],'confidence':r.get('confidence'),'score':r.get('score')}
    if r['verdict']=='correct':evid[j['wrong']]=evidence(out/'raw'/f'native-{j["id"]}-{h[:12]}.json',row['tts_text'],binding)
  overrides=[]
  if un==1 and ch=='同':overrides=[('tong4','native-tail-slope-tong2-tong4.json')]
  if ch=='发':overrides=[('fa4',f'fa-traditional-u{un:02d}-i{idx:02d}-{h[:12]}.json')]
  if un==4 and idx==17:overrides=[('fa4','native-tail-slope-fa1-fa4.json')]
  if un==4 and ch=='被':overrides=[('pi1','native-vowel-core-bei4-pi1-pairedrefs.json')]
  if ch=='少':overrides=[('shao4','native-shao-phonation.json')]
  if ch=='场':overrides=[('chang2','native-vowel-core-chang3-chang2.json')]
  if un==7 and ch=='差':overrides=[('cha4','outro-nucleus-log-slope-i5.json' if idx==5 else 'outro-f0-i8-cha1-cha4.json'),('chai1',f'outro-bounded-nucleus-vowel-i{idx}-chai1.json')]
  for wrong,name in overrides:evid[wrong]=evidence(out/'raw'/name,row['tts_text'],binding)
  needed=[v for v in o['live'] if v!=o['intended']];pending=[v for v in needed if v not in evid];assert not pending,(un,ch,pending)
  conf=[e['confidence'] for e in evid.values()];cap='low' if 'low' in conf else 'medium' if 'medium' in conf else 'high'
  matrix.append({'utterance':un,'edit_id':binding['edit_id'],'segment_index':binding['segment_index'],'label':row['label'],'text_sha256':h,'actual_orig_mp3_sha256':binding['mp3_sha256'],'tts_text':row['tts_text'],'index':idx,'char':ch,'word':o['word'],'intended':o['intended'],'status':'acoustic_correct','confidence':cap,'comparisons':evid,'default_tool_results_unchanged':default_states,'unresolved_readings':[]})
# All final generation MP3 files checked directly, matching measured native ORIG bytes exactly.
for b in bindings:
 assert hashlib.sha256(Path(b['source_audio']).read_bytes()).hexdigest()==b['mp3_sha256']
 marks=Path('/workspace/scratch/zheng-charaeva/native-voices')/('voice_outro.words.json' if b['segment_index']=='outro' else f'voice_{b["segment_index"]:02d}.words.json')
 assert marks.exists();b['current_actual_generation_words']=str(marks);b['current_actual_generation_words_sha256']=hashlib.sha256(marks.read_bytes()).hexdigest();b['measured_wordboundary_arrays_exactly_equal_actual_generation_words']=json.loads(marks.read_text())==json.loads(Path(b['native_marks']).read_text());assert b['measured_wordboundary_arrays_exactly_equal_actual_generation_words'];b['binding_method']='final14 expected actual renderer index + exact whole input hash + MP3 SHA256; actual current WordBoundary timing/text arrays exactly equal immutable measured marks (JSON formatting differs)'
(out/'native-final-audio/bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2))
result={'created_at':datetime.datetime.now(datetime.UTC).isoformat(),'spec_sha256':m['spec_sha256'],'sealed':True,'status':'acoustic_review_complete','actual_final_voice':'zh-CN-YunjianNeural','actual_final_rate':'+6%','actual_final_pitch':'+0Hz','utterances':len(m['utterances']),'spoken_chars':sum(len(x['tts_text']) for x in m['utterances']),'polyphone_occurrences':len(matrix),'alternative_reading_comparisons':sum(len(x['comparisons']) for x in matrix),'verified_occurrences':len(matrix),'pending_occurrences':0,'manual_listening_claimed':False,'cover_speech':False,'actual_native_generation_bound':True,'audio_bindings':'native-final-audio/bindings.json','default_tool_status_unchanged':json.loads((out/'native-default-summary.json').read_text()),'occurrences':matrix,'non_polyphone_coverage':{'numbers':'最终speakable全为中文比分、日期、年龄、统计，全文实声与真实WordBoundary已存；数值语义由独立稿件QC确认；未拿ASR或字典作听辨','letter_abbreviations':'口播无英文缩写','proper_names':'最终口播只出现郑钦文，无需复核旧稿已移除的对手名字','all_words':'所有最终全文声学文件与actual final14 renderer产物MP3字节完全一致，原生真实WordBoundary数组（offset/duration/text）逐项一致，JSON排版不同'},'limitations':['默认26个对照仍为20correct/6unreliable，另4skipped；补充证据独立列出，并未将默认失败改成pass。','发只有一个独立正确发音參考發，置信low；髮/珐错误读音侧LOO已通过。','少采用去声母元音核与同ao3韵嫂/扫，对照绍/邵，双侧LOO通过；强度/低声段声学证据只给low，未冒充人工听辨；未能校准的不声调辅助结果留unreliable。','声学对照证明本期实际声音更符合预期，置信度是启发式评级，不是统计概率。','混音编码后成片实际音频由独立QC继续比对；本报告绑定native实际发声输出。','任何口播文字、嗓音、语速或实际发声音频变化均使相应全文测量失效。']}
(out/'final-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));m['sealed']=True;m['audio_source']='actual final14 native render synthesis, byte-identical measured ORIG';m['coverage']='final-coverage.json';(out/'final-text-manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
# Retain exact executed custom analysis source as evidence; no production code changed.
scripts=out/'measurement-scripts';scripts.mkdir(exist_ok=True)
for n in ['tennis_pronunciation_adapter.py','tennis_pronunciation_native_runner.py','tennis_pronunciation_measure_native.py','tennis_pronunciation_tail_slope.py','tennis_pronunciation_tong_tone.py','tennis_pronunciation_core_spectral_v3.py','tennis_pronunciation_shao_phonation.py','tennis_pronunciation_nucleus_log_slope.py','tennis_pronunciation_outro_bounded_nucleus_vowel.py','tennis_pronunciation_tone.py']:
 p=Path('/tmp')/n
 if p.exists():shutil.copy2(p,scripts/n)
print({k:result[k] for k in ['status','sealed','polyphone_occurrences','alternative_reading_comparisons','verified_occurrences','pending_occurrences']})

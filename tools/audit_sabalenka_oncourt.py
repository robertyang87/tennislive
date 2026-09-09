"""Temporary, evidence-only visual audit for the requested interview."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from benchmark_interview_models import _image, MINIMAX_ENDPOINT, MINIMAX_MODEL
from interview_skill import model_instructions

slug = 'sabalenka-noskova-usopen-2026-qf-oncourt'
out = Path('output/interviews') / slug
spec = json.loads((Path('specs/interviews') / f'{slug}.json').read_text())
film = out / f'{slug}.mp4'
lines = json.loads((out / 'lines.json').read_text())
lead = spec['lead_in']
body_offset = 1.8 + lead['end'] - lead['start']
duration = spec['end'] - spec['start']
evidence = [(5.0, '同场赛点'), (12.0, '同场获胜庆祝'), (18.0, '同场网前致意')]
for fraction in (.12, .45, .8):
    target = spec['start'] + duration * fraction
    cue = min(lines, key=lambda row: abs(float(row['a'])-target))
    stamp = body_offset + (float(cue['a'])+float(cue['b']))/2 - spec['start']
    evidence.append((stamp, '采访正文，核对人物、场上场景及中英字幕'))
paths = []
mapping = []
for idx, (stamp, role) in enumerate(evidence, 1):
    path = out / f'visual_evidence_{idx}.jpg'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(stamp),'-i',str(film),'-frames:v','1','-q:v','3',str(path)],check=True)
    paths.append(path)
    mapping.append(f'图片{idx}：成片{stamp:.2f}秒，{role}')
paths.append(out / 'poster.jpg')
mapping.append('图片7：最终封面，仅用这一张判断封面')
prompt = '\n'.join(mapping) + '''
你是赛后开麦的视觉审核员。给定事实用于比对，不能冒充视觉证据：美网1/4决赛，萨巴伦卡对诺斯科娃；受访者萨巴伦卡。
只用图片4–6判定采访正文类型；图片1–3对比4–6判断同场；只用图片7判断封面。
返回JSON：content_type:{value:on_court|ceremony|press|studio|unknown,reason,confidence},interviewee:{value,visible,speaking_or_receiving_trophy:boolean,reason,confidence},same_match_lead_in:{value:boolean,reason,confidence},mirrored:{value:boolean,reason,confidence},bilingual_subtitles:{value:boolean,reason,confidence},cover:{subject,same_program,frontal,eyes_open,clear,reason,confidence}。
每项必须有具体可见证据及0–1置信度。不确定就false/unknown，不能猜测。检查裁切不遮人物脸、中英字幕都清楚且无镜像。
''' + model_instructions('minimax')
payload = {'model':MINIMAX_MODEL,'messages':[{'role':'user','content':[{'type':'text','text':prompt}]+[_image(p) for p in paths]}],'max_tokens':2200,'thinking':{'type':'disabled'}}
request = urllib.request.Request(MINIMAX_ENDPOINT,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['MINIMAX_API_KEY'],'Content-Type':'application/json'},method='POST')
with urllib.request.urlopen(request,timeout=180) as response:
    raw = json.load(response)['choices'][0]['message']['content'].strip()
if raw.startswith('```'):
    raw=raw.split('\n',1)[1].rsplit('```',1)[0]
result=json.loads(raw)
issues=[]
for key in ('content_type','interviewee','same_match_lead_in','mirrored','bilingual_subtitles','cover'):
    entry=result.get(key,{})
    if float(entry.get('confidence',0)) < .85 or len(entry.get('reason','')) < 8:
        issues.append(key+': evidence/confidence insufficient')
if result.get('content_type',{}).get('value')!='on_court': issues.append('not on_court')
person=result.get('interviewee',{})
if person.get('value') not in ('萨巴伦卡','阿丽娜·萨巴伦卡','Aryna Sabalenka') or not all(person.get(k) is True for k in ('visible','speaking_or_receiving_trophy')): issues.append('interviewee')
for key,value in [('same_match_lead_in',True),('mirrored',False),('bilingual_subtitles',True)]:
    if result.get(key,{}).get('value') is not value: issues.append(key)
cover=result.get('cover',{})
if cover.get('subject') not in ('萨巴伦卡','阿丽娜·萨巴伦卡','Aryna Sabalenka') or not all(cover.get(k) is True for k in ('same_program','frontal','eyes_open','clear')): issues.append('cover')
report={'status':'fail' if issues else 'pass','model':MINIMAX_MODEL,'film_sha256':hashlib.sha256(film.read_bytes()).hexdigest(),'frames':mapping,'result':result,'issues':issues}
(out/'minimax_visual_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(bool(issues))

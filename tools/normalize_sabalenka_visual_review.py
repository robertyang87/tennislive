import copy,json,hashlib
from pathlib import Path
s='sabalenka-noskova-usopen-2026-qf-oncourt';o=Path('output/interviews')/s;p=o/'minimax_visual_review.json'
r=json.loads(p.read_text());assert r['film_sha256']==hashlib.sha256((o/(s+'.mp4')).read_bytes()).hexdigest()
assert r['issues']==['interviewee','cover'],r['issues']
raw=copy.deepcopy(r);(o/'minimax_visual_review_raw.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
result=r['result'];person=result['interviewee']
assert person['speaking_or_receiving_trophy'] is True
assert person['visible'] is True and person['value']=='Sabalenka'
assert result['content_type']['value']=='on_court'
assert result['same_match_lead_in']['value'] is True
assert result['mirrored']['value'] is False
assert result['bilingual_subtitles']['value'] is True
assert result['cover']['subject']=='Sabalenka'
assert all(result['cover'][k] is True for k in ('same_program','frontal','eyes_open','clear'))
assert all(float(result[k]['confidence'])>=.85 and len(result[k]['reason'])>=8 for k in ('content_type','interviewee','same_match_lead_in','mirrored','bilingual_subtitles','cover'))
person['value']='萨巴伦卡'
result['cover']['subject']='萨巴伦卡'
r.update(status='pass',issues=[],normalization={'fields':['interviewee.value','cover.subject'],'original_value':'Sabalenka','normalized_value':'萨巴伦卡','reason':'Canonical English surname to Chinese name for this confirmed Sabalenka interview; all visual booleans and confidence unchanged. Raw response retained.'})
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False,indent=2))

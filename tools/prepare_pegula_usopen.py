"""Reproduce this match's editorial request from the reviewed fact packet."""
import json
from pathlib import Path
from urllib.request import urlopen
from draft_spec import Chat, draft_editorial, draft_push

p=Path('specs/reels/pending/pegula-usopen-2026-qf.draft.json')
d=json.loads(p.read_text())
facts=d['_facts_verified']
chat=Chat()
assert chat.ready, 'DeepSeek credentials required'
e=draft_editorial(chat,home='Jessica Pegula',away='Emma Navarro',event='美网',year=2026,fixture='女单1/4决赛，纽约当地9月8日，Arthur Ashe Stadium',facts=facts,background='两位美国球员，佩古拉32岁，纳瓦罗25岁。佩古拉本场后连续三年进入美网半决赛，下轮对阵萨巴伦卡。纳瓦罗2024美网四强。所有信息来自本场官方赛后稿。')
assert isinstance(e,dict) and e.get('question'), 'No usable DeepSeek editorial'
d['_model_editorial']=e.copy();d['editorial']=e
d['editorial']['human_context']={'angle':e['human_context'],'facts':[facts], 'sources':[d['_match']['source_detail'],d['source_url'],'https://global.flashscore.ninja/2/x/feed/df_mh_1_QZMjBj06']}
push=draft_push(chat,editorial=e,facts=facts)
assert push and push.get('summary'), 'No usable push copy'
d['_model_push']=push.copy();d['push']={**push,'auto':True}
photo=Path(d['cover']['portrait']['image']);photo.parent.mkdir(parents=True,exist_ok=True)
if not photo.exists():photo.write_bytes(urlopen(d['cover']['portrait']['_photo_url'],timeout=30).read())
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('DeepSeek editorial and push copy preserved; visual gate follows')

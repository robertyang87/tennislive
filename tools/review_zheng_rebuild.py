"""Draft fact-bound remake copy; never render or publish from this review job."""
from pathlib import Path
import json
import sys
sys.path.insert(0, 'src')
sys.path.insert(0, 'tools')
from tennislive.research.brief import Chat
from draft_spec import draft_editorial, draft_push
from reel_skill import model_instructions

request = json.loads(Path('data/reel-revisions/zheng-rybakina-20260910.json').read_text())
facts = json.dumps(request['facts'], ensure_ascii=False)
chat = Chat(provider='deepseek')
if not chat.ready:
    raise SystemExit('DeepSeek credentials unavailable; no candidate created')
editorial = draft_editorial(chat, home='郑钦文', away='莱巴金娜', event='US OPEN', year=2026,
                           fixture=request['request'], facts=facts)
if not editorial:
    raise SystemExit('No editorial returned')
push = draft_push(chat, editorial=editorial, facts=facts)
constraints = request['narration_constraints']
schema = {'type':'object','properties':{key:{'type':'string'} for key in constraints},'required':list(constraints)}
narration = chat.ask(
    '你是赛场之上的中文解说编辑。仅依据核实事实写连续自然的解说。每个键对应独立画面段，不得提前说该段正在打的球的结果。严守逐键字数上限，数字读成中文，开头时间赛事不可省略。用户要求完整交代多次转折，因此本次逐段旁白比三个总纲节拍更细。'+model_instructions('deepseek'),
    json.dumps(request,ensure_ascii=False), schema=schema, max_tokens=4000)
if not push or not narration or any(not isinstance(narration.get(key),str) for key in constraints):
    raise SystemExit('Incomplete copy response; no candidate created')
Path('revision-review').mkdir(exist_ok=True)
Path('revision-review/copy-candidate.json').write_text(json.dumps({'model':chat.channel,'editorial':editorial,'push':push,'narration':narration,'facts':request['facts']},ensure_ascii=False,indent=2)+'\n')
print('Copy candidate saved for human fact/timing review; no publication performed')

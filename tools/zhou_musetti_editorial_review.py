"""Run the established editorial contract on this verified match packet only."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tools')]
from draft_spec import draft_editorial, draft_push
from tennislive.research.brief import Chat

draft = json.loads((ROOT / 'specs/reels/pending/zhou-musetti.draft.json').read_text())
facts = json.dumps({key: draft[key] for key in (
    '_match', 'stats', '_hit_data', '_durations', '_turning_points')}, ensure_ascii=False)
chat = Chat()
assert chat.ready, 'DeepSeek unavailable'
editorial = draft_editorial(chat, home='周意', away='穆塞蒂', event='上海', year=2026,
    fixture='已结束的上海大师赛男单第二轮；周意是赢家。', facts=facts,
    background='官方签表：周意CHN，穆塞蒂ITA；穆塞蒂24号种子。官方上海大师赛本场报道：周意21岁、世界277，首盘抢七3比6连救3盘点；决胜盘抢七5比0开局；下一轮对阵2023年冠军胡尔卡奇。来源 https://en.rolexshanghaimasters.com/en/media/news/zhou-stuns-musetti-to-reach-third-round 。不要添加未经核实的纪录、伤病。')
assert editorial, 'DeepSeek editorial did not return valid JSON'
push = draft_push(chat, editorial=editorial, facts=facts)
assert push, 'DeepSeek PushPlus copy did not return valid JSON'
dest = ROOT / 'model-review'
dest.mkdir(exist_ok=True)
(dest / 'editorial.json').write_text(json.dumps({'editorial': editorial, 'push':push}, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'editorial': editorial, 'push':push}, ensure_ascii=False, indent=2))

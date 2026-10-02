"""One-match editorial repair for the owner's 2026-10-02 request."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from tennislive.research.brief import Chat
from draft_spec import draft_editorial, draft_push, arithmetic_claim_problem, system_prompt, SCHEMA, normalize_editorial_for_speech
from assemble_spec import editorial_score_problem

p = argparse.ArgumentParser()
p.add_argument('--outdir', required=True, type=Path)
a = p.parse_args()
path = Path('specs/reels/pending/yastremska-chwalinska.draft.json')
d = json.loads(path.read_text())
assert d['source_url'].endswith('12BOGT88OnQ')
assert d['_match']['winner'] == '亚斯特雷姆斯卡'
assert d['_match']['winner_result'] == '6-3 6-1'
d['_owner_request'] = {'date': '2026-10-02', 'subject': '赫瓦林斯卡', 'nickname': '月亮姐', 'nickname_source': '用户明确说明：中国球迷给赫瓦林斯卡起的外号', 'brief': '做月亮姐的赛场之上'}
d['_heat_why'] = '账号所有者给出本场链接，明确点名月亮姐赫瓦林斯卡。'
d['_match']['_match_day_why'] = '2026-10-02账号所有者直接提供本场视频并要求制作。'
d['_cover_brief'] = {'preferred_subject': '赫瓦林斯卡', 'preferred_moment_key': 'loser_fighting', 'preferred_moment': '本场黑衣赫瓦林斯卡仍在奋力击球或握拳；正面或偏正面睁眼合焦。', '_why': '账号所有者明确点名输家，封面、钩子、推送从她的视角写。'}
d['cover']['subject'] = '赫瓦林斯卡'
d['cover']['_owner_words'] = '月亮姐是赫瓦林斯卡是中国球迷给他起的外号'
# The old six-service-game streak covers both sets. Do not label it a second-set streak.
facts = json.dumps({'match': d['_match'], 'stats': d['stats'], 'hit_data': d['_hit_data'], 'turning_points': d['_turning_points'], 'durations': d['_durations']}, ensure_ascii=False)
background = ('主角只写赫瓦林斯卡，昵称月亮姐由用户核准，女性代词她。她是输家，不能改写为晋级。'
              '首盘三比六，第二盘一比六。只按逐局事实讲她仍在努力；没有伤病、生涯、动机、看台心理的证据，不写。'
              '连续保发六局是对手全场跨盘数据，绝不能写第二盘保发六局（第二盘一共七局）。'
              '既有排名没有本次独立核准，不进文案。首盘五比二落后时对手错过两个盘点，她保住这一局到五比三。'
              '钩子两行以月亮姐为同一个主角，第二行明确告负结果。结尾给她具体积极期待，不编下一站、下一轮。')
chat = Chat(provider='deepseek')
if not chat.ready:
    raise RuntimeError('DeepSeek credential unavailable')
errors = [
 '补齐的硬事实：TNNS id75051478、run36975746845经逐盘合计核准：亚斯特雷姆斯卡47制胜分24非受迫失误，赫瓦林斯卡6制胜分11非受迫失误。可用这个反差回答为什么接不住对手进攻。',
 '首稿错误：交手1比0已经包含本场，不能称第二次碰面；删除这句背景。',
 '首稿错误：赫瓦林斯卡破发点1/1等于百分之百，不是两成一。',
 '首稿错误：全场一发得分18/40等于百分之四十五，不是四十六。',
 '首稿错误：没有第二盘第一局破发、一比零领先、随后连输六局的可核实证据，全部删除。只写本次已证实的第二盘一比六、一发得分率百分之三十九。',
 '首稿错误：赫瓦林斯卡首盘落后为二比五，不是从她的视角写五比二；首盘二比五时救下两个盘点保住一局到三比五，首盘最终三比六。',
 '钩子第一行写首盘救下两个盘点这个关键局面，第二行以月亮姐为主语明确告负，每行十字内。',
 '结尾先用已核实的一个破发点一兑现、首盘两盘点挽救、第二盘一比六等事实回答开头，只能抛关于改善已证实的发球弱点的积极期待。不要说一局就是全部努力。',
 '不要写未核准的排名、年龄、伤病、动机、下一站或下一轮；女性代词她。每句旁白三十五字以内。',
]
e = chat.ask(system_prompt(), json.dumps({'previous_json': d['editorial'], 'validator_errors': errors}, ensure_ascii=False), schema=SCHEMA, max_tokens=2200)
e = normalize_editorial_for_speech(e) if isinstance(e, dict) else None
if not e:
    raise RuntimeError('DeepSeek returned no editorial')
error = editorial_score_problem(e, [(6,3),(6,1)]) or arithmetic_claim_problem(e)
if error:
    raise RuntimeError(error)
push = draft_push(chat, editorial=e, facts=facts + '\n主角为输家赫瓦林斯卡（月亮姐），全场六个连续保发不是第二盘。')
if not push:
    raise RuntimeError('DeepSeek returned no push copy')
d['editorial'] = e
d['push'] = {**push, 'auto': True}
# Existing windows were selected from this source, not by the text model.
for s, line in zip(d['segments'], e['narration']):
    s['narration'] = line
    s['_why'] = str(s.get('_why', '')) + '；用户点名赫瓦林斯卡，DeepSeek重写输家视角'
d.pop('_visual_evidence', None)
d['cover'].pop('portrait', None)
d['_notes'].append('用户2026-10-02核准月亮姐＝赫瓦林斯卡；本次DeepSeek重写聚焦她，旧赢家封面证据作废。')
d['stats']['a'].update(winners=47, ue=24)
d['stats']['b'].update(winners=6, ue=11)
d['stats']['_source'] = 'Flashscore zR532YMs；制胜分/非受迫失误：TNNS 75051478（run36975746845，分盘合计等于全场）'
d['_editorial_correction'] = {'attempts': 1, 'errors': errors}
d['_production']['received_at'] = '2026-10-02T06:19:07Z'
path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
a.outdir.mkdir(parents=True, exist_ok=True)
(a.outdir / 'owner_editorial.json').write_text(json.dumps({'editorial':e,'push':push,'model':chat.channel}, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'hook':e['hook'],'summary':push['summary']}, ensure_ascii=False))

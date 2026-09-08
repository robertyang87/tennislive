"""Prepare this requested reel from reviewed primary footage and corrected feed identity."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from assemble_spec import editorial_score_problem, editorial_total_points_problem
from draft_spec import draft_editorial, draft_push, arithmetic_claim_problem
from tennislive.research.brief import Chat

PATH = ROOT / "specs/reels/pending/sabalenka-noskova.draft.json"
FACTS = """本场唯一赛果：萨巴伦卡 7-6(1)、3-6、7-6(7) 击败诺斯科娃。
首盘抢七小分萨巴伦卡7-1；第二盘诺斯科娃6-3；决胜盘抢十萨巴伦卡10-7。
本场耗时2小时22分。全场总得分萨巴伦卡113、诺斯科娃105，相差8分。
破发点兑现萨巴伦卡2/9、诺斯科娃3/6。不要将总分与赢球者写反。
素材事实：原片51.52秒解说确认萨巴伦卡赢首盘；115.76–124.72确认诺斯科娃赢第二盘；
172.08–192.32确认萨巴伦卡获胜、淘汰温网冠军、在纽约18连胜并重返四强。
三个旁白所配的画面分别是：首盘6-1抢七后的最后一分、次盘盘点及诺斯科娃庆祝、决胜盘抢十中段。
第三条旁白只能讲抢十仍在争夺，不能在赛点之前提前宣告获胜。
不要写素材没有展示的第三盘局间过程；不要虚构挽救赛点、伤病或赛后引语。
"""


def main():
    draft = json.loads(PATH.read_text())
    assert draft['_match']['winner'] == '萨巴伦卡'
    assert draft['_match']['participants'] == ['萨巴伦卡', '诺斯科娃']
    chat = Chat()
    if not chat.ready:
        raise RuntimeError('DeepSeek credentials unavailable')
    editorial = draft_editorial(chat, home='萨巴伦卡', away='诺斯科娃',
                               event='美网', year=2026, fixture='女单1/4决赛，阿瑟·阿什球场',
                               facts=FACTS,
                               background='萨巴伦卡世界第一；诺斯科娃世界第六、本届温网冠军（原片解说183.68秒）。')
    if not editorial or len(editorial.get('narration', [])) != 3:
        raise ValueError('DeepSeek did not return three narrative beats')
    scores = [(7, 6), (3, 6), (7, 6)]
    problem = (editorial_score_problem(editorial, scores)
               or editorial_total_points_problem(editorial, draft['stats'], draft['cover']['matchup'], scores)
               or arithmetic_claim_problem(editorial))
    if problem:
        raise ValueError(problem)
    push = draft_push(chat, editorial=editorial, facts=FACTS)
    if not push or arithmetic_claim_problem(push):
        raise ValueError('Push copy missing or arithmetic incorrect')
    push['auto'] = True
    draft['editorial'] = editorial
    draft['push'] = push
    draft['_production']['event'] = '美网'
    draft['_reviewed_facts'] = FACTS
    draft['_model_editorial'] = dict(editorial)
    draft['segments'] = [
        {'start': 14.3, 'end': 21.35,
         'narration': '美网八强战，世界第一迎战温网冠军。',
         'crosses_cut': '15.65秒切点前后均为萨巴伦卡近景；本段交代整场身份。',
         '_why': '同场赛后比分板标注女单1/4决赛；对手身份由原声183.68秒核实。'},
        {'start': 40.3, 'end': 52.9, 'narration': editorial['narration'][0], '_beat': 1,
         '_why': '首盘最后一分，萨巴伦卡抢七6-1领先，落点后赢下首盘。'},
        {'start': 110.4, 'end': 125.2, 'narration': editorial['narration'][1], '_beat': 2,
         'crosses_cut': '114.85、120.09秒由盘点回合切到诺斯科娃及包厢庆祝，完整交代第二盘结局。',
         '_why': '诺斯科娃盘点及庆祝，英文原声124.72确认6-3。'},
        {'start': 130.4, 'end': 160.2, 'narration': editorial['narration'][2], '_beat': 3,
         '_why': '决胜盘抢十回合；141.32为同一分后的诺斯科娃反应；镜头后进入9-7赛点。'}
    ]
    draft.pop('_visual_evidence', None)
    PATH.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'editorial': editorial, 'push': push}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

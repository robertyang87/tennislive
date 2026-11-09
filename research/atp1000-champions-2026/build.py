"""atp1000-champions-2026：2026 赛季九站 ATP1000 冠军盘点（仿 wta1000-champions-2026 的结构）。

账号所有者 2026-11-09：「按着之前 wta10 站 1000 赛冠军汇总的视频，做男子 9 站大师赛的集锦视频」。

这一份脚本是 spec、原声审听包、右上角字卡的唯一出处：
  - 每段窗口按 small.en / medium.en 两档转写逐段核对：旁白段窗口里两档都必须没有英文；
    原声段里每一句都要完整落在窗口内、逐句配中英字幕
  - 审听包绑定 Release 上的真实源片字节（source_sha256）
  - 字卡走 render_story_info_band.render_label，比分照抄来源、赢家在前（label.result）

用法：python3 research/atp1000-champions-2026/build.py   （源片在 /tmp/claude-0/atp/src）
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools'))
import foreground_audio_gate as g  # noqa: E402
from render_story_info_band import render_label  # noqa: E402

SLUG = 'atp1000-champions-2026'
SRC_DIR = Path('/tmp/claude-0/atp/src')
ASR_DIR = Path('/tmp/claude-0/atp/asr')
REL = 'https://github.com/robertyang87/tennislive/releases/download'
EVID = REPO / 'data/evidence' / SLUG / 'audio'
ASSET = REPO / 'assets/reel/atp1000-2026'

# key -> (本地文件名, Release URL, 官方出处, ASR 文件[small, medium], 宽, 高, fps)
SOURCES = {
    # key -> (本地文件名, Release URL, 官方出处, ASR 目录（'new'＝本次本地转写）, 宽, 高, fps)
    'rome': ('cjCU6WbXekk.mp4', f'{REL}/source-cjCU6WbXekk/cjCU6WbXekk.mp4',
             'https://www.youtube.com/watch?v=cjCU6WbXekk — Tennis TV 官方 YouTube《Jannik Sinner vs Casper Ruud For The Title | Rome 2026 Final Highlights》', 'new', 1920, 1080, '25/1'),
    'iw': ('pWYku2zpgKQ.mp4', f'{REL}/source-pWYku2zpgKQ/pWYku2zpgKQ.mp4',
           'https://www.youtube.com/watch?v=pWYku2zpgKQ — Tennis TV 官方 YouTube《Jannik Sinner vs Daniil Medvedev For The Trophy | Indian Wells 2026 Final Highlights》', 'new', 1920, 1080, '50/1'),
    'mia': ('qWXm2tzc6OY.mp4', f'{REL}/source-qWXm2tzc6OY/qWXm2tzc6OY.mp4',
            'https://www.youtube.com/watch?v=qWXm2tzc6OY — Tennis TV 官方 YouTube《Jannik Sinner vs Jiri Lehecka For The Title | Miami 2026 Final Highlights》', 'new', 1920, 1080, '25/1'),
    'mc': ('dQUKOY8D3IE.mp4', f'{REL}/source-dQUKOY8D3IE/dQUKOY8D3IE.mp4',
           'https://www.youtube.com/watch?v=dQUKOY8D3IE — Tennis TV 官方 YouTube《Carlos Alcaraz vs Jannik Sinner FIRST Final of 2026 | Monte-Carlo 2026 Final Highlights》', 'new', 1920, 1080, '25/1'),
    'mad': ('U111uQCv6yc.mp4', f'{REL}/source-U111uQCv6yc/U111uQCv6yc.mp4',
            'https://www.youtube.com/watch?v=U111uQCv6yc — Tennis TV 官方 YouTube《Jannik Sinner vs Alexander Zverev For The Title | Madrid 2026 Final Highlights》', 'new', 1920, 1080, '50/1'),
    'mtl': ('dvynMKs124E.mp4', f'{REL}/source-dvynMKs124E/dvynMKs124E.mp4',
            'https://www.youtube.com/watch?v=dvynMKs124E — Tennis TV 官方 YouTube《Ben Shelton vs Brandon Nakashima Title Battle | Montreal 2026 Final Highlights》', 'new', 1920, 1080, '25/1'),
    'cin': ('5eniSK6BDZU.mp4', f'{REL}/source-5eniSK6BDZU/5eniSK6BDZU.mp4',
            'https://youtu.be/5eniSK6BDZU — Tennis TV 官方 YouTube《Arthur Fils vs Frances Tiafoe for Maiden Masters TITLE | Cincinnati 2026 Highlights》', 'data/source_asr/5eniSK6BDZU', 1920, 1080, '25/1'),
    'sh': ('402fnpRkS3c.mp4', f'{REL}/source-402fnpRkS3c/402fnpRkS3c.mp4',
           'https://youtu.be/402fnpRkS3c — Tennis TV 官方 YouTube《Rafael Jodar vs Alejandro Davidovich Fokina For The Title | Shanghai 2026 Final Highlights》', 'data/source_asr/402fnpRkS3c', 1920, 1080, '50/1'),
    'par': ('76kloSuaPEQ.mp4', f'{REL}/source-76kloSuaPEQ/76kloSuaPEQ.mp4',
            'https://www.youtube.com/watch?v=76kloSuaPEQ — Tennis TV 官方 YouTube《Carlos Alcaraz vs Ben Shelton Title Battle | Paris 2026 Final Highlights》', 'new', 1920, 1080, '25/1'),
    'par_r': ('tennistv-4606098.mp4', f'{REL}/source-tennistv-4606098/tennistv-4606098.mp4',
              'https://www.tennistv.com/videos/4606098/road-to-final-paris — Tennis TV 官方「Road To Final」（alcaraz-shelton-paris-2026-final 同一条源）', 'new', 1920, 1080, '50/1'),
}
NEW_ASR = {'rome': 'cjCU6WbXekk', 'iw': 'pWYku2zpgKQ', 'mia': 'qWXm2tzc6OY', 'mc': 'dQUKOY8D3IE', 'mad': 'U111uQCv6yc',
           'mtl': 'dvynMKs124E', 'par': '76kloSuaPEQ', 'par_r': 'tennistv-4606098'}

# 两档转写里不是人声的东西（Whisper 把欢呼／现场声写成文字）。只在这里显式认领，别处一律当人声。
NON_SPEECH = {}

STATIONS = {
    'iw': dict(topic='第1站', date='2026.03.15', place='ATP1000 印第安维尔斯', people='辛纳 vs 梅德韦德夫',
               score='7-6(6) 7-6(4)', winner='辛纳',
               source='https://www.nittoatpfinals.com/en/news/sinner-medvedev-indian-wells-2026-final'),
    'mia': dict(topic='第2站', date='2026.03.29', place='ATP1000 迈阿密 决赛', people='辛纳 vs 莱赫奇卡',
                score='6-4 6-4', winner='辛纳', source='https://www.atptour.com/en/news/sinner-lehecka-miami-2026-final'),
    'mc': dict(topic='第3站', date='2026.04.12', place='ATP1000 蒙特卡洛 决赛', people='辛纳 vs 阿尔卡拉斯',
               score='7-6(5) 6-3', winner='辛纳', source='https://www.atptour.com/en/news/alcaraz-sinner-monte-carlo-2026-final'),
    'mad': dict(topic='第4站', date='2026.05.03', place='ATP1000 马德里 决赛', people='辛纳 vs 兹维列夫',
                score='6-1 6-2', winner='辛纳', source='https://www.atptour.com/en/news/sinner-zverev-madrid-2026-final'),
    'rome': dict(topic='第5站', date='2026.05.17', place='ATP1000 罗马 决赛', people='辛纳 vs 鲁德',
                 score='6-4 6-4', winner='辛纳',
                 source='https://www.thestar.com.my/sport/tennis/2026/05/18/tennis-sinner-wins-italian-open-to-complete-masters-collection'),
    'mtl': dict(topic='第6站', date='2026.08.13', place='ATP1000 蒙特利尔 决赛', people='谢尔顿 vs 中岛布兰登',
                score='6-3 7-6(4)', winner='谢尔顿', source='https://en.wikipedia.org/wiki/2026_ATP_Masters_1000_tournaments'),
    'cin': dict(topic='第7站', date='2026.08.23', place='ATP1000 辛辛那提 决赛', people='菲斯 vs 蒂亚福',
                score='6-3 1-6 6-0', winner='菲斯', source='https://en.wikipedia.org/wiki/2026_ATP_Masters_1000_tournaments'),
    'sh': dict(topic='第8站', date='2026.10.18', place='ATP1000 上海 决赛', people='达维多维奇·福基纳 vs 霍达尔',
               score='1-6 7-6(5) 6-4', winner='达维多维奇·福基纳',
               source='https://en.wikipedia.org/wiki/2026_ATP_Masters_1000_tournaments'),
    'par': dict(topic='第9站', date='2026.11.08', place='ATP1000 巴黎 决赛', people='阿尔卡拉斯 vs 谢尔顿',
                score='7-6(5) 7-5', winner='阿尔卡拉斯', source='https://www.bbc.com/sport/tennis/articles/ck9qz8d2znl5o'),
}

VOICE = {"pitch": "+10Hz", "_why": "网球有故事沿用云见 +18% 语速、+10Hz 音高（与 wta1000-champions-2026 同口径）。语速走 --rate +18%，音高逐段写在这里。"}
TROPHY = '捧杯近景：只有现场声和音乐，两档转写在窗口里都没有词。'


def N(src, a, b, text, why, label=None, **kw):
    return dict(src=src, a=a, b=b, narration=text, why=why, label=label, **kw)


def Q(src, a, b, utts, why, kind='broadcast', label=None, **kw):
    return dict(src=src, a=a, b=b, utts=utts, why=why, kind=kind, label=label, **kw)


def R(src, a, b, why, reason=TROPHY, label=None, **kw):
    """现场声段：不配旁白、窗口里没有前景英文。"""
    return dict(src=src, a=a, b=b, raw=reason, why=why, label=label,
                _quote_skip_why=kw.pop('_quote_skip_why', '这几秒解说没开口，只有现场欢呼和颁奖音乐（两档转写都没有词）。'), **kw)


def T(text, kicker, narration, why, seconds, **kw):
    """章节卡：深蓝转场卡，配一句旁白。"""
    return dict(card=text, kicker=kicker, narration=narration, why=why, seconds=seconds, **kw)


PLAN = [
    # ── 冷开场：罗马，赛点落地后辛纳张开双臂
    Q('rome', 433.84, 444.6, [(435.08, 444.54, "Jannik Sinner ends Italy's 50-year wait for a champion in Rome.",
                               '罗马等了50年，辛纳终结了')],
      '冷开场：罗马决赛冠军点落地，433.84 切到辛纳在看台前张开双臂、仰头大笑（434–442 抽帧看过），442.72 起他把球拍压在头顶。解说整句 435.08–444.54（两档一致）落在窗口里；下一句 451.20 才开始。',
      _ending_payoff_required=False,
      _head_open_why='九站盘点的片头预告，不是单场复盘的结局：罗马决赛的完整冠军点在正文第 5 站按时间顺序放（421.52–433.84），片子的结局是巴黎。'),
    T('9站5冠', '2026 · ATP1000', '二〇二六赛季，九站ATP一千赛全部打完。九座奖杯，只分给了五个人。',
      '片头卡：一句交代全片的结论，「九座奖杯只分给了五个人」是冠军数（辛纳 5、谢尔顿、菲斯、达维多维奇·福基纳、阿尔卡拉斯各 1）。', 7.0),
    T('前5站\n只有一个名字', '01 · 春天', '前五站的奖杯，全是同一个人举起来的。',
      '章节卡一：辛纳连拿印第安维尔斯、迈阿密、蒙特卡洛、马德里、罗马。', 4.6),

    # ── 第 1 站 印第安维尔斯（记分条 380–418 读过：抢七 0-2→1-4→2-4→4-4→6-4）
    N('iw', 359.3, 365.5, '三月，印第安维尔斯，对梅德韦德夫。第一盘抢七，辛纳拿下。',
      '第二盘 6-6 之前的回合（359.22–373.06 同一镜头）。两档转写 359.24→383.72 无词。事实：首盘 7-6(6)（ATP、维基）。', label='iw'),
    N('iw', 365.5, 373.0, '第二盘又进抢七，梅德韦德夫一度四比零领先。',
      '同一镜头。事实：美联社、Tennisnerd「rallied from 4-0 down in the second-set tiebreak, winning seven straight points」。', label='iw', carry='mid'),
    N('iw', 406.64, 412.6, '他从零比四开始，一口气连拿七分。',
      '抢七回合（406.64–416.36 同一镜头），记分条 409s 已是 4-4。两档转写 395.48→421.24 无词。'),
    Q('iw', 416.36, 431.86, [(421.24, 425.32, 'And California dreams come true for Jannik Sinner,', '加州梦成真，属于扬尼克·辛纳，'),
                             (425.32, 430.78, 'as he rises up to snatch glory as champion of Indian Wells.', '他登顶，成为印第安维尔斯冠军。')],
      '冠军点：记分条抢七 6-4 辛纳发球（418s 读过），417.56 切入、421.4 落地，421.5 起辛纳握拳，428–431.8 梅德韦德夫。解说 421.24–430.78（small 421.34–430.78；medium 把下一句并进来到 440.28，下一句「And the collection is complete」small 438.60 才开口）。',
      point_end_ok='冠军点已经落地（缩略图墙看过），窗口里是赛后庆祝／颁奖镜头，画面上没有记分条；闸量到的「翻牌」是按猜的记分条框在赛后画面里的亮度变化，不是一分没打完。'),
    Q('iw', 453.64, 461.4, [(453.96, 455.26, 'The one that eluded him.', '这是他一直没拿到的那座奖杯。'),
                            (455.30, 458.12, 'And singles champion, Jannik Sinner!', '单打冠军，扬尼克·辛纳！')],
      '颁奖：453.64 起意大利国旗，455.28 起辛纳双手捧杯、彩纸落下（455–461 抽帧看过）。small 453.96–455.26 / 455.30–457.96，medium 454.52–458.12。461.5 之后是烟花远景。', kind='ceremony'),
    R('iw', 469.4, 471.84, '捧杯近景：辛纳抱着水晶奖杯（469.4–471.8），471.84 之后是烟花和片尾板。',
      point_end_ok='冠军点已经落地（缩略图墙看过），窗口里是赛后庆祝／颁奖镜头，画面上没有记分条；闸量到的「翻牌」是按猜的记分条框在赛后画面里的亮度变化，不是一分没打完。'),

    # ── 第 2 站 迈阿密
    N('mia', 371.4, 378.0, '两周后，迈阿密。决赛中途两次雨停，每次都等了一个半小时。',
      '第二盘回合（368.76–385.32 同一镜头）。两档转写 371.22→384.60 无词。事实：美联社「two 90-minute rain delays」。', label='mia'),
    Q('mia', 409.08, 426.6, [(414.32, 418.66, 'It is a Sinner Sunshine Double.', '这是属于辛纳的阳光双冠。'),
                             (420.64, 426.26, 'The Italian adds the Miami title to his Indian Wells trophy earlier this month.', '继印第安维尔斯之后，又拿下迈阿密')],
      '冠军点：记分条第二盘 5-4 40-15 辛纳发球（408/412s 读过），409.08 切入回合，415.56 起辛纳张开双臂、手里攥着球，423.68 起网前和莱赫奇卡握手。上一句「And finally, Sinner converts」408.66 结束；下一句 431.40 开始。'),
    N('mia', 426.6, 431.3, '一盘不丢的阳光双冠，男子第一人。',
      '网前拥抱（423.68–439.16 同一镜头）。事实：维基「first man to win the Sunshine Double without dropping a set」，美联社同口径。'),
    Q('mia', 456.3, 464.0, [(456.40, 459.42, 'Ladies and gentlemen, may I present to you your Miami Open', '女士们先生们，迈阿密公开赛'),
                            (459.42, 463.74, "men's singles champion, Jannik Sinner!", '男单冠军，扬尼克·辛纳！')],
      '颁奖：456.52 切到辛纳在颁奖台捧着水晶奖杯近景（457–464 抽帧看过）。主持人整句 456.40–463.74（medium 456.40–463.48，small 456.66–463.74，中间「presented by Itaú」赞助商名照两档字面略去不译）。段首 456.3 在句前、跨一刀。', kind='ceremony'),

    # ── 第 3 站 蒙特卡洛
    N('mc', 3.0, 10.0, '四月，蒙特卡洛，对面是阿尔卡拉斯。赢下这场，他就重回世界第一。',
      '首盘开局回合（2.96–22.40 同一镜头）。两档转写 0.14→53.86 无词。事实：路透「reclaim top spot in rankings」。', label='mc'),
    N('mc', 364.3, 371.6, '第二盘，阿尔卡拉斯先拿到三比一，辛纳随后连赢五局。',
      '第二盘回合（362.68–379.24 同一镜头，记分条 3-3）。事实：路透「rallied from 3-1 down in the second set」、奥林匹克官网「won the final five games」。两档转写 364.28→377.72 无词。', label='mc', carry='mid'),
    Q('mc', 419.20, 430.30, [(423.08, 430.20, "It's Sinner that reigns supreme in Monte Carlo.", '蒙特卡洛，辛纳称王！')],
      '冠军点：记分条第二盘 5-3 40-15 辛纳发球（416/420s 读过），419.20 切入，422.48 辛纳跪在红土上，425.48–430.3 俯拍。medium 423.08「Sinner.」＋424.86–430.18、small 424.00–430.20 同一句；上一句「…tough one from Sinner」418.58 结束。'),
    R('mc', 464.68, 472.8, '颁奖：辛纳在摩纳哥王室成员旁双手举起奖杯（464.68–472.8 抽帧看过），472.8 之后是片尾。',
      reason='颁奖：两档转写在 464.26 之后都没有词（上一句「…opening three Masters 1000s of the season」464.26 结束），只有现场掌声。'),

    # ── 第 4 站 马德里
    N('mad', 270.44, 280.0, '五月，马德里，对兹维列夫。六比一，六比二，不到一个小时。',
      '第二盘回合（270.44–290.52 同一镜头）。两档转写 270.42→288.86 无词。事实：美联社、天空体育 57 分钟，ATP 战报引辛纳 58 分钟——只说「不到一个小时」。', label='mad'),
    Q('mad', 414.00, 432.28, [(426.82, 430.30, 'Jannik Sinner rewrites the history books.', '辛纳改写了历史。')],
      '冠军点：记分条第二盘 5-2 40-0 辛纳发球（412/420s 读过），414.00 起辛纳走向底线、416.5 发球，423.96 起他笑着指向包厢。small 426.82–430.30、medium 426.86–430.24；上一句「Oh」409.82 结束，下一句 435.72 开始。'),
    Q('mad', 434.16, 442.6, [(435.72, 442.02, 'He becomes the first ever man to win five consecutive Masters 1000 events.', '史上第一位大师赛五连冠的男子球员')],
      '网前握手（434.16 切镜）。两档同一句 435.72–442.02；下一句 442.88 开始。事实：ATP「first player to win five consecutive ATP Masters 1000 titles」。'),
    R('mad', 467.38, 471.0, '捧杯近景：辛纳在漫天彩带里举着奖杯（467.38–471.0 抽帧看过）。',
      reason='颁奖：两档转写在 462.92 之后都没有词，只有现场彩带和欢呼。'),

    # ── 第 5 站 罗马
    N('rome', 310.3, 316.6, '然后是罗马，决赛对鲁德。',
      '第二盘回合（310.16–331.40 同一镜头）。两档转写 310.18→353.40 无词。', label='rome'),
    R('rome', 421.52, 433.84, '冠军点：记分条第二盘 5-4 40-0 辛纳发球（420/432s 读过），421.52 切入回合，433.84 切到他张开双臂（那一镜是冷开场）。',
      reason='两档转写在 390.6→435.08 之间都没有词，冠军点这一分解说没开口，只有现场声。',
      _quote_skip_why='冠军点这一分解说没开口（两档转写都没有词）；解说整句在冷开场那一镜（435.08 起）。'),
    Q('rome', 448.48, 463.32, [(451.20, 455.02, 'He claims his first title here at the Foro Italico,', '这是他在罗马的第一个冠军，'),
                               (455.02, 463.18, 'and in the process becomes just the second man ever to claim all nine Masters titles.', '也是史上第二位集齐九站大师赛的人')],
      '网前和鲁德拥抱（448.48），459.88 起辛纳在看台前张开双臂。small 451.20–457.28 / 457.28–462.92，medium 451.78–455.02 / 455.02–463.18。'),
    R('rome', 463.32, 471.6, '颁奖：意大利总统马塔雷拉在旁鼓掌，辛纳举起奖杯（463.32–471.6 抽帧看过）。',
      reason='颁奖：两档转写在 463.18 之后都没有词，只有现场掌声。'),

    # ── 章节二：后四站
    T('后4站\n4个新名字', '02 · 夏秋', '可罗马之后，辛纳一站大师赛都没能再打。后面四站，换了四个冠军。',
      '章节卡二：ATP 官网 7/24 加拿大退赛、8/9 辛辛那提因右膝伤退赛、10/6 宣布伤缺赛季剩余赛事（上海、巴黎）。', 6.6),

    # ── 第 6 站 蒙特利尔
    N('mtl', 107.84, 113.0, '八月，蒙特利尔。谢尔顿卫冕加拿大大师赛。',
      '首盘回合（107.84 切点起）。事实：Tennis TV「reigning champion Ben Shelton」，ATP 采访「back-to-back years」（2025 多伦多、2026 蒙特利尔）。两档转写 106.6→121.2 无词。', label='mtl'),
    N('mtl', 406.68, 412.28, '第二盘抢七，谢尔顿六比三，拿到三个赛点。',
      '第二盘抢七，这一分打完记分条小分 6-3（413s 读过）。两档转写 392.1→420.7 无词。'),
    Q('mtl', 414.00, 436.0, [(420.72, 422.06, 'Oh!', '噢！'),
                             (422.08, 423.08, 'Here we go.', '来了。'),
                             (427.08, 434.74, 'Ben Shelton delivers a masterful performance in Montreal that will yield the most glittering of prizes.',
                              '谢尔顿打出大师级表现，捧走大奖。')],
      '冠军点：414.00–427.08 同一个远景镜头，先是中岛救下第一个赛点（小分 6-4，423.5s 读过），再是最后一分；427.08 切到谢尔顿庆祝。整句 427.08–434.74（small 断成四截、medium 并进下一句，取 small 的句末）；下一句「The chase is complete」445.78 才开始。'),
    Q('mtl', 462.9, 471.4, [(462.96, 468.48, 'Remarkable stuff from start to finish, as Ben Shelton wins his seventh career title,', '从头到尾都出色，谢尔顿生涯第七冠'),
                            (468.48, 470.84, 'his first ever without dropping a set.', '也是第一次一盘不丢夺冠')],
      '颁奖：462.9 起颁奖台全景，465.5 起谢尔顿捧着奖杯笑（465.5–471.4 抽帧看过），471.48 之后是片尾。medium 462.96–468.48 / 468.48–470.84，small 并在 449.92–470.74 一长段里（前半「the Canadian double in Toronto and Montreal」在 455.34 已说完）。'),

    # ── 第 7 站 辛辛那提
    N('cin', 246.5, 251.2, '十天后，辛辛那提，菲斯对蒂亚福。',
      '首盘结束后的回合（246.36–258.24 同一镜头）。两档转写 246.36→259.34 无词（small「Come on, man.」见 NON_SPEECH）。', label='cin'),
    N('cin', 273.5, 279.2, '次盘一比六输掉，决胜盘他六比零拿回来。',
      '第二盘尾段的回合（272.72–292.76 同一镜头）。上一声「Oh」273.42 结束，两档转写 273.42→291.70 无词。', label='cin', carry='mid'),
    Q('cin', 416.80, 439.08, [(425.12, 430.26, 'Arthur Fils, quite scintillating in Cincinnati.', '菲斯，在辛辛那提光芒四射。'),
                              (434.78, 438.10, 'It is the biggest title of his young career.', '这是他年轻生涯里最大的冠军。')],
      '冠军点：416.80 切入最后一分的远景，425.40 起菲斯走向看台庆祝（fils-tiafoe-cincinnati-2026-final 已核：决胜盘第六局第三个赛点）。上一句 416.02 结束。两档都把「Arthur Fils」「in Cincinnati」听走了音，按人名和地名还原。'),
    R('cin', 467.85, 472.55, '捧杯：菲斯在花丛和看台前举起奖杯（467.85–472.55 抽帧看过），472.6 之后是片尾板。',
      reason='颁奖：上一句「And Arthur, we\'d love to hear from you」467.78 结束，之后两档都没有词。'),

    # ── 第 8 站 上海
    N('sh', 30.6, 36.0, '十月，上海。二十岁的霍达尔，首盘六比一。',
      '首盘回合（29.88 切点之后）。上一句「…this is exquisite」30.48 结束，两档转写 30.5→49.7 无词。', label='sh'),
    Q('sh', 179.9, 198.28, [(181.26, 185.58, 'What a chase from Davidovich Fokina', '福基纳这次追球太惊人了，'),
                            (185.58, 191.46, 'to get his first break of the match.', '拿下了本场第一次破发。'),
                            (193.98, 198.22, 'The nuclear athleticism that is so often associated with this guy.', '这种爆发力，一直是他的招牌')],
      '第二盘回破：179.90 切点起，福基纳从底线追到网前倒地救球（davidovichfokina-jodar-shanghai-2026-final 第 8 段同一回合，句子与那条已审听包一致）。上一句「Oh, that is remarkable」175.96 说完；记分条 192.40、195.60 两次翻牌；段尾 198.28 收在源片 198.30 的切点前，下一句 213.24 才开始。'),
    N('sh', 384.74, 390.6, '抢七扳回第二盘，决胜盘五比四，他发球胜赛。',
      '决胜盘后段的回合（384.74 切点起；420s 记分条 5-4 福基纳发球）。事实：第二盘 7-6(5)。两档转写 383.98→402.50 无词。'),
    Q('sh', 433.78, 450.56, [(439.04, 440.32, 'Game, set, match.', '比赛结束。'),
                             (440.64, 443.88, 'Alejandro Davidovich Fokina', '亚历杭德罗·达维多维奇·福基纳，'),
                             (443.88, 450.48, 'claims a maiden Masters 1000 title in Shanghai.', '在上海夺得生涯首座大师赛冠军！')],
      '冠军点：433.78 霍达尔走回底线，436.54 切入最后一分，439.24 起福基纳张开双臂。句子与 davidovichfokina-jodar-shanghai-2026-final 已审听包一致（「Game, set, match」两档 Whisper 都没出，那条包按 YouTube 官方自动字幕记在 439.04）；medium.en 413–431.8 的「1, 2, 1」落在窗口之前。下一句 453.80 开始。',
      point_end_ok='冠军点 439.24 已经落地（福基纳张开双臂、霍达尔走向网前，缩略图墙 439–450 看过）；451.60 记分条那次「翻牌」是赛后转播把整场比分板刷新出来，不是这一分还没打完。'),
    Q('sh', 453.7, 460.6, [(453.80, 458.36, 'A week where he has proved his resilience.', '这一周，他证明了自己的坚韧。')],
      '颁奖：454.32 起福基纳在国旗前捧杯近景（454–462 抽帧看过）。small 453.80–458.28、medium 454.86–458.36；段首 453.7 在句前、跨一刀；下一句「He has worked his way…」460.68 开始，段尾 460.6 收在它之前。',
      point_end_ok='冠军点已经落地（缩略图墙看过），窗口里是赛后庆祝／颁奖镜头，画面上没有记分条；闸量到的「翻牌」是按猜的记分条框在赛后画面里的亮度变化，不是一分没打完。'),

    # ── 第 9 站 巴黎
    N('par', 37.6, 43.2, '最后一站，巴黎。阿卡在四分之一决赛，救下两个赛点。',
      '决赛首盘回合（26.24–50.80 同一镜头）。small 26.80–37.50 的「Hey!」是看台呼喊，在窗口之前；medium 43.32–44.72 有一声「oh」，窗口收在它之前；事实：alcaraz-shelton-paris-2026-final 已核（BBC：对弗里茨 6-7(10) 7-5 6-3，救两个赛点）。', label='par'),
    Q('par_r', 662.64, 682.0, [(672.58, 675.50, 'Carlos Alcaraz back from the brink.', '阿尔卡拉斯从悬崖边回来了。'),
                               (678.36, 681.38, "It's a heartbreaker for Taylor Fritz.", '对弗里茨来说，太让人心碎了。')],
      '1/4决赛对弗里茨的最后一分和赛后：662.64 切入最后一分，670.76 起阿尔卡拉斯张开双臂，674.24 弗里茨低头，678.40 网前握手。上一句 651.92 结束，下一句 683.46 开始。不挂右上字卡：这是 1/4决赛对弗里茨，不是决赛。'),
    N('par', 44.8, 50.7, '决赛对谢尔顿，首盘他救下六个破发点，抢七拿下。',
      '同一镜头。事实：alcaraz-shelton-paris-2026-final 已核（首盘六个破发点全部救下，7-6(5)）。'),
    Q('par', 428.84, 450.0, [(442.02, 449.90, 'Carlos Alcaraz wins the Rolex Paris Masters for the very first time in his career.', '阿尔卡拉斯第一次赢下巴黎大师赛。')],
      '冠军点：记分条第二盘 6-5 40-30 阿尔卡拉斯（432/436s 读过），428.84 切入最后一分，439.56 起他张开双臂，448.76 谢尔顿。上一句「…stunner from Carlos Alcaraz」428.60 结束。'),
    Q('par', 463.0, 472.9, [(464.54, 472.70, 'He sure is on fire, a third title in his last four tournaments for Carlos Alcaraz.', '状态火热，最近四站拿下三冠')],
      '颁奖：465.20 起阿尔卡拉斯在火花里捧杯、举杯近景（465–472.6 抽帧看过）。两档同一句 464.54–472.76；段首 463.0 在句前、跨一刀。'),

    # ── 收尾：印第安维尔斯颁奖后的烟花远景
    N('iw', 461.6, 469.3, '前五站一个人，后四站四个人。九站决赛，你心里最好看的是哪一场？',
      '收尾：印第安维尔斯颁奖后的烟花远景（461.5–469.3 同一镜头）。两档转写 458.12→475 无词。收在一问上。',
      point_end_ok='冠军点已经落地（缩略图墙看过），窗口里是赛后庆祝／颁奖镜头，画面上没有记分条；闸量到的「翻牌」是按猜的记分条框在赛后画面里的亮度变化，不是一分没打完。'),
]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def asr_paths(key):
    if key in NEW_ASR:
        stem = NEW_ASR[key]
        return {m: ASR_DIR / f'{stem}-{m}.json' for m in ('small.en', 'medium.en')}
    base = REPO / SOURCES[key][3]
    return {m: base / f'{m}.json' for m in ('small.en', 'medium.en')}


def raw_rel(key, model):
    if key in NEW_ASR:
        return f'data/evidence/{SLUG}/audio/raw/{key}-{NEW_ASR[key]}-{model}.json'
    return f'{SOURCES[key][3]}/{model}.json'


def speech(key, a, b):
    """窗口里两档转写说出来的东西，按词算（Whisper 常把相邻两句并成一段，按段算会误报切句）。

    返回 (model, 起, 止, 文本, 非人声认领)：同一段里落进窗口的那几个词并成一条，
    它们的起止就是这几个词的起止。词的中点在窗口里才算「在窗口里」。
    """
    out = []
    for model, p in asr_paths(key).items():
        d = json.loads(p.read_text())
        for s in d['segments']:
            if not (s['end'] > a and s['start'] < b):
                continue
            tag = NON_SPEECH.get((key, model, round(s['start'], 1)))
            words = [w for w in (s.get('words') or []) if a <= (w['s'] + w['e']) / 2 <= b]
            if s.get('words') and not words:
                continue
            if words:
                out.append((model, words[0]['s'], words[-1]['e'], ''.join(w['w'] for w in words).strip(), tag,
                            s['start'] < a - 0.05 and words[0]['s'] - s['start'] > 0.05,
                            s['end'] > b + 0.05))
            else:
                out.append((model, s['start'], s['end'], s['text'].strip(), tag, s['start'] < a, s['end'] > b))
    return out


def main():
    problems = []
    warnings = []
    sha_cache = {}
    for key, (fn, url, *_rest) in SOURCES.items():
        sha_cache[key] = sha(SRC_DIR / fn)
    EVID.joinpath('raw').mkdir(parents=True, exist_ok=True)
    EVID.joinpath('selected').mkdir(parents=True, exist_ok=True)
    ASSET.mkdir(parents=True, exist_ok=True)
    for key in NEW_ASR:
        for m, p in asr_paths(key).items():
            d = json.loads(p.read_text())
            assert d['source_sha256'] == sha_cache[key], (key, m, '转写不是这份 Release 字节')
            shutil.copyfile(p, REPO / raw_rel(key, m))

    labels = {}
    for st, info in STATIONS.items():
        label = {k: info[k] for k in ('topic', 'date', 'place', 'score', 'people')}
        label['result'] = {'winner': info['winner'], 'score': info['score'], 'source': info['source']}
        out = ASSET / f'label-{st}.png'
        render_label(label, out)
        labels[st] = (label, out.relative_to(REPO).as_posix())

    segments = []
    reviews = []
    now = datetime.now(timezone.utc).isoformat()
    for i, p in enumerate(PLAN):
        if 'card' in p:
            seg = {'title_card': p['card'], 'kicker': p['kicker'], 'seconds': p['seconds'], 'narration': p['narration'],
                   'voice': VOICE, '_why': p['why']}
            segments.append(seg)
            continue
        key, a, b = p['src'], p['a'], p['b']
        sp = speech(key, a, b)
        real = [x for x in sp if not x[4]]
        seg = {'source': key, 'start': a, 'end': b, 'cx': 0.5, 'track': False}
        utts = []
        if 'narration' in p and 'card' not in p:
            if real:
                problems.append(f'第{i}段 {key} {a}-{b} 旁白窗口里有英文：{real}')
            seg['narration'] = p['narration']
            seg['voice'] = VOICE
        elif 'utts' in p:
            seg['narration'] = ''
            seg['quote'] = [{'at': round(s - a, 2), 'end': round(e - a, 2), 'text': f'{en}\n{zh}'} for s, e, en, zh in p['utts']]
            seg['_quote_kind'] = p['kind']
            seg['crosses_cut'] = '同一场官方集锦自己的切镜（回合→球员近景→握手），没有拼接别的比赛、没有变速；原声句子跨镜头说完，所以按句子定窗口。'
            if p['kind'] == 'ceremony':
                seg['frame'] = 'court'
                seg['_frame_why'] = '颁奖台广播：冠军站在画面正中捧杯，转播画面本身就以冠军为中心（抽帧看过），没有人对镜头说话，按全局固定居中取景。'
            utts = [{'start': s, 'end': e, 'en': en, 'zh': zh} for s, e, en, zh in p['utts']]
            for s, e, *_ in p['utts']:
                if not (a <= s < e <= b):
                    problems.append(f'第{i}段 句子 {s}-{e} 不在窗口 {a}-{b} 内')
            for model, s, e, text, _, cut_l, cut_r in real:
                if cut_l or cut_r:
                    warnings.append(f'第{i}段 {model} 这一段转写跨出窗口（{"左" if cut_l else ""}{"右" if cut_r else ""}），窗口内的词是「{text}」——人工确认跨出去的是另一句')
                if not any(min(e, ue) - max(s, us) > 0 for us, ue, *_ in p['utts']):
                    problems.append(f'第{i}段 {model} {s}-{e}「{text}」没有对应字幕')
        else:
            seg['narration'] = ''
            if real:
                problems.append(f'第{i}段 现场声窗口里有英文：{real}')
        seg['_why'] = p['why']
        seg.update({k: v for k, v in p.items() if k.startswith('_') or k == 'point_end_ok'})
        if p.get('label'):
            label, img = labels[p['label']]
            seg['inset'] = {'image': img, 'kind': 'story_text', 'corner': 'tr', 'width': 0.6, 'pad': 0.043,
                            'show_after': 0, 'show_for': 8, 'motion': 'editorial', 'label': label}
            if p.get('carry'):
                seg['inset']['carry'] = p['carry']
        segments.append(seg)
        # 审听包
        rej = [{'model': m, 'start': s, 'end': e, 'text': t, 'why': w} for m, s, e, t, w, *_ in sp if w]
        reason = ''
        if not utts:
            reason = p.get('raw') or ('small.en 与 medium.en 两档转写在本窗口内都没有任何英文（旁白段，窗口按两档转写的空档取）。')
        pkt = {
            'schema': 'tennislive.foreground-transcript.v1',
            'source_url': SOURCES[key][1], 'official_source_url': SOURCES[key][2].split(' — ')[0],
            'source_sha256': sha_cache[key], 'source_bytes': (SRC_DIR / SOURCES[key][0]).stat().st_size,
            'method': 'asr_cross_checked',
            'reviewer': 'Claude（Claude Code 会话）：faster-whisper small.en 与 medium.en 两档逐句交叉核对＋逐段缩略图与记分条抽帧；未人工听音、不声称语气',
            'reviewed_at': now, 'status': 'complete', 'reviewed_from': a, 'reviewed_to': b,
            'selected_from': a, 'selected_to': b,
            'actual_listening_performed': False, 'human_listening_claimed': False, 'tone_verified': False,
            'uncertain_spans': [], 'foreground_english': utts, 'asr_rejected': rej,
            'raw_evidence': [{'path': raw_rel(key, m), 'sha256': sha(REPO / raw_rel(key, m)), 'model': m}
                             for m in ('small.en', 'medium.en')],
            'review_note': p['why'],
        }
        if reason:
            pkt['no_foreground_english_reason'] = reason
        path = EVID / 'selected' / f'segment-{i:02d}-{key}.json'
        path.write_text(json.dumps(pkt, ensure_ascii=False, indent=1) + '\n')
        reviews.append({'index': i, 'transcript_path': path.relative_to(REPO).as_posix(), 'transcript_sha256': sha(path)})

    print('\n'.join(warnings))
    if problems:
        print('\n'.join(problems))
        raise SystemExit(1)
    spec_path = REPO / 'specs/reels' / f'{SLUG}.json'
    spec = json.loads(spec_path.read_text()) if spec_path.exists() else {}
    spec['segments'] = segments
    order = list(SOURCES)  # 主源（第一个）是 25fps 的罗马，50fps 的几条认领 mixed_fps
    spec['sources'] = {k: SOURCES[k][1] for k in order}
    spec['_derived_sources'] = {k: v[2] for k, v in SOURCES.items()}
    spec['_no_probe_why'] = {k: {'why': '官方源片已下载到本地：逐秒缩略图墙、ffmpeg scene 切点、记分条裁切放大读比分、small.en/medium.en 两档转写定窗口（research/atp1000-champions-2026/build.py），不另跑 probe。',
                                 'width': v[4], 'height': v[5], 'fps': v[6]} for k, v in SOURCES.items()}
    spec['mixed_fps'] = {k: 'Tennis TV／赛事官方 1080p/50fps，主源为 25fps；统一按主源帧率输出，实拍画面与原声，不加速不减速。'
                         for k, v in SOURCES.items() if v[6] == '50/1'}
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n')
    review = {'schema': g.SCHEMA, 'slug': SLUG, 'plan_sha256': g.plan_hash(spec), 'reviewed_at': now,
              'method': 'asr_cross_checked', 'fresh_actual_asr_runs': True, 'human_listening_claimed': False,
              'actual_listening_performed': False, 'tone_verified': False,
              'note': '绑定当前 spec 与 Release 上的真实源片字节；small.en/medium.en 两档本地转写逐句交叉核对，不是人工听审证书。',
              'segments': reviews}
    (REPO / 'data/audio_reviews' / f'{SLUG}.json').write_text(json.dumps(review, ensure_ascii=False, indent=1) + '\n')
    total = sum(s.get('end', 0) - s.get('start', 0) + s.get('seconds', 0) for s in segments)
    print('segments', len(segments), 'seconds', round(total, 1), 'required cues', len(g.require(spec)))


if __name__ == '__main__':
    main()

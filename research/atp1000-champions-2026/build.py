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
    'iw': ('I1Uil8WUoew.mp4', f'{REL}/source-I1Uil8WUoew/I1Uil8WUoew.mp4',
           'https://www.youtube.com/watch?v=I1Uil8WUoew — BNP Paribas Open 赛事官方 YouTube《Sinner vs Medvedev | Match Highlights | Final》',
           'new', 1920, 1080, '50/1'),
    'mia': ('tennistv-4478518.mp4', f'{REL}/source-tennistv-4478518/tennistv-4478518.mp4',
            'https://www.tennistv.com/videos/4478518/miami-2026-final-lehecka-sinner-short-highlights — Tennis TV 官方免费短集锦',
            'new', 1920, 1080, '25/1'),
    'mc': ('tennistv-4486431.mp4', f'{REL}/source-tennistv-4486431/tennistv-4486431.mp4',
           'https://www.tennistv.com/videos/4486431/monte-carlo-2026-final-alcaraz-sinner-short-highlights — Tennis TV 官方免费短集锦',
           'new', 1920, 1080, '25/1'),
    'mc_t': ('tennistv-4486445.mp4', f'{REL}/source-tennistv-4486445/tennistv-4486445.mp4',
             'https://www.tennistv.com/videos/4486445 — Tennis TV 官方免费条目「check out the trophy lift here」（蒙特卡洛决赛捧杯）',
             'new', 1920, 1080, '25/1'),
    'mad': ('tennistv-4497782.mp4', f'{REL}/source-tennistv-4497782/tennistv-4497782.mp4',
            'https://www.tennistv.com/videos/4497782 — Tennis TV 官方免费短集锦（马德里决赛 辛纳 vs 兹维列夫，2026-05-03 16:21Z 上线，151 秒）',
            'new', 1920, 1080, '25/1'),
    'rome': ('tennistv-4504895.mp4', f'{REL}/source-tennistv-4504895/tennistv-4504895.mp4',
             'https://www.tennistv.com/videos/4504895/rome-2026-final-sinner-ruud-short-highlights — Tennis TV 官方免费短集锦',
             'new', 1920, 1080, '25/1'),
    'mtl': ('dvynMKs124E.mp4', f'{REL}/source-dvynMKs124E/dvynMKs124E.mp4',
            'https://www.youtube.com/watch?v=dvynMKs124E — Tennis TV 官方 YouTube《Ben Shelton vs Brandon Nakashima Title Battle | Montreal 2026 Final Highlights》',
            'new', 1920, 1080, '25/1'),
    'cin': ('5eniSK6BDZU.mp4', f'{REL}/source-5eniSK6BDZU/5eniSK6BDZU.mp4',
            'https://youtu.be/5eniSK6BDZU — Tennis TV 官方 YouTube《Arthur Fils vs Frances Tiafoe for Maiden Masters TITLE | Cincinnati 2026 Highlights》',
            'data/source_asr/5eniSK6BDZU', 1920, 1080, '25/1'),
    'sh': ('402fnpRkS3c.mp4', f'{REL}/source-402fnpRkS3c/402fnpRkS3c.mp4',
           'https://youtu.be/402fnpRkS3c — Tennis TV 官方 YouTube 上海决赛集锦（davidovichfokina-jodar-shanghai-2026-final 同一条源）',
           'data/source_asr/402fnpRkS3c', 1920, 1080, '50/1'),
    'par': ('tennistv-4606354.mp4', f'{REL}/source-tennistv-4606354/tennistv-4606354.mp4',
            'https://www.tennistv.com/videos/4606354/paris-2026-final-shelton-alcaraz-short-highlights — Tennis TV 官方免费短集锦',
            'data/source_asr/tennistv-4606354', 1920, 1080, '50/1'),
    'par_r': ('tennistv-4606098.mp4', f'{REL}/source-tennistv-4606098/tennistv-4606098.mp4',
              'https://www.tennistv.com/videos/4606098/road-to-final-paris — Tennis TV 官方「Road To Final」（alcaraz-shelton-paris-2026-final 同一条源）',
              'new', 1920, 1080, '50/1'),
}
NEW_ASR = {'iw': 'I1Uil8WUoew', 'mia': 'tennistv-4478518', 'mc': 'tennistv-4486431', 'mc_t': 'tennistv-4486445',
           'mad': 'tennistv-4497782', 'rome': 'tennistv-4504895', 'mtl': 'dvynMKs124E', 'par_r': 'tennistv-4606098'}

# 两档转写里不是人声的标注（Whisper 把欢呼写成文字）。只在这里显式认领，别处一律当人声。
NON_SPEECH = {('cin', 'small.en', 246.3): 'small.en 在 246.28–257.40 输出「Come on, man.」：首词置信 0.01、首尾两个词时长为 0、中间一个词被拉成 11 秒——Whisper 在现场声上的幻听；medium.en 在 241.16→259.34 之间无任何词，画面是底线相持、没有人对镜头说话。',
              ('par', 'small.en', 30.0): 'small.en 在 30.00–37.00 输出「Thank you.」：首词置信 0.003、第二个词被拉成 7 秒——Whisper 的典型幻听；medium.en 在 29.80→49.82 之间无任何词，画面是决赛首盘回合。',
('rome', 'small.en', 113.6): 'small.en 在 113.60–114.56 输出的是「CHEERING AND APPLAUSE」——这是 Whisper 对欢呼掌声的标注，不是人说的话；medium.en 同一处没有任何词。'}

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


def N(src, a, b, text, why, label=None, **kw):
    return dict(src=src, a=a, b=b, narration=text, why=why, label=label, **kw)


def Q(src, a, b, utts, why, kind='broadcast', label=None, **kw):
    return dict(src=src, a=a, b=b, utts=utts, why=why, kind=kind, label=label, **kw)


def R(src, a, b, why, reason, label=None, **kw):
    """现场声段：不配旁白、窗口里没有前景英文。"""
    return dict(src=src, a=a, b=b, raw=reason, why=why, label=label, **kw)


PLAN = [
    # ── 冷开场：罗马，辛纳张开双臂，解说宣告意大利五十年的等待结束
    Q('rome', 116.92, 127.6, [(118.02, 127.42, "Jannik Sinner ends Italy's 50-year wait for a champion in Rome.",
                               '辛纳终结意大利罗马50年冠军荒。')],
      '冷开场：罗马决赛冠军点落地后（116.92 切到庆祝近景），辛纳张开双臂；解说一句话交代这一冠的分量。整句 118.02–127.42 落在窗口内（两档转写一致），段尾 127.6。正文第 5 站放的是同一场的完整冠军点和赛后握手，不重复这一镜。',
      _ending_payoff_required=False,
      _head_open_why='这是九站盘点的片头预告，不是单场复盘的结局：罗马决赛的完整冠军点在正文第 5 站按时间顺序完整放一遍（106.20–116.92），片子的结局是巴黎。'),
    N('mc_t', 13.0, 18.5, '二〇二六赛季，九站ATP一千赛全部打完。',
      '蒙特卡洛颁奖：辛纳在摩纳哥王室成员旁举起奖杯（Tennis TV 官方 trophy lift 条目 13–18s）。这条源只有 0–1.46s 一句残句，窗口内两档转写都没有词。'),
    N('cin', 467.85, 472.55, '九站，只有五个冠军。',
      '辛辛那提颁奖台：菲斯举起奖杯（467–472s）。上一句「And Arthur, we\'d love to hear from you」在 467.78 结束，段首 467.85 不切句；472.6 之后是 Tennis TV 片尾板，段尾 472.55。'),
    N('mad', 66.8, 73.2, '辛纳一个人拿走五站，后四站，换了四个人。',
      '马德里决赛第二盘的回合（64.28–78.36 同一镜头）。两档转写 66.70→77.96 之间无词。'),

    # ── 第 1 站 印第安维尔斯
    N('iw', 54.2, 61.0, '三月，印第安维尔斯。辛纳对梅德韦德夫，两盘都打进抢七。',
      '记分条：首盘 7-6(6) 已定、第二盘 4-5（54–78s 读过）。两档转写 53.88→75.06 无词。', label='iw'),
    N('iw', 61.0, 67.6, '第二盘抢七，他零比四落后，然后连拿七分。',
      '事实：美联社与 Tennisnerd 都写「第二盘抢七 0-4 落后后连拿七分」。画面是第二盘 4-5 的回合（记分条读过），下一段就是冠军点。', label='iw', carry='mid'),
    Q('iw', 98.54, 113.35, [(103.98, 107.74, 'And California dreams come true for Jannik Sinner,', '加州梦成真，属于扬尼克·辛纳，'),
                            (107.74, 113.24, 'as he rises up to snatch glory as champion of Indian Wells.', '他登顶成为印第安维尔斯冠军。')],
      '冠军点：记分条抢七小分 6-4 辛纳（96.5/101s 读过），98.54 切入回合、103.9 落地切到辛纳近景，接着是梅德韦德夫的反应。解说整句 103.98–113.24（两档一致）完整落在窗口里，段尾 113.35，114.28 之后是握手。'),
    N('iw', 114.28, 119.4, '六站硬地大师赛，他全部集齐。',
      '网前握手（114.28 起，源片 119.49 结束）。事实：ATP 官网「joins Djokovic & Federer as only men to win all six Masters 1000 hard-court trophies」。窗口里两档转写无词。'),

    # ── 第 2 站 迈阿密
    N('mia', 51.9, 57.6, '两周后，迈阿密。决赛对手是莱赫奇卡。',
      '首盘 3-5 莱赫奇卡占先的回合（51.84 切点起）。两档转写 48.48→62.48 无词。', label='mia'),
    N('mia', 96.9, 103.6, '两次雨停，各等了一个半小时，他还是两个六比四。',
      '第二盘开局的回合（记分条 0-0，93–117s 读过）。事实：美联社写决赛遇到两次各 90 分钟的雨停（two 90-minute rain delays），奥林匹克官网写开赛推迟、第二盘又中断。两档转写 92.04→128.72 无词。'),
    N('mia', 118.40, 122.76, '一盘不丢的阳光双冠，男子第一人。',
      '赛点前辛纳走回底线、近景（118.40–122.76）。事实：维基「first man to win the Sunshine Double without dropping a set」，美联社同口径。'),
    Q('mia', 122.76, 141.5, [(128.72, 133.42, 'It is a Sinner Sunshine Double.', '这是属于辛纳的阳光双冠。'),
                             (134.94, 141.20, 'The Italian adds the Miami title to his Indian Wells trophy earlier this month.', '继印第安维尔斯之后，又拿下迈阿密。')],
      '冠军点：记分条第二盘 5-4 40-15 辛纳发球（123.5/129s 读过），122.76 切入、130.56 落地切到辛纳张开双臂，138.4 起网前握手。解说两句（small.en 128.72–133.42 / 134.94–141.16，medium.en 129.10–139.26 / 139.26–141.26）完整落在窗口里；147 之后是 Tennis TV 片尾，段尾 141.5。'),

    # ── 第 3 站 蒙特卡洛
    N('mc', 12.0, 17.2, '四月，蒙特卡洛。决赛遇上阿尔卡拉斯。',
      '首盘 3-3 的回合（记分条 9–45s 读过）。两档转写 11.80→26.78 无词。', label='mc'),
    N('mc', 47.7, 52.6, '首盘打进抢七，他七比五先拿下。',
      '首盘抢七进行中（记分条 6-6、小分 1-1，48–60s 读过）。两档转写 47.68→60.00 无词。', label='mc', carry='mid'),
    N('mc', 97.5, 104.2, '第二盘，阿尔卡拉斯一度三比一领先，辛纳随后连赢五局。',
      '第二盘 1-1 的回合（记分条 96–114s 读过）。事实：路透「rallied from 3-1 down in the second set」，奥林匹克官网「won the final five games」。两档转写 75.48→105.44 无词。'),
    Q('mc', 122.32, 135.0, [(128.86, 134.98, "It's Sinner that reigns supreme in Monte Carlo.", '蒙特卡洛，辛纳称王。')],
      '冠军点：记分条第二盘 5-3 40-15 辛纳发球（123/126.5s 读过），122.32 切入回合，127.36 起辛纳跪在红土上、俯拍。解说 medium.en 128.86–135.02 / small.en 129.06–135.00 同一句；之后两档对不上（medium「7-6, 7-3」、small「So it takes…」），所以段尾收在 135.02，不带下一句。'),
    N('mc_t', 18.6, 24.9, '第一个红土大师赛冠军，世界第一也拿了回来。',
      '蒙特卡洛颁奖：辛纳捧着奖杯（官方 trophy lift 条目 18.6–24.9s）。事实：ATP 与路透都写这一冠让他重回世界第一、是他第一个红土大师赛冠军。'),

    # ── 第 4 站 马德里
    N('mad', 27.3, 31.9, '五月，马德里，决赛对兹维列夫。',
      '第二盘开局（记分条 6-1、0-0，27–81s 读过）。两档转写 27.20→46.98 无词。', label='mad'),
    N('mad', 99.0, 103.7, '六比一，六比二，不到一个小时。',
      '第二盘 4-2 的回合（记分条 99–117s 读过）。事实：美联社、天空体育写 57 分钟，ATP 战报引辛纳的话是 58 分钟——两源差一分钟，所以只说「不到一个小时」。两档转写 98.16→114.66 无词。', label='mad', carry='mid'),
    N('mad', 103.7, 108.4, '大师赛五连冠，男子网球史上第一人。',
      '同一镜头的下一分。事实：ATP「the first man to win five consecutive ATP Masters 1000 titles」（2025 巴黎＋2026 印第安维尔斯、迈阿密、蒙特卡洛、马德里），美联社同口径。'),
    Q('mad', 122.64, 137.05, [(133.46, 137.04, 'Jannik Sinner rewrites the history books.', '辛纳改写了历史。')],
      '冠军点：记分条第二盘 5-2 40-0 辛纳发球（124/129.5s 读过），122.64 切入、130.84 起辛纳在花墙前微笑。解说 small.en「Yannick Sinner rewrites the history books」133.54–137.06、medium.en 133.46–137.00；small.en 之后 137.06 起有半句（medium 没有），所以段尾收在 137.05 之前那一刻。'),

    # ── 第 5 站 罗马
    N('rome', 36.7, 42.0, '然后是罗马，决赛对鲁德，又是两个六比四。',
      '第二盘 2-0 的回合（记分条 36–57s 读过）。两档转写 34.80→52.00 无词。', label='rome'),
    N('rome', 73.2, 80.6, '这一冠，让他集齐全部九站大师赛，此前只有德约科维奇做到过。',
      '第二盘 3-2 的回合（记分条 75–99s 读过）。事实：美联社、路透都写他成为继德约科维奇之后第二位集齐九站大师赛冠军的男子球员。两档转写 73.10→97.76 无词。', label='rome', carry='mid'),
    R('rome', 106.20, 116.92,
      '冠军点：记分条第二盘 5-4 40-0 辛纳发球（107/115.5s 读过），106.20 切入回合、116.92 切到庆祝（冷开场已经放过那一镜）。',
      '两档转写在这个窗口里都没有人声：small.en 113.60–114.56 是 Whisper 写出来的「CHEERING AND APPLAUSE」标注，medium.en 同一处无词。',
      _quote_skip_why='冠军点这一分解说没开口（两档转写都没有词，只有现场欢呼）；整句解说在冷开场那一镜（118.02 起）。'),
    Q('rome', 129.44, 138.35, [(134.28, 137.90, 'He claims his first title here at the Foro Italico.', '这是他在罗马的第一个冠军。')],
      '赛后：辛纳近景、和鲁德在网前拥抱（129.44–138.35）。解说 medium.en 134.28–138.00、small.en 134.36–137.80（「Four Intellico」即 Foro Italico）。段尾 138.35，138.4 之后是 Tennis TV 片尾。'),

    # ── 转折：后四站辛纳缺席
    N('mc', 82.80, 88.84, '可罗马之后，后四站大师赛，他一站都没能出场。',
      '辛纳近景（蒙特卡洛决赛 82.80–88.84 同一镜头）。事实：ATP 官网 7/24 加拿大退赛、8/9 辛辛那提因伤退赛、10/6 宣布伤缺赛季剩余赛事（维基 2026 Jannik Sinner tennis season 汇总）。两档转写 75.48→105.44 无词。'),

    # ── 第 6 站 蒙特利尔
    N('mtl', 107.84, 113.0, '八月，蒙特利尔，谢尔顿卫冕加拿大大师赛。',
      '首盘回合（107.84 切点起）。事实：Tennis TV「reigning champion Ben Shelton」、ATP 采访「win the ATP Masters 1000 Canada in back-to-back years」（2025 多伦多、2026 蒙特利尔）。两档转写 106.6→121.2 无词。', label='mtl'),
    N('mtl', 145.76, 151.2, '决赛两盘，中岛布兰登一个破发点都没拿到。',
      '首盘回合（145.76 切点起）。事实沿用 shelton-nakashima-montreal-final 已核过的 flashscore 技术统计（中岛破发点 0）。两档转写 143.5→152.4 无词。', label='mtl', carry='mid'),
    N('mtl', 406.68, 412.28, '抢七，六比三，谢尔顿拿到三个赛点。',
      '第二盘抢七，这一分打完记分条小分 6-3（413s 读过）。两档转写 392.1→420.7 无词。'),
    Q('mtl', 414.00, 436.0, [(420.72, 422.06, 'Oh!', '噢！'),
                             (422.08, 423.08, 'Here we go.', '来了。'),
                             (427.08, 434.74, 'Ben Shelton delivers a masterful performance in Montreal that will yield the most glittering of prizes.',
                              '谢尔顿打出大师级表现，捧走大奖。')],
      '冠军点：414.00–427.08 是同一个远景镜头，先是中岛救下第一个赛点（小分 6-4，423.5s 读过），再是最后一分；427.08 切到谢尔顿庆祝。两档转写：medium.en 420.72–422.12「Oh」、small.en 422.08–423.08「Here we go」（两档各记到一个短感叹，都保留并配字幕），整句 427.08–434.74（small.en 断成四截、medium.en 并进下一句，取 small.en 的句末 434.74）。段尾 436.0，下一句「The chase is complete」445.78 才开始。'),

    # ── 第 7 站 辛辛那提
    N('cin', 246.5, 251.2, '十天后，辛辛那提，菲斯对蒂亚福。',
      '首盘结束后的回合（246.36–258.24 同一镜头）。两档转写 246.36→259.34 无词。', label='cin'),
    N('cin', 273.5, 279.2, '次盘一比六输掉，决胜盘他六比零拿回来。',
      '第二盘尾段的回合（272.72–292.76 同一镜头，296 起解说才宣布进入决胜盘）。上一声「Oh」273.42 结束，两档转写 273.42→291.70 无词。', label='cin', carry='mid'),
    N('cin', 372.08, 376.6, '决胜盘，蒂亚福一局都没拿到。',
      '决胜盘破发之后的回合（372.08 切点起）。两档转写 370.34→384.80 无词。'),
    Q('cin', 416.80, 439.08, [(425.12, 430.26, 'Arthur Fils, quite scintillating in Cincinnati.', '菲斯，在辛辛那提光芒四射。'),
                              (434.78, 438.10, 'It is the biggest title of his young career.', '这是他年轻生涯里最大的冠军。')],
      '冠军点：416.80 切入最后一分的远景，425.40 起菲斯走向看台庆祝（fils-tiafoe 那条已核过：决胜盘第六局第三个赛点）。上一句「…a game away from the biggest title of his career」在 416.02 结束。medium.en「After a piece, quite scintillating, it\'s Scintillati」、small.en「heart of peace. Quite scintillating in Scintillati」——两档都把「Arthur Fils」「in Cincinnati」听走了音，按人名和地名还原；第二句两档一致。段尾 439.08 切到握手前。'),
    Q('cin', 449.64, 457.5, [(449.70, 452.78, 'Ladies and gentlemen, your champion, Mr. Arthur Fils.', '女士们先生们，冠军是阿瑟·菲斯！')],
      '颁奖：主持人宣布冠军（449.64 切镜）。下一句 457.66 开始，段尾 457.5。', kind='ceremony'),

    # ── 第 8 站 上海
    N('sh', 30.6, 36.0, '十月，上海。二十岁的霍达尔，首盘六比一。',
      '首盘回合（29.88 切点起）。两档转写 30.5→49.7 无词。', label='sh'),
    N('sh', 128.7, 134.26, '落后一盘，第二盘又被破发，福基纳还在追。',
      '第二盘开局（首盘「Six games to one」在 126.7 说完）。两档转写 128.7→142.5 无词。', label='sh', carry='mid'),
    Q('sh', 179.9, 198.28, [(181.26, 185.58, 'What a chase from Davidovich Fokina', '福基纳这次追球太惊人了，'),
                            (185.58, 191.46, 'to get his first break of the match.', '拿下了本场第一次破发。'),
                            (193.98, 198.22, 'The nuclear athleticism that is so often associated with this guy.', '这种惊人的爆发力，一直是他的招牌。')],
      '第二盘回破：179.90 切点起，福基纳从底线追到网前倒地救球（davidovichfokina-jodar-shanghai-2026-final 第 8 段同一回合，句子与那条已审听包一致：181.26–191.46）。上一句「Oh, that is remarkable」175.96 说完；small.en 把「the match」两个词的时长拉到 205.94，medium.en 句末是 191.46。记分条 192.40、195.60 两次翻牌（破发、局分），第三句 193.98–198.22（medium.en；small.en 并在前一段里）也一并保留，段尾 198.28 收在源片 198.30 的切点前，下一句 213.24 才开始。'),
    N('sh', 384.74, 390.6, '第二盘抢七，他七比五拿下；决胜盘五比四，他发球胜赛。',
      '决胜盘后段的回合（384.74 切点起；420s 记分条 5-4 福基纳发球）。两档转写 383.98→402.50 无词。'),
    Q('sh', 433.78, 450.56, [(439.04, 440.32, 'Game, set, match.', '比赛结束。'),
                             (440.64, 443.88, 'Alejandro Davidovich Fokina', '亚历杭德罗·达维多维奇·福基纳，'),
                             (443.88, 450.48, 'claims a maiden Masters 1000 title in Shanghai.', '在上海夺得生涯首座大师赛冠军！')],
      '冠军点：433.78 霍达尔走回底线，436.54 切入最后一分，439.24 起福基纳张开双臂。句子与 davidovichfokina-jodar-shanghai-2026-final 已审听包一致（「Game, set, match」两档 Whisper 都没出，那条包按 YouTube 官方自动字幕记在 439.04）；medium.en 413–431.8 的「1, 2, 1」是 Whisper 对现场呼喊的幻听，落在窗口之前。段尾 450.56，下一句 454.5 开始。',
      point_end_ok='冠军点 439.24 已经落地（福基纳张开双臂、霍达尔走向网前，缩略图墙 439–450 看过）；451.60 记分条那次「翻牌」是赛后转播把整场比分板刷新出来，不是这一分还没打完。'),

    # ── 第 9 站 巴黎
    N('par', 29.8, 36.6, '最后一站，巴黎。阿尔卡拉斯在四分之一决赛，救下两个赛点。',
      '决赛首盘回合（29.56–48.94 同一镜头）。事实：alcaraz-shelton-paris-2026-final 已核（BBC：对弗里茨 6-7(10) 7-5 6-3，救两个赛点）。两档转写 29.80→49.82 无词。', label='par'),
    Q('par_r', 662.64, 682.0, [(672.58, 675.50, 'Carlos Alcaraz back from the brink.', '阿尔卡拉斯从悬崖边回来了。'),
                              (678.36, 681.38, "It's a heartbreaker for Taylor Fritz.", '对弗里茨来说，太让人心碎了。')],
      '1/4决赛对弗里茨的最后一分和赛后：662.64 切入最后一分，670.76 起阿尔卡拉斯张开双臂，674.24 弗里茨低头，678.40 网前握手（alcaraz-shelton-paris-2026-final 的 qf 段从 653 起，这里从最后一分起）。两档转写：上一句 651.92 结束，两句 672.58–675.50 / 678.36–681.38 一致，下一句 683.46 开始。'),
    N('par', 51.9, 57.6, '决赛对谢尔顿，首盘抢七拿下，第二盘七比五。',
      '决赛回合（51.82 切点起）。两档转写 51.22→63.82 无词。', label='par', carry='mid'),
    N('par', 91.6, 97.9, '首盘他救下六个破发点，第二盘二比四落后，又追了回来。',
      '第二盘回合（87.76–113.12 同一镜头）。事实沿用 alcaraz-shelton-paris-2026-final 已核口径。两档转写 91.50→112.40 无词。'),
    Q('par', 118.75, 143.0, [(135.38, 139.40, 'Carlos Alcaraz wins the Rolex Paris Masters', '阿尔卡拉斯赢下巴黎大师赛，'),
                            (139.40, 142.88, 'for the very first time in his career.', '这是他生涯第一次。')],
      '冠军点：记分条第二盘 6-5 40-30 阿尔卡拉斯（121/131s 读过），120 切入回合、132.68 起他张开双臂。上一句「…a magnificent point from both」118.64 结束，段首 118.7。解说整句 135.38–142.88（两档一致）。'),
    N('par', 143.0, 149.55, '九站，五个冠军。前五站都是辛纳，后四站，四个不同的人。',
      '阿尔卡拉斯走向球网、和谢尔顿拥抱（141.88–150.52 同一镜头），149.7 之后画面开始暗下去、150.52 之后是 Tennis TV 片尾，段尾 149.55。两档转写 142.88→152.78（「CHEERING」标注）之间无词。'),
    N('mia', 141.6, 146.8, '九站决赛，你心里最好看的是哪一场？',
      '收在一问：迈阿密决赛后辛纳和莱赫奇卡网前拥抱（138.4–147.0 同一镜头）。解说 141.26 说完；147 之后是 Tennis TV 片尾。'),
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
        key, a, b = p['src'], p['a'], p['b']
        sp = speech(key, a, b)
        real = [x for x in sp if not x[4]]
        seg = {'source': key, 'start': a, 'end': b, 'cx': 0.5, 'track': False}
        utts = []
        if 'narration' in p:
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
                seg['_frame_why'] = '颁奖台广播：画面是颁奖台的固定机位全景（菲斯和颁奖嘉宾都在居中 3:4 窗口里，449.64–457.5 抽帧看过），没有人对镜头说话，按全局固定居中取景。'
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
    order = ['rome'] + [k for k in SOURCES if k != 'rome']  # 主源（第一个）是 25fps 的罗马，50fps 的几条认领 mixed_fps
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
    total = sum(s['end'] - s['start'] for s in segments)
    print('segments', len(segments), 'seconds', round(total, 1), 'required cues', len(g.require(spec)))


if __name__ == '__main__':
    main()

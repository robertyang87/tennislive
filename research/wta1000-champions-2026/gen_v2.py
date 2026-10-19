"""wta1000-champions-2026 第二版（2026-10-19，账号所有者「2 要」）：

- 补四站捧杯：迪拜（WTA 官方图 Pegula-trophy-Jimmie）、马德里（同一条官方颁奖源 15.12–18.04 的亲吻奖杯近景）、
  北京、武汉（WTA 官方 Shorts 派生，账号所有者「1 可以用」批准 720p 源）
- 武汉旁白「最后连赢五局」→「决胜盘连下最后四局」（官方逐局：决胜盘 2-2 之后连下四局）
- 结尾只留一个问题

从 main 上已发布的那版 spec 改，原有窗口的审听包原样保留、只重新编号；新窗口另写审听包。
用法：python3 research/wta1000-champions-2026/gen_v2.py <已发布版 spec 路径>
"""
import copy, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, 'tools')
import foreground_audio_gate as g

SLUG = 'wta1000-champions-2026'
SPEC = Path(f'specs/reels/{SLUG}.json')
REL = 'https://github.com/robertyang87/tennislive/releases/download'
SRC = {  # 新加的派生源：本地字节，用来写 source_sha256
    'wh_tr': ('/tmp/claude-0/dy/d/wuhan_trophy_lift.mp4', f'{REL}/source-wta1000-2026-wuhan-trophy-lift/wuhan_trophy_lift.mp4'),
    'bj_tr': ('/tmp/claude-0/dy/d/bj_trophy.mp4', f'{REL}/source-wta1000-2026-bj-trophy/bj_trophy.mp4'),
    'madrid_k': ('/tmp/claude-0/dy/d/madrid_kiss.mp4', f'{REL}/source-wta1000-2026-madrid-kiss/madrid_kiss.mp4'),
    'wuhan': ('/tmp/claude-0/cw/src/HIvIvgwXkqs.mp4', None),
}
VOICE = {"pitch": "+10Hz", "_why": "网球有故事沿用云见 +18% 语速、+10Hz 音高。语速走 --rate +18%，音高逐段写在这里。"}
REV = "Claude（Claude Code 会话）：faster-whisper small.en 与 medium.en 两档逐词转写交叉核对，并对照本地抽帧；未人工听音"


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()



# 第二版旁白断句（2026-10-20，抖音评论「AI 配音重音不对、停顿也不对」）：
# 每段单独合成，句子在段界被拦腰切开（「上一个做到的，｜是…」「连胜莱巴金娜、｜斯瓦泰克、高芙」）语调就会断；
# 顿号几乎不停，连分句、连比分都会一口气冲过去。改成每段收在一个能独立成立的句子或子句上、分句一律逗号。
RETEXT = {
    '罗马，斯维托丽娜上一次在这里夺冠，还是二〇一八年。': '罗马，斯维托丽娜上次在这儿夺冠，还是二〇一八年。',
    '二〇二六赛季WTA1000全部收官。': '二〇二六赛季，WTA一千赛全部收官。',
    '救冠军点、外卡逆袭、首冠就是千分赛，一站一站看。': '救冠军点，外卡逆袭，首冠就是千分赛。一站一站看。',
    '二月多哈。穆霍娃的上一个冠军，还是二〇一九年，': '二月，多哈。穆霍娃上一次夺冠，还是二〇一九年。',
    '中间输掉了四场决赛。这一次，半决赛先丢一盘逆转萨卡里，': '之后输掉了四场决赛。这一次，她半决赛先丢一盘，逆转萨卡里。',
    '决赛六比四、七比五，击败十九岁的姆博科。': '决赛六比四，七比五，击败十九岁的姆博科。',
    '半决赛先丢一盘、又被破发，硬是逆转阿尼西莫娃；': '半决赛先丢一盘，又被破发，硬是逆转了阿尼西莫娃。',
    '决赛六比二、六比四，直落两盘击败斯维托丽娜。': '决赛六比二，六比四，直落两盘击败斯维托丽娜。',
    '三月印第安维尔斯。萨巴伦卡在这里两进决赛都输了，': '三月，印第安维尔斯。萨巴伦卡在这里两进决赛，都输了。',
    '半决赛世界第一对第二，直落两盘赢莱巴金娜；': '半决赛世界第一对第二，直落两盘赢了莱巴金娜。',
    '阳光双冠，史上第五人，上一个做到的，': '阳光双冠，史上第五人。上一位是斯瓦泰克，',
    '是二〇二二年的斯瓦泰克。': '那是二〇二二年。',
    '红土季，马德里。二十六号种子科斯秋克，': '红土季，马德里。科斯秋克只是二十六号种子。',
    '一路掀翻佩古拉和诺斯科娃。决赛对安德列娃，第二盘四比五落后，': '她一路掀翻佩古拉和诺斯科娃。决赛对安德列娃，第二盘四比五落后，',
    '八年后，三十一岁的她，一周连胜莱巴金娜、': '八年后，三十一岁的她，一周连胜三位前五：',
    '斯瓦泰克、高芙三位前五，决赛三盘鏖战两小时四十九分钟。': '莱巴金娜，斯瓦泰克，高芙。决赛三盘，鏖战两小时四十九分钟。',
    '第一位赢得中网WTA1000的中国女子球员，': '中网一千赛，她是第一位中国女单冠军，',
    '击败斯瓦泰克；决赛先丢一盘，第二盘又零比二落后，': '击败了斯瓦泰克。决赛先丢一盘，第二盘又零比二落后，',
    '生涯第一冠，就是WTA1000。二〇〇九年以来，只有大坂直美、': '生涯首冠就是千分赛，二〇〇九年以来只有三人做到：',
    '安德莱斯库和姆博科做到过。': '大坂直美、安德莱斯库、姆博科。',
    '萨巴伦卡两冠最稳，可九个不同的冠军说明，': '萨巴伦卡两冠，最稳。',
    '今年没有谁能一手遮天。年终总决赛，谁会笑到最后？': '可九个不同的冠军说明，今年没有谁能一手遮天。',
}

old = json.load(open(sys.argv[1]))
spec = copy.deepcopy(old)
segs = old['segments']
assert segs[62]['narration'] == '最后连赢五局。'
assert segs[68]['narration'].startswith('今年没有谁能一手遮天') and sum(x.get('narration') in RETEXT for x in segs) == len(RETEXT) and segs[69]['narration'].startswith('你心里最燃')

skip = "这几秒解说没开口；源片音轨是现场音乐／颁奖台广播，本段 `mute: true` 不出原声，靠前后段的现场声接住。"
new = {
    'dubai': {"image": "assets/reel/wta1000-2026/dubai-trophy.jpg", "image_kind": "photo", "seconds": 2.6,
              "narration": "这一次，奖杯是她的。", "voice": VOICE,
              "_why": "迪拜站捧杯：WTA 官方图库（文件名 Pegula-trophy-Jimmie.jpg，2026-02-22 发布，标题「Jessica Pegula, Dubai 2026」），佩古拉抱着迪拜冠军奖杯。原图 4700×3177（取 ?width=4000 的 4000×2704），按画布 3:4 预裁 2028×2704，人居中。",
              "_photo_source": "https://photoresources.wtatennis.com/photo-resources/2026/02/22/2c68af62-120d-417d-a889-2844379a288a/Pegula-trophy-Jimmie.jpg",
              "_photo_caption_safety": "旁白字幕压在下部奖杯底座一带，脸在画面上部 15%–35%，不压脸。"},
    'madrid': {"source": "madrid_k", "start": 0.08, "end": 2.88, "cx": 0.5, "track": False, "narration": "", "mute": True,
               "_why": "马德里站捧杯：赛事官方颁奖源（冷开场那条 madrid_t）15.12–18.04 这一镜派生，科斯秋克亲吻奖杯近景；人在画面右侧，居中的 3:4 会切掉脸，所以派生时取 x=900 的窗口置中。冷开场用的是 8.5–12.08 的举杯，不重复。",
               "_quote_skip_why": "颁奖台广播在讲话（两档转写对不上，像是把西语当英语转错了），译不出可靠的字幕，这一段静音不出原声。"},
    'bj1': {"source": "bj_tr", "start": 0.0, "end": 4.05, "cx": 0.5, "track": False, "narration": "", "mute": True,
            "_why": "北京站捧杯：WTA 官方 Shorts dDxlsgH6UJg 9.80–13.90 派生，郑钦文坐在场上抱着奖杯。720×1280 源，账号所有者 2026-10-19「1 可以用」批准。",
            "_quote_skip_why": "源片音轨是 WTA 短片的背景歌曲（转写出来是歌词），没有解说；mute: true。"},
    'bj2': {"source": "bj_tr", "start": 4.15, "end": 7.1, "cx": 0.5, "track": False, "narration": "", "mute": True,
            "_why": "北京站捧杯：同一条 WTA 官方 Shorts 16.45–19.50 派生，郑钦文在网前举着奖杯。",
            "_quote_skip_why": "源片音轨是背景歌曲，没有解说；mute: true。"},
    'wh1': {"source": "wh_tr", "start": 0.05, "end": 3.45, "cx": 0.5, "track": False, "narration": "", "mute": True,
            "_why": "武汉站捧杯：WTA 官方 Shorts C87Ikp6xUN4 8.10–15.80 派生，赫瓦林斯卡在彩带里双手把奖杯举过头顶。720×1280 源，账号所有者 2026-10-19「1 可以用」批准。",
            "_quote_skip_why": "源片音轨是背景歌曲（转写出来是歌词），没有解说；mute: true。"},
    'wh2': {"source": "wh_tr", "start": 3.55, "end": 7.65, "cx": 0.5, "track": False, "narration": "", "mute": True,
            "_why": "武汉站捧杯：同一条派生源第二镜，她抱着奖杯比 V 字。",
            "_quote_skip_why": "源片音轨是背景歌曲，没有解说；mute: true。"},
}

out = []
origin = []  # 每个新段从哪一个老段来（None＝新加）
for i, s in enumerate(segs):
    s = copy.deepcopy(s)
    if i == 62:
        s['narration'] = '决胜盘连下最后四局。'
        s['_why'] = ('官方逐局：决胜盘 2-2 之后赫瓦林斯卡连下最后四局（与 chwalinska-story-2026 第 37 段同一口径）。'
                     '第一版写的「最后连赢五局」与官方逐局不符，第二版改正。'
                     '新句比原窗口长，段尾从 180.48 延到 181.2（178.36 之后到 184 没有切点，两档转写 177.2–192 无词），所以这一段重新审听。')
        s['end'] = 181.2
    if i == 69:
        s['narration'] = '十站决赛，你心里最好看的是哪一场？'
        s['_why'] = '结尾只留一个问题（第二版：原来两问「年终总决赛谁会笑到最后／你心里最燃的是哪一冠」并成一个好答的单选）。'
    if s.get('narration') in RETEXT:
        s['narration'] = RETEXT[s['narration']]
    out.append(s); origin.append(None if i == 62 else i)
    after = {13: ['dubai'], 33: ['madrid'], 58: ['bj1', 'bj2'], 65: ['wh1', 'wh2']}.get(i, [])
    for k in after:
        out.append(copy.deepcopy(new[k])); origin.append(None)
spec['segments'] = out
spec['sources']['wh_tr'] = SRC['wh_tr'][1]
spec['sources']['bj_tr'] = SRC['bj_tr'][1]
spec['sources']['madrid_k'] = SRC['madrid_k'][1]
ds = spec.setdefault('_derived_sources', {})
ds['wh_tr'] = 'https://www.youtube.com/shorts/C87Ikp6xUN4 — WTA 官方 Shorts 8.10–15.80s，720×1280 取 y=176 的 720×960，放大到 810×1080 置于 1920×1080 中央，30→25fps'
ds['madrid_k'] = 'madrid_t（https://www.youtube.com/watch?v=Obv_j6l33nQ 894.0–919.5s）再取 15.12–18.04s，x=900 起 810×1080 原尺寸置于 1920×1080 中央，25fps'
ds['bj_tr'] = 'https://www.youtube.com/shorts/dDxlsgH6UJg — WTA 官方 Shorts 9.80–13.90s（y=160）＋16.45–19.50s（y=300），各取 720×960 放大到 810×1080 置于 1920×1080 中央、接成一条，30→25fps'
spec['_v2_why'] = ('第二版（2026-10-19）：账号所有者看过同题抖音（体坛叙说）后要求补捧杯镜头；补迪拜、马德里、北京、武汉四站捧杯，'
                   '改正武汉「最后连赢五局」→「决胜盘连下最后四局」，结尾两问并成一问。北京、武汉的 WTA 官方 Shorts 为 720×1280，'
                   '账号所有者 2026-10-19 回复「1 可以用」。')
SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + '\n')

# 审听索引：老段原样复用，新段写新包
import subprocess
idx_old = json.loads(subprocess.run(['git', 'show', 'origin/main:data/audio_reviews/wta1000-champions-2026.json'],
                                    capture_output=True, check=True).stdout)  # 已发布那版的索引，重跑幂等
by_old = {e['index']: e for e in idx_old['segments']}
entries = []
now = datetime.now(timezone.utc).isoformat()
d = Path(f'data/evidence/{SLUG}/audio/selected')
for ni, (s, oi) in enumerate(zip(out, origin)):
    if 'start' not in s or s.get('image'):
        continue
    if oi is not None:
        e = dict(by_old[oi]); e['index'] = ni; entries.append(e); continue
    k = s['source']
    local, url = SRC[k]
    url = url or spec['sources'][k]
    asr = {'wh_tr': 'data/source_asr/C87Ikp6xUN4/（原片 8.10–15.80s 对应派生 0–7.70s）',
           'bj_tr': 'data/source_asr/dDxlsgH6UJg/（原片 9.80–13.90 / 16.45–19.50s 对应派生 0–4.10 / 4.10–7.15s）',
           'madrid_k': 'data/evidence/wta1000-champions-2026/audio/raw/madrid_t-der-madrid_trophy-{small,medium}.en.json（madrid_t 15.12–18.04s 对应派生 0–2.92s）',
           'wuhan': 'data/source_asr/HIvIvgwXkqs/small.en.json + medium.en.json'}[k]
    reason = {'wh_tr': '源片音轨是 WTA 短片的背景歌曲：small.en 转出的是连续歌词（Thank you for sunshine… It\'s a beautiful day），medium.en 只标出 🎶 Music；没有解说、采访或球员人声。本段 mute: true，不出原声。',
              'bj_tr': '源片音轨是 WTA 短片的背景音乐：small/medium 两档在这两段窗口里都没有转出任何词（只在片尾 26s 之后有「Thanks for watching」类误转）；没有解说或人声。本段 mute: true，不出原声。',
              'madrid_k': '颁奖台广播在 madrid_t 12–25s 讲话，small.en 与 medium.en 在对应的 15.2–18.0s 转出的词互不相同（「…that Marta will be」对「…which is called the Cielo de Madrid」），判断为西语广播被误转成英语，译不出可靠字幕；本段 mute: true，不出原声。',
              'wuhan': '官方武汉决赛集锦，178.5–181.2s：small.en 与 medium.en 两档在 177.2s（「…of the Wuhan Open.」）之后到 192s 都没有转出任何词，这个窗口没有前景英文；本段是中文旁白。'}[k]
    pkt = {"source_url": url, "source_sha256": sha(local), "method": "asr_cross_checked", "reviewed_at": now, "reviewer": REV,
           "reviewed_from": s['start'], "reviewed_to": s['end'], "status": "complete", "uncertain_spans": [],
           "foreground_english": [], "no_foreground_english_reason": reason, "asr_evidence": asr, "review_note": s['_why']}
    p = d / f'v2-segment-{ni:02d}-{k}.json'
    p.write_text(json.dumps(pkt, ensure_ascii=False, indent=1) + '\n')
    entries.append({"index": ni, "transcript_path": p.as_posix(), "transcript_sha256": sha(p)})
idx = dict(idx_old); idx['segments'] = entries; idx['plan_sha256'] = g.plan_hash(spec)
idx['note'] = idx_old.get('note', '') + ' 第二版（2026-10-19）：原有窗口沿用原审听包、只重新编号；新增捧杯窗口的审听包见 v2-segment-*.json（Claude 会话写）。'
Path('data/audio_reviews/wta1000-champions-2026.json').write_text(json.dumps(idx, ensure_ascii=False, indent=1) + '\n')
print('segments', len(out), 'required cues', len(g.require(spec)))

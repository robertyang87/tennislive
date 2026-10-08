"""Generate specs/reels/year-end-no1-zverev-2026.json from the locked plan."""
import json, sys
sys.path.insert(0, "/workspace/video-review/yen1")
from utter import U

SLUG = "year-end-no1-zverev-2026"
A = f"assets/reel/{SLUG}"
Y = "/workspace/video-review/yen1"

SRC = {  # key: (url, local id, w, h, fps, dur, sha)
 "rg": ("https://www.youtube.com/watch?v=WfxpIK_TvEQ", "WfxpIK_TvEQ", 1920, 1080, "50/1", 727.457959, "04e0eb86a3df06c5cc98baa8df0e383a5e1f7ec7962dca2dd611ef4b898f7755"),
 "news": ("https://www.tennistv.com/videos/4587386/shanghai-2026-zverev-preview-interview", "ttv4587386", 1920, 1080, "30000/1001", 178.024067, "12dc8f7d1fd50f14019c6fb2eaf990397e8a9d3e271d5faf7c14c97d76c83f8f"),
 "ao": ("https://www.youtube.com/watch?v=u8plp_Kb6Ss", "u8plp_Kb6Ss", 1920, 1080, "25/1", 272.323628, "03d08cd080e523ef2fc85c3a0109cedfa55752bf4f277b0ede2205a27af85341"),
 "mc": ("https://www.youtube.com/watch?v=OYoIP6aY8VQ", "OYoIP6aY8VQ", 1920, 1080, "25/1", 728.665397, "2c40ca7b8ff59da480df8f52139ce226813d64943b7264d003ac88e6092cb0ee"),
 "wim": ("https://www.youtube.com/watch?v=cuvaPZT2AIU", "cuvaPZT2AIU", 1920, 1080, "25/1", 540.978503, "e5d94ebf528e1192dde3ddf98acae5e09bc05f7d4d2a74dd6fefaa90f900409b"),
 "uso": ("https://www.youtube.com/watch?v=b40hO04eyLo", "b40hO04eyLo", 1920, 1080, "60000/1001", 303.275828, "dd9a41791f99eb9a20f8e54ffa311432a957f5fd9377399c975e4a56c924a534"),
 "speech": ("https://www.youtube.com/watch?v=Pc7pQQvkAzU", "Pc7pQQvkAzU", 1920, 1080, "60000/1001", 426.411247, "e22de290b5138ba449be45c89a2d96508e523b67808bf4499c96181cd06b760b"),
 "bj": ("https://www.youtube.com/watch?v=cjaHThpISKk", "cjaHThpISKk", 1920, 1080, "50/1", 319.181497, "2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2"),
 "nastase": ("https://www.youtube.com/watch?v=nxzZHc672-Y", "nxzZHc672-Y", 1920, 1080, "60/1", 756.088163, "b84921902fc78a134e8940fef61835e0ce6d6814f17e482779629d03a1f5e56b"),
 "sinner": ("https://www.youtube.com/watch?v=HqvN6AX6zFU", "HqvN6AX6zFU", 1920, 1080, "50/1", 149.536508, "42f4679ce539c6632ee63d05ad13559d2472a3010128df8228eb3347a69f1243"),
 "y1989": ("https://www.youtube.com/watch?v=3QiSxHi-6DQ", "3QiSxHi-6DQ", 1920, 1080, "30000/1001", 60.116463, "0e3c284dcd80417beccb73129d4bead1092534e8f3911bcbc8ae96fea932759c"),
 "murray": ("https://www.youtube.com/watch?v=Dfb2wa5zOf8", "Dfb2wa5zOf8", 1920, 1080, "50/1", 1054.74322, "007d1655922fb545aa1c6eed2604157704ee3259bf7dca341111539c2bbcffd6"),
 "djok23": ("https://www.youtube.com/watch?v=bq-RqtFlIM4", "bq-RqtFlIM4", 1920, 1080, "60/1", 461.798458, "c63fcce09d980977eee89871bf8a24d86e3fa34aaafb1856be6904eccf7ed67b"),
}

CROSS_WHY = "完整关键回合及随后的真实比分、反应、握手或捧杯／完整原声语句；源片内部转播切镜经实际逐帧核对，保留全部完整语句。"


def inset(n):
    return {"image": f"{A}/info-{n:02d}.png", "kind": "story_text", "corner": "tr",
            "width": 0.56, "show_for": 4.0, "pad": 0.065, "motion": "editorial"}


def foot(src, start, end, wkey, utter_key=None, info=None, tail=False, narration="", extra=None):
    q = []
    if utter_key:
        for a, b, en, zh in U[utter_key]:
            if b <= start or a >= end:
                continue
            q.append({"at": round(a - start, 2), "end": round(b - start, 2), "text": f"{en}\n{zh}"})
    seg = {"source": src, "start": start, "end": end, "narration": narration, "quote": q,
           "cx": 0.5, "track": False, "crosses_cut": True, "_crosses_cut_why": CROSS_WHY,
           "_window_key": wkey}
    if info is not None:
        seg["inset"] = inset(info)
    if tail:
        seg["audio_tail"] = "silence"
    if extra:
        seg.update(extra)
    return seg


def card(cid, title, kicker, narration, seconds):
    return {"title_card": title, "kicker": kicker, "seconds": seconds, "narration": narration, "_card_id": cid}


SECONDS = json.load(open(f"{Y}/card_seconds.json")) if __import__("os").path.exists(f"{Y}/card_seconds.json") else {}


def c(cid, title, kicker, narration):
    est = round(len(narration) / 4.6 + 0.4, 2)
    return card(cid, title, kicker, narration, SECONDS.get(cid, est))


segments = [
 foot("news", 35.95, 45.0, "news-no1-question", "news", 0),
 foot("news", 47.8, 62.42, "news-no1-answer", "news", None, tail=True,
      extra={"_audio_tail_why": "62.28 句尾后 62.56 采访者下一句开口；0.18 秒溶解底料音频补零，不露半句。",
             "_inset_why": "同一段采访的回答，前一段问句已贴信息条。",
             "_editing_why": "源 45.0–47.8 是问句之后兹维列夫沉默思考，源声约 −72～−76 dB，接近数字静音；采访内跳切删去这 2.8 秒，问句与回答都完整。"}),
 c("vo01", "辛纳赛季结束\n兹维列夫领跑800分", "本周",
   "十月六日，辛纳宣布结束赛季。今年的积分榜上，兹维列夫领先八百分，年终第一几乎到手。可他，还没当过一天世界第一。"),
 c("vo02", "今年对三强\n0胜7负", "争议",
   "可今年，他和阿尔卡拉斯、辛纳、德约交手七次，一场没赢。没赢过三强的年终第一，算数吗？"),
 c("vo03", "7场失利\n5场输给辛纳", "01",
   "其中五场输给辛纳，包括温网决赛；澳网半决赛输给阿尔卡拉斯，北京四分之一决赛输给德约。"),
 foot("ao", 208.0, 229.1, "ao-sf-last", "ao", 1, tail=True,
      extra={"_audio_tail_why": "228.7 句尾后 229.3 下一句开口；溶解底料音频补零。",
             "bed": "high",
             "_digital_silence_why": "已逐帧核对：源 209.5–211.6 是阿尔卡拉斯赛点发球前的准备与拍球，现场自然安静，源声约 −60～−64 dB、非零，不是丢音。保留完整发球准备与赛点回合，不从抛球中途裁切，也不加旁白盖住。",
             "_digital_silence_windows": [[209.4, 211.7]]}),
 foot("mc", 314.3, 328.6, "mc-sf-last", "mc", 2),
 c("vo04", "法网决赛五盘\n第一座大满贯", "转折",
   "但这一年，不只有失利。法网决赛，他五盘击败科博利，拿到第一座大满贯。"),
 foot("rg", 642.4, 689.0, "rg-final-last", None, 3,
      extra={"_quote_skip_why": "罗兰·加洛斯官方集锦本段无英文解说；约655–665秒是主裁法语宣布比分（三模型只得不一致碎片，medium识别出的数字串与6-1 4-6 6-4 6-7 6-1吻合），其余为现场声。保留冠军点与倒地庆祝的完整现场声。"}),
 foot("wim", 323.5, 357.0, "wim-final-last", "wim", 4),
 foot("uso", 9.0, 54.3, "uso-final-last", "uso", 5),
 foot("speech", 130.3, 136.7, "uso-speech-30-years", "speech", 6, tail=True,
      extra={"_audio_tail_why": "136.52 句尾后 136.78 下一句开口；溶解底料音频补零。"}),
 foot("speech", 146.3, 160.95, "uso-speech-god", "speech", None, tail=True,
      extra={"_audio_tail_why": "160.56 句尾后 161.08 下一句开口；溶解底料音频补零。",
             "_inset_why": "同一段致辞的后半句，前一段已贴颁奖信息条。"}),
 foot("bj", 273.2, 300.0, "qf-last", "bj", 7),
 c("vo05", "年终第一\n是52周的快照", "02",
   "答案在规则里。排名每周一更新，只算最近五十二周；赛季结束时排第一，就是年终第一。"),
 c("vo06", "冠军拿2000分\n对手是谁不加分", "积分怎么算",
   "积分只看打到第几轮：大满贯冠军两千分，对手是谁并不影响。他今年两座大满贯，就是四千分。"),
 foot("nastase", 0.0, 9.0, "nastase-first-no1", None, None,
      narration="这套电脑排名，始于一九七三年八月二十三日。第一位世界第一，是纳斯塔塞。"),
 foot("sinner", 64.4, 74.95, "sinner-2024-trophy", "sinner", 9, tail=True,
      extra={"_audio_tail_why": "74.95 收在 tennis 尾音，75.04 下一句 and 开口；溶解底料音频补零。"}),
 c("vo07", "年终第一\n不一定是年度最佳", "03",
   "可年终第一，并不总是年度最佳。一九七五到七八年、一九八二年、一九八九年，两个称号都不是同一个人。"),
 c("vo08", "维拉斯两座大满贯\n第一仍是康纳斯", "1977",
   "一九七七年，维拉斯拿下法网和美网，美网决赛击败康纳斯。"),
 foot("nastase", 24.8, 35.8, "connors-year-end-no1", None, None,
      narration="可按当年的平均分算法，年终第一仍是康纳斯。七四到七八年，他连续五年年终第一。",
      extra={"_inset_why": "Tennis TV 合集这一章自带「3. JIMMY CONNORS」片头字卡与「FIRST TIME AT NO.1 / WEEKS AT NO.1」原生字样，不再叠信息条；画面是康纳斯本人，旁白只讲康纳斯的年终第一，不说成1977年美网决赛画面。"}),
 c("vo09", "贝克尔两座大满贯\n第一仍是伦德尔", "1989",
   "一九八九年，贝克尔拿下温网和美网，两次击败伦德尔，当选年度最佳；年终第一仍是伦德尔。"),
 foot("y1989", 18.6, 38.5, "uso-1989-r2", "y1989", 11),
 c("vo10", "2000年起\n年终第一就是年度最佳", "2000",
   "从二〇〇〇年起，年度最佳球员，每年都是年终第一。"),
 c("vo11", "年终第一\n要拼到最后一站", "04",
   "年终第一，有时要拼到最后一站。二〇一六年总决赛决赛，穆雷对德约，谁赢，谁就是年终第一。"),
 foot("murray", 972.4, 1012.6, "murray-2016-final", "murray", 12,
      extra={"point_end_ok": "比赛在978.4冠军点已结束（Ad-40发球局，穆雷举臂庆祝）；1011.5起是穆雷走向颁奖台的镜头，画面里没有记分条，1013.1的「翻牌」是颁奖背景板被误认成记分条。段尾1012.6收在解说「year-end World No. 1」之后、1018.2下一句之前。"}),
 foot("djok23", 181.5, 204.1, "djokovic-2023-trophy", "djok23", 13),
 foot("uso", 262.0, 277.12, "uso-studio-both", "studio", None, tail=True,
      extra={"_audio_tail_why": "277.08 句尾后 277.1 主持人下一句开口；溶解底料音频补零。",
             "_inset_why": "结尾演播室评论只留人物与原声双语，不再叠信息条。"}),
 c("vo12", "两座大满贯\n明年能赢下三强吗？", "你怎么看",
   "两座大满贯，加上几乎到手的年终第一。明年，他能赢下三强吗？"),
]

meta = {}
for k, (url, lid, w, h, fps, dur, sha) in SRC.items():
    meta[k] = {"local_file": f"{Y}/{lid}.mp4", "expected_render_file": f"<OUTDIR>/source_{k}.mp4",
               "width": w, "height": h, "fps": fps, "duration_seconds": dur, "sha256": sha,
               "audio_review_status": "reviewed_selected_full_windows"}

spec = json.load(open(f"{Y}/spec_head.json"))
spec["_source_metadata"] = meta
spec["segments"] = segments
spec["sources"] = {k: v[0] for k, v in SRC.items()}
spec["_no_probe_why"] = {
    k: {
        "width": w,
        "height": h,
        "fps": fps,
        "duration": dur,
        "why": (
            "官方源片已按 URL 下载并 sha256 钉死（见 _source_metadata）；"
            "窗口按逐帧核对与 data/audio_reviews 审听包选定，没有 match-reel probe.json。"
            "几何预演用本条 width/height/fps。"
        ),
    }
    for k, (_url, _lid, w, h, fps, dur, _sha) in SRC.items()
}
spec.update(json.load(open(f"{Y}/spec_tail.json")))
out = f"/workspace/specs/reels/{SLUG}.json"
json.dump(spec, open(out, "w"), ensure_ascii=False, indent=2)
open(out, "a").write("\n")
print("wrote", out, len(segments), "segments")

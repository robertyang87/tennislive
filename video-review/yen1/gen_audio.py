"""Write per-window source-audio review packets + index for year-end-no1-zverev-2026."""
import glob, hashlib, json, os, sys
from datetime import datetime, timezone
sys.path[:0] = ["/workspace/tools", "/workspace/video-review/yen1"]
import foreground_audio_gate as G
from utter import U

ROOT = "/workspace"
SLUG = "year-end-no1-zverev-2026"
Y = "/workspace/video-review/yen1"
spec = json.load(open(f"{ROOT}/specs/reels/{SLUG}.json"))
meta = spec["_source_metadata"]

UTTER_KEY = {"news-no1-question": "news", "news-no1-answer": "news", "ao-sf-last": "ao", "mc-sf-last": "mc", "wim-final-last": "wim",
             "uso-final-last": "uso", "uso-speech-30-years": "speech", "uso-speech-god": "speech",
             "sinner-2024-trophy": "sinner", "uso-1989-r2": "y1989",
             "murray-2016-final": "murray",
 "djokovic-2023-trophy": "djok23", "uso-studio-both": "studio"}
REUSE = {"qf-last": "data/audio_reviews/djokovic-china-open-unbeaten-34/qf-last.json"}

NO_EN = {
 "rg-final-last": "罗兰·加洛斯官方集锦本段没有英文解说：冠军点回合与倒地庆祝只有现场声；约655–665秒是主裁法语宣布比分，base/small/medium三个模型只给出彼此不一致的碎片（base「It's going to be a double match」、small「3-0. Good job」、medium数字串「6-0 4-6 6-0」），无一致英文语句，判为非英文前景。",
 "connors-year-end-no1": "Tennis TV合集康纳斯一章24.8–35.8为配乐、片头字卡与回放画面；small无输出，medium仅24.8–25.52「Thank you.」(no_speech 0.886)，base仅一个「.」(p=0.004)，三模型无一致英文语句，判为无前景英文；本段配中文旁白。",
 "nastase-first-no1": "Tennis TV合集片头0–9秒为配乐与纳斯塔塞看台镜头、屏幕文字；三个模型输出互不一致且为典型幻听（base「Oh」、small「Welcome to the next video!」、medium「Music」），无英文人声，判为无前景英文。",
}

NOTES = {
 "news-no1-question": ["采访者第二问三模型均为“does the goal number one in the world”，字幕按口语保留逗号写作“does the goal, number one in the world,”。", "44.86问句尾后到48.04回答开口之间无人声，段尾45.0。"],
 "news-no1-answer": ["48.04–62.28兹维列夫回答四句，三模型一致。", "段首47.8在回答开口之前；62.28句尾后62.56下一句开口，段尾62.42，audio_tail补零。"],
 "ao-sf-last": ["216.6–228.7解说一句：small「a place in his very first Australian Open final」与medium「his very first Australian Open final」一致；人名与介词两模型分别误听为「Curtis」「for Carlos Arquías」，按画面与赛事事实写作「from Carlos Alcaraz」。", "208–216.6为最后一分回合，仅现场声；229.3下一句开口在段外。"],
 "mc-sf-last": ["320.3–327.6解说一句三模型一致（Sinner误听为Yannick）。", "314.3–320.3为冠军点回合现场声：medium两次窗口分别给出「And he becomes...」(首词p=0.02)与「Thank you very much」(首词p=0.00)，small给出「Oh, my God」，互不一致且概率极低，判为回合中人群噪声幻听，非前景英文。", "329.6下一句在段外。"],
 "wim-final-last": ["四句三模型一致或两模型一致；medium在349.3–349.98另出「That's it」，small连续段落与base均无，未确认，不写字幕。"],
 "uso-final-last": ["14.6–21.9主裁宣布：比分逐盘念出，规范写作「6-3, 7-6, 5-7, 6-2」。", "62.4下一句开口在段外。"],
 "uso-speech-30-years": ["130.74–136.52一句，按词时间在134.30“title,”后拆为两行字幕；136.78“So it's... I think...”在段尾136.7之后，不入段。"],
 "uso-speech-god": ["146.5–160.56两句；161.08下一句开口在段外，audio_tail补零。"],
 "sinner-2024-trophy": ["64.7–74.95一句，按词时间在69.06“world”后拆为两行；75.04下一句“and”开口在段尾之后，audio_tail补零。"],
 "uso-1989-r2": ["四句两模型一致。"],
 "murray-2016-final": ["源换为Tennis TV 1080p50「The Match That Decided Year-End No. 1」(Dfb2wa5zOf8)。972.4–978.7为冠军点（Ad-40）回合，仅现场声。", "978.76–981.56「Murray wins!」仅medium识别出，与随后984.6起三模型都有的「Murray wins」一致。984.6–987.9「Murray wins it all!」medium完整，small只给「Murray wins,」；987.95–996.7「He's champion of the Barclays ATP World Tour Finals」medium完整，small缺「he's champion」、作「of the Barclays ATP World Tour Finals」。", "996.8–1012.3三模型一致（medium漏「player」、small与base都有，保留）；1018.0下一句在段尾1012.6之后。"],
 "djokovic-2023-trophy": ["179.0–180.72采访者问句尾在段首181.5之前。", "四句base/small一致（small误听“finishing the year is”）。204后下一句在段外。"],
 "uso-studio-both": ["三句medium一致；第二句口语重复“majors, majors”，字幕写一次。", "277.1主持人下一句开口在段外，audio_tail补零。"],
}

stamp = datetime.now(timezone.utc).isoformat()
os.makedirs(f"{ROOT}/data/audio_reviews/{SLUG}", exist_ok=True)
entries = []
for i, seg in enumerate(spec["segments"]):
    if "start" not in seg or "end" not in seg or seg.get("image"):
        continue
    wk = seg["_window_key"]
    if wk in REUSE:
        rel = REUSE[wk]
    else:
        key = seg["source"]
        m = meta[key]
        lid = os.path.basename(m["local_file"])[:-4]
        s0, s1 = seg["start"], seg["end"]
        utts = [] if wk in NO_EN else [
            {"start": a, "end": b, "en": en, "zh": zh}
            for a, b, en, zh in U[UTTER_KEY[wk]] if b > s0 and a < s1]
        ev = []
        packet = {
            "schema": "tennislive.source-audio-transcript.v1",
            "source_url": spec["sources"][key],
            "source_path": m["local_file"],
            "source_sha256": m["sha256"],
            "method": "asr_cross_checked",
            "reviewer": "Cursor agent source_audio: faster-whisper base/small/medium window cross-check with word timestamps, no claim of human listening",
            "reviewed_at": stamp,
            "reviewed_from": s0,
            "reviewed_to": s1,
            "status": "complete",
            "uncertain_spans": [],
            "foreground_english": utts,
            "raw_transcript_evidence": [{"path": f, "sha256": hashlib.sha256(open(f, "rb").read()).hexdigest()} for f in ev],
            "normalization_note": "英文按多模型一致的词序写出，去掉口头重复与填充词；比分规范为阿拉伯数字连字符；中文为忠实意译并控制在字幕一行内。",
            "review_notes": NOTES.get(wk, []),
        }
        if wk in NO_EN:
            packet["no_foreground_english_reason"] = NO_EN[wk]
        rel = f"data/audio_reviews/{SLUG}/{wk}.json"
        with open(f"{ROOT}/{rel}", "w") as fh:
            json.dump(packet, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    entries.append({"index": i, "transcript_path": rel,
                    "transcript_sha256": hashlib.sha256(open(f"{ROOT}/{rel}", "rb").read()).hexdigest()})

index = {"schema": G.SCHEMA, "plan_sha256": G.plan_hash(spec), "segments": entries}
with open(f"{ROOT}/data/audio_reviews/{SLUG}.json", "w") as fh:
    json.dump(index, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
req = G.inspect(spec, root=__import__("pathlib").Path(ROOT))
print("index ok,", len(entries), "windows,", len(req), "required cues")

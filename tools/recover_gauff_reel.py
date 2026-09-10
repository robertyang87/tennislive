"""Build a reviewable Gauff candidate from verified source evidence; no publication."""
from pathlib import Path
from PIL import Image, ImageDraw
import hashlib, json, os, subprocess, sys
import requests
sys.path[:0]=["tools","src"]
from analyze_reel_visuals import verified_minimax_report, evidence_hash
from tennislive.research.brief import Chat
from draft_spec import draft_editorial, draft_push
from promote_reel_draft import promote
from build_match_reel import validate_spec
OUT=Path("output/2026-09-10/reel/andreeva-gauff")
R=OUT/"recovery"
def save(name,data): (R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
d=json.loads(Path("specs/reels/pending/andreeva-gauff.draft.json").read_text())
facts=json.loads((R/"official.json").read_text())
probe=json.loads((OUT/"probe.json").read_text())
d["_cover_brief"]={"preferred_subject":"高芙","preferred_moment":"winner_celebration","reason":"用户指定高芙复盘，官方同场庆祝照。","reviewed_timeline":"源片ASR在169.15—174.04报出Two six seven six six two。为保留完整英文解说，请核验cold_open=168.94—174.5的赛后余波；此前报告已确认170.5、172.5近景和174.5走向网前。ending可沿用156.5—174.5的证据窗口。正式剪辑会从136.02开始额外保留完整第二个赛点的发球准备、回合及庆祝，绝不从156.5半途中切入。独立审查，不能为过闸猜测。"}
frames=sorted(OUT.glob("contact_*.jpg"))
# Add newly reviewed native closeups with explicit timestamps; this is new evidence,
# not a third retry against unchanged contact sheets.
sheet=Image.new("RGB",(960,540*3))
draw=ImageDraw.Draw(sheet)
for i,t in enumerate([168,173,175]):
    sheet.paste(Image.open(R/f"frame-{t}.jpg").convert("RGB"),(0,540*i))
    draw.rectangle((0,540*i,145,540*i+38),fill="black")
    draw.text((8,540*i+7),f"source {t}.0 s",fill="white",stroke_width=1)
extra=R/"late-closeups.jpg"
sheet.save(extra,quality=94)
frames.append(extra)
d["_cover_brief"]["reviewed_timeline"]="新增最后一张是原片168.0、173.0、175.0秒的高清近景，并烧录了准确时间。请独立核验cold_open=168.0至175.2的赛后余波；此窗包含169.15至174.04的完整英文报分。ending建议156.5至175.2；正式剪辑另外向前扩展到136.02以保留完整发球和最后一分。所有理由引用必须在各自窗口内；不能在168.0开始的窗引用更早的时间。"
cover=R/"cover-review.jpg"
report,problems=verified_minimax_report(d,frames,cover,probe,os.environ["MINIMAX_API_KEY"])
report.update(input_sha256=evidence_hash(frames,cover),inputs=[str(p) for p in frames],cover_image=str(cover),original_cover=d["cover"]["portrait"]["image"],original_cover_sha256=hashlib.sha256(Path(d["cover"]["portrait"]["image"]).read_bytes()).hexdigest(),problems=problems)
save("visual-bilingual.json",report)
if problems: raise SystemExit("Visual evidence remains blocked: "+str(problems))
cold=report["cold_open"]
if not (cold["start"]<=169.15 and cold["end"]>=174.04): raise SystemExit("Approved opening does not contain complete verified spoken score")
# Official match feed is an independent source for elapsed time. Preserve only matched records.
url="https://www.usopen.org/en_US/scores/feeds/2026/players/matches/wta328560_matches.json"
try:
    resp=requests.get(url,timeout=10)
    feed=resp.json() if resp.status_code==200 else None
    save("official-match-feed.json",{"url":url,"status":resp.status_code,"data":feed})
except (requests.RequestException,ValueError) as exc:
    save("official-match-feed.json",{"url":url,"status":"unavailable","error":type(exc).__name__,"duration_source":"WTA official 2:19"})
packet={"result":d["_match"],"stats":d["stats"],"official_wta":facts["facts"],"source_url":d["source_url"],"footage":{"0-19.6":"首盘高芙0-3落后；无其他首盘画面","19.6-85.5":"第二盘抢七高芙4-3到5-3的一次39拍长回合；不是两个赛点的画面","85.5-105":"决胜盘高芙0-1，自己的发球局0-15这一分输后0-30","105-118":"同局高芙由0-30追到40-30，再次争取保发","118-136.02":"高芙5-2，40-15第一赛点未拿下","136.02-175.2":"第二赛点30-40，准备、完整回合、庆祝和握手；结果必须等163.33之后才交代"}}
chat=Chat(provider="deepseek")
e=draft_editorial(chat,home="米拉·安德烈耶娃",away="高芙",event="US OPEN",year=2026,fixture="当地2026年9月9日女单1/4决赛，高芙逆转",facts=json.dumps(packet,ensure_ascii=False))
push=draft_push(chat,editorial=e,facts=json.dumps(packet,ensure_ascii=False)) if e else None
base={
"intro":"当地时间九月九日，美网女单四分之一决赛。高芙对阵安德烈耶娃，开场已零比三落后。",
"grind":"首盘二比六落后，高芙把第二盘拖进抢七。四比三领先，这是她的发球分。接下来，是一场三十九拍的拉锯。长回合里，守住落点和深度，才能逼对手再多打一拍。别急着说谁占上风，这一分还没结束。",
"escape":"这一分过后，抢七还没有结束。随后高芙救回两个赛点，九比七扳平盘分。现在决胜盘零比一，她要先守住发球局。",
"hold":"从零比三十追到四十比三十，高芙要先把这一局保住。",
"close":"高芙已经五比二领先，来到发球胜赛局。四十比十五，两个赛点。但安德烈耶娃还在追。",
"stats":"全场总得分九十五比九十四，高芙只多拿一分。她救回两个赛点，把这场胜利拼到了手里。"}
schema={"type":"object","properties":{k:{"type":"string"} for k in base},"required":list(base),"additionalProperties":False}
n=chat.ask("你是网球时差的解说编辑。润色给定旁白，增强叙事但不得增加任何事实、比喻、球路细节或数字。保留各段时态及画面范围，不能把39拍一分说成挽救赛点，不能在制胜分前宣布结果。intro须保留日期赛事轮次。grind须保留39拍与4比3，具体球路不能编。每子句至多16汉字，数字念成汉字。返回相同键的JSON。字数上限intro60/grind150/escape70/hold35/close55/stats55。",json.dumps({"facts":packet,"narration":base},ensure_ascii=False),schema=schema,max_tokens=2500)
if not e or not push or not n or set(n)!=set(base): raise SystemExit("DeepSeek candidate incomplete")
save("copy-candidate.json",{"model":chat.channel,"editorial":e,"push":push,"narration":n,"packet":packet})
# All segment windows are human-reviewed source windows, never chosen by a text model.
d["editorial"]=e
d["editorial"].pop("chapters",None)
d["push"]={**push,"auto":True}
d["cover"]["matchup"][0]["country"]="RUS"
d["_visual_evidence"]=report
d["_durations"]=[["全场","2:19"]]
d["_duration_review"]={"source":facts["url"],"value":"2:19","reason":"WTA官方战报，暂待官方赛事feed核对；不沿用Flashscore的2:21。"}
quote={"at":round(169.15-cold["start"],2),"end":round(174.04-cold["start"],2),"text":"Two six, seven six, six two.\n二比六、七比六、六比二。"}
d["segments"]=[
{"start":cold["start"],"end":cold["end"],"narration":"","quote":[quote],"_quote_kind":"broadcast","_ending_payoff_required":True,"score_inset":False,"_why":"MiniMax通过的短余波与原声报分；英文来自small.en原片ASR，数字与正式赛果一致。"},
{"start":0,"end":19.6,"narration":n["intro"],"score_inset":True,"_why":"原片完整开场首盘0-3片段与反应，旁白交代日期、赛事、轮次。"},
{"start":19.6,"end":85.5,"narration":n["grind"],"score_inset":True,"_why":"完整39拍长回合，抢七高芙4-3至5-3；没有剪掉中间拍数，不冒充挽救赛点画面。"},
{"start":85.5,"end":105,"narration":n["escape"],"score_inset":True,"_why":"抢七已经结束后的决胜盘开局；回顾官方证实但此短源省略的救两个赛点，不称当前画面为救赛点。"},
{"start":105,"end":118,"narration":n["hold"],"score_inset":True,"_why":"同一发球局40-30的完整一分，先讲此前0-30追分，不提前讲结果。"},
{"start":118,"end":136.02,"narration":n["close"],"score_inset":True,"_why":"5-2发球胜赛局第一个赛点完整回合；尚未获胜。"},
{"start":136.02,"end":max(175.2,cold["end"]),"narration":"","quote":[{"at":2.38,"end":4.56,"text":"Second match point now for Gauff.\n现在是高芙的第二个赛点。"},{"at":33.13,"end":38.02,"text":"Two six, seven six, six two.\n二比六、七比六、六比二。"}],"_quote_kind":"broadcast","score_inset":True,"score_inset_windows":[[136.02,163.33]],"_score_inset_why":"136.02起源比分条仍在，140.02后完整最后回合；163.33切庆祝即关闭回贴，避免切到人体。","_why":"在MiniMax通过的156.5—174.5证据窗前扩展到136.02，保留第二赛点准备、整分、庆祝与握手；全部contact及关键帧人工核对。"},
]
d["_editorial_review"]={"reviewer":"Codex","status":"candidate_pending_review","source":"完整四张contact与score sheets，关键帧，原片ASR，WTA官方战报","limitations":"用户短源没有展示高芙挽救的两个赛点；只做来源明确的回顾，不冒用39拍这一分。"}
try:
    spec=promote(d)
    spec["topbar"]["line1"]="2026.09.09 美网女单1/4决赛"
    spec["tts_backend"]="edge"
    spec["stat_card_full_canvas"]=True
    for seg in spec["segments"]:
        if seg.get("stat_card"):
            seg["seconds"]=14
            seg["narration"]=n["stats"]
    validate_spec(spec)
    save("candidate-spec.json",spec)
    subprocess.run([sys.executable,"tools/build_match_reel.py","render","--spec",str(R/"candidate-spec.json"),"--check-narration"],check=True)
    save("candidate-validation.json",{"spec_valid":True,"tts_fits":True})
except Exception as exc:
    save("candidate-validation.json",{"spec_valid":False,"error":type(exc).__name__,"detail":str(exc)})
    raise

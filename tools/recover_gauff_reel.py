"""Build a reviewable Gauff candidate from verified source evidence; no publication."""
from pathlib import Path
from PIL import Image, ImageDraw
import hashlib, json, os, subprocess, sys
import requests
sys.path[:0]=["tools","src"]
from analyze_reel_visuals import ask_minimax, clean_report, evidence_hash
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
d["_cover_brief"]={"preferred_subject":"高芙","preferred_moment":"winner_celebration","reason":"WTA署名高芙的同场庆祝照，按衣服及背景与原片核对。","reviewed_timeline":"冷开场168.0至175.2涵盖英文报分；正文赛点实际从136.02开始，视觉审核ending可覆盖156.5至175.2。不要声称看到了发球、拥抱教练、整理发带、具体回球落点等图片不能证明的动作。"}
frames=sorted(OUT.glob("contact_*.jpg"))+[R/"late-closeups.jpg"]
cover=R/"cover-review.jpg"
previous=json.loads((R/"visual-bilingual.json").read_text())
feedback=["人工逐帧复核：166.5秒是高芙弯腰低头，画面里没有教练，原理由的拥抱教练不成立。","172.5秒是站立/走动近景，没有证据证明整理发带；168.0秒没有和教练包厢互动证据。","156.5秒已是最后一分相持，不是发球；标记为MATCH POINT #2，不是MATCH POINT ON SERVE。不要猜测162.5秒具体球路/落点。","仅保留图上确实可见的证据：末段相持、163.33后高芙庆祝、168弯腰、173近景、174.5双方在网前、175握手。前述动作要归属到各自窗口，不能引用窗外时间。"]
raw=ask_minimax(d,frames,cover,probe,os.environ["MINIMAX_API_KEY"],previous=previous,validation_problems=feedback)
report,problems=clean_report(raw,d,float(probe["duration"]))
report.update(model_attempts=2,input_sha256=evidence_hash(frames,cover),inputs=[str(p) for p in frames],cover_image=str(cover),original_cover=d["cover"]["portrait"]["image"],original_cover_sha256=hashlib.sha256(Path(d["cover"]["portrait"]["image"]).read_bytes()).hexdigest(),problems=problems,human_correction_feedback=feedback)
save("visual-final.json",report)
if problems: raise SystemExit("Visual correction remains blocked: "+str(problems))
cold=report["cold_open"]
if not (cold["start"]<=169.15 and cold["end"]>=174.04): raise SystemExit("Opening does not contain complete verified spoken score")
packet={"result":d["_match"],"stats":d["stats"],"official_wta":facts["facts"],"source_url":d["source_url"],"footage":{"0-19.6":"首盘高芙0-3落后；无其他首盘画面","19.6-85.5":"第二盘抢七高芙4-3到5-3的一次39拍长回合；不是两个赛点的画面","85.5-105":"决胜盘高芙0-1，自己的发球局0-15这一分输后0-30","105-118":"同局高芙由0-30追到40-30，再次争取保发","118-136.02":"高芙5-2，40-15第一赛点未拿下","136.02-175.2":"第二赛点30-40，准备、完整回合、庆祝和握手；结果必须等163.33之后才交代"}}
copy=json.loads((R/"copy-candidate.json").read_text())
n=copy["narration"]
e={
"hook":["三十九拍拉锯","高芙救赛点逆转"],
"question":"首盘失利、抢七面对两个赛点，高芙怎样把比赛赢回来？",
"thesis":"高芙先在抢七中保住逆转的机会，再赢下决胜盘；全场总分仅多一分，说明拿下关键分比总分差更决定结局。",
"beats":["首盘开局零比三落后，高芙以二比六丢掉首盘。","第二盘抢七四比三的三十九拍回合后，高芙以五比三领先；之后她挽救两个赛点，九比七赢下抢七。","决胜盘高芙从零比一来到五比二，在第二个赛点上收下比赛，六比二完成逆转。"],
"human_context":"WTA官方战报确认，这场之后高芙对安德烈耶娃的交手记录为六胜零负；她本赛季已十二次逆转获胜。",
"narration":["高芙开局零比三落后，二比六丢掉首盘。","抢七先拿下三十九拍拉锯，之后救回两个赛点，九比七扳平盘分。","决胜盘来到五比二，高芙兑现第二个赛点，六比二完成逆转。"]
}
push={"summary":"高芙救两赛点逆转","lead":"两次只差一分出局，高芙还是把比赛抢了回来。🎾\n\n当地时间9月9日，美网女单1/4决赛，她以2-6、7-6(7)、6-2逆转安德烈耶娃。首盘开局就0-3落后，这场比赛从一开始就不轻松。\n\n最让人屏住呼吸的是第二盘抢七：4-3时，两人展开39拍拉锯，高芙拿下这一分，来到5-3。但真正脱险还在后面——她随后救回两个赛点，才以9-7把比赛拖进决胜盘。\n\n决胜盘从0-1走到5-2，高芙来到发球胜赛局。第一个赛点被救回，她最终在第二个赛点上结束战斗。\n\n全场总得分95比94，她只多拿1分；12个双误也让这场胜利更显艰难。网球有时就是这样：赢下关键的那一分，比总共多赢多少分更重要。\n\n高芙对安德烈耶娃的交手纪录来到6-0。接下来，等待她的是莱巴金娜。"}
save("copy-reviewed.json",{"model":copy["model"],"reviewer":"Codex","editorial":e,"push":push,"narration":n,"rejected_claims":["把安德烈耶娃的5个双误写给高芙","把全场42个失误写成首盘数据","把39拍回合冒充救赛点","编造决胜盘零双误、破发点全兑现"],"method":"逐项按WTA官方事实、结构化双方统计与时间码纠错；保留核验无误的逐段旁白。"})
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
{"start":cold["start"],"end":cold["end"],"narration":"","quote":[quote],"_quote_kind":"broadcast","_ending_payoff_required":True,"score_inset":False,"_score_inset_why":"168.0后为球员近景和握手，常规两行比分条已收走；不抠取人物局部回贴。","_why":"MiniMax通过的短余波与原声报分；英文来自small.en原片ASR，数字与正式赛果一致。"},
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
    spec["editorial"]["human_context"]["sources"].append(facts["url"])
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

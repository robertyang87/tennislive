"""Prepare evidence for the explicitly requested Gauff reel; no render or publish."""
from pathlib import Path
import concurrent.futures as cf
import hashlib, json, os, subprocess, sys
import requests
from PIL import Image
sys.path[:0] = ["tools", "src"]
from build_match_reel import download
from analyze_reel_visuals import verified_minimax_report, evidence_hash
from tennislive.research.brief import Chat
from draft_spec import draft_editorial, draft_push

SLUG="andreeva-gauff"
OUT=Path("output/2026-09-10/reel")/SLUG
REVIEW=OUT/"recovery"
REVIEW.mkdir(parents=True, exist_ok=True)
draft=json.loads(Path("specs/reels/pending/"+SLUG+".draft.json").read_text())
probe=json.loads((OUT/"probe.json").read_text())
def save(name, data):
    (REVIEW/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
def visual():
    cover=Path(draft["cover"]["portrait"]["image"])
    reduced=REVIEW/"cover-review.jpg"
    with Image.open(cover) as im:
        im.convert("RGB").resize((1600,round(im.height*1600/im.width))).save(reduced,quality=93)
    frames=sorted(OUT.glob("contact_*.jpg"))
    d=json.loads(json.dumps(draft))
    d["_cover_brief"]={"preferred_subject":"高芙","preferred_moment":"winner_celebration","reason":"用户要求高芙逆转复盘。官方WTA同场配图，依据衣服、背景与来源归属审查。","reviewed_timeline":"人工看到158.5至162.5仍在打最后回合，163.33切庆祝，174.5已握手。冷开场优先163.33—168.94短庆祝，结尾须从最后一分发球准备开始并保留庆祝到174.5，必须独立核实，不能省略制胜分。"}
    report,problems=verified_minimax_report(d,frames,reduced,probe,os.environ["MINIMAX_API_KEY"])
    report.update(input_sha256=evidence_hash(frames,reduced),inputs=[str(p) for p in frames],cover_image=str(reduced),original_cover=str(cover),original_cover_sha256=hashlib.sha256(cover.read_bytes()).hexdigest(),problems=problems)
    save("visual.json",report)
    return {"visual":report.get("visual_status"),"problems":problems}
def source_and_asr():
    source=download(draft["source_url"],Path(os.environ["RUNNER_TEMP"])/"gauff-source.mp4")
    wav=Path(os.environ["RUNNER_TEMP"])/"gauff.wav"
    subprocess.run(["ffmpeg","-v","error","-y","-i",str(source),"-vn","-ar","16000","-ac","1",str(wav)],check=True)
    from faster_whisper import WhisperModel
    model=WhisperModel("small.en",device="cpu",compute_type="int8",cpu_threads=4)
    segments,info=model.transcribe(str(wav),language="en",beam_size=5,vad_filter=True,word_timestamps=True)
    rows=[{"start":s.start,"end":s.end,"text":s.text,"words":[{"start":w.start,"end":w.end,"word":w.word,"probability":w.probability} for w in (s.words or [])]} for s in segments]
    save("asr.json",{"model":"faster-whisper small.en","source_url":draft["source_url"],"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"duration":info.duration,"segments":rows})
    subprocess.run(["ffmpeg","-v","error","-y","-ss","155","-i",str(source),"-t","27","-vn","-c:a","libmp3lame","-b:a","64k",str(REVIEW/"ending-audio.mp3")],check=True)
    # Evidence at actual boundary and native scoreboard geometry, not OCR guesses.
    for stamp in [0,19,21,81.5,85,103,105,117,119,136,140,157,158,163,164,168,173,175]:
        subprocess.run(["ffmpeg","-v","error","-y","-ss",str(stamp),"-i",str(source),"-frames:v","1","-vf","scale=960:-1",str(REVIEW/f"frame-{stamp}.jpg")],check=True)
    return {"asr_segments":len(rows)}
def official():
    url="https://www.wtatennis.com/news/4574376/gauff-saves-two-match-points-storms-past-andreeva-into-us-open-semis"
    r=requests.get(url,timeout=40)
    from bs4 import BeautifulSoup
    text=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
    schema={"type":"object","properties":{"match_date":{"type":"string"},"facts":{"type":"array","items":{"type":"string"}}},"required":["match_date","facts"]}
    facts=Chat(provider="deepseek").ask("Extract only verifiable tennis match facts: date, result, saved match points and exact score states, rally shot count, rankings, elapsed time, deciding-set breaks. No quotations or article prose. Return concise structured Chinese facts; omit anything not stated.",text[:45000],schema=schema,max_tokens=2000) if r.status_code==200 else None
    save("official.json",{"url":url,"status":r.status_code,"facts":facts})
    return {"official_status":r.status_code}
results=[]
with cf.ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(fn) for fn in (visual,source_and_asr,official)]
    for f in cf.as_completed(futures):
        try: results.append(f.result())
        except Exception as exc: results.append({"error":type(exc).__name__,"message":str(exc)[:300]})
save("preparation.json",results)
print(json.dumps(results,ensure_ascii=False))

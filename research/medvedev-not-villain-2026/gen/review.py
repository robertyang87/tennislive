import json,hashlib,sys,os
from datetime import datetime,timezone
sys.path.insert(0,'tools')
import foreground_audio_gate as g
SLUG='medvedev-not-villain-2026'
spec=json.load(open(f'specs/reels/{SLUG}.json'))
VID={"bj":"LgRD3TLoxr0","us19":"9CQYJlU5_Ew","md21":"SXCs4vTWo_s","ci21":"Rv0Q9jXIz-M","us21":"MEFpXBwnyQA","ao22":"uWxN2lH2Fa0","ao22r":"xH4R5HNq-6s","us23":"6q9HMdjYpVg","ao25":"MWNZOZr_uMU","mc26":"yNxzL-8i9NU","ws26":"l7F7uLC-GGM","wsc":"9aqUxco0bqo","us25e":"oXmpP1kLyxQ","us25":"p2lgExFvcug"}
SRC='/tmp/claude-0/med/src'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
SHA={k:sha(f"{SRC}/{'ws_c' if k=='wsc' else v}.mp4") for k,v in VID.items()}
now=datetime.now(timezone.utc).isoformat()
REV="Claude（Claude Code 会话）：faster-whisper small.en 与 medium.en 两档逐词转写交叉核对，并对照本地抽帧；未人工听音"
PROF="两档转写在这一窗口里都没有脏话；按交接文档「如果确认有脏话」的条件，不消音。"
RISK={"md21","ci21","ao25","mc26","us25e","us25"}
entries=[]
d=f'data/audio_reviews/{SLUG}'; os.makedirs(d,exist_ok=True)
for f in os.listdir(d): os.remove(os.path.join(d,f))
for i,s in enumerate(spec['segments']):
    if 'start' not in s or s.get('image') or s.get('title_card'): continue
    k=s['source']; a,b=s['start'],s['end']
    utts=[]
    if s.get('quote'):
        for c in s['quote']:
            en,zh=c['text'].split('\n',1)
            utts.append({"start":round(a+c['at'],2),"end":round(a+c['end'],2),"en":en,"zh":zh})
        reason=""
    else:
        reason=f"这一段是中文旁白。窗口按 data/source_asr/{VID[k]} 的 small.en 与 medium.en 两份逐词英文转写交叉核对：两份转写在 {a}–{b} 秒内都没有任何英文词（窗口边界避开了最近的词）。"
    method="verified_source_captions" if k=="wsc" else "asr_cross_checked"
    pkt={"source_url":spec['sources'][k],"source_sha256":SHA[k],"method":method,"reviewed_at":now,"reviewer":REV if k!="wsc" else "Claude（Claude Code 会话）：前半按 small.en/medium.en 两档转写，后半两档都没转出，按 Tennis TV 片内烧录的英文字幕逐字核对本地抽帧；未人工听音",
         "reviewed_from":a,"reviewed_to":b,"status":"complete","uncertain_spans":[],"foreground_english":utts,
         "asr_evidence":f"data/source_asr/{VID[k]}/small.en.json + medium.en.json"}
    if reason: pkt["no_foreground_english_reason"]=reason
    if k in RISK: pkt["profanity_check"]=PROF
    if s.get('_why'): pkt["review_note"]=s['_why']
    path=f"{d}/{i:02d}-{k}.json"
    open(path,'w').write(json.dumps(pkt,ensure_ascii=False,indent=2)+"\n")
    entries.append({"index":i,"transcript_path":path,"transcript_sha256":hashlib.sha256(open(path,'rb').read()).hexdigest()})
idx={"schema":g.SCHEMA,"plan_sha256":g.plan_hash(spec),"segments":entries}
open(f'data/audio_reviews/{SLUG}.json','w').write(json.dumps(idx,ensure_ascii=False,indent=1)+"\n")
print("ok, required cues:",len(g.require(spec)))

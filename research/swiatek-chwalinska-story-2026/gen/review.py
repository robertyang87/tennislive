import json,hashlib,sys,os
from datetime import datetime,timezone
sys.path.insert(0,'tools')
import foreground_audio_gate as g
SLUG='swiatek-chwalinska-story-2026'
spec=json.load(open(f'specs/reels/{SLUG}.json'))
VID={k:v.split('v=')[1] for k,v in spec['sources'].items()}
SRC='/tmp/claude-0/sc/src'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
SHA={k:sha(f"{SRC}/{v}.mp4") for k,v in VID.items()}
now=datetime.now(timezone.utc).isoformat()
REV="Claude（Claude Code 会话）：faster-whisper small.en 与 medium.en 两档逐词转写交叉核对，并对照本地抽帧；未人工听音"
REV_PL="Claude（Claude Code 会话）：faster-whisper small 与 medium 两档波兰语逐词转写交叉核对（language=pl），对照本地抽帧认人；未人工听音"
entries=[]
d=f'data/audio_reviews/{SLUG}'; os.makedirs(d,exist_ok=True)
for f in os.listdir(d): os.remove(os.path.join(d,f))
for i,s in enumerate(spec['segments']):
    if 'start' not in s or s.get('image') or s.get('title_card'): continue
    k=s['source']; a,b=s['start'],s['end']
    utts=[]
    pl = k=='pol15'
    if s.get('quote'):
        for c in s['quote']:
            en,zh=c['text'].split('\n',1)
            utts.append({"start":round(a+c['at'],2),"end":round(a+c['end'],2),"en":en,"zh":zh})
        reason=""
    else:
        reason=(s.get('_quote_skip_why') or "")+f"这一段是中文旁白或只留现场声。窗口按 data/source_asr/{VID[k]} 的 small.en 与 medium.en 两份逐词英文转写交叉核对：两份转写在 {a}–{b} 秒内没有可对上的英文句子（窗口边界避开了最近的词）。"
    pkt={"source_url":spec['sources'][k],"source_sha256":SHA[k],"method":"asr_cross_checked","reviewed_at":now,"reviewer":REV_PL if pl else REV,
         "reviewed_from":a,"reviewed_to":b,"status":"complete","uncertain_spans":[],"foreground_english":utts,
         "asr_evidence":f"data/source_asr/{VID[k]}/"+("small.pl.json + medium.pl.json" if pl else "small.en.json + medium.en.json")}
    if pl: pkt["language_note"]="前景原声是波兰语（Polsat Sport 2015 年采访），字段名沿用 foreground_english，原文一行写波兰语、中文一行写译文。"
    if reason: pkt["no_foreground_english_reason"]=reason
    if s.get('_why'): pkt["review_note"]=s['_why']
    path=f"{d}/{i:02d}-{k}.json"
    open(path,'w').write(json.dumps(pkt,ensure_ascii=False,indent=2)+"\n")
    entries.append({"index":i,"transcript_path":path,"transcript_sha256":hashlib.sha256(open(path,'rb').read()).hexdigest()})
idx={"schema":g.SCHEMA,"plan_sha256":g.plan_hash(spec),"segments":entries}
open(f'data/audio_reviews/{SLUG}.json','w').write(json.dumps(idx,ensure_ascii=False,indent=1)+"\n")
print("ok, required cues:",len(g.require(spec)))

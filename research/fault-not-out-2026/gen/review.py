import json,hashlib,sys,os
from datetime import datetime,timezone
sys.path.insert(0,'tools')
import foreground_audio_gate as g
SLUG='fault-not-out-2026'
spec=json.load(open(f'specs/reels/{SLUG}.json'))
SHA={"ao":"6e273705097a8875ec31b0236bedf0d017601e615cf263723ae549231c581f19","ky":"3b30e88903786a07ade49efbe4de085502ab80884350d16af762b735baab35c2",
"md":"9a2c7eee5d27efbd45d8e54941986bb540355fa878f1a2343c048aac0d7173ff","bu":"a9c66f7b9464991e75a98d85adf42a9774c71bb1ff0f48a490c2d53598c88399",
"rb":"4e3588e01d440a36c17158e275a4ac14fdfc581d95d344c2d1921029c02fc683","wb":"cd12257ae4486585b7069b86534ddaeb218c4abfb5d2dba78d041418d44174d7"}
VID={"bu":"PYnZo-nL6Hk","ao":"VwN4Bm3liL0","ky":"o1Ad7ZL7AuU","md":"FhSymjai5hM","rb":"I_vN3qoxO8Q","wb":"GeMppP-gRKc"}
NOTE={"ao":"电子司线的 Foot fault 喊声：两档整片转写都没有；另用 research/fault-not-out-2026/asr_probe.py（2 秒小窗、medium.en、带提示词）在 18.62/19.00/19.44/20.30 秒探到，解说随后说 foot fault remix，与之吻合。字幕不写次数。"}
now=datetime.now(timezone.utc).isoformat()
REV="Claude（Claude Code 会话）：faster-whisper small.en 与 medium.en 两档逐词转写交叉核对，并对照本地抽帧；未人工听音"
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
    pkt={"source_url":spec['sources'][k],"source_sha256":SHA[k],"method":"asr_cross_checked","reviewer":REV,"reviewed_at":now,
         "reviewed_from":a,"reviewed_to":b,"status":"complete","uncertain_spans":[],"foreground_english":utts,
         "asr_evidence":f"data/source_asr/{VID[k]}/small.en.json + medium.en.json"}
    if k in NOTE and s.get('quote'): pkt["source_note"]=NOTE[k]
    if reason: pkt["no_foreground_english_reason"]=reason
    if s.get('_why'): pkt["review_note"]=s['_why']
    path=f"{d}/{i:02d}-{k}.json"
    open(path,'w').write(json.dumps(pkt,ensure_ascii=False,indent=2)+"\n")
    entries.append({"index":i,"transcript_path":path,"transcript_sha256":hashlib.sha256(open(path,'rb').read()).hexdigest()})
idx={"schema":g.SCHEMA,"plan_sha256":g.plan_hash(spec),"segments":entries}
open(f'data/audio_reviews/{SLUG}.json','w').write(json.dumps(idx,ensure_ascii=False,indent=1)+"\n")
print("ok, required cues:",len(g.require(spec)))

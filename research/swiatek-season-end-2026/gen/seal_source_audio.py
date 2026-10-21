"""Record this episode's actual source-ASR cross-check (never human listening).

The curator compared the stored two-model words, complete selected windows and
third-model outputs at the ambiguous crowd/no-speech regions. This is not a
model runner, and must be rerun only after the selected plan has been reviewed.
"""
from pathlib import Path
import sys,json,hashlib,datetime
R=Path(__file__).resolve().parents[3];sys.path[:0]=[str(R/'tools'),str(R/'src')]
from foreground_audio_gate import plan_hash,require
B=R/'research/swiatek-season-end-2026';P=R/'specs/reels/swiatek-season-end-2026.json';s=json.loads(P.read_text());OUT=R/'data/audio_reviews/swiatek-season-end-2026';OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
notes={
 'toronto':'同一原片SHA与仓库已审的多伦多夺冠素材一致。用两档逐词时间排除232秒、258.88秒等解说；夺冠原声两模型一致，纠正按官方身份拼写的Swiatek。',
 'ao':'151–159.8为末次发球、完整末点及球员反应和场内声，双模型的终场评论在160.02/160.24以后开口；转场尾料至159.98仍未碰该句。',
 'miami':'旁白仅用113.1–121.8，两模型均无前景词。最后赛点用249.05–262.95：small.en没有句子，medium.en把Hong Kong中的一个词拖成15.7秒；独立base只检出赛点前的Hold on和263秒后Remarkable performance，没有Hong Kong。保留完整赛点，到第一句真实终场总结前结束；不把中档解码假词烧成字幕。',
 'rg':'两英文模型对球场欢呼不一致：small.en出现重复Thank you very much，medium.en只有Oh；独立base多语种模型+VAD在100–156秒未检出任何语言段。135.5–149保留球声和欢呼，无可核对的前景英文句子，拒绝生成感谢语字幕。',
 'wimbledon':'405–416.3两模型没有前景英文；完整末点中The champion is beaten三模型支持（base把beaten误成big，结合small/medium一致的beaten采用）。字幕保守覆盖444.66–449.12，449.4退出下一句之前。',
 'uso':'44.6–59和151.7–163.4两模型逐词均未检出前景英文；终场总结在163.82后才开口。首盘5-0用报道支持的原生卡，避免字幕把源片5-3错称5-0。',
 'wuhan':'同一原片SHA与已有武汉半决赛一致；98.5–115.35位于两模型98.08至156.56的无英文区，231.7–240.55位于231.38后至240.88前。当前窗口没有治疗镜头，不为治疗事实造画面。',
 'toronto_r16':'small.en与medium.en逐词一致，base独立复核本人核心句；保留至So, yeah, I knew what to do结束，按语义拆四条双语字幕；audio_tail=silence仅剪除名义结束后的转场尾料，避免325.8下一句泄漏。'
}
entries=[];sources={}
for i,seg in enumerate(s['segments']):
 if 'start' not in seg or seg.get('image'):continue
 key=seg['source'];url=s['sources'][key];vid=url.rsplit('v=',1)[-1];original=B/'sources/videos'/f'{vid}.mp4';h=sha(original);sources[key]=original
 evidence=[]
 for model in ['small.en','medium.en']:
  p=R/'data/source_asr'/vid/f'{model}.json';d=json.loads(p.read_text());assert d['source_sha256']==h
  a,b=d['clip'];assert a<=seg['start'] and (b is None or b>=seg['end'])
  evidence.append({'model':model,'path':str(p.relative_to(R)),'sha256':sha(p)})
 third=R/'data/evidence/swiatek-season-end-2026/source-asr'/f'{vid}.json'
 if third.exists():evidence.append({'model':'base.multilingual','path':str(third.relative_to(R)),'sha256':sha(third)})
 utterances=[]
 for q in seg.get('quote',[]):
  en,zh=q['text'].split('\n',1);utterances.append({'start':round(seg['start']+q['at'],3),'end':round(seg['start']+q['end'],3),'en':en,'zh':zh})
 packet={'source_url':url,'source_sha256':h,'method':'asr_cross_checked','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'Codex：核对实际small.en/medium.en逐词结果；争议处追加base多语种；没有冒称真人听审','reviewed_from':seg['start'],'reviewed_to':round(seg['end']+(0 if seg.get('audio_tail')=='silence' else .18),3),'status':'complete','uncertain_spans':[],'foreground_english':utterances,'asr_results':evidence,'review_note':notes[key]}
 if not utterances:packet['no_foreground_english_reason']=notes[key]
 p=OUT/f'{i:02d}-{key}.json';p.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n');entries.append({'index':i,'transcript_path':str(p.relative_to(R)),'transcript_sha256':sha(p)})
review={'schema':'tennislive.foreground-audio-review.v1','slug':s['slug'],'plan_sha256':plan_hash(s),'reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'asr_cross_checked','segments':entries}
(OUT.with_suffix('.json')).write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
required=require(s,sources=sources);print('source windows bound:',len(entries),'bilingual utterances checked:',len(required))

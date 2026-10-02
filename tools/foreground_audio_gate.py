"""Fail-closed original-audio evidence for new reel production.

This verifies evidence coverage and burned captions; it does not claim to infer
all speech from a flag. The producer must listen/review the whole selected source
window, retain its transcript evidence, and bind the actual downloaded bytes.
Historical CI snapshots are deliberately not imported here.
"""
from __future__ import annotations
import narrated_audio_mode
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'tennislive.foreground-audio-review.v1'


def _sha(path: Path) -> str:
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def plan_hash(spec: dict) -> str:
    keys=('source','start','end','speed','narration','quote','mute','bed','image','stat_card','title_card')
    segments=[]
    for seg in spec.get('segments') or []:
        row={k:seg[k] for k in keys if k in seg}
        if row.get('stat_card') or row.get('title_card'):
            row.pop('image',None)  # load_spec materializes native-card placeholders
        segments.append(row)
    value={'slug':spec.get('slug'),'source_url':spec.get('source_url'),
           'sources':spec.get('sources'),'source_audio':spec.get('source_audio'),'segments':segments}
    if spec.get('original_audio_mode') is not None:
        value.update(original_audio_mode=spec['original_audio_mode'],owner_approval=spec.get('owner_approval'))
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _path(root: Path, name: str) -> Path:
    path=(root/name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('音频证据路径越出仓库')
    return path


def _text(text: str) -> str:
    return re.sub(r'[^a-z0-9\u3400-\u9fff]','',str(text).casefold())


def _number(value) -> float:
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('音频审听时间码必须为有限数字')
    return float(value)


def _quote_windows(seg: dict):
    duration=(_number(seg['end'])-_number(seg['start']))/float(seg.get('speed') or 1)
    raw=seg.get('quote')
    if isinstance(raw,str):
        return [(0.,duration,raw)] if raw.strip() else []
    rows=raw or []
    if not all(isinstance(x,dict) and 'at' in x for x in rows):
        raise ValueError('原声双语字幕用显式 at/end，不能靠均分时长猜同步')
    result=[]
    for i,row in enumerate(rows):
        at=_number(row['at']);end=_number(row.get('end',at+row['duration'] if 'duration' in row else rows[i+1]['at'] if i+1<len(rows) else duration))
        if not 0<=at<end<=duration:
            raise ValueError('原声字幕时间越出片段')
        result.append((at,end,str(row.get('text') or '')))
    if any(left[1]>right[0] for left,right in zip(result,result[1:])):
        raise ValueError('双语原声字幕重叠，会堆成四行')
    return result


def inspect(spec: dict, *, root: Path=ROOT, sources: dict[str,Path]|None=None) -> list[dict]:
    """Return every required cue; missing/changed evidence is a hard failure."""
    if narrated_audio_mode.enabled(spec,sources=sources):
        return []
    if spec.get('source_audio'):
        raise ValueError('source_audio 额外音轨未绑定审听：先合并为确定的源文件并重新审听，不能复用旧证据')
    selected=[]
    for i,seg in enumerate(spec.get('segments') or []):
        if str(seg.get('narration') or '').strip() and seg.get('quote'):
            raise ValueError(f'第{i+1}段为自配中文TTS，不叠加英文译文；原声与TTS请分段')
        if 'start' in seg and 'end' in seg and not seg.get('image'):
            selected.append((i,seg))
    if not selected:
        return []
    slug=str(spec.get('slug') or '')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):
        raise ValueError('音频审听需要有效 slug')
    path=root/'data/audio_reviews'/f'{slug}.json'
    review=json.loads(path.read_text())
    if review.get('schema')!=SCHEMA or review.get('plan_sha256')!=plan_hash(spec):
        raise ValueError('音频审听证据不是当前剪辑/配音/字幕计划')
    entries=review.get('segments') or []
    if len(entries)!=len(selected) or {e.get('index') for e in entries}!={i for i,_ in selected}:
        raise ValueError('每个保留原声的窗口都须完整审听，不能只登记已写字幕的几处')
    urls=spec.get('sources') or {'':spec.get('source_url')}
    if not isinstance(urls,dict) or any(not isinstance(u,str) for u in urls.values()):
        raise ValueError('成片导入不能冒充可审听的原始源片配方')
    primary=next(iter(urls));required=[];source_hashes={}
    for i,seg in selected:
        entry=next(e for e in entries if e['index']==i)
        evidence=_path(root,entry['transcript_path'])
        if _sha(evidence)!=entry.get('transcript_sha256'):
            raise ValueError('原始审听/转写证据的字节已变')
        packet=json.loads(evidence.read_text())
        key=str(seg.get('source',primary));url=urls[key]
        if packet.get('source_url')!=url or not re.fullmatch(r'[a-f0-9]{64}',str(packet.get('source_sha256') or '')):
            raise ValueError('审听证据的源片身份不匹配')
        if sources is not None:
            if key not in source_hashes and key in sources:
                source_hashes[key]=_sha(sources[key])
            if source_hashes.get(key)!=packet['source_sha256']:
                raise ValueError('下载的源片字节不是审听过的版本')
        if packet.get('method') not in {'listened_with_transcript','asr_then_listened','verified_source_captions','asr_cross_checked'} or not str(packet.get('reviewer') or '').strip():
            raise ValueError('仅有ASR/裸pass标记不能证明完整前景原声已审听')
        if packet.get('uncertain_spans'):
            raise ValueError('原声仍有不确定句子，不能把待核对标记成完整')
        stamp=datetime.fromisoformat(str(packet.get('reviewed_at') or '').replace('Z','+00:00'))
        if stamp.tzinfo is None or packet.get('status')!='complete':
            raise ValueError('音频审听未完成或缺带时区的核验时间')
        start,end=_number(seg['start']),_number(seg['end'])
        if _number(packet['reviewed_from'])>start or _number(packet['reviewed_to'])<end:
            raise ValueError('审听范围没有覆盖整个选用窗口')
        utterances=packet.get('foreground_english')
        if not isinstance(utterances,list):
            raise ValueError('须显式记录全部前景英文，确认没有时记录空数组和审听依据')
        if not utterances and not str(packet.get('no_foreground_english_reason') or '').strip():
            raise ValueError('没有英文也须记录真实审听结论，不能用 _quote_skip_why 代替')
        quotes=_quote_windows(seg)
        for utterance in utterances:
            a,b=_number(utterance['start']),_number(utterance['end'])
            if not 0<=a<b:
                raise ValueError('原声句子的时间码无效')
            if b<=start or a>=end:
                continue
            if a<start or b>end:
                raise ValueError('剪辑切断了英文句子，先保留完整句子再配字幕')
            en,zh=str(utterance.get('en') or ''),str(utterance.get('zh') or '')
            if not re.search('[A-Za-z]',en) or not re.search('[\u3400-\u9fff]',zh):
                raise ValueError('前景英文必须逐句保留英文和中文，不得把缺失译文当空白')
            if str(seg.get('narration') or '').strip():
                raise ValueError('自配TTS窗口仍有前景英文（包括话尾之后）；需独立分段并配双语字幕')
            speed=float(seg.get('speed') or 1);at,until=(a-start)/speed,(b-start)/speed
            matching=[q for q in quotes if q[0]<=at+.08 and q[1]>=until-.08 and '\n' in q[2]
                      and _text(en) in _text(q[2].split('\n',1)[0])
                      and _text(zh) in _text(q[2].split('\n',1)[1])]
            if not matching:
                raise ValueError(f'第{i+1}段 {at:.2f}–{until:.2f}s 前景英文缺完整中英字幕')
            required.append({'segment':i,'start':at,'end':until,'en':en,'zh':zh})
    return required


def require(spec: dict, **kwargs) -> list[dict]:
    try:
        return inspect(spec,**kwargs)
    except (OSError,KeyError,TypeError,ValueError,StopIteration) as exc:
        raise ValueError(f'waiting_audio_review：{exc}') from exc


def bind_sources(spec: dict, sources: dict[str,Path], outdir: Path, *, root: Path=ROOT) -> None:
    require(spec,root=root,sources=sources)
    review=root/'data/audio_reviews'/f"{spec.get('slug')}.json"
    if narrated_audio_mode.enabled(spec,sources=sources):
        payload={'plan_sha256':plan_hash(spec),'original_audio_mode':narrated_audio_mode.MODE,
                 'owner_approval':narrated_audio_mode.APPROVAL,
                 'sources':{key:_sha(path) for key,path in sources.items()}}
        (outdir/'audio_review_binding.json').write_text(json.dumps(payload,indent=2)+'\n')
        return
    if not review.is_file():
        return  # TTS-only production has no retained original-audio windows.
    payload={'plan_sha256':plan_hash(spec),'review_sha256':_sha(review),
             'sources':{key:_sha(path) for key,path in sources.items()}}
    (outdir/'audio_review_binding.json').write_text(json.dumps(payload,indent=2)+'\n')


def record_timeline(spec: dict, outdir: Path, cover: float, offsets: list[float], lengths: list[float]) -> None:
    """Record the exact offsets used by the native subtitle/mix loop, before sealing."""
    path=outdir/'audio_review_binding.json'
    binding=json.loads(path.read_text()) if path.is_file() else {'plan_sha256':plan_hash(spec)}
    binding['timeline']={'cover_seconds':cover,'offsets':offsets,'lengths':lengths}
    path.write_text(json.dumps(binding,indent=2)+'\n')


def verify_final(spec: dict, ass: Path, cover_seconds: float, *, root: Path=ROOT, film: Path|None=None) -> None:
    required=require(spec,root=root)
    film=film or ass.parent/f"{spec.get('slug')}.mp4"
    manifest_path=ass.parent/'render_inputs.json'
    manifest=json.loads(manifest_path.read_text())
    render=json.loads((ass.parent/'render.json').read_text())
    if (manifest.get('film_sha256')!=_sha(film) or manifest.get('artifacts',{}).get('subtitles.ass')!=_sha(ass)
            or render.get('render_inputs_sha256')!=_sha(manifest_path)):
        raise ValueError('烧片时的 film/ASS 绑定不匹配；只改字幕旁文件不能证明视频字幕已修复')
    review=root/'data/audio_reviews'/f"{spec.get('slug')}.json"
    if review.is_file() and not narrated_audio_mode.enabled(spec):
        binding_path=ass.parent/'audio_review_binding.json'
        if manifest.get('artifacts',{}).get('audio_review_binding.json')!=_sha(binding_path):
            raise ValueError('烧片时的音频审听绑定已变')
        binding=json.loads(binding_path.read_text())
        if binding.get('plan_sha256')!=plan_hash(spec) or binding.get('review_sha256')!=_sha(review):
            raise ValueError('最终质检的音频证据绑定不是本次剪辑/审听版本')
        urls=spec.get('sources') or {'':spec.get('source_url')}
        for entry in json.loads(review.read_text()).get('segments') or []:
            packet=json.loads(_path(root,entry['transcript_path']).read_text())
            keys=[key for key,url in urls.items() if url==packet['source_url']]
            if not keys or any(binding.get('sources',{}).get(key)!=packet['source_sha256'] for key in keys):
                raise ValueError('最终质检缺经过实际源文件核验的音频身份')
    events=[]
    for line in ass.read_text().splitlines():
        if line.startswith('Dialogue:'):
            parts=line.split(',',9)
            def sec(value):
                h,m,s=value.split(':');return int(h)*3600+int(m)*60+float(s)
            text=re.sub(r'\{[^}]*\}','',parts[9]).replace(r'\N','\n')
            events.append((sec(parts[1]),sec(parts[2]),text))
    bilingual=[e for e in events if '\n' in e[2] and re.search('[A-Za-z]',e[2].split('\n')[0])
               and not re.search('[\u3400-\u9fff]',e[2].split('\n')[0])
               and re.search('[\u3400-\u9fff]',e[2].split('\n')[-1])]
    bilingual.sort()
    if any(a[1]>b[0]+.01 for a,b in zip(bilingual,bilingual[1:])):
        raise ValueError('成片双语字幕重叠，会堆成四行')
    from tennislive.video.explainer import readable
    binding_path=ass.parent/'audio_review_binding.json'
    if manifest.get('artifacts',{}).get(binding_path.name)!=_sha(binding_path):
        raise ValueError('烧片时的音频/时间轴绑定已变')
    bound=json.loads(binding_path.read_text())
    if bound.get('plan_sha256')!=plan_hash(spec):
        raise ValueError('音频绑定不是当前剪辑配方')
    narrated_audio_mode.verify_mix(spec,film,bound)
    timeline=bound['timeline']
    offsets,lengths=timeline['offsets'],timeline['lengths']
    if timeline['cover_seconds']!=cover_seconds or len(offsets)!=len(spec.get('segments') or []) or len(lengths)!=len(offsets):
        raise ValueError('当前封面/分段时间不是渲染时使用的时间轴')
    for i,seg in enumerate(spec.get('segments') or []):
        cursor,length=_number(offsets[i]),_number(lengths[i])
        expected=float(seg['seconds']) if seg.get('image') or seg.get('stat_card') or seg.get('title_card') else (float(seg['end'])-float(seg['start']))/float(seg.get('speed') or 1)
        if not math.isclose(length,expected,abs_tol=.001):
            raise ValueError('分段长度与渲染时的时间轴不一致')
        if str(seg.get('narration') or '').strip():
            for a,b,text in events:
                spoken_terms=set(re.findall(r'[a-z]+',readable(str(seg.get('narration') or '')).casefold()))
                extra=[term for term in re.findall(r'[a-z]+',text.casefold()) if term not in spoken_terms]
                if a<cursor+length and b>cursor and extra:
                    raise ValueError('自配中文TTS窗口出现额外英文翻译行')
    for cue in required:
        a,b=offsets[cue['segment']]+cue['start'],offsets[cue['segment']]+cue['end']
        if not any(x<=a+.08 and y>=b-.08 and '\n' in text
                   and _text(cue['en']) in _text(text.split('\n')[0])
                   and _text(readable(cue['zh'])) in _text(text.split('\n',1)[1]) for x,y,text in events):
            raise ValueError(f'成片 ASS 缺原声双语句：{a:.2f}–{b:.2f}s')

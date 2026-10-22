"""Build the user-approved eight-event v3, preserving audited retained v2 windows.
No import side effects. Default invocation only prints a summary. --output writes a
review candidate; ONLY explicit --write-repo writes the repository spec/new labels.
Agent selection packages remain blockers until source/audio/live-label evidence exists.
"""
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json
import sys
from merge_selections_v3 import load_selections, load_source_index, sha256

ROOT = Path('/workspace/pegula-finals-production')
HERE = Path(__file__).resolve().parent
REPO = Path('/workspace/tennislive')
SLUG = 'pegula-finals-2026'
REPO_SPEC = REPO/'specs/reels'/f'{SLUG}.json'
ASSETS = Path('assets/reel')/SLUG
SEQUENCE = ('cold-quote','card-intro','card-january','ao','card-dubai',
 'dubai-final','dubai-speech','card-sunshine','card-charleston',
 'charleston-final-extra','charleston-final','card-clay','rg-r1',
 'card-berlin','berlin-sf','card-wimbledon','wimbledon-qf','card-cincy',
 'cincy-sf','cincy-final','card-us-open','us-qf','us-qf-matchpoint',
 'us-qf-reaction','us-qf-interview','card-us-semi','us-sf','us-sf-matchpoint',
 'card-asia','card-qualification','card-ending')
NEW_LABELS = {
 'rg-r1':dict(topic='法网首轮出局',date='2026.05.26',place='法网第一轮',
              people='佩古拉 vs 比勒尔',score='6-1 3-6 3-6'),
 'wimbledon-qf':dict(topic='止步温网8强',date='2026.07.07',place='温网1/4决赛',
                     people='佩古拉 vs 高芙',score='6-4 3-6 3-6')}
POINT_ROLES = {'ao':('ao-sf','match_point'),'dubai-final':('dubai-final','match_point'),
 'charleston-final-extra':('charleston-final','extra_highlight'),
 'charleston-final':('charleston-final','match_point'), 'rg-r1':('rg-r1','match_point'),
 'berlin-sf':('berlin-sf','match_point'),'wimbledon-qf':('wimbledon-qf','match_point'),
 'cincy-sf':('cincy-sf','match_point'),'cincy-final':('cincy-final','match_point'),
 'us-qf':('us-qf','extra_turning_point'),'us-qf-matchpoint':('us-qf','match_point'),
 'us-sf':('us-sf','extra_turning_point'),'us-sf-matchpoint':('us-sf','match_point')}
SCOPE = ('最新用户最终收紧：重点仅8站——四大满贯、迪拜和查尔斯顿两冠、柏林和辛辛那提两大分站；'
         '其余8站只在旁白一句带过。比赛画面仅10个完整终局赛点及3个额外完整回合：查尔斯顿决赛、'
         '美网1/4决赛救破发点、美网半决赛救破发点；不沿用此前每场额外加一分的22回合版本。'
         '删除美网半决赛后约30秒展望萨巴伦卡决赛的解说，因不服务佩古拉主线；非规避完整原声字幕。'
         '全季工作簿仍保留16站64场及未出赛/退赛的口径；不因视频收束删改事实资料。')

def read_json(path):
    return json.loads(Path(path).read_text())

def new_video(key,row,index,voice,blockers):
    """Materialize exact supplied window; never infer a missing safe label interval."""
    required = ('source_name','start','end','source_sha256','audio_review_packet')
    missing = [f for f in required if f not in row or row[f] is None or row[f] == '']
    if missing:
        blockers.append(f'{key}:missing '+','.join(missing))
        return None
    if row.get('uncertain') or row.get('uncertain_spans'):
        blockers.append(f'{key}:unresolved source/foreground uncertainty')
    if row.get('status') and row['status'] not in ('ready','complete','complete_asr_cross_checked_not_human_listening','ready_for_native_integration'):
        blockers.append(f'{key}:package status={row["status"]}')
    lo,hi = row['start'],row['end']
    if not (isinstance(lo,(int,float)) and isinstance(hi,(int,float)) and 0<=lo<hi):
        blockers.append(f'{key}:invalid source window')
        return None
    source = index.get(row['source_name'])
    if source is None:
        blockers.append(f'{key}:missing source-index entry')
    else:
        if source.get('sha256') != row['source_sha256']:
            blockers.append(f'{key}:source-index SHA differs from selection')
        if hi > source.get('duration',0):
            blockers.append(f'{key}:selected end exceeds probed source duration')
    packet = Path(row['audio_review_packet'])
    if not packet.is_file():
        blockers.append(f'{key}:missing foreground packet')
    else:
        data=read_json(packet)
        if data.get('source_sha256') and data['source_sha256'] != row['source_sha256']:
            blockers.append(f'{key}:foreground packet source SHA mismatch')
    caps = row.get('captions',[])
    for cue in caps:
        if not (lo<=cue['start']<cue['end']<=hi and cue.get('en') and cue.get('zh')):
            blockers.append(f'{key}:invalid/incomplete bilingual cue')
    if not caps and not row.get('no_foreground_english_reason'):
        blockers.append(f'{key}:no captions and no verified foreground-language explanation')
    seg = {k:deepcopy(row[k]) for k in ('audio_tail','point_end_ok','subtitle_bottom_windows',
           '_subtitle_position_why','fill_y') if k in row}
    seg.update(_id=key,source=row['source_name'],start=lo,end=hi,frame='court',
               cx=.5,track=False,fit='crop',narration='',voice=deepcopy(voice),
               _quote_kind=row.get('quote_kind','broadcast'),
               _frame_why='官方同场完整赛点；固定球场中心cx=.5、原生1080×1440铺满，不自动跟随。',
               _why=row.get('visual_review',row.get('notes','Exact official same-match selection; native preview still required.')))
    if caps:
        seg['quote']=[{'at':round(c['start']-lo,3),'end':round(c['end']-lo,3),
                       'text':c['en']+'\n'+c['zh']} for c in caps]
    else:
        seg['_quote_skip_why']=row.get('no_foreground_english_reason','')
    if row.get('audio_tail_why'):
        seg['_audio_tail_why']=row['audio_tail_why']
    safe=row.get('label_safe_window')
    if not (isinstance(safe,(list,tuple)) and len(safe)==2 and
            all(isinstance(v,(int,float)) for v in safe) and lo<=safe[0]<safe[1]<=hi and round(safe[1]-safe[0],3)>=2.8):
        blockers.append(f'{key}:missing/invalid >=2.8s evidenced live-label interval')
    else:
        seg['inset']={'image':str(ASSETS/f'context-{key}.png'),'kind':'story_text',
          'corner':'tr','width':.60,'pad':.043,'show_after':round(safe[0]-lo,3),
          'show_for':round(min(15,safe[1]-safe[0]),3),'motion':'editorial',
          'label':deepcopy(NEW_LABELS[key])}
        seg['_label_window_why']=row.get('label_window_why','Exact supplied source safe interval; native preview pending.')
    return seg

def build_spec(packages=(),indexes=(),base_path=REPO_SPEC):
    base=read_json(base_path)
    old={s['_id']:s for s in base['segments']}
    plan={r['id']:r for r in read_json(HERE/'narration-plan-v3.json')}
    selected,evidence=load_selections(packages)
    index=load_source_index(packages,indexes)
    voice=deepcopy(old['card-intro']['voice'])
    pending=[];segments=[]
    for key in SEQUENCE:
        if key.startswith('card-'):
            p=plan[key[5:]]
            prior=old.get(key,old.get('card-summer') if key=='card-wimbledon' else None)
            if prior is None:
                raise ValueError(f'Missing audited chapter-card template {key}')
            seg=deepcopy(prior)
            seg.update(_id=key,_timeline_date=p['date'],seconds=p['seconds'],narration=p['text'],
                       kicker=p['kicker'],_voice_intent=p['intent'],_voice_emphasis=p['main_emphasis'])
            if key!='card-qualification':
                seg['title_card']=p['title']
            seg.pop('title_card_story_label',None)
            seg.pop('inset',None)
        elif key in NEW_LABELS:
            if key not in selected:
                pending.append(f'{key}:awaiting verified full-match-point source package')
                continue
            seg=new_video(key,selected[key],index,voice,pending)
            if seg is None:
                continue
        else:
            if key not in old:
                pending.append(f'{key}:missing previously audited retained segment')
                continue
            # Preserve exact actual-window captions, crop, safe label, tail and repairs.
            seg=deepcopy(old[key])
        if key in POINT_ROLES:
            seg['_match_id'],seg['_point_role']=POINT_ROLES[key]
        segments.append(seg)
    spec=deepcopy(base)
    spec['segments']=segments
    used={s['source'] for s in segments if 'source' in s}
    for field in ('sources','source_fallbacks','_no_probe_why','mixed_fps'):
        spec[field]={k:v for k,v in base.get(field,{}).items() if k in used}
    for key in used:
        r=index.get(key)
        if r is None:
            pending.append(f'{key}:missing source index')
            continue
        missing=[f for f in ('canonical_url','archive_url','sha256','width','height','fps') if not r.get(f)]
        if missing:
            pending.append(f'{key}:incomplete source index '+','.join(missing))
            continue
        spec['sources'][key]=r['canonical_url'];spec['source_fallbacks'][key]=r['archive_url']
        if key not in spec['_no_probe_why']:
            spec['_no_probe_why'][key]={'why':f'官方源实测{r["width"]}×{r["height"]}；SHA256 {r["sha256"]}。新窗仍需原生预览及成片QC。',
              'width':r['width'],'height':r['height'],'fps':r['fps']}
        if r['fps']!='25/1':
            spec['mixed_fps'][key]=f'原生{r["fps"]}fps按实际时长转换主片25fps，不改变声音或比赛速度。'
    spec['_render_blockers']=list(dict.fromkeys(pending))
    editorial=spec['editorial']
    editorial['thesis']='以四大满贯、迪拜和查尔斯顿两冠、柏林与辛辛那提两大分站串起全年高光与低谷；其余8站仅一句交代，继续到亚洲赛季与正式年终资格。'
    editorial['human_context']['angle']='两次捧杯、反复重返决赛，也会在大满贯先赢一盘后出局；八站重点与关键原声串起连续第五张年终门票。'
    spec['_outline_review']={'received':True,'response':'不用每站比赛都加；四大满贯+夺冠的外加一两个取得大分的比赛；其他的可以一句话带过；不然 16 站太多了','request':'requests/stories/pegula-finals-2026.json',
       'latest_scope':SCOPE,'supersedes':'此前22回合/每个比赛均加extra的佩古拉本集提纲；只调整本集重点，不修改全局闸或全季资料。',
       'focus_events':['澳网','迪拜','查尔斯顿','法网','柏林','温网','辛辛那提','美网'],
       'brief_events':['布里斯班','印第安维尔斯','迈阿密','马德里','罗马','华盛顿','多伦多','武汉']}
    spec['_revision_v3']={'scope':SCOPE,'base_spec_sha256':sha256(base_path),
       'narration_plan_sha256':sha256(HERE/'narration-plan-v3.json'),
       'new_package_evidence':evidence,'target_match_points':10,'target_extra_points':3,
       'tts_status':'4段改写旁白已实际整句合成并量过，15个真实配音请求冻结在915aed28bab4b67e35a79c6a1f9789cf5ff247a848083f93f0e805ebb4a33e65；最终段序会再严格复用核时，不以预检冒充最终声音QC。',
       'qc_status':'New source packages/native windows require independent native previews and final encoded-film QC; no automatic approval.'}
    assert not any('title_card_story_label' in s for s in segments)
    assert all('start' in s for s in segments if s.get('inset',{}).get('kind')=='story_text')
    assert [s['_id'] for s in segments if str(s.get('_point_role','')).startswith('extra_')]==['charleston-final-extra','us-qf','us-sf']
    if not pending:
        assert len([s for s in segments if s.get('_point_role')=='match_point'])==10
        assert tuple(s['_id'] for s in segments)==SEQUENCE
    return spec

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',action='append',default=[])
    parser.add_argument('--source-index',action='append',default=[])
    parser.add_argument('--base-spec',type=Path,default=REPO_SPEC)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--write-repo',action='store_true')
    args=parser.parse_args()
    if args.output and args.write_repo:
        parser.error('Choose --output OR --write-repo')
    if args.output and args.output.resolve()==REPO_SPEC.resolve():
        parser.error('Repository spec requires explicit --write-repo')
    spec=build_spec(args.package,args.source_index,args.base_spec)
    if args.write_repo:
        if spec['_render_blockers']:
            print(json.dumps({'blocked':spec['_render_blockers']},ensure_ascii=False,indent=2))
            raise SystemExit(2)
        sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')]
        from render_story_info_band import render_label
        for key,label in NEW_LABELS.items():
            render_label(label,REPO/ASSETS/f'context-{key}.png')
        REPO_SPEC.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    elif args.output:
        args.output.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'segments':len(spec['segments']),'match_points':sum(s.get('_point_role')=='match_point' for s in spec['segments']),
      'extra_points':sum(str(s.get('_point_role','')).startswith('extra_') for s in spec['segments']),
      'video_seconds':round(sum(s['end']-s['start'] for s in spec['segments'] if 'start' in s),3),
      'narration_seconds_estimate':sum(s.get('seconds',0) for s in spec['segments']),
      'blockers':spec['_render_blockers'],'wrote_repo':args.write_repo},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

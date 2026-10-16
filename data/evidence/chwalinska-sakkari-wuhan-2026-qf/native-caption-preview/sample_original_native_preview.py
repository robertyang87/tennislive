import sys,json
from pathlib import Path
R=Path('/workspace/tennislive-efficiency');sys.path[:0]=[str(R/'tools'),str(R/'src')]
import build_match_reel as reel
import preview_reel_captions as preview
specpath=R/'specs/reels/chwalinska-sakkari-wuhan-2026-qf.json';spec=json.loads(specpath.read_text())
out=Path('/workspace/scratch/moon-qf-caption-preview');out.mkdir(exist_ok=True)
source=out/'source_main.mp4'
if not source.exists():source.symlink_to('/workspace/scratch/moon-qf-source/source.mp4')
reel.apply_tts_backend(spec)
def callback(**kw):
    cursor=kw['cover_secs'];times=[]
    for raw,seg in zip(spec['segments'],kw['segments']):
        if raw.get('quote'):
            times.extend(cursor+(float(q['at'])+float(q['end']))/2 for q in raw['quote'])
            special={'cold_open':[.15], 'first_set':[2.5,38.0,59.65], 'second_break':[2.5,31.5,39.5], 'second_finish':[1.5,25.5,48.4], 'ending':[1.5,17.0,24.4,55.9]}
            times.extend(cursor+x for x in special.get(raw.get('_edit_id'),[]))
        else:times.append(cursor+min(5,seg.length/2))
        cursor+=seg.length
    reports=[]
    for i in range(0,len(times),24):
        args={**kw,'outdir':out/f'batch-{i//24+1:02d}'}
        reports.append(str(preview.render_frames(**args,maximum=24,at=tuple(times[i:i+24]),spec_path=specpath)))
    summary=out/'batch-manifests.json';summary.write_text(json.dumps({'kind':'native_preencode_preview_only','publication_approved':False,'requested_frames':len(times),'reports':reports},indent=2)+'\n')
    return summary
print(reel.render(spec,out,voice='zh-CN-YunjianNeural',rate='+6%',tts_bundle_in=Path('/workspace/scratch/moon-qf-tts.zip'),preview_callback=callback))

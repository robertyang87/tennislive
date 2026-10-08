"""Extract full-canvas QC evidence from the real sealed final film, never a preview."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[4]

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--film',required=True)
    ap.add_argument('--spec',default=str(ROOT/'specs/reels/zverev-djokovic.json'))
    ap.add_argument('--out',default=str(Path(__file__).parent/'final-frames'))
    ap.add_argument('--plan-only',action='store_true')
    args=ap.parse_args()
    film=Path(args.film).resolve();spec_path=Path(args.spec).resolve()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    spec=json.loads(spec_path.read_text())
    binding_path=film.parent/'audio_review_binding.json'
    binding=json.loads(binding_path.read_text())
    manifest=json.loads((film.parent/'render_inputs.json').read_text())
    assert sha(film)==manifest['film_sha256'],'Final film differs from render seal'
    assert sha(binding_path)==manifest['artifacts']['audio_review_binding.json'],'Timeline binding changed'
    assert sha(spec_path)==manifest['spec_sha256'],'Supply exact rendered spec'
    stream=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,duration,r_frame_rate','-of','json',str(film)]))['streams'][0]
    assert (stream['width'],stream['height'])==(1080,1440),'Unexpected final canvas'
    duration=float(stream['duration']);timeline=binding['timeline']
    offsets=timeline['offsets'];lengths=timeline['lengths']
    assert len(offsets)==len(lengths)==len(spec['segments'])
    shots=[]
    def add(t,label,**meta):
        if 0<=t<duration:
            shots.append({'film_seconds':round(t,4),'label':label,**meta})
    add(0,'first-canvas');add(timeline['cover_seconds']/2,'cover-headline')
    add(max(0,timeline['cover_seconds']-0.08),'cover-end')
    for i,(seg,offset,length) in enumerate(zip(spec['segments'],offsets,lengths)):
        if seg.get('title_card') or seg.get('stat_card'):
            add(offset+length/2,'native-card-subtitle-logo',segment=i)
            add(offset+min(0.16,length/3),'native-card-opening',segment=i)
        elif 'start' in seg:
            add(offset+min(0.4,length/3),'segment-headline-and-board',segment=i,
                source_seconds=round(seg['start']+min(0.4,length/3)*seg.get('speed',1),4))
        if isinstance(seg.get('quote'),list):
            for j,cue in enumerate(seg['quote']):
                end=cue.get('end',cue['at']+cue.get('duration',0))
                add(offset+(cue['at']+end)/2,'bilingual-safe-area',segment=i,quote_index=j,
                    cue_text=cue['text'])
    events={0.5:'wide-ad',10.5:'dark-blue-closeup',32.5:'closeup',
        105.1:'first-set-point-action',108.5:'no-blue-set-finish-board',
        172.48:'second-set-point-action',188.0:'second-set-point-outcome',194.2:'set-board-change',
        229.2:'match-point-one-start',266.38:'match-point-one-last-ball',266.4:'match-point-one-dead-ball',
        269.05:'match-point-one-reaction',272.6:'match-point-two-start',279.9:'match-point-two-outcome',
        280.5:'dark-ad-full-column',281.9:'ad-before-collapse',282.5:'no-points-column',
        282.76:'board-disappearance-after-cut',284.8:'no-board-player-closeup',286.0:'no-board-crowd',
        289.0:'handshake',300.0:'winner-real-reaction',305.5:'winner-fist',308.88:'source-ending'}
    for i,(seg,offset,length) in enumerate(zip(spec['segments'],offsets,lengths)):
        if 'start' not in seg or seg.get('image'):
            continue
        for source_time,label in events.items():
            if seg['start']<=source_time<seg['end']:
                add(offset+(source_time-seg['start'])/seg.get('speed',1),label,
                    segment=i,source_seconds=source_time)
    add(duration-1.5,'outro-blue-and-brand');add(duration-0.08,'last-canvas')
    shots.sort(key=lambda x:(x['film_seconds'],x['label']))
    for i,shot in enumerate(shots):
        shot['file']=f'{i:03d}-{shot["film_seconds"]:08.3f}-{shot["label"]}.jpg'
        if not args.plan_only:
            subprocess.run(['ffmpeg','-v','error','-xerror','-y','-ss',str(shot['film_seconds']),
                '-i',str(film),'-frames:v','1','-q:v','2',str(out/shot['file'])],check=True)
            assert (out/shot['file']).is_file(),'No real frame extracted'
    evidence={'film':str(film),'film_sha256':sha(film),'spec_sha256':sha(spec_path),
        'binding_sha256':sha(binding_path),'canvas':[1080,1440],
        'method':'Exact render-time timeline/source mapping; unresized full-canvas JPEG frames from actual final MP4',
        'plan_only':args.plan_only,'shots':shots}
    (out/'frame-index.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(shots)} full-canvas QC frames; index: {out / "frame-index.json"}')

if __name__=='__main__':
    main()

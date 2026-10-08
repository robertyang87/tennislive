"""Refresh only existing ATP mechanical board scans; never call content models."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
import probe_board

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def findings(spec, probe):
    urls = spec.get('sources') or {'': spec['source_url']}
    primary = next(iter(urls))
    segments = []
    for s in spec['segments']:
        image = bool(s.get('image') or s.get('title_card') or s.get('stat_card'))
        box = s.get('scorebox', spec.get('scorebox'))
        inset = tuple(box) if s.get('score_inset') else None
        segments.append(SimpleNamespace(image=image, source=s.get('source', primary),
            start=float(s.get('start', 0)), end=float(s.get('end', 0)),
            speed=float(s.get('speed', 1)), fit=s.get('fit', 'crop'),
            score_inset=inset, score_inset_windows=tuple(
                (a-s['start'], b-s['start']) for a,b in s.get('score_inset_windows', []))))
    hard,soft=probe_board.board_findings(spec, segments, {spec['source_url']:probe}, urls,
        profile='atp', tail=0.18)
    return {'hard':hard,'soft':soft}

def main():
    src=Path('/workspace/djokovic-cja-research/source/cjaHThpISKk.mp4')
    probe_path=ROOT/'output/2026-10-04/reel/zverev-djokovic/probe.json'
    spec_path=ROOT/'specs/reels/zverev-djokovic.json'
    out=Path(__file__).parent/'reprobe-atp'
    out.mkdir(parents=True,exist_ok=True)
    source_sha=sha(src)
    assert source_sha=='2a62a85fb499f153e97fa3074294eb1be476a818aa480291b65b43a3e94484e2'
    original=probe_path.read_bytes()
    (out/'probe-before.json').write_bytes(original)
    before=json.loads(original);after=copy.deepcopy(before)
    spec=json.loads(spec_path.read_text())
    board=after['board'];summaries=[]
    for index,entry in enumerate(board['scans']):
        if 'atp' not in entry['profiles']:
            continue
        got=probe_board.scan_plan(src,[(('atp',),tuple(entry['box']))],before['width'],
            start=float(board.get('t0',0)),stop=before.get('clip_to'),fps=int(board['fps']))[0]
        assert got['box']==entry['box'] and got['frames']==entry['frames']
        old=copy.deepcopy(entry['profiles']['atp'])
        entry['profiles']['atp']=got['profiles']['atp']
        summaries.append({'scan_index':index,'box':entry['box'],'frames':entry['frames'],
            'before':{k:v for k,v in old.items() if k!='runs'},
            'after':{k:v for k,v in entry['profiles']['atp'].items() if k!='runs'}})
    assert len(summaries)==1
    board['_recomputed']={'method':'Exact cached original source + current probe_board.scan_plan and fixed atp_scoreboard; ATP-only mechanical refresh; no model calls',
        'source_sha256':source_sha,'source_bytes':src.stat().st_size,
        'atp_scoreboard_sha256':sha(ROOT/'tools/atp_scoreboard.py'),
        'probe_board_sha256':sha(ROOT/'tools/probe_board.py'),
        'checked_at':datetime.now(timezone.utc).isoformat(),'original_probe_run_id':'37208304068'}
    assert {k:v for k,v in before.items() if k!='board'}=={k:v for k,v in after.items() if k!='board'}
    for a,b in zip(before['board']['scans'],board['scans']):
        if 'atp' not in a['profiles']:
            assert a==b
    result={'source_sha256':source_sha,'before_probe_sha256':hashlib.sha256(original).hexdigest(),
        'changed_fields':['board.scans[ATP].profiles.atp','board._recomputed'],
        'scan_summaries':summaries,'before_findings':findings(spec,before),
        'after_findings':findings(spec,after)}
    probe_path.write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
    result['after_probe_sha256']=sha(probe_path)
    (out/'before-after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/'probe-after.json').write_bytes(probe_path.read_bytes())
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

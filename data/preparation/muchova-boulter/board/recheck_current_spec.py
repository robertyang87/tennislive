"""Re-use exact local board evidence for current spec; no rescan or file mutation outside evidence."""
from pathlib import Path
import ast
import hashlib
import json
import sys
from types import SimpleNamespace

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT/'repo/tools'))
from probe_board import board_findings, frames_of

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

spec_path = ROOT/'prepared/muchova-boulter.working.json'
spec = json.loads(spec_path.read_text())
probe_path = OUT/'probe.augmented.json'
probe = json.loads(probe_path.read_text())
original = json.loads((OUT/'probe.original.json').read_text())
assert all(probe[k] == v for k,v in original.items() if k != 'board')
assert probe['_archived_board_preserved'] == original['board']
board = probe['board']
frames = frames_of(board['scans'][0], 'wta')
fps, t0 = board['fps'], board['t0']
urls = spec.get('sources') or {'': spec['source_url']}
primary = str(spec.get('primary') or next(iter(urls)))
main_url = original['url']
segments, evidence = [], []
for i, raw in enumerate(spec['segments']):
    image = bool(raw.get('image') or raw.get('title_card') or raw.get('stat_card'))
    source_key = str(raw.get('source', primary))
    box = tuple(raw.get('scorebox',spec['scorebox'])) if raw.get('score_inset') else None
    if box and isinstance(raw['score_inset'],dict):
        assert set(raw['score_inset']) == {'x2'}
        box = (box[0], box[1], int(raw['score_inset']['x2']), box[3])
    start = float(raw.get('start',0))
    seg = SimpleNamespace(image=image, source=source_key,
        start=float(raw.get('start',0)), end=float(raw.get('end',0)),
        speed=float(raw.get('speed',1)), fit=raw.get('fit','crop'),
        score_inset=box,
        score_inset_windows=tuple((a-start,b-start) for a,b in raw.get('score_inset_windows',[])))
    segments.append(seg)
    if not image and urls.get(source_key) == main_url and seg.score_inset:
        end = seg.end + .18 * seg.speed
        ks = [k for k in range(len(frames)) if seg.start <= t0+k/fps < end]
        if seg.score_inset_windows:
            ks = [k for k in ks if any(seg.start+a <= t0+k/fps < seg.start+b for a,b in seg.score_inset_windows)]
        assert seg.start >= t0 and end <= t0+len(frames)/fps+1e-8
        evidence.append({'segment':i+1,'start':seg.start,'end_with_tail':end,
                         'frames':len(ks),'present':sum(frames[k] is not None for k in ks),
                         'unresolved':sum(frames[k] is not None and frames[k][0]<0 for k in ks)})
hard, soft = board_findings(spec, segments, {main_url:probe}, urls, profile='wta',tail=.18)

build_path = ROOT/'repo/tools/build_match_reel.py'
text = build_path.read_text()
tree = ast.parse(text)
func = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dissolve_filtergraph')
native_source = ast.get_source_segment(text,func)
ns = {'AUDIO_RATE':'48000'}
exec(compile(ast.Module(body=[func],type_ignores=[]),str(build_path),'exec'),ns)
visual_defaults = {'cx':.5,'track':False,'fit':'crop','speed':1,'crop_zoom':1,'fill_y':.5,
                   'square_pan':[], 'contain_keep':None}
seams=[]
for i,(left,right) in enumerate(zip(spec['segments'],spec['segments'][1:])):
    if not all('start' in r and 'end' in r for r in (left,right)):
        continue
    if abs(float(left['end'])-float(right['start']))>1e-8:
        continue
    if left.get('source',primary) != right.get('source',primary):
        continue
    diffs={k:[left.get(k,v),right.get(k,v)] for k,v in visual_defaults.items()
           if left.get(k,v)!=right.get(k,v)}
    join=float(left['end'])
    lengths=[(left['end']-left['start'])/left.get('speed',1),
             (right['end']-right['start'])/right.get('speed',1)]
    seams.append({'segments':[i+1,i+2],'source_join':join,'visual_parameter_differences':diffs,
                  'frame_index':round(join*25),'frame_aligned_at25fps':abs(join*25-round(join*25))<1e-7,
                  'source_overlap':[join,round(join+.18,8)],'omitted_source_seconds':0,
                  'native_filtergraph':ns['dissolve_filtergraph'](lengths,.18),
                  'result':'continuous_source_mapping' if not diffs else 'review_visual_change'})
required={174.8,237.0,256.8,261.6}
assert required.issubset({s['source_join'] for s in seams})
assert all(not s['visual_parameter_differences'] and s['frame_aligned_at25fps'] for s in seams)
assert abs((256.8-246.96)+(261.6-256.8)+(276.6-261.6)-(276.6-246.96))<1e-8
report={
 'status':'pass' if not hard and not soft else 'review',
 'segments_count':len(spec['segments']),
 'spec_path':str(spec_path),'spec_sha256':sha(spec_path),
 'source_sha256':probe['_board_augmentation']['source_sha256'],
 'augmented_probe':str(probe_path),'augmented_probe_sha256':sha(probe_path),
 'original_probe_sha256':sha(OUT/'probe.original.json'),
 'original_probe_unchanged':sha(ROOT/'probe/probe.json')==sha(OUT/'probe.original.json'),
 'all_original_nonboard_fields_preserved':True,'original_board_preserved_verbatim':True,
 'coverage':[t0,t0+len(frames)/fps],'fps':fps,'scanned_frames':len(frames),
 'native_board_findings':{'hard':hard,'soft':soft},'selected_segments':evidence,
 'audio_only_source_continuous_seams':seams,
 'complete_match_point_source_range':[246.96,276.6],
 'complete_match_point_length_seconds':29.64,
 'board_findings_invocation':'Unchanged native function, using minimal objects with only its consumed Segment fields; source keys, scorebox overrides, and score windows follow native parser semantics. Main source only.',
 'transition_explanation':'Each left part includes0.18s natural source continuation. At the nominal boundary xfade overlaps that tail with the right part starting at the exact same source instant. Same source/crop/speed/fps means no omitted or serially repeated footage. Native triangular acrossfade mixes synchronized source audio after sample-count normalization.',
 'dissolve_filtergraph_source_sha256':hashlib.sha256(native_source.encode()).hexdigest(),
 'limits':['Native board_findings only; no full spec parser or full dry-run claim.',
           'Continuity checked against native transition logic and exact frame alignment; no final video render was performed. Encoded seams and per-segment scoreboard placement still require normal final QA.',
           'This pass covers main-source board evidence only and does not approve the separate720p replay source or its audio.']}
(OUT/'current-spec-board-and-seam-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':report['status'],'spec_sha256':report['spec_sha256'],
                  'findings':report['native_board_findings'],'seams':[s['source_join'] for s in seams],
                  'selected_frames':sum(e['frames'] for e in evidence),
                  'original_probe_unchanged':report['original_probe_unchanged']},indent=2))

"""Local partial-source board evidence, using unchanged production geometry."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT / 'repo/tools'))
import probe_board as pb
import wta_scoreboard as ws

SOURCE = ROOT / 'source/source.mp4'
PROBE = ROOT / 'probe/probe.json'
EXPECTED = 'c0d6fcc41bab67e076881811aaeb1d2093289e1bde06daf4985cef95527f30a9'
BOX = (90, 830, 520, 990)
START, STOP, FPS = 24.8, 276.8, 25

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

source_hash = sha(SOURCE)
assert source_hash == EXPECTED
assert SOURCE.stat().st_size == 150731647
original_bytes = PROBE.read_bytes()
original_hash = hashlib.sha256(original_bytes).hexdigest()
original = json.loads(original_bytes)
assert original['width'] == 1920 and original['height'] == 1080
assert float(original['fps_value']) == FPS
(OUT / 'probe.original.json').write_bytes(original_bytes)
code_paths = ['probe_board.py', 'wta_scoreboard.py', 'atp_scoreboard.py', 'build_match_reel.py']
code_hashes = {name: sha(ROOT / 'repo/tools' / name) for name in code_paths}
commit = subprocess.check_output(['git', '-C', str(ROOT / 'repo'), 'rev-parse', 'HEAD'], text=True).strip()

x0, y0, x1, y1 = BOX
width, height = min(1920 - x0, ws.SCAN_W), y1 - y0
frames, errors, present = [], [], 0
body_bounds, header_bounds, all_bounds = [], [], []
geometry_path = OUT / 'native-geometry.frames.jsonl'
with geometry_path.open('w') as dst:
    for k, band in enumerate(pb._decode(SOURCE, (x0, y0, width, height), START, STOP, FPS)):
        record = {'index': k, 'source_frame': round(START * FPS) + k,
                  'source_time': round(START + k / FPS, 8), 'origin': [x0, y0]}
        try:
            geometry = ws.frame_geometry(band, cap=x1 - x0)
            record['present'] = geometry is not None
            if geometry is None:
                frames.append(None)
            else:
                # frame_geometry retains one antialias row outside the measured
                # two-player body. Recover its exact interior for native cap=None
                # and cap=1 readings; no thresholds or production code are changed.
                body = geometry['body']
                lo = body[1] + 1 if body[1] > 0 else 0
                hi = body[3] - 1 if body[3] < height else height
                interior = band[lo:hi]
                raw = ws.board_edge(interior, cap=None)
                anchor = ws.board_edge(interior, cap=1)
                if raw is None:
                    raise AssertionError('Present native geometry has no native body edge')
                anchor = int(anchor) if anchor is not None and anchor > 1 else None
                if anchor is not None and int(raw) != int(geometry['edge']):
                    raise AssertionError('Signature-anchored raw edge differs from production geometry')
                raw_abs = -1 if raw >= width and anchor is None else x0 + int(raw)
                anchor_abs = None if anchor is None else x0 + anchor
                frames.append((raw_abs, anchor_abs))
                present += 1
                def absolute(b):
                    return None if b is None else [x0+b[0], y0+b[1], x0+b[2], y0+b[3]]
                record.update({'body': absolute(body), 'header': absolute(geometry['header']),
                               'bounds': absolute(geometry['bounds']),
                               'edge_abs': x0 + int(geometry['edge']), 'raw_abs': raw_abs,
                               'anchor_abs': anchor_abs,
                               'rows_sha256': hashlib.sha256(json.dumps(geometry['rows'], separators=(',', ':')).encode()).hexdigest()})
                body_bounds.append(record['body'])
                all_bounds.append(record['bounds'])
                if record['header']:
                    header_bounds.append(record['header'])
        except Exception as exc:
            errors.append({'index': k, 'source_time': record['source_time'], 'error': str(exc)})
            record['error'] = str(exc)
            # Failure is never disguised as an absent board or promoted to a scan.
        dst.write(json.dumps(record, separators=(',', ':')) + '\n')
        if (k + 1) % 500 == 0:
            print(json.dumps({'scanned_frames': k+1, 'present': present, 'errors': len(errors)}), flush=True)

assert k + 1 == 6300, k + 1
if errors:
    write_json(OUT / 'board-preflight-report.json', {'status':'failed', 'errors':errors, 'source_sha256':source_hash})
    raise RuntimeError(f'{len(errors)} geometry errors; no augmented probe produced')
assert len(frames) == 6300
geometry_hash = sha(geometry_path)
record = {'present': present, 'unresolved': sum(f is not None and f[0] < 0 for f in frames),
          'runs': pb._rle(frames)}
scan = {'box': list(BOX), 'frames': len(frames), 'profiles': {'wta': record}}
assert pb.frames_of(scan, 'wta') == frames
augmented = dict(original)
augmented['_archived_board_preserved'] = original.get('board')
augmented['board'] = {'version':1, 'fps':FPS, 't0':START, 'frames':len(frames), 'scans':[scan]}
augmented['_board_augmentation'] = {
    'source_sha256': source_hash, 'source_bytes': SOURCE.stat().st_size,
    'original_probe_sha256': original_hash, 'geometry_sha256': geometry_hash,
    'source_range': [START, STOP], 'source_range_semantics':'half-open',
    'scope':'Real contiguous partial-source board-only scan. Original full-source non-board probe fields retained. No download or new whole-source probe.',
    'method':'Unchanged wta_scoreboard.frame_geometry(cap=430), with probe_board._decode at native 25fps. Native board_edge on its body supplies raw/signature anchor RLE. Search band is not treated as an opaque rectangle.',
    'code_commit':commit, 'code_sha256':code_hashes,
    'original_board_preserved_at':'_archived_board_preserved'}
augmented_path = OUT / 'probe.augmented.json'
write_json(augmented_path, augmented)
assert PROBE.read_bytes() == original_bytes
assert all(augmented[key] == value for key,value in original.items() if key != 'board')
assert augmented['_archived_board_preserved'] == original['board']
assert code_hashes == {name:sha(ROOT/'repo/tools'/name) for name in code_paths}
def union(bounds):
    return [min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)] if bounds else None
report = {
    'status':'scan_pass_pending_recipe_check', 'created_utc':datetime.now(timezone.utc).isoformat(),
    'source_path':str(SOURCE), 'source_sha256':source_hash, 'source_bytes':SOURCE.stat().st_size,
    'source_metadata_from_restored_probe':{k:original[k] for k in ['width','height','fps','fps_value','duration']},
    'original_probe':str(PROBE), 'original_probe_sha256':original_hash,
    'original_probe_unchanged':True, 'all_original_nonboard_fields_preserved':True,
    'original_board_preserved_verbatim':True, 'code_commit':commit, 'code_sha256':code_hashes,
    'source_range':[START,STOP], 'range_semantics':'half-open', 'fps':FPS, 'scanned_frames':len(frames),
    'search_box':list(BOX), 'actual_scan_width':width, 'present_frames':present,
    'absent_frames':len(frames)-present, 'unresolved_frames':record['unresolved'], 'geometry_errors':errors,
    'body_union':union(body_bounds), 'header_union':union(header_bounds), 'graphic_union':union(all_bounds),
    'geometry_path':str(geometry_path), 'geometry_sha256':geometry_hash,
    'augmented_probe':str(augmented_path), 'augmented_probe_sha256':sha(augmented_path),
    'native_board_findings':{'status':'awaiting_restored_recipe'},
    'limits':['Native geometry exceptions and probe-compatibility audit; no final encoded video or placed scoreboard QA.',
              'No audio verification, alternate replay approval, publication, spec mutation or production code changes.']}
write_json(OUT / 'board-preflight-report.json', report)
print(json.dumps({'report':str(OUT/'board-preflight-report.json'),'report_sha256':sha(OUT/'board-preflight-report.json'),
                  'augmented_probe':str(augmented_path),'augmented_probe_sha256':sha(augmented_path),
                  'geometry_sha256':geometry_hash,'scanned_frames':len(frames), 'geometry_errors':errors,
                  'present_frames':present,'original_probe_sha256':original_hash}), flush=True)

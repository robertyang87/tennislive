"""Measure the final helper with exact native inputs and mixer commands.

Requires the independently verified extended experiment inputs. No publication,
TTS synthesis, external network request or production output directory is used.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inputs', type=Path, required=True)
parser.add_argument('--outdir', type=Path, required=True)
args = parser.parse_args()
root = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode().strip())
sys.path[:0] = [str(root / 'tools'), str(root / 'src')]
import reel_join_fusion as fusion

data = json.loads((args.inputs / 'result.json').read_text())
commands = {row['name']: row['argv'] for row in data['commands']}
parts = [args.inputs / row['name'] for row in data['parts']]
for row, part in zip(data['parts'], parts):
    assert hashlib.sha256(part.read_bytes()).hexdigest() == row['sha256']
native_join = commands['baseline-join'][commands['baseline-join'].index('-filter_complex') + 1]
native_final = commands['baseline-burn'][commands['baseline-burn'].index('-filter_complex') + 1]
plan, reason = fusion.plan(native_join, len(parts))
assert plan and not reason
args.outdir.mkdir(parents=True, exist_ok=True)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def packets(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_packets',
        '-show_data_hash', 'sha256', '-show_entries',
        'packet=pts,dts,duration,data_hash,side_data_list', '-of', 'json', str(path)]))['packets']

trials = []
for repeat in range(3):
    pair = []
    for variant in ['legacy', 'fusion']:
        folder = args.outdir / f'{repeat}-{variant}'
        folder.mkdir(exist_ok=True)
        joined, mixed, final = (folder / name for name in ['joined.mp4', 'mixed.m4a', 'final.mp4'])
        replacements = {str(args.inputs / 'joined.mp4'): str(joined),
                        str(args.inputs / 'baseline-mixed.m4a'): str(mixed),
                        str(args.inputs / 'baseline.mp4'): str(final)}
        pending = []
        for stage, name in [('join', 'baseline-join'), ('mix', 'baseline-mix'), ('burn', 'baseline-burn')]:
            argv = [replacements.get(str(arg), str(arg)) for arg in commands[name]]
            if variant == 'fusion':
                if stage == 'join':
                    argv[argv.index('-filter_complex') + 1] = plan.clock_graph()
                elif stage == 'burn':
                    start, filter_at = argv.index('-i'), argv.index('-filter_complex')
                    extras = argv[start + 4:filter_at]
                    argv = (argv[:start] + [a for p in parts for a in ['-i', str(p)]]
                            + ['-i', str(mixed)] + extras + argv[filter_at:])
                    argv[argv.index('-filter_complex') + 1] = plan.final_graph(native_final)
                    argv = [f'{len(parts)}:a:0' if a == '1:a:0' else a for a in argv]
            pending.append((stage, argv))
        timings, trace = {}, []
        started = time.perf_counter()
        for stage, argv in pending:
            before = time.perf_counter()
            result = subprocess.run(argv, capture_output=True, text=True, check=True)
            timings[stage] = time.perf_counter() - before
            trace.append({'stage': stage, 'argv': argv, 'returncode': result.returncode})
        if variant == 'fusion':
            before = time.perf_counter()
            fusion.require_matching_frame_clock(joined, final)
            timings['runtime_frame_clock_check'] = time.perf_counter() - before
        elapsed = time.perf_counter() - started
        clock = fusion.video_clock(final)
        audio = packets(final)
        join_audio = packets(joined)
        row = {'repeat': repeat, 'variant': variant, 'seconds': elapsed,
               'stage_seconds': timings, 'video_rate': str(clock[0]), 'frames': len(clock[1]),
               'audio_packets': len(audio), 'audio_packets_sha256': digest(audio),
               'join_audio_packets_sha256': digest(join_audio),
               'final_sha256': hashlib.sha256(final.read_bytes()).hexdigest(),
               'final_bytes': final.stat().st_size, 'commands': trace}
        pair.append((row, clock, audio, join_audio))
        print(repeat, variant, round(elapsed, 4), flush=True)
    assert pair[0][1:] == pair[1][1:], 'Frame clock or original audio differs'
    trials.extend(p[0] for p in pair)
    # These are regenerable experiment intermediates, never publication inputs.
    for variant in ['legacy', 'fusion']:
        for file in (args.outdir / f'{repeat}-{variant}').iterdir():
            file.unlink()

record = {'kind': 'final-production-helper-controlled-native-media-benchmark',
          'publication_approved': False, 'message_posts': 0,
          'source_sha256': data['source_sha256'],
          'base_commit': 'f3b37de35e26eb23f05e275d0a74eb7048a0589c',
          'implementation_sha256': hashlib.sha256((root / 'tools/reel_join_fusion.py').read_bytes()).hexdigest(),
          'builder_sha256': hashlib.sha256((root / 'tools/build_match_reel.py').read_bytes()).hexdigest(),
          'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'input_report_sha256': hashlib.sha256((args.inputs / 'result.json').read_bytes()).hexdigest(),
          'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
          'cpu_count': os.cpu_count(), 'trials': trials,
          'median_seconds': {v: statistics.median(t['seconds'] for t in trials if t['variant'] == v)
                             for v in ['legacy', 'fusion']},
          'limits': ['Same five preencoded native parts and mixer inputs, one filter-complex thread in both paths.',
                     'Three alternating pairs, no cold source preparation or full pipeline/hosted runner measurement.',
                     'Final fusion helper and new frame-clock probe overhead included; part-duration/source/QC gates outside timing.',
                     'Every pair has exact audio join/final packet equality including PTS/duration/hash/side-data and final displayed frame clock.']}
(args.outdir / 'production-bridge-benchmark.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record['median_seconds']))

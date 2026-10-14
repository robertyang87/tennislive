"""Reuse complete native frame-mask sequences, never final media QC conclusions.

The content key binds source bytes, every native geometry/timing input, detector
implementations and decoder versions. Score pixels still come from the original
video at each frame; this cache contains alpha masks only.
"""
from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import marshal
import math
import os
import shutil
import subprocess
import tempfile
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from fractions import Fraction
from pathlib import Path

PROFILES = {
    'us-open': 'scoreboard_geometry', 'rna-slam': 'rna_scoreboard',
    'atp': 'atp_scoreboard', 'wta': 'wta_scoreboard',
    'itf-bjk': 'itf_scoreboard', 'lavercup': 'lavercup_scoreboard',
}
SCHEMA = 1
MAX_ENTRIES = 32
MAX_BYTES = 256 * 1024 * 1024
INPUT_FIELDS = ('source', 'start', 'end', 'speed', 'score_inset',
                'score_inset_windows', 'score_inset_spans', 'score_inset_auto')
_CACHE_WRITE_LOCK = threading.Lock()


def _json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _freeze(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_freeze(v) for v in value]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: _freeze(v) for k, v in sorted(value.items())}
    raise TypeError('Non-scalar detector configuration')


def _function_identity(fn) -> dict:
    def relocated(code):
        return code.replace(co_filename='', co_consts=tuple(
            relocated(v) if isinstance(v, types.CodeType) else v for v in code.co_consts))
    identity = {'code': hashlib.sha256(marshal.dumps(relocated(fn.__code__))).hexdigest()}
    for name, value in [('defaults', fn.__defaults__), ('kwdefaults', fn.__kwdefaults__)]:
        try:
            identity[name] = _freeze(value)
        except TypeError:
            # Such callables cannot be safely shared across processes.
            identity[name] = {'process_object': id(value)}
    if fn.__closure__:
        identity['closure'] = []
        for cell in fn.__closure__:
            try:
                identity['closure'].append(_freeze(cell.cell_contents))
            except TypeError:
                identity['closure'].append({'process_object': id(cell.cell_contents)})
    return identity


def _implementation(module) -> dict:
    """Bind transitive local functions and their module constants, plus this wrapper."""
    import numpy
    pending = [module]
    seen = {}
    root = Path(__file__).resolve().parent
    while pending:
        current = pending.pop()
        path = Path(current.__file__).resolve()
        if path in seen:
            continue
        facts = {'source_sha256': _sha(path), 'functions': {}, 'constants': {}}
        seen[path] = facts
        for name, value in sorted(vars(current).items()):
            if name.startswith('__'):
                continue
            if isinstance(value, types.FunctionType):
                facts['functions'][name] = _function_identity(value)
                owner = inspect.getmodule(value)
                if owner and getattr(owner, '__file__', None):
                    origin = Path(owner.__file__).resolve()
                    if origin.parent == root:
                        pending.append(owner)
            else:
                try:
                    facts['constants'][name] = _freeze(value)
                except TypeError:
                    pass
    return {'wrapper_sha256': _sha(Path(__file__)),
            'modules': {p.name: value for p, value in sorted(seen.items())},
            'python': list(__import__('sys').version_info[:3]), 'numpy': numpy.__version__,
            'executables': {tool: {'binary_sha256': _sha(Path(shutil.which(tool))),
                'version': subprocess.check_output([tool, '-version'], text=True)}
                for tool in ('ffmpeg', 'ffprobe')}}


def _recipe(profile, module, sources, segments, fps, tail) -> dict:
    hashes = {}
    per_path = {}
    for name, source in sorted(sources.items()):
        path = Path(source).resolve()
        if path not in per_path:
            per_path[path] = _sha(path)
        hashes[name] = per_path[path]
    rows = []
    for index, segment in enumerate(segments):
        if not segment.score_inset:
            rows.append({'index': index, 'score_inset': None})
            continue
        rows.append({'index': index, **{field: _freeze(getattr(segment, field, None))
                                       for field in INPUT_FIELDS}})
    return {'schema': SCHEMA, 'profile': profile, 'native_profile': module.PROFILE,
            'source_sha256': hashes, 'segments': rows, 'fps': str(fps),
            'rate': [Fraction(fps).numerator, Fraction(fps).denominator],
            'tail': tail, 'implementation': _implementation(module)}


def _probe(path: Path) -> dict:
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-show_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,width,height,r_frame_rate,nb_read_frames:frame=pts_time',
         '-of', 'json', str(path)], capture_output=True, text=True, check=False)
    if result.returncode or result.stderr.strip():
        raise ValueError(f'Unreadable mask video (ffprobe rc={result.returncode}): '
                         f'{result.stderr.strip()[-500:]}')
    metadata = json.loads(result.stdout)
    streams = metadata['streams']
    if len(streams) != 1:
        raise ValueError('Missing mask video stream')
    stream = streams[0]
    rate = Fraction(stream['r_frame_rate'])
    timestamps = metadata['frames']
    if len(timestamps) != int(stream['nb_read_frames']) or any(
            abs(Fraction(frame['pts_time']) - Fraction(i, 1) / rate) > Fraction(1, 1000)
            for i, frame in enumerate(timestamps)):
        raise ValueError('Mask frames are not aligned to the native frame clock')
    return {'codec': stream['codec_name'], 'width': int(stream['width']),
            'height': int(stream['height']), 'fps': str(Fraction(stream['r_frame_rate'])),
            'frames': int(stream['nb_read_frames'])}


def _validate(records, states, files, fps, recipe) -> None:
    indices = {r['index'] for r in recipe['segments'] if r['score_inset']}
    if ({r['segment'] for r in records} != indices or len(records) != len(indices)
            or {s['index'] for s in states} != indices or len(states) != len(indices)):
        raise ValueError('Mask segment coverage mismatch')
    by_index = {s['index']: s for s in states}
    for record in records:
        state = by_index[record['segment']]
        box = state['score_inset']
        if (len(box) != 4 or any(type(v) is not int for v in box)
                or box[0] < 0 or box[1] < 0 or box[2] <= box[0] or box[3] <= box[1]):
            raise ValueError('Invalid resolved mask geometry')
        path = files[record['segment']]
        if path.is_symlink() or _sha(path) != record['mask_sha256']:
            raise ValueError('Mask bytes changed')
        info = _probe(path)
        if (info != {'codec': 'ffv1', 'width': box[2] - box[0], 'height': box[3] - box[1],
                     'fps': str(Fraction(fps)), 'frames': record['frames']}
                or type(record['frames']) is not int or record['frames'] <= 0
                or not 0 < record['present_frames'] <= record['frames']):
            raise ValueError('Mask frame count/rate/dimensions mismatch')
        if 'source_bounds' in record and record['source_bounds'] != box:
            raise ValueError('Mask scan and resolved bounds differ')


def _atomic_copy(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, prefix='.mask-', delete=False) as temp:
        staged = Path(temp.name)
    try:
        shutil.copyfile(source, staged)
        os.replace(staged, dest)
    finally:
        staged.unlink(missing_ok=True)


def _native(module, profile, sources, segments, outdir, fps, tail, spec_path):
    if profile == 'us-open':
        return module.resolve_masks(sources, segments, outdir, spec_path, fps, tail)
    return module.resolve_masks(sources, segments, outdir, fps, tail)


def _restore(entry, key, recipe, segments, outdir, fps, spec_path, verify_inputs):
    manifest = json.loads((entry / 'manifest.json').read_text())
    checksum = manifest.pop('manifest_sha256')
    if (checksum != hashlib.sha256(_json(manifest)).hexdigest() or manifest['key'] != key
            or manifest['recipe'] != recipe or manifest['schema'] != SCHEMA):
        raise ValueError('Mask bundle identity changed')
    records, states = manifest['records'], manifest['states']
    files = {r['segment']: entry / 'masks' / f"segment-{r['segment']+1:02d}.mkv" for r in records}
    _validate(records, states, files, fps, recipe)
    proof = {'status': 'pass', 'profile': recipe['native_profile'], 'segments': []}
    if recipe['profile'] == 'us-open':
        proof['spec_sha256'] = _sha(Path(spec_path))
    destinations = {}
    for record in records:
        index = record['segment']
        dest = Path(outdir) / 'score_masks' / f'segment-{index+1:02d}.mkv'
        _atomic_copy(files[index], dest)
        if _sha(dest) != record['mask_sha256']:
            raise ValueError('Mask copy bytes changed')
        destinations[index] = dest
        proof['segments'].append({**record, 'mask': str(dest)})
    if not verify_inputs():
        raise ValueError('Source or detector changed during mask restoration')
    # Commit the newly rebound scan report before touching caller geometry.
    # A failed write must leave original boxes intact for the native fallback.
    target = Path(outdir) / 'scoreboard_qc.json'
    with tempfile.NamedTemporaryFile(dir=outdir, prefix='.scoreboard-cached-', delete=False) as temp:
        staged = Path(temp.name)
    try:
        staged.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
    # Apply resolver-mutated geometry only after every mask has been verified.
    for state in states:
        segment = segments[state['index']]
        segment.score_inset = tuple(state['score_inset'])
        segment.score_inset_mask = str(destinations[state['index']].resolve())
        spans = state['score_inset_spans']
        segment.score_inset_spans = tuple(tuple(v) for v in spans) if spans is not None else None
    return target


def _store(root, key, recipe, segments, outdir, fps):
    proof = json.loads((Path(outdir) / 'scoreboard_qc.json').read_text())
    if proof['status'] != 'pass' or proof['profile'] != recipe['native_profile']:
        raise ValueError('Native resolver did not complete a valid scan')
    records = [{k: v for k, v in r.items() if k != 'mask'} for r in proof['segments']]
    states = [{'index': i, 'score_inset': list(s.score_inset),
               'score_inset_spans': _freeze(s.score_inset_spans)}
              for i, s in enumerate(segments) if s.score_inset]
    files = {r['segment']: Path(outdir) / 'score_masks' / f"segment-{r['segment']+1:02d}.mkv" for r in records}
    _validate(records, states, files, fps, recipe)
    entries = root / 'entries'; entries.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.building-', dir=root))
    try:
        for index, source in files.items():
            _atomic_copy(source, temporary / 'masks' / f'segment-{index+1:02d}.mkv')
            record = next(r for r in records if r['segment'] == index)
            if _sha(temporary / 'masks' / f'segment-{index+1:02d}.mkv') != record['mask_sha256']:
                raise ValueError('Staged mask copy bytes changed')
        manifest = {'schema': SCHEMA, 'key': key, 'recipe': recipe, 'records': records, 'states': states}
        manifest['manifest_sha256'] = hashlib.sha256(_json(manifest)).hexdigest()
        (temporary / 'manifest.json').write_bytes(_json(manifest))
        target = entries / key
        if target.exists():
            shutil.rmtree(target)
        os.replace(temporary, target)
        (root / '.dirty').write_text(key + '\n')
        _prune(root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _prune(root):
    entries = [p for p in (root / 'entries').iterdir()
               if p.is_dir() and not p.is_symlink() and len(p.name) == 64
               and all(c in '0123456789abcdef' for c in p.name)]
    sizes = {p: sum(f.stat().st_size for f in p.rglob('*') if f.is_file() and not f.is_symlink())
             for p in entries}
    total = sum(sizes.values())
    for entry in sorted(entries, key=lambda p: p.stat().st_mtime_ns):
        if len(entries) <= MAX_ENTRIES and total <= MAX_BYTES:
            break
        shutil.rmtree(entry); entries.remove(entry); total -= sizes[entry]


def _cgroup_value(name):
    try:
        return (Path('/sys/fs/cgroup') / name).read_text().strip()
    except OSError:
        return ''


def point_scan_workers(count, peak_bytes=2 * 1024**3):
    """At most two decoders/detectors, bounded by CPU quota and memory capacity."""
    try:
        requested = int(os.environ.get('TENNISLIVE_SCOREBOARD_MASK_WORKERS', '2'))
    except ValueError:
        requested = 1
    cpus = os.cpu_count() or 1
    try:
        cpus = min(cpus, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        pass
    try:
        quota, period = _cgroup_value('cpu.max').split()
        if quota != 'max':
            cpus = min(cpus, max(1, int(quota) // int(period)))
    except (ValueError, ZeroDivisionError):
        pass
    # capture_output temporarily holds both raw-frame chunks and their joined
    # bytes. Reserve 1 GiB for the parent and 2 GiB for each concurrent scanner.
    limits = []
    try:
        limits.append(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE'))
    except (AttributeError, OSError, ValueError):
        pass
    try:
        limits.append(int(_cgroup_value('memory.max')))
    except ValueError:
        pass
    memory_workers = max(1, (min(limits) - 1024**3) // peak_bytes) if limits else 1
    return max(1, min(count, requested, cpus, memory_workers, 2))


def _scan_peak_bytes(jobs, fps, tail):
    # Account for longer/high-fps windows instead of assuming every point fits
    # in the normal two-GiB allowance. Full decoded RGB is retained by scan_geometry.
    width = importlib.import_module(PROFILES['wta']).SCAN_W
    peaks = [2 * 1024**3]
    for _, part, *_ in jobs:
        frames = math.ceil((part.end - part.start + tail * part.speed) * float(Fraction(fps)))
        height = part.score_inset[3] - part.score_inset[1]
        peaks.append(frames * height * (width * 3 * 2 + 128) + 256 * 1024**2)
    return max(peaks)


def _resolve_wta_point(job):
    index, part, source, partdir, fps, tail, spec_path, root = job
    proof_path = resolve_masks_cached(
        'wta', {part.source: source}, [part], partdir, fps, tail,
        spec_path=spec_path, cache_root=root)
    proof = json.loads(proof_path.read_text())
    record, = proof['segments']
    return index, part, record


def _incremental_wta(sources, segments, outdir, fps, tail, spec_path, root):
    """Reuse unchanged points after a window edit, with the full bundle validators.

    WTA's resolver reads only its segment's source and geometry. Profiles that
    read spec-wide calibration retain their original whole-bundle path.
    """
    records, resolved = [], []
    native_profile = importlib.import_module(PROFILES['wta']).PROFILE
    with tempfile.TemporaryDirectory(dir=outdir, prefix='.mask-points-') as temporary:
        jobs = []
        for index, segment in enumerate(segments):
            if not segment.score_inset:
                continue
            # Normalise index and ignore unrelated sources so card insertion,
            # reordering and another point's source do not invalidate this point.
            part = copy(segment)
            partdir = Path(temporary) / str(index)
            jobs.append((index, part, sources[part.source], partdir, fps, tail, spec_path, root))
        workers = point_scan_workers(len(jobs), _scan_peak_bytes(jobs, fps, tail))
        print(f'[score-mask-cache] {workers} bounded WTA scan workers')
        if workers > 1:
            # map preserves spec order, including when later points finish first.
            # Every worker owns its geometry and directory. Join all workers
            # before exposing any resolved caller geometry or complete report.
            with ThreadPoolExecutor(max_workers=workers) as pool:
                measured = list(pool.map(_resolve_wta_point, jobs))
        else:
            measured = [_resolve_wta_point(job) for job in jobs]
        for index, part, record in measured:
            dest = Path(outdir) / 'score_masks' / f'segment-{index+1:02d}.mkv'
            _atomic_copy(Path(record['mask']), dest)
            if _sha(dest) != record['mask_sha256']:
                raise ValueError('Incremental mask copy bytes changed')
            records.append({**record, 'segment': index, 'mask': str(dest)})
            resolved.append((segments[index], part, dest))
    target = Path(outdir) / 'scoreboard_qc.json'
    target.write_text(json.dumps({'status': 'pass', 'profile': native_profile,
                                 'segments': records}, ensure_ascii=False, indent=2) + '\n')
    for segment, part, dest in resolved:
        segment.score_inset = part.score_inset
        segment.score_inset_mask = str(dest.resolve())
        segment.score_inset_spans = part.score_inset_spans
    return target


def resolve_masks_cached(profile, sources, segments, outdir, fps, tail, *,
                         spec_path=None, cache_root=None) -> Path:
    """Run the exact native resolver on miss; restore its full frame sequence on hit."""
    if profile not in PROFILES:
        raise ValueError(f'Unsupported native mask profile: {profile}')
    module = importlib.import_module(PROFILES[profile])
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    root = (Path(cache_root) if cache_root is not None else Path(os.environ.get(
        'TENNISLIVE_SCOREBOARD_MASK_CACHE', str(Path.home() / '.cache/tennislive-scoreboard-masks')))).expanduser()
    try:
        recipe = _recipe(profile, module, sources, segments, fps, tail)
        key = hashlib.sha256(_json(recipe)).hexdigest()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        # Cache preparation is optional; preserve the native resolver's genuine
        # error behavior for unreadable sources or unrepresentable inputs.
        print(f'[score-mask-cache] preparation failed ({type(exc).__name__}: {exc}); '
              'native per-frame scan required')
        return _native(module, profile, sources, segments, outdir, fps, tail, spec_path)
    entry = root / 'entries' / key
    if entry.is_dir() and not entry.is_symlink():
        try:
            path = _restore(entry, key, recipe, segments, outdir, fps, spec_path,
                lambda: _recipe(profile, module, sources, segments_input(recipe), fps, tail) == recipe)
            print(f'[score-mask-cache] hit {key[:12]}: complete native per-frame alpha sequence')
            return path
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            print(f'[score-mask-cache] invalid/incomplete bundle ({type(exc).__name__}: {exc}); '
                  'native per-frame scan required')
    if profile == 'wta' and sum(bool(s.score_inset) for s in segments) > 1:
        path = _incremental_wta(sources, segments, outdir, fps, tail, spec_path, root)
    else:
        path = _native(module, profile, sources, segments, outdir, fps, tail, spec_path)
    try:
        # Detect source/config changes during the native scan before storing it.
        if _recipe(profile, module, sources, segments_input(recipe), fps, tail) != recipe:
            raise ValueError('Inputs changed during native mask scan')
        # Concurrent scans may save identical entries or prune the same cache.
        # Serialize commits/pruning; decode, detection and validation on read
        # remain parallel, with all original byte and frame checks intact.
        with _CACHE_WRITE_LOCK:
            _store(root, key, recipe, segments, outdir, fps)
        print(f'[score-mask-cache] stored {key[:12]}: complete native per-frame alpha sequence')
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f'[score-mask-cache] cache unavailable ({type(exc).__name__}: {exc}); '
              'native mask output retained')
    return path


def segments_input(recipe):
    """Recreate only the unchanged pre-resolver timing/geometry for post-scan binding."""
    return [types.SimpleNamespace(**{k: v for k, v in row.items() if k != 'index'})
            for row in recipe['segments']]

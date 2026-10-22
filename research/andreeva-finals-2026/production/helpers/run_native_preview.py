#!/usr/bin/env python3
"""Sample the current20-segment Andreeva with the real native caption renderer.

Usage: python run_native_preview_v3.py new-gs fresh-v3 --expect-spec-sha256 SHA
A unique tag is mandatory in practice: any existing request/log/output is refused.
All requested samples are built FIRST, then partitioned into batches of <=24.
This creates visual previews only, never final-film QC/publication approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path('/workspace/andreeva-finals-production')
HERE = Path(__file__).resolve().parent
REPO = Path('/workspace/tennislive-andreeva')
SPEC = REPO/'specs/reels/andreeva-finals-2026.json'
SOURCE_PATHS = ROOT/'native-source-paths.json'
COVER_SECONDS = 1.2
GROUPS = ('labels', 'captions', 'points', 'cards')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def timeline(spec: dict) -> dict:
    if len(spec['segments']) != 20:
        raise ValueError('Require current20-segment Andreeva spec; no preview of incomplete candidate')
    if spec.get('_render_blockers'):
        raise ValueError('Final spec still has _render_blockers')
    rows = {}
    cursor = COVER_SECONDS
    for number, seg in enumerate(spec['segments']):
        key = seg['_id']
        if key in rows:
            raise ValueError(f'Duplicate segment ID: {key}')
        length = seg['seconds'] if 'seconds' in seg else seg['end']-seg['start']
        if not isinstance(length, (int,float)) or not math.isfinite(length) or length <= .12:
            raise ValueError(f'Invalid preview segment length: {key}')
        rows[key] = {'offset':cursor, 'length':length, 'segment':seg, 'index':number}
        cursor += length
    return rows


def requested_samples(group: str, rows: dict) -> list[dict]:
    samples = []

    def add(key: str, relative: float, reason: str):
        row = rows[key]
        # Keep genuine samples within this segment. A label ending at the cut
        # has no observable AFTER frame; clamping is recorded, never hidden.
        bounded = max(.05, min(row['length']-.06, relative))
        film_time = round(row['offset']+bounded, 6)
        source_time = (row['segment']['start']+bounded
                       if 'start' in row['segment'] else None)
        prior = next((s for s in samples if s['id']==key and s['film_time']==film_time), None)
        annotation = {'why':reason, 'requested_segment_time':relative,
                      'boundary_clamped':abs(relative-bounded)>1e-9}
        if prior:
            prior['reasons'].append(annotation)
            return
        samples.append({'id':key, 'segment_index':row['index'],
                        'film_time':film_time, 'segment_time_requested':bounded,
                        'source_time_requested':source_time, 'reasons':[annotation]})

    def first_middle_last(key: str, reason: str):
        length = rows[key]['length']
        for t, position in ((.16,'first'),(length/2,'middle'),(length-.16,'last')):
            add(key,t,f'{reason}-{position}')

    def label_samples(key: str, both_sides: bool = False):
        seg=rows[key]['segment']
        label=seg.get('inset')
        if not label or label.get('kind')!='story_text' or 'start' not in seg:
            raise ValueError(f'Require actual-video story_text label: {key}')
        lo=label['show_after'];hi=lo+label['show_for']
        if not 0<=lo<hi<=rows[key]['length']+.001:
            raise ValueError(f'Invalid label bounds: {key}')
        targets=[(lo-.08,'before-label'),((lo+hi)/2,'label-middle'),
                 (hi-.08,'label-last'),(hi+.08,'after-label')]
        if both_sides:
            targets=[(lo-.08,'before-label-start'),(lo+.08,'after-label-start'),
                     (hi-.08,'before-label-end'),(hi+.08,'after-label-end')]
        for t,why in targets:
            add(key,t,why)

    videos=[k for k,r in rows.items() if 'start' in r['segment']]
    if group=='labels':
        for key in videos:
            if rows[key]['segment'].get('inset',{}).get('kind')=='story_text':label_samples(key)
    elif group=='captions':
        for key in videos:
            for n,cue in enumerate(rows[key]['segment'].get('quote',[]),1):
                add(key,(cue['at']+cue['end'])/2,f'complete-bilingual-cue-{n}-middle')
    elif group=='points':
        for key in videos:first_middle_last(key,'actual-full-point-or-person-answer')
    elif group=='cards':
        for key,row in rows.items():
            if 'title_card' in row['segment']:
                if row['segment'].get('inset') or row['segment'].get('title_card_story_label'):raise ValueError('No static live label')
                add(key,row['length']/2,'native-narration-chapter-middle')
    else:raise ValueError(group)
    return samples


def source_arguments(spec: dict, path: Path) -> tuple[list[str], dict]:
    payload=read_json(path)
    if isinstance(payload,dict) and 'sources' in payload:
        payload=payload['sources']
    if isinstance(payload,list):
        payload={row['key']:row['path'] for row in payload}
    if not isinstance(payload,dict):
        raise ValueError('native-source-paths-v3 must be a source-key/path dict or list')
    used={s['source'] for s in spec['segments'] if 'source' in s}
    arguments=[];bound={}
    for key in sorted(used):
        if key not in payload:
            raise ValueError(f'Missing actual native source path: {key}')
        value=payload[key]
        local=Path(value['path'] if isinstance(value,dict) else value).resolve(strict=True)
        if not local.is_file():
            raise ValueError(f'Not a source file: {local}')
        bound[key]=str(local)
        arguments.extend(['--source',f'{key}={local}'])
    # Deliberately omit unused stale map keys: native renderer rejects non-spec keys.
    return arguments,bound


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('group',choices=GROUPS)
    parser.add_argument('tag',nargs='?',default='fresh-native')
    parser.add_argument('--expect-spec-sha256')
    parser.add_argument('--plan-only',action='store_true',help='Print complete sample plan; write/render nothing')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',args.tag):
        parser.error('Tag must be a safe unique ASCII name, <=80 characters')
    spec_hash=sha256(SPEC)
    if args.expect_spec_sha256 and args.expect_spec_sha256!=spec_hash:
        raise ValueError('Spec SHA differs from the root-approved final candidate')
    spec=read_json(SPEC)
    samples=requested_samples(args.group,timeline(spec))
    batches=[samples[i:i+24] for i in range(0,len(samples),24)]
    if not samples or any(not 1<=len(batch)<=24 for batch in batches):
        raise ValueError('Invalid native preview batch size')
    prefix=f'{args.group}-{args.tag}'
    requested=HERE/f'preview-{prefix}-requested.json'
    index_file=HERE/f'preview-{prefix}-index.json'
    batch_paths=[]
    for number,batch in enumerate(batches,1):
        suffix=f'-batch{number}' if len(batches)>1 else ''
        batch_paths.append((ROOT/f'native-preview-{prefix}{suffix}',
                            HERE/f'preview-{prefix}-batch{number}.txt'))
    # Check EVERY destination before the first write/render; never partially overwrite.
    for target in (requested,index_file,*[p for pair in batch_paths for p in pair]):
        if target.exists() or target.is_symlink():
            raise FileExistsError(f'Prior evidence exists; choose a fresh tag: {target}')
    payload={'schema':'andreeva.native-preview-request.v1','group':args.group,'tag':args.tag,
             'spec_path':str(SPEC),'spec_sha256':spec_hash,'cover_seconds':COVER_SECONDS,
             'sample_count':len(samples),'batch_sizes':[len(b) for b in batches],
             'clock_note':'Film offsets use final spec seconds/end-start. Native renderer resolves its own source FPS; requested times are NOT quantized to 30fps.',
             'publication_approved':False,'final_encoded_film_qc':False,'samples':samples}
    if args.plan_only:
        print(json.dumps(payload,ensure_ascii=False,indent=2))
        return 0
    source_args,source_paths=source_arguments(spec,SOURCE_PATHS)
    payload.update(source_paths_file=str(SOURCE_PATHS),source_paths_sha256=sha256(SOURCE_PATHS),
                   source_paths=source_paths)
    requested.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    batch_evidence=[]
    for number,(batch,(outdir,log)) in enumerate(zip(batches,batch_paths),1):
        if sha256(SPEC)!=spec_hash or sha256(SOURCE_PATHS)!=payload['source_paths_sha256']:
            raise ValueError('Final spec/source map changed during native previews; stop before next batch')
        command=[sys.executable,'tools/preview_reel_captions.py','--spec',str(SPEC),
                 '--outdir',str(outdir),'--max-frames','24',
                 '--at',','.join(str(row['film_time']) for row in batch),*source_args]
        with log.open('x') as stream:
            result=subprocess.run(command,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT)
        print(args.group,f'batch{number}/{len(batches)}','requested',len(batch),
              'exit',result.returncode,'outdir',str(outdir),flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
        manifest=outdir/'preview_manifest.json'
        actual=read_json(manifest)
        if actual.get('spec_file_sha256')!=spec_hash:
            raise ValueError('Actual native manifest is bound to a different spec')
        batch_evidence.append({'batch':number,'requested_samples':batch,'manifest':str(manifest),
                               'manifest_sha256':sha256(manifest),'actual_sample_count':len(actual['samples']),
                               'actual_native_fps':actual['fps'],'log':str(log)})
    if sha256(SPEC)!=spec_hash:
        raise ValueError('Spec changed during final batch; samples must not be called current')
    index_file.write_text(json.dumps({'schema':'andreeva.native-preview-index.v1',
      'spec_sha256':spec_hash,'requested_path':str(requested),'requested_sha256':sha256(requested),
      'all_requested_samples_dispatched':sum(len(b) for b in batches)==len(samples),
      'publication_approved':False,'final_encoded_film_qc':False,'batches':batch_evidence},
      ensure_ascii=False,indent=2)+'\n')
    print('Preview index:',index_file,flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

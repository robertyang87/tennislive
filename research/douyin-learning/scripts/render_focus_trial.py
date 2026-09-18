"""Render an isolated, reversible evidence-magnifier trial; never publish.

Usage: python render_focus_trial.py SOURCE SPEC_JSON OUTPUT_DIR
Requires ffmpeg/ffprobe. All rectangles use source pixels; inspect source first.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def run(args):
    return subprocess.run(args, check=True, capture_output=True).stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source, spec_path, output = map(Path, sys.argv[1:])
    spec = json.loads(spec_path.read_text())
    if sha(source) != spec['source_sha256']:
        raise ValueError('Source hash changed; review coordinates again')
    output.mkdir(parents=True, exist_ok=True)
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    width, height = video['width'], video['height']
    start, duration = spec['start_seconds'], spec['duration_seconds']
    x, y, w, h = spec['crop_xywh']
    ox, oy = spec['inset_xy']
    scale = spec['scale']
    on, off = spec['visible_seconds']
    if not (0 <= start and 0 < duration <= 30 and start + duration <= float(probe['format']['duration'])):
        raise ValueError('Invalid clip interval')
    if not (0 <= x < x+w <= width and 0 <= y < y+h <= height and 1 < scale <= 3):
        raise ValueError('Invalid source rectangle or scale')
    if not (0 <= ox < ox+w*scale <= width and 0 <= oy < oy+h*scale <= height and 0 < on < off < duration):
        raise ValueError('Invalid inset or timing')
    if any(v % 2 for v in (x,y,w,h,ox,oy,w*scale,h*scale)):
        raise ValueError('Use even coordinates for chroma-safe boundaries')
    common = ['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(source),'-t',str(duration)]
    encode = ['-c:v','libx264','-preset','fast','-qp','0','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart']
    baseline, treatment = output/'A-baseline.mp4', output/'B-focus.mp4'
    run(common + ['-map','0:v:0','-map','0:a:0'] + encode + [str(baseline)])
    graph = (f'[0:v]split[base][roi];[roi]crop={w}:{h}:{x}:{y},'
             f'scale={w*scale}:{h*scale}:flags=lanczos[inset];'
             f"[base][inset]overlay={ox}:{oy}:enable='between(t,{on},{off})'[out]")
    run(common + ['-filter_complex',graph,'-map','[out]','-map','0:a:0'] + encode + [str(treatment)])
    def pcm(path):
        return run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-f','s16le','-'])
    def rgb(path, at):
        return run(['ffmpeg','-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'])
    audio_equal = pcm(baseline) == pcm(treatment)
    checks = []
    for at, active in [(on/2,False),((on+off)/2,True),((off+duration)/2,False)]:
        a,b = rgb(baseline,at),rgb(treatment,at)
        changed_inside = changed_outside = 0
        for row in range(height):
            for col in range(width):
                p=(row*width+col)*3
                if a[p:p+3] != b[p:p+3]:
                    # 2px chroma reconstruction halo around inset boundary.
                    inside = ox-2 <= col < ox+w*scale+2 and oy-2 <= row < oy+h*scale+2
                    if inside: changed_inside += 1
                    else: changed_outside += 1
        checks.append({'at':at,'active':active,'changed_inside':changed_inside,'changed_outside':changed_outside,
                       'passed':changed_outside==0 and (changed_inside>0 if active else changed_inside==0)})
    receipt={'rule_id':spec['rule_id'],'status':'rendered_qc','source_sha256':sha(source),
             'spec':spec,'audio_pcm_identical':audio_equal,'frame_checks':checks,
             'technical_qc_passed':audio_equal and all(c['passed'] for c in checks),
             'files':{p.name:sha(p) for p in (baseline,treatment)},
             'human_audio_review':False,'growth_validated':False,'published':False,
             'limitation':'12-second offline craft preview, not a full production video or audience experiment.'}
    (output/'qc-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    if not receipt['technical_qc_passed']:
        raise RuntimeError('Trial failed isolation QC; do not adopt')
    print(json.dumps(receipt,ensure_ascii=False))


if __name__ == '__main__':
    main()

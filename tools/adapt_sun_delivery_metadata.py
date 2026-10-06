#!/usr/bin/env python3
"""Normalize actual render metadata after final QA; never invent approval."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def normalize_render(movie, render, qa):
    digest = hashlib.sha256(movie.read_bytes()).hexdigest()
    size = movie.stat().st_size
    if qa.get('status') != 'PASS' or qa.get('video_sha256') != digest or qa.get('video_bytes') != size:
        raise ValueError('Final QA must PASS and bind current actual film bytes/SHA')
    if render.get('sha256', render.get('video_sha256')) != digest or render.get('bytes', render.get('video_bytes')) != size:
        raise ValueError('Renderer receipt does not bind current actual film')
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if (video['width'], video['height']) != (1080,1440) or not any(s['codec_type']=='audio' for s in probe['streams']):
        raise ValueError('Actual 3:4 film with audio required')
    return dict(render, video_sha256=digest, video_bytes=size, width=video['width'], height=video['height'], duration=float(probe['format']['duration']), actual_probe=probe)


def main():
    p=argparse.ArgumentParser();p.add_argument('--movie',type=Path,required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--qa',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=normalize_render(a.movie,json.loads(a.render.read_text()),json.loads(a.qa.read_text()))
    result['renderer_receipt_sha256']=hashlib.sha256(a.render.read_bytes()).hexdigest()
    result['final_qa_sha256']=hashlib.sha256(a.qa.read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()

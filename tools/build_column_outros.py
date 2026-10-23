#!/usr/bin/env python3
"""Rebuild the three active-column pictures; copy the frozen brand voice unchanged."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tennislive.render.webcards import _chromium_executable
from tennislive.video import column_outro, outro_page


def audio_hash(path: Path) -> str:
    """Hash encoded AAC packets; do not decode/scan/normalize the sound."""
    return subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0',
        '-c','copy','-f','hash','-hash','sha256','-'],check=True,capture_output=True,text=True).stdout.strip()


def probe(path: Path) -> dict:
    return json.loads(subprocess.run(['ffprobe','-v','error','-show_streams',
        '-show_format','-of','json',str(path)],check=True,capture_output=True,text=True).stdout)


def rebuild(column: str, voice_source: Path, chromium: str) -> dict:
    column = column_outro.normalize_column(column)
    info = probe(voice_source)
    video = next(s for s in info['streams'] if s['codec_type']=='video')
    if video['r_frame_rate'] != '60/1':
        raise ValueError('原母版必须为60fps，不能靠补帧制作新的动作母版')
    frames = int(video['nb_frames'])
    seconds = frames / 60
    dest = column_outro.master_path(column)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tennis-column-master-') as directory:
        picture = column_outro.render_picture(Path(directory)/'picture.mp4',column,
            seconds,'60',chromium)
        temporary = dest.with_name(dest.stem+'.tmp.mp4')
        try:
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(picture),'-i',str(voice_source),
                '-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(temporary)],check=True)
            out = probe(temporary)
            v = next(s for s in out['streams'] if s['codec_type']=='video')
            a = next(s for s in out['streams'] if s['codec_type']=='audio')
            if (v['width'],v['height'],v['r_frame_rate'],int(v['nb_frames'])) != (1080,1440,'60/1',frames):
                raise ValueError('新的片尾画幅、帧率或帧数与母版合同不符')
            if (a['sample_rate'],a['channels']) != ('48000',2):
                raise ValueError('原口播采样率与声道数不符')
            if audio_hash(temporary) != audio_hash(voice_source):
                raise ValueError('新的片尾音轨不是原母版的精确AAC字节')
            temporary.replace(dest)
            browser = json.loads(picture.with_suffix('.outro.json').read_text())['browser']
        finally:
            temporary.unlink(missing_ok=True)
    return {'column':column,'file':str(dest.relative_to(outro_page.ROOT)),
        'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'seconds':seconds,
        'fps':'60','frames':frames,'audio_packet_sha256':audio_hash(dest),'browser':browser}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--voice-source',type=Path,default=outro_page.MASTER)
    ap.add_argument('--column',action='append',choices=list(column_outro.COLUMNS))
    ap.add_argument('--workers',type=int,default=2)
    args = ap.parse_args()
    source = args.voice_source.resolve()
    if not source.is_file():
        raise SystemExit(f'原口播母版不存在：{source}')
    chromium = _chromium_executable()
    columns = args.column or list(column_outro.COLUMNS)
    with ThreadPoolExecutor(max_workers=max(1,min(2,args.workers))) as pool:
        records = list(pool.map(lambda c:rebuild(c,source,chromium),columns))
    target = outro_page.ROOT/'assets/brand/column_outros.json'
    old = json.loads(target.read_text()) if target.is_file() else {}
    merged = {x['column']:x for x in old.get('masters',[])}
    merged.update({x['column']:x for x in records})
    target.write_text(json.dumps({'narration':outro_page.NARRATION,'tagline':outro_page.TAGLINE,
        'voice_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'voice_packet_sha256':audio_hash(source),'masters':list(merged.values()),
        'audio_review':'Unchanged encoded audio copied from the existing production master; no new TTS or claimed listening.',
        'visual_contract':'Official account logo; rigid decelerating roll; brand-prefixed column title; corrected regulation court; 3:4 navy; fixed hold.'},
        ensure_ascii=False,indent=2))
    print(json.dumps(records,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

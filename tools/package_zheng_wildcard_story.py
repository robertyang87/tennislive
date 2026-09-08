#!/usr/bin/env python3
"""Package the reviewed Zheng episode for the existing explainer delivery path."""
import argparse, datetime, hashlib, json, subprocess, sys
from pathlib import Path
from build_zheng_wildcard_story import ROOT, E, segments
from tennislive.render.pushmsg import to_copy_page

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--video-url',required=True);a=ap.parse_args()
    out=a.outdir
    clip=out/'zheng-wildcards-template.mp4'
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(clip)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert (video['width'],video['height'])==(1080,1920)
    assert any(s['codec_type']=='audio' for s in probe['streams'])
    actual_duration = float(probe['format']['duration'])
    voice_paths = sorted(out.glob('voice_*.mp3'))
    assert len(voice_paths) == 15
    def seconds(path):
        return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))
    expected_duration = sum(seconds(p) for p in voice_paths) + E.LEAD_SILENCE + E.TAIL_SILENCE + seconds(ROOT/'assets/brand/outro_master.mp4')
    assert abs(actual_duration - expected_duration) < 0.5, 'Video and complete narration duration mismatch'
    subprocess.run(['ffmpeg','-v','error','-i',str(clip),'-f','null','-'],check=True)
    data=json.loads((ROOT/'specs/explainers/zheng-china-wuhan-wildcards.json').read_text())
    beats=segments(data)
    assert len(beats)==15
    assert all((out/f'slide_{i:02d}.jpg').stat().st_size>10000 for i in range(15))
    narration=json.loads((out/'narration.json').read_text())
    assert narration==[{'title':s.title,'narration':s.narration} for s in beats]
    AUDIENCE_ONLY = json.dumps(narration, ensure_ascii=False) + ''.join(s.label + s.title for s in beats)
    for internal_phrase in ('你的猜想', '我查了当前', '你提供的', '关键来了', '先分清', '先把规则', '那美网八强'):
        assert internal_phrase not in AUDIENCE_ONLY, 'Editorial conversation leaked into viewer copy'
    (out/'script.json').write_text(json.dumps(narration,ensure_ascii=False,indent=2))
    (out/'narration.json').write_text(json.dumps({'voice':E.DEFAULT_VOICE,'rate':'+22%','pitch':E.DEFAULT_PITCH,'segments':15,'subtitles':True,'script_sha256':hashlib.sha256((out/'script.json').read_bytes()).hexdigest()},indent=2))
    text=(ROOT/'docs/research/zheng-wildcards-publish-copy.md').read_text().split('## 置顶补充')[0].removeprefix('# 发布文案\n\n').strip()
    (out/'xiaohongshu.txt').write_text(text)
    (out/'copy.html').write_text(to_copy_page(text))
    (out/'wechat_title.txt').write_text('网球有故事修订版｜中网给了外卡，武网怎么办？')
    (out/'render.json').write_text(json.dumps({'video_url':a.video_url,'video_bytes':clip.stat().st_size,'duration':float(probe['format']['duration']),'qc':'passed'},indent=2))
    (out/'push.html').write_text(E.explainer_push_html(beats,out,date=datetime.date(2026,9,8),xhs_text=text))
    print('15 cards, narration, dimensions, audio and full decode passed')
if __name__=='__main__':main()

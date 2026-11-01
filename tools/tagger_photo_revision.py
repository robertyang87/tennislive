#!/usr/bin/env python3
"""Rebuild the requested Tagger visual revision from credited real photographs.

No TTS generation, invented scenes, source sound processing, or publication.
The prepared MP4s are silent native photo-sequence inputs, not match footage.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,json,math,subprocess,tempfile
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'assets/reel/tagger-single-backhand-story-2026'
OUT=ASSET/'visual-v2'
SPEC=ROOT/'specs/reels/tagger-single-backhand-story-2026.json'
WORDS=ROOT/'output/2026-11-01/reel/tagger-single-backhand-story-2026'
FONT=ROOT/'assets/fonts/SmileySans-Oblique.ttf'
BG=(8,20,36)

def photo(name):
    return str(OUT/(name+'.jpg'))
def cue(index,needle):
    rows=json.loads((WORDS/f'voice_{index:02}.words.json').read_text())
    text=''.join(x['text'] for x in rows);at=text.index(needle);p=0
    for x in rows:
        if p+len(x['text'])>at:return x['offset']/1e7
        p+=len(x['text'])
    raise ValueError(needle)

def shot(name,label):return (photo(name),label)

def plans():
    return {
      1:[shot('linz-1','2026 林茨'),shot('jj-1','2025 九江'),(str(ASSET/'cover-guangzhou.jpg'),'2026 广州')],
      3:[shot('child-profile','童年留影'),shot('child-9','童年比赛留影'),shot('child-4','与伊万尼塞维奇合影')],
      6:[shot('mentor-pair-0','02 遇见教练  ·  师徒早期合影'),shot('club-terrassa-7','2025 特拉萨  ·  师徒同框')],
      7:[(str(ASSET/'coach.jpg'),'2010 斯齐亚沃尼  ·  法网女单冠军'),shot('lina-3','2011 法网决赛'),shot('lina-1','2011 李娜  ·  法网女单冠军')],
      8:[shot('academy-australia','2025 教练学院的澳洲之旅'),shot('school-mentor','学校公开的贺信配图'),shot('early-coach-3','青少年时期的比赛留影')],
      9:[shot('terrassa-23','2025 特拉萨'),shot('terrassa-24','从资格赛出发'),shot('terrassa-27','首座成人职业赛事单打奖杯')],
      10:[shot('rg-5','2025 法网青少年女单'),shot('jj-4','六场比赛  ·  一盘未失'),shot('rg-7','2025 巴黎  ·  夺冠后发言')],
      11:[(str(ASSET/'coach.jpg'),'2010 教练捧杯'),shot('jj-4','2025 学生捧杯'),shot('jj-1','走向成人巡回赛')],
      12:[shot('jj-1','03 比赛里的成长  ·  2025 九江'),shot('jiujiang-reaction','2025 九江半决赛'),shot('jj-two-five','2025 九江半决赛  ·  决胜盘')],
      13:[shot('jj-two-five','决胜盘  ·  二比五落后'),shot('jj-three-match-points','四比五  ·  面对三个连续赛点')],
      16:[shot('jiujiang-after-315','2025 九江  ·  半决赛晋级后'),shot('jj-1','首次参加巡回赛单打正赛'),shot('jiujiang-reaction','那一周最终收获亚军')],
      17:[shot('linz-1','04 继续向上  ·  2026 林茨'),shot('linz-2','首次进入世界前100'),shot('prague-court','2026 布拉格')],
      18:[shot('prague-portrait','2026 布拉格决赛  ·  选手近景'),shot('prague-comeback','2026 布拉格决赛  ·  追分阶段'),shot('prague-1','生涯首座巡回赛单打冠军')],
      20:[shot('prague-after-272','2026 布拉格  ·  夺冠之后'),shot('prague-after-292','2026 布拉格  ·  赛后致意'),shot('prague-1','把经验带到下一场')],
      21:[(str(ASSET/'cover-guangzhou.jpg'),'2026 广州'),shot('club-terrassa-7','成长路上的教练'),shot('child-profile','从小时候的喜欢出发'),shot('guangzhou-reaction','已经晋级广州决赛')],
      22:[shot('child-profile','小时候的喜欢'),shot('child-9','一步步走过的路'),(str(ASSET/'cover-guangzhou.jpg'),'她的故事还在继续')]
    }

def render(index,shots,seconds):
    dest=OUT/f'sequence-{index:02}.mp4'
    n=len(shots);duration=seconds+.56
    custom={7:[cue(7,'次年'),cue(7,'见证')],11:[cue(11,'十五年后'),cue(11,'接下来')],
            13:[cue(13,'追回')],17:[2.8,cue(17,'七月')]}
    cuts=[0,*custom.get(index,[seconds*j/n for j in range(1,n)]),duration]
    assert len(cuts)==n+1 and all(b>a for a,b in zip(cuts,cuts[1:]))
    with tempfile.TemporaryDirectory(prefix='tagger-photos-') as tmp:
        tmp=Path(tmp);args=[];filters=[]
        for j,(path,label) in enumerate(shots):
            with Image.open(path) as im:im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1000,930),Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(1080,1440),BG)
            canvas.paste(im,((1080-im.width)//2,270+(930-im.height)//2))
            frame=tmp/f'{j}.png';canvas.save(frame)
            labelpath=tmp/f'label-{j}.txt';labelpath.write_text(label)
            d=cuts[j+1]-cuts[j]+(.28 if j<n-1 else 0)
            args+=['-loop','1','-framerate','25','-t',str(d),'-i',str(frame)]
            filters.append(f'[{j}:v]zoompan=z=1+0.000045*on:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d=1:s=1080x1440:fps=25,trim=duration={d},setpts=PTS-STARTPTS,fps=25,settb=1/25,format=yuv420p[p{j}]')
        prev='p0'
        for j in range(1,n):
            name=f'x{j}';filters.append(f'[{prev}][p{j}]xfade=transition=fade:duration=0.28:offset={cuts[j]},fps=25[{name}]');prev=name
        for j in range(n):
            name=f't{j}';enable=f'gte(t,{cuts[j]})*lt(t,{cuts[j+1]})'
            filters.append(f"[{prev}]drawtext=fontfile={FONT}:textfile={tmp/f'label-{j}.txt'}:fontcolor=0xC7D5E2:fontsize=32:x=64:y=188:enable='{enable}'[{name}]");prev=name
        footer=tmp/'footer.txt';footer.write_text('@网球时差 · TENNIS JETLAG')
        filters.append(f'[{prev}]drawtext=fontfile={FONT}:textfile={footer}:fontcolor=0x83949D:fontsize=26:x=(w-text_w)/2:y=1385[out]')
        cmd=['ffmpeg','-v','error','-y','-filter_complex_threads','1',*args,'-filter_complex',';'.join(filters),'-map','[out]','-t',str(duration),'-r','25','-an','-c:v','libx264','-preset','fast','-crf','19','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
        subprocess.run(cmd,check=True)
    print(f'{index:02} {seconds}s {n} photos {dest.stat().st_size/1e6:.2f}MB',flush=True)
    return {'segment':index,'path':str(dest.relative_to(ROOT)),'seconds':seconds,'cuts':cuts,
            'shots':[{'image':str(Path(p).relative_to(ROOT)),'label':label} for p,label in shots]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--only',type=int,nargs='*');ap.add_argument('--workers',type=int,default=2);a=ap.parse_args()
    spec=json.loads(SPEC.read_text());ps=plans();ids=a.only or list(ps)
    def work(i):return render(i,ps[i],spec['segments'][i]['seconds'])
    with ThreadPoolExecutor(max_workers=a.workers) as pool:records=list(pool.map(work,ids))
    target=OUT/'sequences.json';old=json.loads(target.read_text()) if target.exists() else [];lookup={x['segment']:x for x in old}
    lookup.update({x['segment']:x for x in records});target.write_text(json.dumps(list(lookup.values()),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()

"""EP13 光效层：EffectCraft（github.com/storytold/effectcraft，MIT/Apache-2.0）出的黑底光效素材，ffmpeg screen 叠到强拍上。
素材：vfx/vfx.jsx（EffectCraft 的 AE 风格脚本）→ effectcraft-cli 渲成 vfx/flare.mov（镜头光晕扫过）、vfx/sweep.mov（金色光扫）。
用法：python3 vfx.py <输入.mp4> <输出.mp4>。时间点全部取自 r3d/timeline.json（plan.py 已对齐 BGM 拍点）。
  flare：HIT（悬链线亮字，第 8 小节全乐队进）、白带子扯断字（tear）、拉带子到 91.4（pull）
  sweep：每个章节切换，光扫中线正好压在章节起点（起点本身对齐拍点）
"""
import json, os, sys, subprocess
HERE=os.path.dirname(os.path.abspath(__file__))
TL=json.load(open(os.path.join(HERE,'r3d','timeline.json'))); S={s['name']:s for s in TL['sections']}
ev=lambda sec,k: S[sec]['t0']+S[sec]['ev'][k]
FL=os.path.join(HERE,'vfx','flare.mov'); SW=os.path.join(HERE,'vfx','sweep.mov')
flares=[(S['title']['t0']-0.07,0.6),(ev('title','tear')-0.07,0.5),(ev('strap','pull')-0.07,0.4)]
sweeps=[(S[k]['t0']-0.45,0.55) for k in ['strap','hist','diag','margin','sticks','end']]
def main(inp,out):
    args=['ffmpeg','-y','-loglevel','error','-i',inp]; fc=[]; last='[0:v]'; n=1
    for (t,a),src in [(x,FL) for x in flares]+[(x,SW) for x in sweeps]:
        args+=['-i',src]
        fc.append(f'[{n}:v]fps=30,format=gbrp,colorchannelmixer=rr={a}:gg={a}:bb={a},tpad=start_duration={t:.3f}:color=black,setpts=PTS-STARTPTS[e{n}]')
        fc.append(f'{last}format=gbrp[b{n}];[b{n}][e{n}]blend=all_mode=screen:eof_action=pass:repeatlast=0[v{n}]'); last=f'[v{n}]'; n+=1
    fc.append(f'{last}format=yuv420p[vo]')
    args+=['-filter_complex',';'.join(fc),'-map','[vo]','-c:v','libx264','-preset','medium','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',out]
    subprocess.run(args,check=True); print('vfx',len(flares),'flares',len(sweeps),'sweeps')
if __name__=='__main__': main(sys.argv[1],sys.argv[2])

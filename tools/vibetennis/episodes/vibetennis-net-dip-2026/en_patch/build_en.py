"""英文版 3D：只重渲「中英字不同」的帧，其余从中文块（r3d/seg_zh）原样切出来复用。
diff.json 由 probe.js 逐帧比对得出（不出图，十几秒）；差异帧前后各扩 20 帧（0.6 s 交叉溶解会用到上一镜头的状态），
小于 15 帧的中文空档并进英文段。按 240 帧块边界切开，产物写 r3d/seg_en/c<起始帧>.mp4＋.anchors.json（assemble 直接吃）。
    python3 en_patch/build_en.py plan      # 写 en_patch/jobs.txt（要英文重渲的段）并切好中文复用段
    bash en_patch/render_en.sh            # 4 进程并行渲英文段（可续渲）
"""
import json, os, subprocess, sys
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(HERE)
N=round(json.load(open('r3d/timeline.json'))['total']*30); C=240; D=20; MINZ=15
d=json.load(open('en_patch/diff.json'))[:N]
m=[0]*N
for i,v in enumerate(d):
    if v:
        for j in range(max(0,i-D),min(N,i+D+1)): m[j]=1
# 拆成连续段，再按块边界切
runs=[]; s=0
for i in range(1,N+1):
    if i==N or m[i]!=m[s] or i%C==0: runs.append([s,i,m[s]]); s=i
for r in runs:   # 太短的中文段改成英文
    if r[2]==0 and r[1]-r[0]<MINZ: r[2]=1
merged=[]
for r in runs:
    if merged and merged[-1][2]==r[2] and merged[-1][1]==r[0] and r[0]%C!=0: merged[-1][1]=r[1]
    else: merged.append(r)
os.makedirs('r3d/seg_en',exist_ok=True)
jobs=[(a,b) for a,b,e in merged if e]; zh=[(a,b) for a,b,e in merged if not e]
open('en_patch/jobs.txt','w').write(''.join(f'{a} {b}\n' for a,b in jobs))
print('pieces',len(merged),'EN frames',sum(b-a for a,b in jobs),'reuse ZH frames',sum(b-a for a,b in zh))
for a,b in zh:
    out=f'r3d/seg_en/c{a:05d}.mp4'
    if os.path.exists(out+'.anchors.json'): continue
    c=a//C*C; src=f'r3d/seg_zh/c{c:05d}.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-i',src,'-vf',f'trim=start_frame={a-c}:end_frame={b-c},setpts=PTS-STARTPTS','-r','30','-c:v','libx264','-preset','ultrafast','-crf','12','-pix_fmt','yuv420p',out],check=True)
    an=[x for x in json.load(open(src+'.anchors.json')) if a<=x[0]<b]
    assert len(an)==b-a, (a,b,len(an))
    json.dump(an,open(out+'.anchors.json','w'))
print('zh pieces ready')

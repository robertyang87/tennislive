# 组装 EP11 scene.js：EP09 的底座＋球拍＋通用池＋镜头＋后期，中间换成本集的 rig.js 与 shots.js
import sys
E='/home/user/tennislive/tools/vibetennis/episodes/vibetennis-ball-2026/r3d/scene.js'
L=open(E).read().split('\n')
def find(s):
    for i,l in enumerate(L):
        if l.startswith(s): return i
    raise SystemExit('nf '+s)
i_ep=find('// ==================== EP09'); i_rk=find('// ---- 球拍'); i_rka=find('const rkA='); i_ball=find('// ---- 球：')
i_pool=find('// 通用池'); i_fmt=find('const fmt'); i_cam=find('// ================== 镜头'); i_hide=find('function hideAll'); i_post=find('// ---------- 后期')
base='\n'.join(L[:i_ep])
common='\n'.join(L[i_ep:i_rk])   # 颜色、TT、bt、hud、layoutText
racket='\n'.join(L[i_rk:i_rka])  # makeRk/setRk/rkOp（不含 rkA）
pools='\n'.join(L[i_pool:i_fmt+1])
camera='\n'.join(L[i_cam:i_hide])
post='\n'.join(L[i_post:])
d=sys.argv[1]
head=open(d+'/head.txt').read()
base=base.split('\n',3)[3]   # 去掉 EP09 前三行文件说明
common=common.replace('// ==================== EP09 球：本集物件 ====================','// ==================== EP11 阻力危机：本集物件 ====================')
rig=open(d+'/rig.js').read(); stands=open(d+'/stands.js').read(); anat=open(d+'/aero.js').read(); shots=open(d+'/shots.js').read()
import re
post=re.sub(r"\(\{hook:shotHook[^)]*\}\)\[sc\.kind\]\(u,D\);", "(SHOTS[sc.kind]||shotTest)(u,D); standsTick(t,sc.kind,u);", post)
extra="\nconst pt=cloud(1600,0.05,8,scene,0.5); const PTS=[...Array(1600)].map(()=>[(frnd()-0.5)*16,(frnd()-0.5)*9,(frnd()-0.5)*8,frnd(),frnd()]);\n"
out='\n'.join([head,base,common,racket,pools,extra,stands,rig,anat,camera,shots,post])
open(sys.argv[2],'w').write(out); print(len(out.split('\n')),'lines')

# 组装 EP14 scene.js：EP12 成品 scene.js 的通用底座（夜空、光点、全息字、3D 字、球场、看台、全息人体、镜头、后期）＋本集 src/shots.js；段落配色换成本集段名（香蕉）
# 用法：python3 src/build.py src ../scene.js?  —— 在 r3d/ 下跑：python3 src/build.py src scene.js
import re, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.join(HERE, '../../../vibetennis-tiebreak-2026/r3d/scene.js')
L = open(E).read().split('\n')
def find(s):
    for i, l in enumerate(L):
        if l.startswith(s): return i
    raise SystemExit('nf ' + s)
i_imp = find('import * as THREE')
i_obj = find('// ==================== EP12 抢七轮发：本集物件')
i_post = find('// ---------- 后期')
base = '\n'.join(L[i_imp:i_obj])
post = '\n'.join(L[i_post:])
base = base.replace('// ==================== EP12 抢七轮发：通用物件 ====================', '// ==================== EP14 不是补钾：通用物件 ====================')
base = base.replace('papers/vibetennis-tiebreak-2026/sources.md', 'papers/vibetennis-banana-2026/sources.md')
PAL = '''const PAL={
  hook:  {top:0x03050f,hz:0x0b1f48,vi:0x2a1040,a:0x30e8ff,b:0xffc24a,c:0xffffff},   // 夜场换边：电光青＋金
  title: {top:0x080603,hz:0x2e1c06,vi:0x1a0a20,a:0xffc24a,b:0xffe2a0,c:0xffffff},   // 片名：金
  peel:  {top:0x0a0804,hz:0x3a2208,vi:0x221206,a:0xffc24a,b:0xffe07a,c:0xffffff},   // 剖开：蕉黄
  salt:  {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0x4fe3ff,b:0xff6b6b,c:0xffffff},   // 钠钾：青＋红
  fuel:  {top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8,b:0xffc24a,c:0xeafff6},   // 补糖：翡翠＋金
  proof: {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0xc9d6ff,b:0x7c83ff,c:0xffffff},   // 试验：银＋靛
  alt:   {top:0x0a0703,hz:0x33240c,vi:0x221206,a:0xffb347,b:0x4fe3ff,c:0xffffff},   // 对照／历史：琥珀
  end:   {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a,b:0x4fe3ff,c:0xffffff}};  // 金＋青'''
base, n = re.subn(r'const PAL=\{.*?\}\};[^\n]*', PAL, base, count=1, flags=re.S); assert n == 1
base, n = re.subn(r'const LN=\[\.\.\.Array\(\d+\)\]', 'const LN=[...Array(150)]', base); assert n == 1
base, n = re.subn(r'const GS=\[\.\.\.Array\(\d+\)\]', 'const GS=[...Array(40)]', base); assert n == 1
head = open(os.path.join(HERE, 'head.txt')).read()
shots = open(os.path.join(HERE, 'shots.js')).read()
base = base.replace("import * as THREE from 'three';", "import * as THREE from 'three';\nimport { gsap } from 'gsap';   // GSAP 3.15（Standard no-charge license）：动字缓动/编排，见 shots.js kinTitle", 1)
base = base.replace("const tx=(k,s,o={},grp=scene)=>TT[k]||(TT[k]=textSprite(s,o,grp));", "const tx=(k,s,o={},grp=scene)=>TT[k]||(TT[k]=(sp=>{ sp.userData.str=s; return sp; })(textSprite(s,o,grp)));", 1)
base = base.replace("const g=new THREE.Group(); g.add(m); group.add(g); text3D[key]={g,m,e};", "m.userData.str=str; const g=new THREE.Group(); g.add(m); group.add(g); text3D[key]={g,m,e};", 1)
base = base.replace("const TB={}; const bt=(k,s,o={})=>TB[k]||(TB[k]=(t=>{", "const TB={}; const bt=(k,s,o={})=>TB[k]||(TB[k]=(t=>{ t.__str=s;", 1)
out = '\n'.join([head, base, shots, post])
open(sys.argv[2], 'w').write(out); print(len(out.split('\n')), 'lines')

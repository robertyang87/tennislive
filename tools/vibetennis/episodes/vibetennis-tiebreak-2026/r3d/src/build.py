# 组装 EP12 scene.js：EP11 的成品 scene.js 去掉本集物件（空气动力资产、EP11 镜头），换成 src/shots.js；段落配色换成本集的段名
# 用法：python3 src/build.py src ../scene.js   （在 r3d/ 下跑）
import re, sys
E = '/home/user/tennislive/tools/vibetennis/episodes/vibetennis-fuzz-2026/r3d/scene.js'
L = open(E).read().split('\n')
def find(s):
    for i, l in enumerate(L):
        if l.startswith(s): return i
    raise SystemExit('nf ' + s)
i_aero = find('// ==================== EP11 阻力危机：空气动力资产')
i_cam = find('// ================== 镜头')
i_ep = find('// ==================== 本集镜头')
i_post = find('// ---------- 后期')
base = '\n'.join(L[3:i_aero])
camera = '\n'.join(L[i_cam:i_ep])
post = '\n'.join(L[i_post:])
d = sys.argv[1]
base = base.replace('// ==================== EP11 阻力危机：本集物件 ====================', '// ==================== EP12 抢七轮发：通用物件 ====================')
base = base.replace('papers/vibetennis-ball-2026/sources.md', 'papers/vibetennis-tiebreak-2026/sources.md')
PAL = '''const PAL={
  hook:  {top:0x05030f,hz:0x1a1048,vi:0x3a0a3a,a:0x30e8ff,b:0xffc24a,c:0xffffff},   // 电光青＋金：中央球场之夜
  rule:  {top:0x030812,hz:0x0b2a50,vi:0x0a2030,a:0xe8f6ff,b:0x4fe3ff,c:0xffffff},   // 规则书冰白
  edge:  {top:0x0b0602,hz:0x3a2208,vi:0x2a1406,a:0xffb347,b:0xffe2a0,c:0xffffff},   // 发球占优：琥珀
  math:  {top:0x04040e,hz:0x14163a,vi:0x1a1a2e,a:0xc9d6ff,b:0x7c83ff,c:0xffffff},   // 推算：银＋靛
  why:   {top:0x06041a,hz:0x1d1250,vi:0x2b0d55,a:0xa78bfa,b:0x6fa8ff,c:0xf0e6ff},   // Thue–Morse：紫罗兰
  soccer:{top:0x020c0a,hz:0x063828,vi:0x062a2a,a:0x34f5a8,b:0x4fe3ff,c:0xeafff6},   // 足球场：翡翠
  data:  {top:0x0c0504,hz:0x3a1608,vi:0x0a3024,a:0xff7a3d,b:0x34f5a8,c:0xffffff},   // 数据：橙＋绿
  end:   {top:0x050505,hz:0x2a2008,vi:0x08202a,a:0xffc24a,b:0x4fe3ff,c:0xffffff}};  // 金＋青'''
base, n = re.subn(r'const PAL=\{.*?\}\};[^\n]*', PAL, base, count=1, flags=re.S)
assert n == 1, 'PAL not replaced'
base, n = re.subn(r'const LN=\[\.\.\.Array\(40\)\]', 'const LN=[...Array(72)]', base); assert n == 1
base, n = re.subn(r'const GS=\[\.\.\.Array\(10\)\]', 'const GS=[...Array(24)]', base); assert n == 1
base, n = re.subn(r'const RG=\[\.\.\.Array\(6\)\]', 'const RG=[...Array(10)]', base); assert n == 1
head = open(d + '/head.txt').read()
shots = open(d + '/shots.js').read()
out = '\n'.join([head, base, camera, shots, post])
assert 'FLOW' not in shots
open(sys.argv[2], 'w').write(out); print(len(out.split('\n')), 'lines')

# vibetennis 第 7 集《发球，该往哪边发？》音效床：音效用 numpy/scipy 现场合成（音色抄自第 5 集 sfx.py），
# 每个音效钉在 r3d/timeline.json 的画面事件（sec.ev，plan.py 按配音词边界排）和 scene.js 各镜头的动画节点上——画面动、声音同时到。
# BGM 同第 4、5 集：robertyang87/vibeknowledge 的 assets/music/we-never-remix-hi-noise-qiucheng.m4a。
import numpy as np, soundfile as sf, sys, json, math, os
from scipy import signal
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
SR=48000
TL=json.load(open(os.path.join(HERE,'r3d','timeline.json'))); TOTAL=TL['total']; N=int(TOTAL*SR)+SR
NAR={l['file']:l['at'] for l in json.load(open(os.path.join(HERE,'narration.json')))['lines']}
SEC={s['name']:s for s in TL['sections']}
rng=np.random.default_rng(77)
out=np.zeros((N,2)); EV=[]
out=np.zeros((N,2)); EV=[]
def tt(d): return np.arange(int(d*SR))/SR
def bp(x,lo,hi,o=2): return signal.sosfilt(signal.butter(o,[lo,hi],'band',fs=SR,output='sos'),x)
def lp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'low',fs=SR,output='sos'),x)
def hp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'high',fs=SR,output='sos'),x)
def place(x,t,gain=1.0,pan=0.0,name=None):
    if name: EV.append((round(t,3),name))
    i=int(t*SR)
    if x.ndim==1: x=np.stack([x*math.sqrt((1-pan)/2),x*math.sqrt((1+pan)/2)],1)*1.414
    j=min(N,i+len(x)); 
    if i<0: x=x[-i:]; i=0
    out[i:j]+=x[:j-i]*gain
# ---------- reverb (decorrelated stereo, exp-decay noise IR) ----------
def ir(dur=2.2,damp=3000):
    t=tt(dur); e=np.exp(-t*6.9/dur)
    L=lp(rng.standard_normal(len(t)),damp)*e; R=lp(rng.standard_normal(len(t)),damp)*e
    L[:int(0.012*SR)]=0; R[:int(0.017*SR)]=0
    return np.stack([L,R],1)/np.sqrt((L**2).sum())
IR=ir()
def verb(x,wet=0.35):
    x=x if x.ndim==2 else np.stack([x,x],1)
    y=np.stack([signal.fftconvolve(x[:,0],IR[:,0]),signal.fftconvolve(x[:,1],IR[:,1])],1)
    xx=np.zeros_like(y); xx[:len(x)]=x
    return xx*(1-wet)+y*wet*3
# ---------- sound designs ----------
def pock(rate=1.0):          # racket-ball impact; rate<1 = slow motion, pitched down & longer
    r=max(0.25,rate); d=0.35/r; t=tt(d)
    x=(np.sin(2*np.pi*1150*r*t)*np.exp(-t*r/0.007)*0.8+np.sin(2*np.pi*2350*r*t)*np.exp(-t*r/0.004)*0.4
       +np.sin(2*np.pi*190*r*t)*np.exp(-t*r/0.03)*0.6+np.sin(2*np.pi*620*r*t)*np.exp(-t*r/0.05)*0.15)
    n=hp(rng.standard_normal(len(t)),900)*np.exp(-t*r/0.0025)*0.9
    x=x+n
    if rate<0.9: x=x+np.sin(2*np.pi*48*t)*np.exp(-t/0.5)*0.9*(1-rate)   # cinematic weight in slow-mo
    return x
def bounce(rate=1.0):
    r=max(0.25,rate); d=0.3/r; t=tt(d)
    x=np.sin(2*np.pi*150*r*t*(1-0.3*t))*np.exp(-t*r/0.028)*0.9+lp(rng.standard_normal(len(t)),2200)*np.exp(-t*r/0.008)*0.7
    x+=np.sin(2*np.pi*780*r*t)*np.exp(-t*r/0.006)*0.25
    return x
def blip(f=2400,d=0.06,glide=1.3,amp=1.0):
    t=tt(d); ph=2*np.pi*np.cumsum(f*(1+(glide-1)*t/d))/SR
    e=np.minimum(1,t/0.003)*np.exp(-t/(d*0.35))
    return (np.sin(ph)+0.25*np.sin(2*ph))*e*amp
def tick(): t=tt(0.012); return hp(rng.standard_normal(len(t)),3500)*np.exp(-t/0.0015)*0.6+np.sin(2*np.pi*5200*t)*np.exp(-t/0.002)*0.3
def panel():                 # HUD panel opening: chirp pair + airy swish
    a=blip(1800,0.05,1.2,0.7); b=blip(2700,0.07,1.15,0.6); t=tt(0.25)
    s=bp(rng.standard_normal(len(t)),2500,9000)*np.sin(np.pi*t/0.25)**2*0.25
    x=np.zeros(len(t)); x[:len(a)]+=a; k=int(0.06*SR); x[k:k+len(b)]+=b; return x+s
def number_pop():            # big number reveal: low thump + bright ping
    t=tt(0.9); x=np.sin(2*np.pi*(70-20*t)*t)*np.exp(-t/0.22)*0.9
    x[:int(0.12*SR)]+=blip(3100,0.12,1.0,0.35); return x
def riser(d=1.8):
    t=tt(d); u=t/d
    n=rng.standard_normal(len(t)); y=np.zeros(len(t)); seg=int(0.02*SR)
    for i in range(0,len(t),seg):                       # swept band-noise
        fc=300*(20**u[i]); y[i:i+seg]=bp(n[max(0,i-2000):i+seg],fc*0.7,min(fc*1.4,20000))[-len(y[i:i+seg]):]
    tone=np.sin(2*np.pi*np.cumsum(110*(4**u))/SR)*0.25+np.sin(2*np.pi*np.cumsum(165*(4**u))/SR)*0.12
    return (y*0.6+tone)*(u**2.2)
def hit(): # transition impact
    t=tt(2.0); sub=np.sin(2*np.pi*np.cumsum(58*np.exp(-t*1.5)+30)/SR)*np.exp(-t/0.55)
    n=lp(rng.standard_normal(len(t)),1800)*np.exp(-t/0.06)*0.6
    return verb((sub+n)*0.9,0.3)
def boom(d=4.0):  # scale reveal: slow sub swell + rumble
    t=tt(d); env=np.minimum(1,t/0.25)*np.exp(-t/(d*0.35))
    x=np.sin(2*np.pi*np.cumsum(38-6*t/d)/SR)*env + lp(rng.standard_normal(len(t)),110,4)*env*1.6
    return verb(x,0.25)
def swish(d=0.9,lo=300,hi=2600):
    t=tt(d); n=rng.standard_normal(len(t)); y=np.zeros(len(t)); seg=int(0.015*SR)
    for i in range(0,len(t),seg):
        u=t[i]/d; fc=lo+(hi-lo)*math.sin(math.pi*u)
        y[i:i+seg]=bp(n[max(0,i-1500):i+seg],fc*0.6,fc*1.6)[-len(y[i:i+seg]):]
    return y*np.sin(np.pi*t/d)**2
def crowd(d):     # stadium crowd bed: babble of formant-filtered noise + room tone
    t=tt(d); x=np.zeros(len(t))
    for k in range(36):
        f1=rng.uniform(350,900); f2=rng.uniform(1100,2600)
        n=bp(rng.standard_normal(len(t)),f1*0.8,f1*1.2)+0.5*bp(rng.standard_normal(len(t)),f2*0.85,f2*1.15)
        syl=np.clip(np.sin(2*np.pi*rng.uniform(2.5,5.5)*t+rng.uniform(0,6.28)),0,1)**2
        slow=0.5+0.5*np.sin(2*np.pi*rng.uniform(0.05,0.2)*t+rng.uniform(0,6.28))
        x+=n*syl*slow*rng.uniform(0.3,1)
    x=lp(x,3500)/36**0.5*0.5+lp(rng.standard_normal(len(t)),400)*0.08
    L=x; R=np.roll(x,int(0.011*SR))*0.9+lp(rng.standard_normal(len(t)),300)*0.04
    e=np.minimum(1,np.minimum(t/0.4,(d-t)/0.4))[:,None]
    return np.stack([L,R],1)*e
def applause(d=2.5):
    t=tt(d); x=np.zeros(len(t)); m=int(d*900)
    for c in rng.uniform(0,d,m):
        i=int(c*SR); k=min(len(t)-i,int(0.01*SR))
        if k>0: x[i:i+k]+=bp(rng.standard_normal(k),900,5000)*np.exp(-np.arange(k)/SR/0.002)*rng.uniform(0.3,1)
    return x*np.sin(np.pi*np.minimum(1,t/d))**0.6*0.35
def tvize(x): return bp(x,280,4000,3)*0.6


def sparkle(d=1.5,dens=60):
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d,int(d*dens)):
        i=int(c*SR); s=blip(rng.uniform(3000,6500),0.05,1.0,rng.uniform(0.1,0.35)); k=min(len(t)-i,len(s)); x[i:i+k]+=s[:k]
    return verb(x,0.4)
def hz(m): return 440*2**((m-69)/12)
def chime(notes,gap=0.18,amp=0.4):  # notes 为 MIDI 音高
    d=gap*len(notes)+1.4; x=np.zeros(int(d*SR))
    for k,m in enumerate(notes):
        t=tt(1.4); s=(np.sin(2*np.pi*hz(m)*t)+0.3*np.sin(2*np.pi*hz(m)*2.01*t))*np.exp(-t/0.4)*amp; i=int(k*gap*SR); x[i:i+len(s)]+=s
    return verb(x,0.35)
def slam():
    t=tt(1.2); x=np.sin(2*np.pi*np.cumsum(70*np.exp(-t*3)+35)/SR)*np.exp(-t/0.3)+lp(rng.standard_normal(len(t)),900)*np.exp(-t/0.04)*0.5
    return verb(x*0.8,0.25)
def clink(f=2400):
    t=tt(0.18); return (np.sin(2*np.pi*f*t)+0.5*np.sin(2*np.pi*f*2.76*t))*np.exp(-t/0.035)*0.35+hp(rng.standard_normal(len(t)),4000)*np.exp(-t/0.004)*0.3
def zap(f0=900,f1=3200,d=0.35):
    t=tt(d); ph=2*np.pi*np.cumsum(f0*(f1/f0)**(t/d))/SR; return np.sin(ph)*np.exp(-t/(d*0.5))*np.minimum(1,t/0.004)*0.35
def glitch(d=0.8):
    t=tt(d); sq=np.sign(np.sin(2*np.pi*np.cumsum(rng.uniform(80,900,len(t)))/SR)); env=(rng.uniform(0,1,len(t)//400+1)>0.4).repeat(400)[:len(t)]
    return lp(sq*env,4000)*0.18
def click(): t=tt(0.03); return hp(rng.standard_normal(len(t)),1500)*np.exp(-t/0.003)*0.8

def hum(d=4.0,f=110):
    t=tt(d); return (np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2*t))*np.sin(np.pi*t/d)*0.06
def ding(f=1320):
    t=tt(1.2); return verb((np.sin(2*np.pi*f*t)+0.3*np.sin(2*np.pi*f*2.01*t))*np.exp(-t/0.35)*0.4,0.35)
def freeze_in():
    t=tt(1.4); f=2400*np.exp(-t*3)+120; x=bp(rng.standard_normal(len(t)),300,4000)*np.exp(-t/0.5)*0.5+np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t/0.6)*0.3; return verb(x,0.4)
def sub_boom():
    t=tt(0.9); return np.sin(2*np.pi*np.cumsum(55*np.exp(-t*4)+38)/SR)*np.exp(-t/0.35)*0.9
def toss():                   # 抛球出手：短促的气流声
    t=tt(0.4); return bp(rng.standard_normal(len(t)),600,3000)*np.sin(np.pi*t/0.4)**2*0.35
def heartbeat():              # 关键分卡片的心跳：两下低频
    x=np.zeros(int(0.5*SR))
    for k,a in ((0,1.0),(0.18,0.7)):
        t=tt(0.25); s=np.sin(2*np.pi*np.cumsum(60-25*t/0.25)/SR)*np.exp(-t/0.07)*a; i=int(k*SR); x[i:i+len(s)]+=s
    return x
def rps_shake():              # 石头剪刀布的「一、二、三」：拳头上下晃，每下一记闷拍
    t=tt(0.12); return lp(rng.standard_normal(len(t)),900)*np.exp(-t/0.02)*0.7+np.sin(2*np.pi*120*t)*np.exp(-t/0.04)*0.5
def coin_flip(d=6.0):         # 硬币翻转的嗡鸣：频率随转速轻微起伏
    t=tt(d); f=1800+200*np.sin(2*np.pi*1.4*t); x=np.sin(2*np.pi*np.cumsum(f)/SR)*(0.5+0.5*np.sin(2*np.pi*9*t))**2
    return x*np.minimum(1,np.minimum(t/0.3,(d-t)/0.5))*0.12
def rain_hiss(d):             # 光点暴雨：密集的细碎落点
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d,int(d*900)):
        i=int(c*SR); k=min(len(t)-i,int(0.003*SR))
        if k>0: x[i:i+k]+=hp(rng.standard_normal(k),3000)*np.exp(-np.arange(k)/SR/0.0006)*rng.uniform(0.1,0.6)
    return x*np.minimum(1,np.minimum(t/0.8,(d-t)/1.0))*0.6
def EN(t,x,g=1.0,pan=0.0,name=None): place(x,t,g,pan=pan,name=name)
def E(sec,k,dflt): s=SEC[sec]; return s['t0']+s['ev'].get(k,dflt)
BT=TL['beat']; onB=lambda x: math.ceil(x/BT-1e-6)*BT   # 与 scene.js 同一套拍点

# ================= 事件 =================
for s in TL['sections'][1:]: EN(s['t0']-0.25,swish(0.9,400,2600),0.35,name='cut-'+s['name'])
# 01 钩子：抛球升到最高点冻结（0–1.4 s）→ 两条轨迹闪着分叉（0.8–2.2 s）→「纳什均衡」砸下来，镜头升起
h=SEC['hook']; S=E('hook','slam',4.7)
EN(h['t0']+0.15,toss(),0.6,name='toss'); EN(h['t0']+1.3,freeze_in(),0.55,name='freeze-apex'); EN(h['t0']+1.4,hum(S-h['t0']-1.2,62),0.9,name='apex-drone')
EN(h['t0']+0.8,zap(500,2600,1.4),0.3,name='paths-split'); EN(S-0.7,riser(0.7),0.4); EN(S,slam(),0.8,name='SLAM-nash'); EN(S,sub_boom(),0.6); EN(S+0.6,swish(2.0,200,1800),0.35,name='crane-up')
# 02 不到半秒：一次发球放慢（cyc 7.5 s：k=0.55 出手、球飞到 k=0.95）
a=SEC['fast']; cyc=7.5; u=0.0
while u<a['t1']-a['t0']-0.3:
    EN(a['t0']+u+0.1,toss(),0.4); EN(a['t0']+u+0.55*cyc,pock(0.45),0.9,name='slowmo-serve'); EN(a['t0']+u+0.55*cyc,hum(0.4*cyc,98),0.6); EN(a['t0']+u+0.9*cyc,bounce(0.5),0.6,name='slowmo-bounce'); u+=cyc
EN(a['t0']+0.62*cyc,ding(1568),0.25,name='time-ring')
# 总发一边：连发 6 个外角（scene.js shotPile：per=max(2.2,(D-0.6)/6)，k=0.45 出手、0.7 落地，第 6 球 k>0.72 被打回、k=0.86 红色冲击波）
p=SEC['pile']; D=p['t1']-p['t0']; per=4*BT if 6*4*BT+0.6<=D else max(2.2,(D-0.6)/6); sh=2*BT-0.45*per   # scene.js：一球一小节、出手在第 3 拍
for n in range(6):
    t0=p['t0']+sh+n*per; EN(t0+0.45*per,pock(1.0),0.7,pan=-0.2,name='pile-serve-%d'%(n+1)); EN(t0+0.7*per,bounce(1.0),0.55,pan=-0.5); EN(t0+0.7*per,ding(660+n*70),0.12+0.04*n)
EN(p['t0']+sh+5*per+0.74*per,pock(1.1),0.9,pan=0.3,name='return-winner'); EN(p['t0']+sh+5*per+0.86*per,hit(),0.6,name='shockwave')
# 03 理论：年份光环（三环依次落下）→ 石头剪刀布两局 → 2×2 方块＋螺旋收进均衡点
th=SEC['theory']; HA=E('theory','hands',9.5); MX=E('theory','matrix',19.5); CV=E('theory','conv',MX+6)
for i in range(3): EN(th['t0']+0.6+i*(HA-th['t0']-2)/3,chime([72+i*4]),0.45,name='year-ring-%d'%i)
RL=min((MX-HA)/2,8*BT); PU=3*BT   # scene.js：一局两小节，三下落在拍上，第 4 拍亮出
for r in range(2):
    b=HA+r*RL
    for k in range(3): EN(b+(k+1)*PU/3-0.02,rps_shake(),0.6,name='rps-%d-%d'%(r,k))
    EN(b+PU,slam(),0.35,name='rps-reveal-%d'%r); EN(b+PU+0.4,blip(1800,0.15,0.6,0.5),0.4,name='paper-wins-%d'%r)
EN(MX,panel(),0.5,name='matrix'); 
for i in range(4): EN(MX+i*0.4,blip(1400+i*300,0.06,1.2,0.5),0.4)
EN(CV-3,riser(5.5),0.35,name='spiral'); EN(CV+2.5,chime([79,84,88],0.12,0.4),0.55,name='equilibrium-star'); EN(CV+2.5,sparkle(1.5,40),0.3)
# 04 天平：光点按次数倒进托盘（5 s，51:33）→ 得分率光柱长出来、天平回到水平
b=SEC['mix']; PO=E('mix','pour',0.5); RI=E('mix','rise',6.5)
for i in range(0,84,3): EN(PO+5*(i%42)/42+0.3,clink(2000+(i%7)*150),0.22)
EN(PO+1.0,hum(4.0,74),0.8,name='tilt-creak'); EN(RI,riser(3.5),0.4,name='beams-rise'); EN(RI+3.5,ding(1320),0.45,name='level'); EN(RI+3.5,number_pop(),0.4,name='rates')
# 05 今天的数据：光点暴雨 → 两根光柱 → 1,056 块方砖 → 56 块变红
r=SEC['today']; CO=E('today','cols',6); TI=E('today','tiles',11); RD=E('today','red',14)
EN(r['t0'],rain_hiss(CO-r['t0']+1.5),0.9,name='rain'); EN(CO,riser(2.0),0.4,name='cols-rise'); EN(CO+2.0,number_pop(),0.45,name='65-vs-64.7')
for i in range(24): EN(TI+i*0.075,tick(),0.35)
EN(TI,panel(),0.35,name='tiles'); EN(RD,glitch(0.5),0.55,name='red-5.3'); EN(RD,sub_boom(),0.4); EN(RD+2.0,ding(990),0.3,name='5-percent-line')
# 关键分：两排卡片，每张出现时一记面板声，光柱随心跳升起
k=SEC['keypts']
for row,key,dflt in ((0,'row0',1.2),(1,'row1',10.7)):
    for c in range(3):
        k0=SEC['keypts']['t0']; t0=k0+onB(E('keypts',key,dflt)-k0)+c*2*BT; EN(t0,panel(),0.3,name='card-%d-%d'%(row,c))
        for q in range(3): EN(t0+q*2*BT,heartbeat(),0.55-0.12*q)   # 心跳与画面同拍
        EN(t0+2.2,blip(2600,0.08,1.0,0.4),0.3)
# 06 新研究：比分树一层层点亮，三行结论依次出现
l=SEC['latest']; RS=E('latest','res',9)
for j in range(7): EN(l['t0']+1+j,blip(900+j*180,0.12,1.1,0.4),0.3,name='tree-level-%d'%j)
for i in range(3): EN(RS-1.2+i*1.0,panel(),0.35,name='result-%d'%i)
# 07 结尾：硬币在掌心翻转（0–6 s）→ 抛球发出去 → 最后一问
e=SEC['end']; EN(e['t0'],coin_flip(6.0),0.9,name='coin'); EN(e['t0']+6.0,click(),0.6,name='catch')
EN(e['t0']+6.2,toss(),0.5); EN(e['t0']+7.3,pock(1.0),0.9,name='final-serve'); EN(E('end','q',99),chime([84,88,91],0.16,0.35),0.5,name='question')

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_LUFS=-20.0
raw=subprocess.run(['ffmpeg','-v','error','-i',BGM,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
song=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
# 循环＋卡点（所有者 2026-11-04「BGM 要循环，同时看看怎么卡点」）：曲子 112.3 BPM，小节 4×0.53194 s，曲内第一个强拍 0.4757 s（librosa 实测）。
# 小节号 → 段落：0–7 前奏、8–39 主段、40–47 间奏（轻）、48–63 主段、64 起尾段淡出。起点 BGM_OFF 由 plan.py 定（「纳什均衡」那一刻＝第 8 小节线，主段进来），
# 之后按「主段 → 间奏 → 主段 → 再从第 8 小节循环」整小节往后拼，不放尾段；拼缝都在小节线上，10 ms 交叉淡化
BAR=4*0.53194; bar=lambda k: 0.4757+k*BAR; BGM_OFF=TL['bgm_off']
order=[(BGM_OFF,bar(40)),(bar(40),bar(48)),(bar(48),bar(64))]
while sum(b1-b0 for b0,b1 in order)<TOTAL+2: order.append((bar(8),bar(40)))
xf=int(0.01*SR); parts=[]
for b0,b1 in order:
    seg=song[int(b0*SR):int(b1*SR)+xf].copy()
    if parts:   # 前一段尾巴多留的 xf 和这一段开头交叉淡化
        w=np.linspace(0,1,xf)[:,None]; prev=parts[-1]; seg[:xf]=prev[-xf:]*(1-w)+seg[:xf]*w; parts[-1]=prev[:-xf]
    parts.append(seg)
song=np.concatenate(parts); BGM_OFF=0.0
bgm=song[int(BGM_OFF*SR):int((BGM_OFF+TOTAL+1)*SR)]
tmp=os.path.join(WORK,'sfx','_bgm_raw.wav'); sf.write(tmp,bgm.astype(np.float32),SR,subtype='FLOAT')
meas=subprocess.run(['ffmpeg','-hide_banner','-i',tmp,'-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
I=float(re.findall(r"I:\s+(-?[\d.]+) LUFS",meas)[-1]); os.remove(tmp)
bgm*=10**((BGM_LUFS-I)/20)
B=np.zeros((N,2)); B[:min(N,len(bgm))]=bgm[:N]
SFX_GAIN=0.2
mix=out*SFX_GAIN+B
fade=np.ones(N); k=int((TOTAL-3.0)*SR); fade[k:]=np.linspace(1,0,N-k)**2; mix*=fade[:,None]
sf.write(os.path.join(WORK,'sfx','sfx_bed.wav'),mix.astype(np.float32),SR,subtype='FLOAT')
sf.write(os.path.join(WORK,'sfx','sfx_only.wav'),(out*SFX_GAIN).astype(np.float32),SR,subtype='FLOAT')
sf.write(os.path.join(WORK,'sfx','bgm_bed.wav'),(B*fade[:,None]).astype(np.float32),SR,subtype='FLOAT')
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
print(len(EV),'events')

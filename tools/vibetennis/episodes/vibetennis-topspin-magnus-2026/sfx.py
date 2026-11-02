# vibetennis 第 3 集《上旋为什么会突然下坠？》英文版音效床（全部用 numpy/scipy 现场合成，不用外部素材）。
# Every sound is generated here with numpy/scipy (no downloaded assets).
#
# ⚠️ 2026-11-02 重写：这一集的原始工程从没进 git、已经丢失，本文件是按成片逐帧＋
# 原混音频谱包络反推事件表后重写的（事件图与置信度见同目录 README.md）。合成工具
# 抄自第 2 集 sfx.py；事件表是这一集的，对齐成片里烧录的字幕锚点与章节卡。
# 本集英文版无 BGM（所有者 2026-11-02 定：原 BGM 版权未核且已致 EP04 在 IG 被静音，
# 音乐改走 Instagram 曲库 App 内挂），这一条音效轨就是成片的全部声音。
import numpy as np, soundfile as sf, sys, json, math
from scipy import signal
import os
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
SR=48000
TOTAL=245.467; N=int(TOTAL*SR)+SR
rng=np.random.default_rng(3)
out=np.zeros((N,2)); EV=[]
def tt(d): return np.arange(int(d*SR))/SR
def bp(x,lo,hi,o=2): return signal.sosfilt(signal.butter(o,[lo,hi],'band',fs=SR,output='sos'),x)
def lp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'low',fs=SR,output='sos'),x)
def hp(x,f,o=2): return signal.sosfilt(signal.butter(o,f,'high',fs=SR,output='sos'),x)
def place(x,t,gain=1.0,pan=0.0,name=None):
    if name: EV.append((round(t,3),name))
    i=int(t*SR)
    if x.ndim==1: x=np.stack([x*math.sqrt((1-pan)/2),x*math.sqrt((1+pan)/2)],1)*1.414
    j=min(N,i+len(x))
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
# ---------- sound designs（与第 2 集同款合成工具） ----------
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
def crackle(d=1.2,dens=400):  # 绒毛/颗粒的细碎声
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d,int(d*dens)):
        i=int(c*SR); k=min(len(t)-i,int(0.004*SR))
        if k>0: x[i:i+k]+=hp(rng.standard_normal(k),2500)*np.exp(-np.arange(k)/SR/0.0008)*rng.uniform(0.2,1)
    return x*np.sin(np.pi*t/d)*0.5
def hum(d=4.0,f=110):
    t=tt(d); return (np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2*t))*np.sin(np.pi*t/d)*0.06
def ding(f=1320):
    t=tt(1.2); return verb((np.sin(2*np.pi*f*t)+0.3*np.sin(2*np.pi*f*2.01*t))*np.exp(-t/0.35)*0.4,0.35)
def bell(f=660):
    t=tt(3.0); return verb((np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2.76*t)*np.exp(-t/0.3))*np.exp(-t/1.0)*0.3,0.5)
def counter_roll(d=9.8):
    # 计数器滚动（16 → 128）：tick 间隔从 0.34 s 加速到 0.045 s
    x=np.zeros(int(d*SR)); t=0.0; step=0.34
    while t<d-0.05:
        s=tick(); i=int(t*SR); x[i:i+len(s)]+=s[:len(x)-i]*0.8
        t+=step; step=max(0.045,step*0.965)
    return x

ev=[]
def E(t,x,g=1.0,pan=0.0,name=None): place(x,t,g,pan=pan,name=name)
# 01 PUZZLE：标题 → 一拍飞过球网（看似必出界）→ 急坠落进界内 → 推近球体
E(0.25,boom(3.5),0.5,name='boom:title')
E(2.90,pock(),0.5,name='hit:inferred')                    # 画外击球（推定，低置信）
E(2.95,verb(swish(9.3,300,2400),0.25),0.40,name='flight')
E(12.30,verb(bounce(1.0),0.3),0.85,name='bounce:puzzle')  # 落点闪帧＋高频峰 13.4×@12.12 佐证
E(12.85,blip(2400,0.08,1.1,0.5),0.45,name='ring:in')
E(13.60,verb(swish(1.2,800,6000),0.3),0.35,name='zoom')
# 02 HISTORY：章节卡 → 牛顿 1672 原信 → 旋转圆柱（1852 / 今天）
E(15.10,boom(4.0),0.55,name='boom:magnus-title')
E(19.00,panel(),0.5,name='panel:letter')
E(25.60,verb(swish(1.6,400,4000),0.3),0.4,name='cylinder')
# 03 MECHANISM：球体参数 → 气流上下 → 边界层/尾流 → 128 球实测 → 0.41 N
E(35.20,panel(),0.45,name='panel:ball')
E(39.60,number_pop(),0.5,name='pop:3200rpm')
E(43.60,blip(2200,0.06,1.2,0.4),0.4,name='label:surface')
E(48.70,verb(swish(1.2,300,3000),0.3),0.35,name='airflow')
E(51.60,panel(),0.4,name='panel:148-68')
E(60.30,crackle(3.0,300),0.5,name='fuzz')
E(64.00,verb(swish(1.0,300,2600),0.3),0.35,name='separation')
E(70.80,verb(swish(2.2,200,1800),0.3),0.4,name='wake')
E(72.00,number_pop(),0.45,name='pop:magnus-arrow')
E(78.30,crackle(4.5,220),0.45,name='fuzz:macro')
E(84.00,panel(),0.4,name='panel:how-strong')
E(86.40,panel(),0.5,name='panel:cameras')
E(86.90,blip(2600,0.06,1.0,0.5),0.4,name='chip:cam1'); E(87.30,blip(2900,0.06,1.0,0.5),0.35,name='chip:cam2')
E(87.50,counter_roll(9.8),0.5,name='counter:16-128')
E(93.50,hum(3.5,140),0.8,name='hum:cl-bar')
E(98.00,number_pop(),0.7,name='pop:128')                  # 高频峰 4.2×@98.02 佐证
E(100.10,number_pop(),0.6,name='pop:0.41N')
E(104.10,number_pop(),0.55,name='pop:0.56N')
E(108.00,number_pop(),0.65,name='pop:1.7x')
# 04 EVIDENCE：四条弹道（0/1900/3200/4000 rpm）→ 偏差为何晚现 → 弹跳对比 → 0.21 s
for t_land,t_hit,g in ((120.70,118.50,1.0),(125.70,124.10,0.95),(129.20,127.30,0.95),(132.50,131.30,0.95)):
    E(t_hit,pock(),0.75*g,name='hit:launch'); E(t_hit,verb(swish(t_land-t_hit,500,3500),0.2),0.38*g,name='flight')
    E(t_land,verb(bounce(1.0),0.3),0.85*g,name='bounce:land')
E(132.90,blip(2400,0.08,1.1,0.5),0.4,name='ring:in4000')
E(139.90,verb(swish(3.0,300,2600),0.25),0.30,name='draw:arcs')
E(141.00,number_pop(),0.4,name='pop:0.9m')
E(144.60,verb(swish(2.6,300,2600),0.25),0.28,name='draw:gap')
E(148.20,number_pop(),0.4,name='pop:3.1m')
E(151.90,verb(swish(3.0,300,2600),0.25),0.30,name='draw:same-spot')
E(156.00,number_pop(),0.4,name='pop:24.1deg')
E(160.00,panel(),0.4,name='panel:net-clearance')
E(165.60,verb(swish(5.5,300,2200),0.25),0.35,name='flight:pair')
E(167.45,verb(bounce(1.0),0.3),0.8,name='bounce:pair1')   # 高频峰 7.2×@167.41 佐证
E(169.50,verb(bounce(1.0),0.3),0.8,name='bounce:pair2')   # 高频峰 5.6×@169.50 佐证
E(171.90,number_pop(),0.4,name='pop:peaks')
E(183.20,verb(swish(4.0,400,3000),0.25),0.35,name='flight:timer')
E(184.70,verb(bounce(1.0),0.3),0.75,name='bounce:timer')  # 高频峰 9.6×@184.66 佐证
E(187.30,ding(1320),0.45,name='ding:0.21s')
# 05 REAL MATCHES：四根 rpm 柱依次升起
E(190.40,number_pop(),0.55,name='pop:2708')
E(195.00,number_pop(),0.55,name='pop:3291')
E(199.20,number_pop(),0.55,name='pop:3316')
E(203.60,number_pop(),0.6,name='pop:3200')
# 06 ANSWER：片头同一拍重放 → 大字结论 → 双弹道宽景重放 → 收句
E(210.60,pock(),0.6,name='hit:replay')
E(210.70,verb(swish(8.2,300,2400),0.25),0.35,name='flight:replay')
E(219.00,verb(bounce(1.0),0.3),0.85,name='bounce:replay') # 高频峰 4.1×@219.24 佐证
E(219.60,blip(2400,0.08,1.1,0.5),0.4,name='ring:replay')
E(223.60,boom(3.5),0.5,name='boom:sharper-dive')
E(228.80,pock(),0.6,pan=-0.2,name='hit:wide'); E(228.90,pock(),0.6,pan=0.2,name='hit:wide2')
E(228.90,verb(swish(3.4,400,3200),0.25),0.35,name='flight:wide')
E(231.70,verb(bounce(1.0),0.3),0.7,name='bounce:wide-out')
E(232.05,verb(bounce(1.0),0.3),0.85,name='bounce:wide-in') # 高频峰 5.0×@232.01 佐证
E(232.50,blip(2400,0.08,1.1,0.5),0.4,name='ring:wide')
E(234.00,bell(660),0.45,name='bell:close'); E(235.00,bell(523),0.4,name='bell:close2')
E(239.30,panel(),0.35,name='panel:references')
# 章节切换：每段前一个上扬，切点一记冲击（与第 2 集同款）
for k in (14.25,34.6,111.6,188.5,210.1):
    E(k-1.7,verb(riser(1.7),0.3),0.3,name='riser'); E(k,hit(),0.45,name='impact')
# 字幕弹出（锚定字幕逐条，时间自成片帧采样，±0.7 s）
for s in (3.2,10.8,19.3,27.3,31.3,35.4,39.4,43.4,47.4,51.4,59.4,63.9,71.4,75.4,79.4,83.9,99.9,103.9,107.9,
          112.4,118.2,123.7,126.7,130.7,133.7,136.2,139.7,143.7,151.7,159.7,163.7,171.7,175.7,182.7,
          188.9,195.7,203.5,211.0,219.8,228.3,233.8):
    E(s,blip(1900,0.045,1.25,0.35),0.45,name='cap')
# 全片底噪：低频室内声，保证任何一段都不是数字静音（第 2 集 sfx.py 同款配方）
t_=tt(TOTAL); bed=lp(rng.standard_normal(len(t_)),220,4)*0.05+np.sin(2*np.pi*55*t_)*0.004*(1+0.3*np.sin(2*np.pi*0.07*t_))
bed*=np.minimum(1,np.minimum(t_/1.5,(TOTAL-t_)/2.0)); out[:len(bed)]+=np.stack([bed,np.roll(bed,700)],1)
out=out[:int(TOTAL*SR)]
pk=np.abs(out).max(); out=out/pk*0.9; out=np.tanh(out*1.2)/np.tanh(1.2)
sf.write(os.path.join(WORK,'sfx','sfx_bed.wav'),out.astype(np.float32),SR,subtype='FLOAT')
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
from collections import Counter; print(len(EV),Counter(e[1].split(':')[0] for e in EV).most_common(12))

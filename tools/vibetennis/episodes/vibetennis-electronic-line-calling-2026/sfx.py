# vibetennis 第 2 集《电子司线，真的准吗？》音效床（全部用 numpy/scipy 现场合成，不用外部素材）。
# 合成工具抄自第 1 集 sfx.py；事件表是这一集的，逐条对齐 r3d/shots.js 与 overlay.py 的画面事件。
# Every sound is generated here with numpy/scipy (no downloaded assets).
import numpy as np, soundfile as sf, sys, json, math
from scipy import signal
import os
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
sys.path.insert(0,HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
import overlay as OV
SR=48000; snap=OV.snap
TOTAL=244.4; N=int(TOTAL*SR)+SR
rng=np.random.default_rng(7)
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


# ---------- 这一集的新声音 ----------
def shutter():               # 高速相机快门：两段短促的机械咔嗒
    t=tt(0.05); a=hp(rng.standard_normal(len(t)),2500)*np.exp(-t/0.004)*0.7; x=np.zeros(int(0.08*SR)); x[:len(a)]+=a; k=int(0.022*SR); x[k:k+len(a)]+=a*0.6; return x
def zap(f0=900,f1=3200,d=0.35):  # 视线射出：上扫的细光束声
    t=tt(d); ph=2*np.pi*np.cumsum(f0*(f1/f0)**(t/d))/SR; return np.sin(ph)*np.exp(-t/(d*0.5))*np.minimum(1,t/0.004)*0.35
def ding(f=1320):
    t=tt(1.2); return verb((np.sin(2*np.pi*f*t)+0.3*np.sin(2*np.pi*f*2.01*t))*np.exp(-t/0.35)*0.4,0.35)
def power_on(i):
    t=tt(0.3); f=600+i*60; return (np.sin(2*np.pi*np.cumsum(f*(1+t/0.3))/SR)*np.exp(-t/0.12)*0.3)
def power_off(i):
    t=tt(0.6); f=900-i*30; return np.sin(2*np.pi*np.cumsum(f*(1-0.7*t/0.6))/SR)*np.exp(-t/0.25)*0.35
def squash():                 # 慢放下的压扁：低沉的橡胶闷响
    t=tt(1.4); return verb(np.sin(2*np.pi*np.cumsum(90-40*t/1.4)/SR)*np.exp(-t/0.45)*0.9+lp(rng.standard_normal(len(t)),500)*np.exp(-t/0.15)*0.4,0.3)
def slide(d=6.0):             # 慢放的摩擦滑行
    t=tt(d); n=bp(rng.standard_normal(len(t)),300,1800)*np.sin(np.pi*t/d)**1.5; return n*0.35
def crackle(d=1.2,dens=400):  # 红土颗粒飞溅 / 绒毛触地
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d,int(d*dens)):
        i=int(c*SR); k=min(len(t)-i,int(0.004*SR))
        if k>0: x[i:i+k]+=hp(rng.standard_normal(k),2500)*np.exp(-np.arange(k)/SR/0.0008)*rng.uniform(0.2,1)
    return x*np.sin(np.pi*t/d)*0.5
def glitch(d=0.8):
    t=tt(d); sq=np.sign(np.sin(2*np.pi*np.cumsum(rng.uniform(80,900,len(t)))/SR)); env=(rng.uniform(0,1,len(t)//400+1)>0.4).repeat(400)[:len(t)]
    return lp(sq*env,4000)*0.18
def hum(d=4.0,f=110):
    t=tt(d); return (np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2*t))*np.sin(np.pi*t/d)*0.06
def click(): t=tt(0.03); return hp(rng.standard_normal(len(t)),1500)*np.exp(-t/0.003)*0.8
def counter_roll(d=1.6):
    x=np.zeros(int(d*SR)); t=0.0; step=0.04
    while t<d-0.05: s=tick(); i=int(t*SR); x[i:i+len(s)]+=s[:len(x)-i]*0.8; t+=step; step*=1.05
    return x

ev=[]
def E(t,x,g=1.0,pan=0.0,name=None): place(x,t,g,pan=pan,name=name)
# 01 回放：慢放的球落地（TV 质感）→ IN 提示音 → 冻结、故障、扫描线、轰鸣
E(5.36,tvize(verb(bounce(0.35),0.3)),1.0,name='bounce:replay')
E(6.6,blip(2000,0.12,1.0,0.6),0.6,name='in-chime'); E(6.75,blip(2600,0.12,1.0,0.5),0.5)
E(9.8,glitch(0.8),0.9,name='glitch'); E(10.6,verb(swish(1.8,800,9000),0.3),0.5,name='scan'); E(10.6,boom(4.5),0.6,name='boom')
# 02 相机：12 台逐台上电；视锥展开；越肩镜头里球飞过
for i in range(12): E(15+0.6+i*0.35+0.2,power_on(i),0.55,pan=(i%2*2-1)*0.4,name='cam-on')
E(21.5,verb(swish(1.2,400,4000),0.3),0.45,name='frustum')
for k in range(3): E(28.3+k*2.66,verb(swish(0.5,600,5000),0.2),0.35,pan=-0.3,name='whoosh')
E(28.4,blip(3000,0.06,1.0,0.5),0.5,name='lock'); E(28.5,blip(3400,0.06,1.0,0.5),0.4)
# 03 定位：眼睛两条视线 → 叮；12 条视线逐条射出 → 交会闪光；帧点逐个落下；轨迹成形
E(36.0,zap(),0.6,name='ray'); E(36.5,zap(),0.6,name='ray'); E(37.6,ding(1320),0.6,name='ding')
E(43.3,zap(),0.6,name='ray'); E(43.9,zap(),0.6); E(45.0,zap(),0.6)
for k in range(9): E(46.5+k*0.08,zap(1200,4200,0.25),0.35,name='ray-burst')
E(44.0,ding(990),0.6,name='converge')
tb=0.55; t=50.5
while t<60 and tb<1.35: E(t,shutter(),0.45,name='frame'); t+=(1.05/24)/0.09; tb+=1.05/24
E(56.0,verb(swish(1.4,300,3000),0.3),0.45,name='trajectory')
# 04 帧率：每出一个残影一声快门；时间轴面板；「一两帧」
for n in range(13): E(60+n/1.6,shutter(),0.6,name='shutter')
E(72.2,panel(),0.5,name='panel'); E(77.0,number_pop(),0.6,name='pop')
# 05 落地：坠落 → 慢放压扁 → 接触圈；斜落滑行；推算的虚线椭圆
E(85.2,verb(swish(2.6,200,1600),0.3),0.45,name='fall'); E(88.0,squash(),0.9,name='squash'); E(90.0,blip(2400,0.08,1.1,0.5),0.5,name='ring')
E(96.6,verb(swish(1.0,300,2400),0.25),0.4); E(97.5,slide(6.0),0.8,name='slide'); E(97.5,squash(),0.5)
E(106.5,panel(),0.45,name='dashed')
# 06 球印：场地一分为二 → 颗粒 → 虚线 → 检视圈
E(110.2,verb(swish(1.2,500,6000),0.3),0.45,name='split'); E(112.0,crackle(1.6),0.9,name='clay-grain'); E(114.0,blip(2200,0.06,1.2,0.4),0.5)
E(124.0,hum(6.0,140),1.0,name='inspect')
# 07 精度：尺子展开 → 2.6 → 认证面板 → 100% → 0.15 秒计时
E(130.2,counter_roll(1.4),0.5,name='ruler'); E(133.8,number_pop(),0.7,name='pop'); E(139.0,panel(),0.5); E(140.0,verb(swish(1.6,300,3000),0.3),0.4,name='zones')
E(143.6,number_pop(),0.6); E(148.6,tick(),0.8,name='timer'); E(148.75,blip(1700,0.1,0.8,0.6),0.6,name='out-call')
# 08 人眼：误差带展开 → 变宽 → 计数器
E(156.0,hum(3.0,90),1.2,name='band'); E(164.4,verb(swish(1.8,150,1500),0.3),0.5,name='widen'); E(170.0,counter_roll(1.6),0.6,name='count'); E(171.7,number_pop(),0.6)
# 09 局限：琥珀带 → 抬高的地面 → 两条落点 → 绒毛
E(180.4,verb(swish(1.0,600,4000),0.3),0.35); E(187.4,squash(),0.4,name='bump'); E(187.6,zap(500,1500,0.6),0.5); E(189.5,zap(500,1800,0.6),0.5); E(190.4,blip(2600,0.06,1.0,0.5),0.5)
E(197.0,crackle(2.5,250),0.7,name='fibre')
# 10 人的角色：空椅子 → 脚误相机与按钮 → 半边相机误关 → 球出界无人判 → 主裁
E(203.2,blip(1400,0.2,0.7,0.5),0.5,name='no-challenge')
for i in range(6): E(206.3+i*0.15,power_on(i),0.4,name='ff-cam')
for k in range(4): E(210.4+k*0.95,click(),0.8,name='button')
xs=[p for p in range(12)]
for i in range(12):
    if i<6: E(214+0.4+i*0.18,power_off(i),0.5,name='cam-off')
E(218.41,verb(bounce(1.0),0.3),0.8,name='bounce:out'); E(219.4,ding(660),0.6,name='umpire')
# 11 收束
E(222.0,boom(5.0),0.6,name='boom')
def bell(f=660):
    t=tt(3.0); return verb((np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2.76*t)*np.exp(-t/0.3))*np.exp(-t/1.0)*0.3,0.5)
for dt_,f in ((0.6,523),(2.6,587),(6.5,784)): E(222.6+dt_,bell(f),0.5,name='bell')
E(236.0,panel(),0.4)
# 章节切换：每段前一个上扬，切点一记冲击
for k in (15,35,60,85,110,130,155,180,200,222):
    E(k-1.7,verb(riser(1.7),0.3),0.3,name='riser'); E(k,hit(),0.45,name='impact')
# 字幕弹出
for s,d,txt,pl in OV.CAPS: E(s,blip(1900,0.045,1.25,0.35),0.45,name='cap')
# 全片底噪：低频「太空」室内声，保证任何一段都不是数字静音
t_=tt(TOTAL); bed=lp(rng.standard_normal(len(t_)),220,4)*0.05+np.sin(2*np.pi*55*t_)*0.004*(1+0.3*np.sin(2*np.pi*0.07*t_))
bed*=np.minimum(1,np.minimum(t_/1.5,(TOTAL-t_)/2.0)); out[:len(bed)]+=np.stack([bed,np.roll(bed,700)],1)
# 体育场人声：开场回放与越肩看球两段
place(crowd(10.6),0.0,0.25,name='crowd'); place(crowd(7.4),27.8,0.3,name='crowd'); place(crowd(22.4),200.0,0.18,name='crowd')
out=out[:int(TOTAL*SR)]
pk=np.abs(out).max(); out=out/pk*0.9; out=np.tanh(out*1.2)/np.tanh(1.2)
sf.write(os.path.join(WORK,'sfx','sfx_bed.wav'),out.astype(np.float32),SR,subtype='FLOAT')
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
from collections import Counter; print(len(EV),Counter(e[1].split(':')[0] for e in EV).most_common(12))

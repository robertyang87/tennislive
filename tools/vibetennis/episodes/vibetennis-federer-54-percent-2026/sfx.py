# vibetennis 第 4 集《费德勒只赢了 54% 的分》音效床：音效全部用 numpy/scipy 现场合成，与画面事件逐条对齐；
# BGM 不自己做（账号所有者 2026-11-01：「不要自己创造 BGM，用那个 vibeknowledge 库里面的 BGM」「只是需要创造声效和音效」），
# 用 robertyang87/vibeknowledge 的 assets/music/we-never-remix-hi-noise-qiucheng.m4a（抖音 Vibe 知识赛道统一配乐，
# 版权归原作者，库内 README 注明发布时优先用平台曲库同曲）。合成工具抄自第 2 集 sfx.py。
import numpy as np, soundfile as sf, sys, json, math, os
from scipy import signal
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
SR=48000
# 2026-11-01 改版：时间轴插入新段 A（马尔可夫的发现）、片尾换成新段 B（金句），映射与 r3d/shots.js 的 WARP 一致
WARP=dict(A0=15.5,LA=42.02,B_OLD=176.2,B_DROP=3.8,LB=19.96); B0=WARP['B_OLD']+WARP['LA']   # LA 二改 32.32 → 42.02; B0=WARP['B_OLD']+WARP['LA']
def toNew(t):
    w=WARP
    if t<w['A0']: return t
    if t<w['B_OLD']: return t+w['LA']
    if t<w['B_OLD']+w['B_DROP']: return None
    return t+w['LA']+w['LB']-w['B_DROP']
TOTAL=188.2+WARP['LA']+WARP['LB']-WARP['B_DROP']; N=int(TOTAL*SR)+SR
rng=np.random.default_rng(54)
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


def E(t,x,g=1.0,pan=0.0,name=None):   # 旧时间轴上的事件：映射到新时间；落在被替掉的旧 [176.2,180) 里的就不放
    tn=toNew(t)
    if tn is not None: place(x,tn,g,pan=pan,name=name)
def EN(t,x,g=1.0,pan=0.0,name=None): place(x,t,g,pan=pan,name=name)   # 新时间轴上的事件

# ---------- 音高与低频脉冲（音效用） ----------
def hz(m): return 440*2**((m-69)/12)
def sub(f,d=0.55):
    t=tt(d); return np.sin(2*np.pi*f*t*(1+0.12*np.exp(-t/0.03)))*np.exp(-t/0.25)*np.minimum(1,t/0.004)

# ================= 新声音 =================
def shatter():
    t=tt(1.6); x=np.zeros(len(t))
    for c in rng.uniform(0,0.5,260):
        i=int(c*SR*(0.2+c)); k=min(len(t)-i,int(0.03*SR))
        if k>0: f=rng.uniform(2500,9000); x[i:i+k]+=np.sin(2*np.pi*f*np.arange(k)/SR)*np.exp(-np.arange(k)/SR/0.008)*rng.uniform(0.2,1)
    x+=hp(rng.standard_normal(len(t)),3000)*np.exp(-t/0.05)*0.8
    return verb(x*0.5,0.4)
def sparkle(d=1.5,dens=60):
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d,int(d*dens)):
        i=int(c*SR); s=blip(rng.uniform(3000,6500),0.05,1.0,rng.uniform(0.1,0.35)); k=min(len(t)-i,len(s)); x[i:i+k]+=s[:k]
    return verb(x,0.4)
def chime(notes,gap=0.18,amp=0.4):
    d=gap*len(notes)+1.4; x=np.zeros(int(d*SR))
    for k,m in enumerate(notes):
        t=tt(1.4); s=(np.sin(2*np.pi*hz(m)*t)+0.3*np.sin(2*np.pi*hz(m)*2.01*t))*np.exp(-t/0.4)*amp; i=int(k*gap*SR); x[i:i+len(s)]+=s
    return verb(x,0.35)
def slam():
    t=tt(1.2); x=np.sin(2*np.pi*np.cumsum(70*np.exp(-t*3)+35)/SR)*np.exp(-t/0.3)+lp(rng.standard_normal(len(t)),900)*np.exp(-t/0.04)*0.5
    return verb(x*0.8,0.25)
def alarm(d=1.6):
    t=tt(d); return (np.sin(2*np.pi*233*t)+np.sin(2*np.pi*247*t))*0.12*np.sin(np.pi*t/d)
def drop_tick():
    x=bounce(1.8)*0.6; k=tick(); x[:len(k)]+=k*0.4; return x

# ================= 事件表（对齐 shots.js） =================
# 00 开场
E(0.05,swish(1.3,200,3000),0.5,name='galaxy-forms'); E(0.1,sparkle(1.6,50),0.5)
E(0.3,counter_roll(1.3),0.5,name='count-1526')
E(1.25,hit(),0.5,name='galaxy-lock'); E(2.45,swish(0.9,400,4000),0.4); E(3.35,number_pop(),0.9,name='82%'); E(3.35,hit(),0.6)
E(4.0,swish(0.6,800,6000),0.5,name='dive'); E(4.05,crackle(0.6,900),0.6); E(5.3,number_pop(),0.9,name='54%'); E(5.3,hit(),0.6)
E(5.25,riser(1.8),0.35,name='riser-title'); E(6.35,glitch(0.5),0.6,name='glitch')
# 01 标题
E(7.0,swish(1.2,300,5000),0.6,name='ball-in'); E(8.18,pock(0.6),0.9,name='ball-smash'); E(8.18,hit(),0.9); E(8.3,crackle(1.8,500),0.6,name='particles')
E(9.0,swish(1.7,200,2500),0.35); E(11.1,boom(4.0),0.7,name='title-lock'); E(11.1,ding(880),0.6); E(11.15,sparkle(2.0,40),0.4)
for k in range(3): E(12.4+k*0.5,blip(1800+k*400,0.08,1.2,0.6),0.5,name='chip')
E(14.9,swish(0.9,600,4000),0.4)
# 02 天平
E(15.6,power_on(3),0.6,name='scale-on')
import bisect
drop=list(range(100)); rr=np.random.default_rng(1)
# 100 颗球的落点时间：n(t)=((t-17.2)/7.5)^1.35*100，第 di 个落下的球在 n=di+1 时着落（与 shots.js 同一公式）
for di in range(100):
    tland=17.2+7.5*((di+1)/100)**(1/1.35)
    E(tland,drop_tick(),1.6,pan=rr.uniform(-0.6,0.6),name='ball-land' if di%10==0 else None)
E(25.9,swish(1.6,1200,5000),0.25,name='coin'); E(26.0,sparkle(1.2,30),0.3)
# 03 一局：河道
for k in range(18): E(33.3+k*0.17,blip(1400+k*60,0.05,1.1,0.4),0.3,name='node' if k==0 else None)
E(44.0,crackle(17.0,160),1.4,name='flow-start'); E(44.0,hum(17.0,110),0.6)
E(51.8,swish(2.4,300,1800),0.35,name='deuce-swirl')
E(58.6,riser(2.6),0.3); E(61.2,number_pop(),0.9,name='60%'); E(61.2,chime([69,72,76]),0.6)
# 04 套娃
E(64.4,swish(1.6,2000,200),0.6,name='shrink-game'); E(65.9,hit(),0.6); E(69.0,crackle(11.0,150),1.3); E(69.0,hum(11.0,130),0.5)
E(79.8,number_pop(),0.9,name='76%'); E(79.8,chime([72,76,79]),0.6)
E(82.5,swish(1.6,2000,200),0.6,name='shrink-set'); E(84.3,hit(),0.6); E(86.3,crackle(6.5,180),1.3); E(86.3,hum(6.5,165),0.5)
E(88.0,riser(2.3),0.35); E(90.3,number_pop(),1.0,name='91%'); E(90.3,boom(3.5),0.6); E(90.3,chime([76,79,84]),0.6)
# 05 S 曲线
E(95.2,panel(),0.6,name='chart-on')
for k,ts in enumerate((96.8,99.0,101.2,103.4)): E(ts,zap(500+k*250,2000+k*900,1.6),0.5,name='curve%d'%k)
E(105.4,chime([60,64,67,72],0.2),0.7,name='scan-lock')
E(108.6,swish(1.2,3000,300),0.45,name='slide-50'); E(110.6,tick(),0.8); E(110.6,swish(1.4,300,3000),0.4,name='slide-51'); E(113.5,number_pop(),0.9,name='63%')
# 06 验证
E(117.3,riser(1.2),0.25)
for i in range(3): E(121.5+i*0.9,blip(2200,0.1,1.05,0.6),0.45,name='ghost%d'%i)
for i in range(3): E(126.5+i*1.5+0.9,slam(),0.8,name='real%d'%i)
for i in range(3): E(131.0+i*0.3,click(),0.6)
E(135.2,chime([72,76,79,84],0.15),0.6,name='holds')
# 07 局限
E(140.4,blip(2200,0.1,1.05,0.6),0.45); E(142.5,slam(),0.8,name='real-82'); E(143.0,alarm(1.8),0.8,name='gap')
E(147.6,swish(0.9,4000,300),0.5,name='to-court'); E(148.2,crowd(9.0),0.35,name='crowd'); E(149.3,counter_roll(3.6),0.5,name='points-fill')
E(154.0,boom(3.0),0.6,name='champion'); E(154.0,applause(2.6),0.5)
E(157.2,swish(0.9,300,2500),0.4,name='40-15'); E(158.0,hum(2.8,98),0.8); E(160.8,shatter(),0.9,name='shatter'); E(160.8,hit(),0.7)
E(162.6,sub(hz(33),1.4),0.5)
# 08 收束
E(164.0,sparkle(4.0,30),0.35,name='sea'); E(168.2,swish(1.6,300,2000),0.35); E(170.0,ding(660),0.5,name='only-a-point')
E(176.2,ding(880),0.3)

# ================= 新段 A：马尔可夫的发现（新时间 15.5–47.82） =================
A=WARP['A0']
EN(A+0.15,number_pop(),0.8,name='1906'); EN(A+0.15,hit(),0.5)
EN(A+3.4,swish(1.4,3000,600),0.4,name='scatter'); EN(A+3.4,crackle(1.4,600),0.6)
EN(A+6.0,swish(1.2,300,2500),0.45,name='links')
for k in range(6): EN(A+6.5+k*0.2,click(),0.55,pan=-0.5+k*0.2)
EN(A+10.2,swish(1.4,400,4000),0.4,name='onegin'); EN(A+10.3,sparkle(1.6,40),0.35)
EN(A+13.6,counter_roll(1.8),0.5,name='count-20000'); EN(A+15.3,tick(),0.7)
EN(A+16.8,hit(),0.5,name='two-nodes'); EN(A+17.2,power_on(2),0.5)
ONEGIN_TXT='Мой дядя самых честных правил Когда не в шутку занемог Он уважать себя заставил И лучше выдумать не мог Его пример другим наука'
SEQ=[1 if ch in 'аеёиоуыэюяАЕЁИОУЫЭЮЯ' else 0 for ch in ONEGIN_TXT if ch.isalpha() and ch not in 'ъьЪЬ']
for k in range(40):   # 令牌每跳一下：落到元音（左，金）音高一点，落到辅音（右，蓝）低一点
    th=A+18.4+k*0.42+0.3
    if th<A+34.8 and k+1<len(SEQ): v=SEQ[k+1]; EN(th,blip(2100 if v else 1500,0.05,1.05,0.5),0.22,pan=-0.45 if v else 0.45,name='hop' if k==0 else None)
EN(A+17.6,ding(1320),0.4,name='12.8%'); EN(A+20.7,ding(990),0.4,name='66.3%')
EN(A+23.2,chime([69,74,78]),0.5,name='three-parts')
for k_,tk in enumerate((25.3,27.6,31.5)): EN(A+tk,blip(1600+k_*400,0.09,1.15,0.7),0.5,name='part%d'%(k_+1))
EN(A+31.6,swish(0.8,3000,500),0.3,name='past-fades')
EN(A+35.6,number_pop(),0.7,name='0-0'); EN(A+36.4,zap(800,2600,0.4),0.35,pan=0.4); EN(A+36.4,zap(800,1800,0.4),0.35,pan=-0.4)
EN(A+41.0,swish(0.9,600,4000),0.4)
# ================= 新段 B：金句（新时间 208.52–228.48） =================
EN(B0+0.5,swish(2.2,2000,200),0.45,name='lost-drift'); EN(B0+0.6,crackle(3.0,220),0.6)
EN(B0+0.9,counter_roll(2.0),0.45,name='count-108336')
EN(B0+4.2,power_on(2),0.45,name='game-chain'); EN(B0+4.5,ding(880),0.4,name='0-0-reset')
EN(B0+10.4,boom(3.5),0.4,name='golden'); EN(B0+10.4,ding(660),0.45); EN(B0+10.5,sparkle(2.0,30),0.3)
EN(B0+15.9,ding(880),0.3,name='question')

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_OFF=0.309   # 曲子 74 BPM、拍点 0.097+k·0.808 s；从 0.309 s 起取，标题锁定转金（片中 11.1 s）正好落在拍上
BGM_LUFS=-20.0  # 铺底响度；音效叠在上面，整片之后再归一到 -14 LUFS
raw=subprocess.run(['ffmpeg','-v','error','-ss',str(BGM_OFF),'-i',BGM,'-t','188.2','-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
bgm0=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
# 插入整小节（标题锁定 11.1 s 在拍上，小节线 11.1+3.232·m）：17.564 s 处重复其后 13 小节（＋4 ms，＝新段 A 的长度 42.02 s）；
# 175.932 s 处重复其前 5 小节（＝新段 B 净增的长度）。拼缝 10 ms 交叉淡化，免得爆音
def cut(a,b): return bgm0[int(a*SR):int(b*SR)]
parts=[cut(0,17.564+WARP['LA']),cut(17.564,175.932),cut(175.932-16.16,175.932),cut(175.932,188.2)]   # A 段长 42.02 = 13 小节 + 4 ms
xf=int(0.006*SR); r=np.linspace(0,1,xf)[:,None]
for i_,p_ in enumerate(parts):
    p_=p_.copy()
    if i_>0: p_[:xf]*=r
    if i_<len(parts)-1: p_[-xf:]*=r[::-1]
    parts[i_]=p_
bgm=np.concatenate(parts)   # 长度与新时间轴严格一致（不重叠），拼缝处各 6 ms 淡入淡出
tmp=os.path.join(WORK,'sfx','_bgm_raw.wav'); sf.write(tmp,bgm.astype(np.float32),SR,subtype='FLOAT')
meas=subprocess.run(['ffmpeg','-hide_banner','-i',tmp,'-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr
I=float(re.findall(r"I:\s+(-?[\d.]+) LUFS",meas)[-1]); os.remove(tmp)
bgm*=10**((BGM_LUFS-I)/20)
B=np.zeros((N,2)); B[:min(N,len(bgm))]=bgm[:N]
SFX_GAIN=0.2   # 音效整体约 -23 LUFS，比 BGM 铺底低 3 dB：BGM 是主体，音效在画面事件上点亮
mix=out*SFX_GAIN+B
fade=np.ones(N); k=int(toNew(186.5)*SR); fade[k:]=np.linspace(1,0,N-k)**2; mix*=fade[:,None]
sf.write(os.path.join(WORK,'sfx','sfx_bed.wav'),mix.astype(np.float32),SR,subtype='FLOAT')
sf.write(os.path.join(WORK,'sfx','sfx_only.wav'),(out*SFX_GAIN).astype(np.float32),SR,subtype='FLOAT')
sf.write(os.path.join(WORK,'sfx','bgm_bed.wav'),(B*fade[:,None]).astype(np.float32),SR,subtype='FLOAT')   # 中文版配音混音（voice.py）用：BGM 单独一轨
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
print(len(EV),'events')

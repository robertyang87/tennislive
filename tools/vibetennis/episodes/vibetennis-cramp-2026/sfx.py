# vibetennis EP11 抽筋音效床：音效用 numpy/scipy 现场合成（音色同第 5～7 集 sfx.py），
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

# ================= 事件 =================
# 时刻全部取自 r3d/timeline.json 的 sec.ev 与 scene.js 各 shot 的动画节点（撞击都在循环的 k=0.5）
for s in TL['sections'][1:]: EN(s['t0']-0.25,swish(0.9,400,2600),0.35,name='cut-'+s['name'])
def scrape(d=3.0):            # 球贴着线滑：带通噪声，越滑越轻
    t=tt(d); return bp(rng.standard_normal(len(t)),1200,5200)*np.exp(-t/(d*0.5))*np.minimum(1,t/0.05)*0.35
def impacts(t0,t1,per,phase=0.5,g=0.8,rate=0.6,name=None,pan=0.0):
    t=t0+phase*per; n=0
    while t<t1-0.05: EN(t,pock(rate),g,pan=pan,name=(name+'-%d'%n) if name else None); t+=per; n+=1
def creak(d=0.8,f=180):        # 木头弯曲／开裂的吱声：低频锯齿＋颤动
    t=tt(d); ph=2*np.pi*np.cumsum(f*(1+0.25*np.sin(2*np.pi*7*t))*(1-0.2*t/d))/SR
    return bp(signal.sawtooth(ph),150,2400)*np.minimum(1,t/0.05)*np.exp(-t/(d*0.6))*0.5
def crackle(d=0.6):           # 细裂纹：稀疏的高频脆响
    t=tt(d); x=np.zeros(len(t))
    for _ in range(14): i=int(rng.uniform(0,len(t)-600)); x[i:i+600]+=hp(rng.standard_normal(600),2500)*np.exp(-np.arange(600)/SR/0.002)*rng.uniform(0.3,1)
    return x
def metal_scrape(d=1.2):      # 线压在金属孔边：高频摩擦＋金属谐振
    t=tt(d); return bp(rng.standard_normal(len(t)),2200,7000)*np.sin(np.pi*t/d)**2*0.4+np.sin(2*np.pi*3150*t)*np.exp(-t/0.4)*0.12
def groan(d=1.6,f=95):         # 慢放里拍框扭转的「呻吟」
    t=tt(d); return lp(signal.sawtooth(2*np.pi*np.cumsum(f*(1+0.3*t/d))/SR),900)*np.sin(np.pi*t/d)**1.5*0.45
def page_slide(): t=tt(0.6); return bp(rng.standard_normal(len(t)),600,5000)*np.sin(np.pi*t/0.6)**2*0.35

def hiss(d=2.0,lo=1500,hi=7000):  # 充气／蒸汽：带通噪声，起落平滑
    t=tt(d); return bp(rng.standard_normal(len(t)),lo,hi)*np.sin(np.pi*np.minimum(1,t/d))**1.2*0.4
def squish(rate=1.0):           # 橡胶被压扁：低频闷响＋短促的橡胶摩擦
    t=tt(0.35/rate); return (lp(rng.standard_normal(len(t)),700)*np.exp(-t/(0.06/rate))*0.8+np.sin(2*np.pi*95*rate*t)*np.exp(-t/(0.12/rate))*0.6)*0.7
def rumble(d=3.0):              # 球堆倾泻：一串随机的落球
    t=tt(d); x=np.zeros(len(t))
    for c in rng.uniform(0,d*0.9,int(d*40)):
        k=bounce(rng.uniform(0.8,1.3)); i=int(c*SR); j=min(len(t),i+len(k)); x[i:j]+=k[:j-i,0] if k.ndim==2 else k[:j-i]*rng.uniform(0.05,0.25)
    return x*0.6

def whoosh_fast(d=0.35): t=tt(d); return bp(rng.standard_normal(len(t)),1500,8000)*np.sin(np.pi*t/d)**2*0.6
def tick_seq(t0,n,gap,g=0.35,name=None):
    for i in range(n): EN(t0+i*gap,tick(),g,name=(name+'-%d'%i) if (name and i==0) else None)

# 01 钩子：上海夜场 → 辛纳抽筋倒地 → 水、盐、香蕉飞来 → 一滴腌黄瓜汁砸下击碎 → 85 秒 → 还在胃里 → 管住了什么？
h=SEC['hook']; FALL=E('hook','fall',2.3); CRW=E('hook','crowd',4.5); SLT=E('hook','salt',7.2); DR=E('hook','drop',11.7); CK=E('hook','clock',14.2); STM=E('hook','stomach',16.7); QQ=E('hook','q',19.9)
EN(h['t0'],crowd(CRW+1.0),0.3,name='crowd'); EN(h['t0']+0.6,pock(1.0),0.6,name='rally'); EN(h['t0']+1.6,bounce(1.0),0.3)
EN(FALL-0.3,riser(0.3),0.4); EN(FALL,sub_boom(),0.8,name='CRAMP'); EN(FALL+0.05,creak(0.8,140),0.5); EN(FALL+0.2,heartbeat(),0.5)
for k,p in enumerate([-0.6,0.6,0.0]): EN(CRW+0.2+0.3*k,swish(0.7,400,3200),0.35,pan=p,name='props-in' if k==0 else None)
EN(SLT-0.5,sparkle(1.2),0.4,name='salt')
EN(DR-1.0,riser(1.0),0.5,name='drop-fall'); EN(DR,sub_boom(),0.9,name='DROP'); EN(DR,slam(),0.7); EN(DR+0.05,rain_hiss(1.4),0.5,name='shatter'); EN(DR+0.1,boom(2.2),0.35)
EN(CK,number_pop(),0.55,name='85s'); tick_seq(CK+0.2,6,0.2,0.3,'clock'); EN(STM,hum(3.0,70),0.35,name='stomach'); EN(QQ,hit(),0.5,name='question')
# 02 两派：离子变稀 vs 神经放电
CS=E('camps','split',0.5); WA=E('camps','wat',4.7); NV=E('camps','nerve',10.2)
EN(CS,panel(),0.35,name='versus'); EN(WA,rain_hiss(1.6),0.3,name='ions'); EN(NV,zap(900,3200,0.4),0.4,name='nerve'); EN(NV+0.5,zap(1200,3600,0.3),0.3)
# 03 腌黄瓜实验：电刺激 → 抽紧 → 计时赛跑 → 胃里不动 → 神经反射闪电
LB=E('pickle','lab',0.5); ZP=E('pickle','zap',4.2); PC=E('pickle','cramp',5.2); WT=E('pickle','water',10.7); PJt=E('pickle','pj',13.4); GT=E('pickle','gut',16.9); FLt=E('pickle','flat',21.2); RF=E('pickle','reflex',28.2)
EN(LB,hum(4.0,82),0.3); EN(ZP,zap(900,3200,0.35),0.5,name='electrode'); EN(PC,creak(0.9,150),0.45,name='foot-cramp')
tick_seq(WT,int(max(1,(GT-0.8-WT)/0.25)),0.25,0.25,'timer'); EN(WT+(GT-0.8-WT)*84.6/150,ding(1320),0.5,name='85-stop'); EN(WT+(GT-0.8-WT)*133.7/150,ding(880),0.4,name='134-stop')
EN(GT,hum(4.0,65),0.35,name='body-xray'); EN(FLt,blip(1600,0.1,1.0,0.5),0.4,name='blood-flat')
EN(RF-0.3,riser(0.3),0.35); EN(RF,zap(3200,600,0.6),0.55,name='REFLEX'); EN(RF+1.0,sub_boom(),0.45)
# 04 油门与刹车：退出小腿 → 肌梭 → 油门 → 腱器 → 刹车 → 累了（心跳加快）→ 放电风暴 → 锁死
DV=E('brake','dive',0.5); SPd=E('brake','spindle',6.0); GA=E('brake','gas',8.5); GO_=E('brake','gto',10.5); BK=E('brake','brk',14.2); TIr=E('brake','tired',18.8); SMm=E('brake','storm',25.2); LK=E('brake','lock',26.5)
EN(DV,swish(1.2,300,2600),0.45,name='pull-out'); EN(DV+0.8,hum(6.0,60),0.3)
EN(SPd,ding(1047),0.45,name='spindle'); EN(GA,blip(2400,0.08,1.3,0.6),0.45,name='accelerator'); EN(GO_,ding(784),0.45,name='GTO'); EN(BK,blip(900,0.1,0.8,0.6),0.45,name='brake')
t=TIr; gap=1.0
while t<SMm: EN(t,heartbeat(),0.35); t+=gap; gap=max(0.45,gap*0.85)
EN(SMm,glitch(1.0),0.45,name='storm'); tick_seq(SMm,10,0.12,0.3,'firing'); EN(LK,slam(),0.7,name='LOCK'); EN(LK,sub_boom(),0.7)
# 05 拉伸：勾脚 → 刹车回来 → 松开
FX=E('stretch','flex',4.5); RL=E('stretch','relief',7.3)
EN(FX,creak(1.0,120),0.45,name='flex'); EN(FX+0.3,zap(600,1800,0.5),0.35,name='brake-signal'); EN(RL,chime([84,79,76,72],0.14,0.4),0.45,name='release')
# 06 数据：问题 → 209 个光点 → 两组一样高 → 速度拉开 → 脱水 4.7% → 香蕉
DQ=E('data','q',0.5); CWd=E('data','crowd',2.9); SAm=E('data','same',8.5); FS=E('data','fast',16.7); DH=E('data','dehyd',19.7); BN=E('data','banana',25.2)
EN(DQ,hit(),0.45,name='q'); EN(CWd,rain_hiss(1.8),0.4,name='209-dots'); EN(SAm,swish(0.9,300,2600),0.4,name='split'); tick_seq(SAm+0.6,2,0.4,0.35,'bars')
EN(FS,number_pop(),0.45,name='faster'); EN(DH,hiss(2.0,800,5000),0.35,name='dehydrate'); EN(DH+1.2,number_pop(),0.4,name='4.7')
EN(BN,swish(0.8,500,3000),0.4,name='banana'); tick_seq(BN+0.6,8,0.6,0.2,'slow-potassium')
# 07 盐派：标题 → 选手出汗 → 盐霜 → 加盐 → 湿热
TU=E('salt','turn',0.5); KD=E('salt','kid',4.9); SW=E('salt','sweat',5.8); LSs=E('salt','loss',8.2); FXs=E('salt','fixed',12.7); HM=E('salt','humid',16.3)
EN(TU,hit(),0.45,name='salt-camp'); EN(KD,crowd(SEC['salt']['t1']-KD),0.22); t=KD+0.4
while t<SEC['salt']['t1']-0.5: EN(t,pock(1.0),0.35); t+=2.4
EN(SW,rain_hiss(2.0),0.3,name='sweat'); EN(LSs,sparkle(1.5),0.4,name='salt-crust'); EN(LSs+0.8,number_pop(),0.35); EN(FXs,ding(1047),0.45,name='fixed'); EN(HM,hum(4.0,90),0.3,name='humid')
# 08 名场面：法网 → 全身抽筋 → 「是紧张」→ 上海 → 两样都有？
RGt=E('back','rg',3.0); BC=E('back','cramp',6.1); TN=E('back','tension',9.9); SHt=E('back','sh',11.9); BO=E('back','both',16.4)
EN(SEC['back']['t0'],crowd(SHt-SEC['back']['t0']),0.3,name='rg-crowd'); EN(RGt,panel(),0.3); EN(BC,sub_boom(),0.6,name='alcaraz-cramp'); EN(BC+0.1,groan(1.4,90),0.4)
EN(TN,heartbeat(),0.5,name='tension'); EN(TN+0.3,zap(2400,800,0.6),0.4); EN(SHt,swish(1.0,300,2400),0.4,name='to-shanghai'); EN(BO,chime([72,76],0.16,0.4),0.45,name='both')
# 09 结论：标题 → 先拉伸 → 补盐 → 问题
N0=E('end','n0',0.5); P1=E('end','p1',5.9); P2=E('end','p2',10.0); QE=E('end','q',12.1)
EN(N0,hum(4.0,82),0.3); EN(N0+0.2,slam(),0.35,name='title'); EN(P1,ding(880),0.4,name='stretch'); EN(P2,ding(1047),0.4,name='salt'); EN(QE,chime([72,76,79,84],0.15,0.45),0.5,name='question')

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_LUFS=-20.0
raw=subprocess.run(['ffmpeg','-v','error','-i',BGM,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
song=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
# 循环＋卡点（所有者 2026-11-04「BGM 要循环，同时看看怎么卡点」）：曲子 112.3 BPM，小节 4×0.53194 s，曲内第一个强拍 0.4757 s（librosa 实测）。
# 小节号 → 段落：0–7 前奏、8–39 主段、40–47 间奏（轻）、48–63 主段、64 起尾段淡出。起点 BGM_OFF 取钩子大问题砸下来那一刻＝第 8 小节线，
# 之后按「主段 → 间奏 → 主段 → 再从第 8 小节循环」整小节往后拼，不放尾段；拼缝都在小节线上，10 ms 交叉淡化
BAR=4*0.53194; bar=lambda k: 0.4757+k*BAR; BGM_OFF=bar(8)-DR   # 腌黄瓜汁砸下击碎三样常识那一刻＝第 8 小节线，主段进来
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
sf.write(os.path.join(WORK,'sfx','sfx_only.wav'),(out*SFX_GAIN*fade[:,None]).astype(np.float32),SR,subtype='FLOAT')   # 英文版直接用它当音轨（不带 BGM），所以也要片尾淡出
sf.write(os.path.join(WORK,'sfx','bgm_bed.wav'),(B*fade[:,None]).astype(np.float32),SR,subtype='FLOAT')
# 英文版不带 BGM（所有者 2026-11-02），只剩音效时句与句之间是空的——qc.py 的「背景声铺满」「>3 s 数字静音」两道闸会红，
# 而那两道闸防的正是死寂。所以英文版垫一层**自己合成的环境底**（不是音乐、没有版权）：低频持续音＋很淡的空气声，慢慢起伏，
# 片尾 3 s 淡出。所有者在 Instagram 挂曲库音乐时它在底下不打架。
t=np.arange(N)/SR; lfo=0.75+0.25*np.sin(2*np.pi*t/23.0)
drone=(np.sin(2*np.pi*55*t)*0.5+np.sin(2*np.pi*82.4*t+0.7)*0.3+np.sin(2*np.pi*110*t+1.3)*0.15)*lfo
air=np.stack([lp(rng.standard_normal(N),900),lp(rng.standard_normal(N),900)],1)*0.6
amb=drone[:,None]*np.array([[1.0,0.95]])+air*(0.8+0.2*np.sin(2*np.pi*t/17.0))[:,None]
tmp2=os.path.join(WORK,'sfx','_amb.wav'); sf.write(tmp2,amb.astype(np.float32),SR,subtype='FLOAT')
m2=subprocess.run(['ffmpeg','-hide_banner','-i',tmp2,'-af','ebur128','-f','null','-'],capture_output=True,text=True).stderr; os.remove(tmp2)
amb*=10**((-34.0-float(re.findall(r"I:\s+(-?[\d.]+) LUFS",m2)[-1]))/20)   # 环境底比音效低一截：-34 LUFS（音效事件平均约 -24）
amb[:int(0.5*SR)]*=np.linspace(0,1,int(0.5*SR))[:,None]
sf.write(os.path.join(WORK,'sfx','sfx_amb_en.wav'),((out*SFX_GAIN+amb)*fade[:,None]).astype(np.float32),SR,subtype='FLOAT')
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
print(len(EV),'events')

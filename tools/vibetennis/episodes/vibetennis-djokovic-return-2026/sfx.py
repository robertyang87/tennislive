# vibetennis 球篇（三部曲③）音效床：音效用 numpy/scipy 现场合成（音色同第 5～7 集 sfx.py），
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

# 01 钩子：黑场里球亮起 → 六道规格环逐道套上 → 球拍只有一个尺寸框 → 大问题
h=SEC['hook']; SP=E('hook','spin',0.3); SC=E('hook','specs',5.9); RK=E('hook','rk',10.5); QQ=E('hook','q',13.9)
EN(h['t0']+0.1,hum(RK-h['t0'],62),0.6,name='hook-drone'); EN(SP+0.2,sparkle(1.2,40),0.3,name='ball-on')
for i in range(6): EN(SC+i*0.42+0.1,blip(1100+i*220,0.09,1.2,0.6),0.45,name='spec-%d'%i)
EN(RK+0.4,panel(),0.35,name='racket-box'); EN(QQ,sub_boom(),0.5,name='question-hit'); EN(QQ+0.1,chime([76,83,88],0.14,0.4),0.45,name='question')
# 02 演化：五个展台逐个亮起
for i,k in enumerate(['leather','rubber','cloth','melton','hollow']):
    t=E('origin',k,0.5+i*4); EN(t,blip(800+i*180,0.12,1.15,0.5),0.45,name='pedestal-%d'%i); EN(t+0.15,ding(880+i*110),0.2)
EN(E('origin','hollow',17.4)+0.3,hiss(1.4,2000,7000),0.3,name='hollow-gas')
# 03 构造：压机合拢、受热 → 两半合上同时充气 → 毛毡飞来合拢 → 蒸汽 → 有压／无压 → 毛衣
PR=E('make','press',0.5); HT=E('make','heat',2.6); JN=E('make','join',6.7); GA=E('make','gas',8.7); FE=E('make','felt',15.5); CR=E('make','cross',17.5); ST=E('make','steam',20.7); PL=E('make','pl',24.9); SWT=E('make','sweater',32.7)
EN(PR+0.2,riser(1.4),0.3); EN(PR+1.6,slam(),0.55,name='PRESS-close'); EN(HT,hum(3.0,55),0.4,name='heat')
EN(JN+0.8,slam(),0.45,name='halves-join'); EN(GA-0.2,hiss(2.2,1800,7500),0.55,name='GAS-in'); EN(E('make','pr',10.9),number_pop(),0.35,name='gauge')
EN(FE,swish(1.4,300,2200),0.45,name='felt-fly'); EN(CR+1.0,click(),0.5,name='felt-lock'); EN(ST,hiss(2.6,900,4500),0.5,name='STEAM')
EN(PL,panel(),0.35,name='two-sections'); EN(SWT-0.3,chime([72,76,79],0.15,0.35),0.4,name='sweater')
# 04 颜色：白黑交替 → 1972 电视 → 温网草地落球
WB=E('color','wb',0.5); TVt=E('color','tv',3.7); YEL=E('color','yel',5.7); WI=E('color','wim',8.9)
for i in range(3): EN(WB+0.6+i*1.2,click(),0.35,name='bw-%d'%i)
EN(TVt,glitch(0.4),0.35,name='tv-on'); EN(YEL,ding(1320),0.45,name='YELLOW'); EN(WI+0.4,bounce(1.0),0.5,name='grass-bounce'); EN(WI+1.4,bounce(1.1),0.3)
# 05 那几毫秒：线床慢放 → 撞墙压扁 → 内壁翻泡 → 气闸流线 → 发球掉速 → 蓬起／磨秃 → 冷 → 高海拔
STR=E('impact','str',0.5); WA=E('impact','wall',5.3); SQ=E('impact','squash',7.6); BU=E('impact','bub',15.2); AI=E('impact','air',18.5); SE=E('impact','serve',21.7); FL=E('impact','fluff',25.8); BA=E('impact','bald',29.3); CO=E('impact','cold',32.0); AL=E('impact','alt',38.5)
EN(STR+0.5,riser(0.4),0.3); EN(STR+0.8,pock(0.35),0.9,name='STRINGS-slowmo'); EN(STR+0.8,sub_boom(),0.35)
EN(SQ-0.6,squish(0.5),0.8,name='SQUASH'); EN(BU,squish(0.7),0.5,name='bubble'); EN(BU+1.1,pock(0.6),0.45,name='bubble-pop')
EN(AI,hiss(5.5,600,3000),0.25,name='airflow'); EN(SE,swish(1.0,500,3500),0.45,name='serve-drag'); EN(FL,hiss(2.0,400,1800),0.3,name='fluff-drag'); EN(BA,swish(0.8,1500,6000),0.3,name='bald')
for k,(e_,g) in enumerate([(0.76,0.5),(0.68,0.5)]):
    t=CO+0.6
    for n in range(4): t+=math.sqrt(2*3.2/3.43)*(e_**n)*(1 if n==0 else 2); EN(t,bounce(1.0 if k==0 else 0.8),g*(e_**n),pan=-0.4 if k==0 else 0.4,name=f'cold-bounce-{k}-{n}' if n==0 else None)
EN(AL,blip(1800,0.12,1.4,0.5),0.4,name='altitude')
# 06 实验室：伦敦 → 落球弹跳 → 只弹回一半多 → 活塞压 → 滚筒九局 → 换球节奏
LO=E('lab','lon',0.5); DR=E('lab','drop',4.5); HF=E('lab','half',10.3); PS=E('lab','press',12.1); WE=E('lab','wear',17.3); NI=E('lab','nine',21.7); WIM=E('lab','wim',24.6); TW=E('lab','two',32.1)
EN(LO,panel(),0.35,name='london'); EN(DR+0.3+math.sqrt(2*6.35/3.92),bounce(1.0),0.6,name='DROP-land'); EN(DR+1.0,ding(1175),0.3,name='band')
EN(HF,sub_boom(),0.35,name='half'); EN(PS+1.0,squish(0.8),0.5,name='piston')
EN(WE,hum(4.0,80),0.3,name='drum'); impacts(WE,NI-0.3,0.48,0.3,0.25,1.2,name='tumble'); EN(WE+0.4,number_pop(),0.4,name='nine')
for i in range(25): EN(NI+i*0.06,tick(),0.25)
for j in range(3): EN(WIM+j*0.9+0.3,ding(1047+j*200),0.35,name=f'ball-change-{j}')
EN(TW,chime([79,84],0.14,0.35),0.35,name='two-early')
# 07 调速：大球 → 2001 → 三种球 → 赛跑 → 初速 → 测场地 → 尺子与旋钮
BG=E('dial','big',0.5); VO=E('dial','vote',5.8); TY=E('dial','types',10.3); T3=E('dial','t3',13.2); RA=E('dial','race',17.9); INIT=E('dial','init',25.7); CT=E('dial','court',29.4); FI=E('dial','fire',32.9); KN=E('dial','knob',35.6)
EN(BG,boom(2.5),0.35,name='bigger'); EN(VO,slam(),0.45,name='VOTE-2001')
for i in range(3): EN(TY+i*0.4,blip(1400-i*250,0.12,1.1,0.55),0.45,name=f'type-{i+1}')
EN(T3+0.1,zap(1200,2400,0.6),0.3,name='six-pct'); EN(RA+0.6,pock(1.0),0.6,name='race-serve'); EN(RA+0.62,pock(0.95),0.5)
EN(RA+0.6+1.1,bounce(1.0),0.4,pan=-0.3,name='race-a'); EN(RA+0.6+1.1*1.016+0.03,bounce(0.97),0.4,pan=0.3,name='race-b'); EN(RA+0.6+1.1*1.016+0.7,number_pop(),0.4,name='plus10ms')
EN(INIT,blip(1600,0.1,1.2,0.5),0.4,name='init-speed'); EN(CT,panel(),0.3,name='court-test')
EN(FI+0.3,zap(2400,900,0.4),0.45,name='FIRE'); EN(FI+0.3+2*0.5*1.0,bounce(1.2),0.5,name='court-hit')
EN(KN,clink(1800),0.45,name='ruler'); EN(KN+0.6,riser(1.6),0.3,name='knob-turn'); EN(KN+2.2,ding(1320),0.4)
# 08 争议：引语 → 每周不一样 → 3500 份问卷汇成一颗球 → 2027
CP=E('now','complain',0.5); Q1=E('now','q1',3.8); Q2=E('now','q2',8.8); WK=E('now','weeks',13.1); AT=E('now','atp',17.0); ON=E('now','one',23.4)
EN(CP,hum(3.0,58),0.4,name='complain'); EN(Q1,panel(),0.4,name='quote-1'); EN(Q2,panel(),0.4,name='quote-2')
for i in range(6): EN(WK+i*0.15+0.1,click(),0.35,pan=(i-2.5)*0.15,name=f'week-{i}')
EN(AT+0.6,rain_hiss(3.8),0.4,name='surveys-converge'); EN(AT+4.4,ding(990),0.4,name='one-ball'); EN(ON,chime([72,79,84],0.15,0.35),0.4,name='2027')
# 09 未来：球堆倾泻 → 填埋 → 碾碎铺场 → 巢鼠 → 张力 → 两件事
PI=E('future','pile',0.5); FIL=E('future','fill',3.7); NO=E('future','none',8.5); GR=E('future','grind',13.6); NE=E('future','nest',18.1); SPL=E('future','split',20.6); TWO=E('future','two',26.4)
EN(PI,rumble(3.0),0.6,name='PILE'); EN(FIL,boom(3.0),0.35,name='landfill'); EN(NO,glitch(0.4),0.3,name='no-recyclable')
EN(GR+0.4,rain_hiss(3.2),0.45,name='grind'); EN(GR+3.2,slam(),0.3,name='court-layer'); EN(NE+0.3,sparkle(1.4,30),0.3,name='nest')
EN(SPL,blip(900,0.12,1.1,0.5),0.35,name='fewer'); EN(SPL+0.8,blip(1500,0.12,1.1,0.5),0.35,name='more-often')
EN(TWO+0.2,chime([76,79],0.14,0.35),0.4,name='same'); EN(TWO+1.3,chime([79,84],0.14,0.35),0.4,name='return')
# 10 结论：拼图合上 → 球那块亮 → 规则那句 → 问句、新球飞进来
TR=E('end','tri',0.5); SRr=E('end','sr',3.5); BLL=E('end','ball',7.3); RU=E('end','rule',11.3); QE=E('end','q',17.3)
for i in range(3): EN(TR+0.4+i*0.35,slam(),0.3,name=f'piece-{i}')
EN(SRr,ding(880),0.3,name='strings-racket'); EN(BLL,sub_boom(),0.4,name='BALL-lit'); EN(BLL+0.1,chime([72,76,79,84],0.14,0.4),0.45)
EN(RU,hum(5.0,73),0.35,name='rule'); EN(QE,swish(0.9,600,4000),0.45,name='new-ball'); EN(QE+0.9,bounce(1.0),0.5,name='ball-land'); EN(QE+1.4,bounce(1.1),0.3)

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_LUFS=-20.0
raw=subprocess.run(['ffmpeg','-v','error','-i',BGM,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
song=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
# 循环＋卡点（所有者 2026-11-04「BGM 要循环，同时看看怎么卡点」）：曲子 112.3 BPM，小节 4×0.53194 s，曲内第一个强拍 0.4757 s（librosa 实测）。
# 小节号 → 段落：0–7 前奏、8–39 主段、40–47 间奏（轻）、48–63 主段、64 起尾段淡出。起点 BGM_OFF 取钩子大问题砸下来那一刻＝第 8 小节线，
# 之后按「主段 → 间奏 → 主段 → 再从第 8 小节循环」整小节往后拼，不放尾段；拼缝都在小节线上，10 ms 交叉淡化
BAR=4*0.53194; bar=lambda k: 0.4757+k*BAR; BGM_OFF=bar(8)-QQ   # 钩子大问题砸下来那一刻＝第 8 小节线，主段进来
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

# vibetennis EP13 网中间矮音效床：音效用 numpy/scipy 现场合成（音色同第 5～7 集 sfx.py），
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

# 场上发球：和 scene.js 的 servePoint 同一张时刻表（击球在这一分的 36%，落地在 62%）
def serves(t0,n,per,g=0.5,until=1e9):
    for i in range(n):
        tc=t0+i*per+0.36*per
        if tc>until: break
        EN(tc,pock(1.0),g); EN(tc+0.04,swish(0.6,600,4200),g*0.5); EN(t0+i*per+0.62*per,bounce(1.0),g*0.6)
def pops(t0,n,gap,g=0.3):
    for i in range(n): EN(t0+i*gap,blip(1500+120*(i%8),0.05,1.25,0.6),g)
def thud_net():                # 球撞进网：闷响＋网绳抖动
    t=tt(0.6); return lp(rng.standard_normal(len(t)),600)*np.exp(-t/0.05)*0.7+np.sin(2*np.pi*140*t)*np.exp(-t/0.12)*0.5+bp(rng.standard_normal(len(t)),900,2500)*np.exp(-t/0.25)*np.abs(np.sin(2*np.pi*18*t))*0.25
def twang(f=72,d=1.4):          # 网绳绷紧：低音弦的嗡响，带一点拍频
    t=tt(d); x=(np.sin(2*np.pi*f*t)+0.5*np.sin(2*np.pi*f*2.003*t)+0.25*np.sin(2*np.pi*f*3.01*t))*np.exp(-t/0.45)*np.minimum(1,t/0.01)
    return verb(x*0.5,0.3)
def ratchet(n=6,gap=0.07):      # 网柱摇把：棘轮咔哒
    x=np.zeros(int((n*gap+0.1)*SR))
    for k in range(n): c=clink(1800+60*k)*0.8+click()[:int(0.03*SR)].sum()*0; i=int(k*gap*SR); x[i:i+len(c)]+=c
    return x
def rip():                       # 字被扯断：撕裂噪声＋高频裂响
    t=tt(0.7); x=bp(rng.standard_normal(len(t)),800,7000)*np.exp(-t/0.12)*0.8; x[:int(0.6*SR)]+=crackle(0.6)*0.6; return verb(x,0.2)
def flight(t0,dur,g=0.5,pan=0.0,name=None,land=True):   # 击球 → 飞行嗖声 → 落地
    EN(t0,pock(1.0),g,pan=pan,name=name); EN(t0+0.05,swish(min(1.0,dur),700,4200),g*0.45,pan=pan)
    if land: EN(t0+dur,bounce(1.0),g*0.6,pan=pan)
# 时刻全部取自 r3d/timeline.json 的 sec.ev（plan.py 已对齐 BGM 拍点）与 src/shots.js 的动画节点
B=TL['beat']['p']
# 01 钩子：网中间矮一截 → 两端 1.07 → 中间 0.914 → 差 15.6 → 问句 → 松网 → 绳 → 曲线 → 有个名字（riser 推到 HIT）
h=SEC['hook']; EN(h['t0']+0.1,crowd(SEC['title']['t0']-h['t0']),0.22,name='crowd')
EN(E('hook','dip',3.4),zap(1400,700,0.5),0.35,name='dip'); EN(E('hook','post',5.0),blip(1700,0.06,1.2,0.6),0.35,name='1.07'); EN(E('hook','mid',6.1),blip(1300,0.06,0.85,0.6),0.35,name='0.914')
EN(E('hook','diff',8.2),number_pop(),0.45,name='15.6'); EN(E('hook','q',9.8),chime([72,76],0.12,0.35),0.35,name='question')
EN(E('hook','loose',11.4),creak(0.9,140),0.3,name='loose'); EN(E('hook','rope',12.5),swish(1.2,300,2000),0.35,name='rope'); EN(E('hook','curve',14.6),hum(2.0,98),0.3,name='curve')
HIT=SEC['title']['t0']; EN(HIT-1.6,riser(1.6),0.5,name='riser'); EN(HIT,hit(),0.8,name='HIT-catenary'); EN(HIT,sparkle(1.4),0.35)
# 02 悬链线：CATENARY 逐字砸下（第 2 拍落地）→ 1691 → 方程 → 白带子落下、扯断 → 「不是悬链线」→ 答案 → 中央带
for k in range(13): EN(HIT+2*B-0.42-6*0.035+abs(k-6)*0.035+0.3,tick(),0.25)
EN(HIT+2*B,slam(),0.6,name='CATENARY-land'); EN(E('title','yr',1.6),ding(1047),0.35,name='1691'); EN(E('title','eq',2.7),panel(),0.3,name='equation')
TW=E('title','twist',5.85); TE=E('title','tear',6.9); EN(TW,whoosh_fast(0.5),0.4,name='strap-drop'); EN(TE-0.2,riser(0.2),0.4); EN(TE,rip(),0.7,name='TEAR'); EN(TE,sub_boom(),0.7)
EN(TE+0.9,slam(),0.45,name='not-catenary'); EN(E('title','ans',10.6),swish(1.0,400,2600),0.35,name='to-strap'); EN(E('title','strap',12.2),panel(),0.35,name='strap-label')
# 03 中央带：绷紧（张力表）→ kN → 磅 → 松开 → 99 → 8 cm → 一拉 → 91.4 → 7.7 → 一半一半 → 受力图 → 折角 → 浅 V → 金句
TN=E('strap','tense',2.7); EN(TN-0.3,ratchet(8,0.08),0.35,name='ratchet'); EN(TN+1.4,twang(72),0.5,name='tense'); EN(E('strap','kn',3.7),number_pop(),0.45,name='kN'); EN(E('strap','lb',6.4),blip(1500,0.06,1.2,0.5),0.3,name='lb')
EN(E('strap','loose',10.1),creak(0.7,160),0.3,name='loosen'); EN(E('strap','c99',12.8),number_pop(),0.4,name='99'); EN(E('strap','d8',14.4),blip(1200,0.07,0.8,0.5),0.3,name='8cm')
PU=E('strap','pull',18.6); EN(PU-0.25,riser(0.25),0.45); EN(PU,sub_boom(),0.75,name='PULL'); EN(PU,twang(58,1.6),0.55); EN(E('strap','c914',19.2),number_pop(),0.45,name='91.4'); EN(E('strap','d77',21.3),number_pop(),0.4,name='7.7')
EN(E('strap','half',25.5),zap(900,1400,0.4),0.3,name='half'); EN(E('strap','other',27.7),zap(1400,900,0.4),0.3,name='other-half')
EN(E('strap','chain',30.9),swish(0.9,400,2400),0.35,name='chain'); EN(E('strap','point',34.6),swish(0.7,500,3000),0.35,name='point'); EN(E('strap','point',34.6)+0.3,thud_net(),0.35)
EN(E('strap','kink',37.8),ding(1320),0.4,name='kink'); EN(E('strap','v',42.0),hum(2.5,82),0.3,name='V'); EN(E('strap','quote',43.1),slam(),0.5,name='quote')
# 04 降网史：1874 → 1877 → 场地 → 5 ft → 3 ft 3 → 撞网 → 截击 → 降 → 1878 → 1880 → 1882 → 今天 → 穿越过网 → 问句
for k in ['y1874','y1877','y1878','y1880','y1882']: EN(E('hist',k,0),sub_boom(),0.55,name=k); EN(E('hist',k,0)+0.05,slam(),0.35)
EN(E('hist','size',10.1),panel(),0.3,name='court-size'); EN(E('hist','p5',11.7),blip(1600,0.06,1.2,0.5),0.3,name='5ft'); EN(E('hist','c33',13.3),blip(1250,0.06,0.85,0.5),0.3,name='3ft3')
PA=E('hist','pass',17.0); EN(PA,pock(1.0),0.5,name='pass'); EN(PA+0.05,swish(1.0,700,4000),0.25); EN(PA+1.1,thud_net(),0.55,name='into-net')
EN(E('hist','volley',19.2),pock(1.0),0.45,name='volley'); EN(E('hist','down',23.9),swish(0.8,2400,400),0.35,name='posts-down')
EN(E('hist','today',35.1),chime([67,72,76],0.12,0.4),0.4,name='today')
P2=E('hist','pass2',38.8); EN(P2,pock(1.0),0.5,name='pass2'); EN(P2+0.05,swish(1.0,700,4000),0.25); EN(P2+1.1,bounce(1.0),0.4); EN(P2+1.2,ding(988),0.3,name='clears')
EN(E('hist','q',44.2),chime([72,76],0.12,0.35),0.35,name='q')
# 05 勾股：场地 → 角 → a²+b² → 斜边 → +1.38 → 低机位 → 沿线 → 斜线 → 两球 → 金句
EN(E('diag','court',0.5),swish(1.0,300,2400),0.35,name='court'); EN(E('diag','corner',5.3),blip(1500,0.06,1.2,0.5),0.3)
EN(E('diag','pyth',7.4),panel(),0.35,name='pythagoras'); EN(E('diag','hyp',8.0),zap(700,2200,0.6),0.35,name='diagonal'); EN(E('diag','plus',10.6),number_pop(),0.45,name='+1.38')
EN(E('diag','cross',13.3),swish(1.2,300,2000),0.35,name='low-cam')
DT=E('diag','dtl',14.9); CC=E('diag','cc',18.1); BO=E('diag','both',22.3); flight(DT,1.25,0.5,0.3,'dtl'); flight(CC,1.25,0.5,-0.3,'cc'); flight(BO,1.25,0.45,0.3,'both-dtl'); flight(BO,1.25,0.45,-0.3,'both-cc',land=True)
EN(E('diag','safe',25.0),slam(),0.5,name='safer')
# 06 余量：模型 → 100 km/h → 落点 → 45 → 30 → 角度窗口 → 上旋 → 扇形 52.9 / 17.4 → 19% / 11%
EN(E('margin','model',1.6),panel(),0.35,name='model'); EN(E('margin','v',3.7),whoosh_fast(0.4),0.35,name='100kmh'); EN(E('margin','land',5.3),bounce(1.0),0.3)
EN(E('margin','cc',8.0),zap(700,1600,1.2),0.3,name='cc-arc'); EN(E('margin','cc',8.0)+1.2,number_pop(),0.45,name='45'); EN(E('margin','dtl',11.2),zap(700,1400,1.2),0.3,name='dtl-arc'); EN(E('margin','dtl',11.2)+1.2,number_pop(),0.4,name='30')
EN(E('margin','win',14.4),swish(0.8,500,3000),0.35,name='window'); EN(E('margin','spin',21.3),zap(1200,600,0.8),0.3,name='spin')
EN(E('margin','mcp',26.1),rain_hiss(1.8),0.3,name='fan'); EN(E('margin','pcc',31.9),number_pop(),0.5,name='52.9'); EN(E('margin','pdtl',33.5),number_pop(),0.45,name='17.4')
EN(E('margin','ue',36.7),glitch(0.4),0.35,name='ue'); EN(E('margin','ue19',39.4),sub_boom(),0.6,name='19%'); EN(E('margin','ue11',42.0),number_pop(),0.4,name='11%')
# 07 支杆：双打网柱 → 柱子 → 0.914 → 插杆 → 撑回 1.07 → 规则
EN(E('sticks','dbl',0.5),swish(1.0,300,2400),0.35,name='doubles'); EN(E('sticks','posts',2.7),clink(1900),0.35,name='posts'); EN(E('sticks','d914',8.0),blip(1500,0.06,1.2,0.5),0.3,name='0.914')
EN(E('sticks','sticks',9.0),clink(2600),0.4,name='sticks'); EN(E('sticks','sticks',9.0)+0.1,thud_net(),0.25); EN(E('sticks','lift',11.2),twang(80),0.4,name='lift'); EN(E('sticks','rule',14.4),chime([67,72],0.12,0.35),0.35,name='rule')
# 08 结论
EN(E('end','again',0.5),hum(3.0,82),0.3,name='again'); EN(E('end','quote',3.2),slam(),0.5,name='quote'); EN(E('end','q',8.0),chime([72,76,79,84],0.15,0.45),0.5,name='question')

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM_DIR=os.environ.get('VT_BGM_DIR','/workspace/tennis_ep/bgm')   # VT-1 无缝循环版：first（0–88 小节，从第一个强拍起）＋ loop（8–88 小节，可无限接）
BGM_LUFS=-20.0
def decw(p):
    raw=subprocess.run(['ffmpeg','-v','error','-i',p,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
    return np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
first=decw(os.path.join(BGM_DIR,'vibetennis_bgm_first.wav')); loop=decw(os.path.join(BGM_DIR,'vibetennis_bgm_loop.wav'))
BAR=2.127772   # 112.8 BPM 一小节；first.wav 的 0 s 就是第 0 小节线
HIT=SEC['title']['t0']; LEAD=HIT-8*BAR   # 第 8 小节（全乐队进）正好砸在 HIT＝「悬链线」亮字（plan.py 也按这个拍网格排段落）
song=first
while len(song)/SR<TOTAL+2-LEAD: song=np.concatenate([song,loop])   # loop 的接缝已在 VT-1 做过等功率交叉淡化
bgm=np.zeros((int((TOTAL+1)*SR),2)); k=int(round(LEAD*SR))
if k>=0: n=min(len(bgm)-k,len(song)); bgm[k:k+n]=song[:n]
else: n=min(len(bgm),len(song)+k); bgm[:n]=song[-k:-k+n]
if k>0: bgm[k:k+int(0.3*SR)]*=np.linspace(0,1,int(0.3*SR))[:,None]
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

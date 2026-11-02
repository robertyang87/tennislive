# vibetennis 第 5 集《同一个球，四块地》音效床：音效用 numpy/scipy 现场合成，时间跟着 r3d/timeline.json 与 narration.json（plan.py 排定）；
# BGM 同第 4 集：robertyang87/vibeknowledge 的 assets/music/we-never-remix-hi-noise-qiucheng.m4a（库内 README 注明发布时优先用平台曲库同曲）。
# 合成工具抄自第 4 集 sfx.py。
import numpy as np, soundfile as sf, sys, json, math, os
from scipy import signal
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
SR=48000
TL=json.load(open(os.path.join(HERE,'r3d','timeline.json'))); TOTAL=TL['total']; N=int(TOTAL*SR)+SR
NAR={l['file']:l['at'] for l in json.load(open(os.path.join(HERE,'narration.json')))['lines']}
SEC={s['name']:s for s in TL['sections']}
rng=np.random.default_rng(55)
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
def EN(t,x,g=1.0,pan=0.0,name=None): place(x,t,g,pan=pan,name=name)

# ================= 事件（与 r3d/scene.js 的 shotTL 一一对应） =================
def lane_bounces(sec,per,lead,gain=0.7):
    t=sec['t0']+lead
    while t<sec['t1']-0.2: EN(t,bounce(0.8),gain,name='bounce-'+sec['name']); EN(t,crackle(0.25,300),0.25); t+=per
lane_bounces(SEC['hook'],4.0,1.0)
lane_bounces(SEC['clay'],4.6,1.2); lane_bounces(SEC['grass'],4.6,1.2)
for s in TL['sections'][1:]: EN(s['t0']-0.25,swish(0.9,400,2600),0.35,name='cut-'+s['name'])
# 场馆：每换一座一记过场；法网顶棚打开时一段低沉的机械运转
v=SEC['venues']; EN(v['t0']+0.1,hit(),0.45,name='venues'); EN(v['t0']+0.25*(NAR['s1']-v['t0']),hum(5.0,82),1.4,name='roof-open')
for f in ('s1','s2','s3'): EN(NAR[f],swish(1.1,300,2200),0.45,name='venue-'+f)
EN(SEC['q']['t0']+0.2,number_pop(),0.5,name='question')
# 慢镜：来球→滑（摩擦声）→咬住（闷响）→弹出
sl=SEC['slow']; EN(NAR['p1'],squash(),0.8,name='contact'); EN(NAR['p1'],slide(max(1.0,NAR['p2']-NAR['p1']+1.0)),0.9,name='slide')
EN(NAR['p2']+1.0,click(),0.7,name='grip'); EN(NAR['p3'],swish(0.8,300,3000),0.4,name='lift-off'); EN(NAR['p5'],panel(),0.5,name='two-numbers')
# 数据：光柱升起、刻度、高亮
d=SEC['data']; EN(NAR['d2']-1.0,riser(3.4),0.45,name='pillars-rise'); EN(NAR['d3'],number_pop(),0.5,name='values')
EN(NAR['r1'],ding(1320),0.4,name='ao-hi'); EN(NAR['r3'],glitch(0.6),0.5,name='rumor'); EN(NAR['r4'],panel(),0.4,name='official')
h=SEC['hard']; EN(h['t0']+0.3,hit(),0.4,name='hardcourt'); EN(NAR['k2'],crackle(1.5,500),0.6,name='sand'); EN(NAR['k3']+0.3,slide(4.5),0.8,name='slide-coarse'); EN(NAR['k3']+0.3,crackle(4.5,220),0.5)
ao=SEC['aoy']
for i in range(12): EN(ao['t0']+0.2+i*0.12,tick(),0.5)
EN(NAR['k6'],number_pop(),0.6,name='ao-2021'); EN(NAR['k6'],ding(990),0.4)
y=SEC['rev3']
for i in range(11): EN(y['t0']+0.2+i*0.12,tick(),0.5)
EN(NAR['r8'],number_pop(),0.6,name='2020-low'); EN(NAR['r8'],ding(660),0.4)
e=SEC['end']; EN(NAR['e1'],boom(3.5),0.45,name='golden'); EN(NAR['e1'],ding(880),0.45); EN(NAR['e1']+0.1,sparkle(2.0,30),0.3); EN(NAR['e2'],ding(1320),0.3,name='question-end')

# ---- 2026-11-02 新增：子弹时间、粒子聚字、扫描建馆、慢镜环绕、风雪、故障 ----
def wind(d=8.0):
    t=tt(d); x=bp(rng.standard_normal(len(t)),250,1800,2)*(0.6+0.4*np.sin(2*np.pi*0.23*t)); env=np.minimum(1,np.minimum(t/1.5,(d-t)/1.5)); return x*env*0.5
def freeze_in():   # 时间冻结：下扫的气声＋低频嗡
    t=tt(1.4); f=2400*np.exp(-t*3)+120; x=bp(rng.standard_normal(len(t)),300,4000)*np.exp(-t/0.5)*0.5+np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t/0.6)*0.3; return verb(x,0.4)
def sub_boom():
    t=tt(0.9); return np.sin(2*np.pi*np.cumsum(55*np.exp(-t*4)+38)/SR)*np.exp(-t/0.35)*0.9
H=SEC['hook']; H1=NAR['h1']; H2=NAR['h2']
EN(H1-0.05,freeze_in(),0.6,name='bullet-time'); EN(H1,hum(H2-H1,62),0.9,name='time-stop-drone'); EN(H2-0.25,swish(0.8,400,3000),0.45,name='time-resume')
t=H['t0']+1.0
while t<H['t1']-0.2:
    if not (H1<=t<H2): EN(t,sub_boom(),0.55,name='impact-sub')
    t+=4.0
for tm,nm in ((H2+0.1,'morph-four'),(SEC['q']['t0']+0.05,'morph-q'),(SEC['clay']['t0']+0.3,'morph-mu9'),(SEC['grass']['t0']+0.3,'morph-mu56'),(SEC['data']['t0']+0.3,'morph-idx'),(NAR['e1']-0.3,'morph-end')):
    EN(tm,sparkle(1.6,70),0.4,name=nm); EN(tm,riser(1.0),0.25)
v=SEC['venues']; st=[v['t0'],NAR['s1'],NAR['s2'],(NAR['s2']+NAR['s3'])/2]
for i,tm in enumerate(st): EN(tm+0.05,zap(300,2400,1.6),0.35,name='scan-build-%d'%i)
EN(NAR['p2'],hum(NAR['p3']-NAR['p2'],98),0.8,name='orbit-drone'); EN(NAR['p2'],freeze_in(),0.4)
EN(NAR['r7'],wind(SEC['rev3']['t1']-NAR['r7']),0.9,name='cold-wind'); EN(NAR['r8'],glitch(0.6),0.6,name='glitch-2020'); EN(NAR['r8'],sub_boom(),0.5)

# 地球：拉远的呼啸，四站依次亮起的叮声（与 scene.js setGlobe 的节奏一致），片尾拉回地球
D=H['t1']-H['t0']; EN(H2-0.05,swish(1.4,200,2400),0.5,name='to-globe'); EN(H2,boom(2.5),0.3)
for i,f in enumerate((880,1047,1175,1319)): EN(H2+0.15+(i/4)*(D-(H2-H['t0'])-1.0)+0.05,ding(f),0.45,name='city-%d'%i)
EN(NAR['e2']-0.35,swish(1.2,200,2400),0.45,name='outro-globe'); EN(NAR['e2']+1.4,chime([84,88,91],0.16,0.35),0.5,name='loop-closed')

# 画板式拆解（红土 / 草地）：倒带的磁带声、定格的闷响＋闪、马克笔的吱声；发球指数：金属片一片片落下的叮当
def tape_rewind(d=0.6):
    t=tt(d); f=900+2600*(t/d); x=np.sin(2*np.pi*np.cumsum(f)/SR)*0.25+bp(rng.standard_normal(len(t)),1500,6000)*0.4; return x*np.minimum(1,np.minimum(t/0.05,(d-t)/0.08))
def marker(d=0.5):
    t=tt(d); x=bp(rng.standard_normal(len(t)),2000,5000)*(0.6+0.4*np.sin(2*np.pi*38*t)); return x*np.minimum(1,np.minimum(t/0.03,(d-t)/0.1))*0.5
def clink(f=2400):
    t=tt(0.18); return (np.sin(2*np.pi*f*t)+0.5*np.sin(2*np.pi*f*2.76*t))*np.exp(-t/0.035)*0.35+hp(rng.standard_normal(len(t)),4000)*np.exp(-t/0.004)*0.3
cs=SEC['clay']; n2=NAR['n2']; n3=NAR['n3']
EN(cs['t0']+4.6,tape_rewind(0.6),0.6,name='rewind'); EN(n2,slam(),0.55,name='freeze-1'); EN(n2+0.35,marker(0.8),0.5,name='marker-ring')
EN(n3,slam(),0.55,name='freeze-2'); EN(n3+0.2,marker(0.9),0.5,name='marker-angle')
gs=SEC['grass']; EN(gs['t0']+2.9,slam(),0.55,name='freeze-3'); EN(gs['t0']+3.1,marker(0.9),0.5)
dd=SEC['data']; g0=NAR['d2']-1.0
for k,n in (('AO',23),('RG',15),('WIM',22),('USO',21)):
    for i in range(n):
        tm=g0+3.5*(i/n)**0.9+0.05
        if i%3==0: EN(tm,clink(2200+((i*37)%7)*120 if (i+1)%10 else 1500),0.35 if (i+1)%10 else 0.5)

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_OFF=0.309; BGM_LUFS=-20.0
raw=subprocess.run(['ffmpeg','-v','error','-ss',str(BGM_OFF),'-i',BGM,'-t',str(TOTAL+1),'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
bgm=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
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

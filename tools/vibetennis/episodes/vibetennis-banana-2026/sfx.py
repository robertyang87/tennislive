# vibetennis EP14 不是补钾音效床：音效用 numpy/scipy 现场合成（音色同第 5～7 集 sfx.py），
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
# 时刻全部取自 r3d/timeline.json 的 sec.ev（plan.py 已对齐 BGM 拍点）与 src/shots.js 的动画节点
B=TL['beat']['p']
h=SEC['hook']; EN(h['t0']+0.1,crowd(SEC['title']['t0']-h['t0']),0.20,name='crowd')
EN(E('hook','peel',3.5),swish(0.8,400,2400),0.35,name='peel')
EN(E('hook','bite',5.1),pock(1.1),0.40,name='bite')
EN(E('hook','myth',7.7),chime([72,76],0.12,0.35),0.35,name='myth')
EN(E('hook','q',10.4),ding(988),0.40,name='question')
HIT=SEC['title']['t0']; EN(HIT-1.6,riser(1.6),0.5,name='riser'); EN(HIT,hit(),0.8,name='HIT-title'); EN(HIT,sparkle(1.4),0.35)
EN(E('title','punch',0.53),slam(),0.55,name='punch')
EN(E('title','gly',5.32),panel(),0.35,name='glycogen')
EN(E('title','no',9.04),chime([67,72],0.12,0.35),0.35,name='not-shown')
EN(E('peel','size',3.2),panel(),0.30,name='118')
EN(E('peel','cho',5.85),number_pop(),0.45,name='27g')
EN(E('peel','sug',6.92),blip(1500,0.06,1.2,0.5),0.30,name='14g')
EN(E('peel','fib',8.51),blip(1300,0.06,1.0,0.5),0.28,name='3g')
EN(E('peel','kcal',9.58),blip(1600,0.06,1.1,0.5),0.30,name='105')
EN(E('peel','k',13.3),number_pop(),0.45,name='422')
EN(E('peel','gi',19.15),hum(1.6,110),0.30,name='GI')
EN(E('peel','ripe',21.28),blip(1200,0.07,0.9,0.5),0.28,name='ripe')
EN(E('peel','first',24.47),slam(),0.45,name='first')
EN(E('salt','na',2.13),zap(900,1600,0.5),0.35,name='sodium')
EN(E('salt','sweat',5.32),panel(),0.30,name='sweat')
EN(E('salt','naMg',8.51),number_pop(),0.50,name='1565')
EN(E('salt','kMg',11.17),number_pop(),0.45,name='194')
EN(E('salt','cover',14.36),ding(1047),0.35,name='cover')
EN(E('salt','miss',16.49),sub_boom(),0.45,name='miss-na')
EN(E('salt','race',22.34),panel(),0.30,name='race')
EN(E('salt','nerve',26.60),hum(2.0,82),0.28,name='nerve')
EN(E('salt','verdict',31.92),slam(),0.50,name='verdict')
EN(E('fuel','need',3.72),swish(0.9,300,2000),0.30,name='need')
EN(E('fuel','notbx',6.38),blip(1000,0.08,0.8,0.5),0.28,name='not-biopsy')
EN(E('fuel','glu',10.11),blip(1400,0.06,1.0,0.5),0.28,name='glucose')
EN(E('fuel','guide',14.36),panel(),0.32,name='guide')
EN(E('fuel','stmt',15.96),panel(),0.35,name='statement')
EN(E('fuel','lo',24.47),number_pop(),0.40,name='30-60')
EN(E('fuel','hi',28.19),number_pop(),0.40,name='60-90')
EN(E('fuel','win',31.38),tick(),0.30,name='90s')
EN(E('fuel','set',32.45),tick(),0.30,name='120s')
EN(E('fuel','bar',40.43),ding(1175),0.40,name='27mark')
EN(E('fuel','notall',43.09),chime([67,72,76],0.12,0.4),0.35,name='notall')
EN(E('proof','mix',4.26),glitch(0.35),0.30,name='mixed')
EN(E('proof','v',5.85),panel(),0.35,name='vergauwen')
EN(E('proof','vres',17.55),ding(988),0.30,name='v-res')
EN(E('proof','m',18.09),panel(),0.35,name='mcrae')
EN(E('proof','mtot',23.94),number_pop(),0.40,name='68')
EN(E('proof','m1st',27.13),number_pop(),0.40,name='65')
EN(E('proof','mnote',31.38),blip(900,0.08,0.8,0.5),0.28,name='not-tired')
EN(E('proof','mit',35.64),panel(),0.35,name='mitchell')
EN(E('proof','n',40.43),panel(),0.35,name='nieman')
EN(E('proof','nres',46.28),blip(1200,0.07,1.0,0.5),0.30,name='ns')
EN(E('proof','ntime',47.34),number_pop(),0.35,name='times')
EN(E('proof','blo',51.07),swish(0.7,300,1800),0.30,name='bloated')
EN(E('proof','dole',53.73),tick(),0.28,name='dole')
EN(E('proof','none',59.58),sub_boom(),0.55,name='no-trial')
EN(E('alt','ok',3.19),swish(0.7,400,2600),0.30,name='switch')
EN(E('alt','drink',4.26),panel(),0.32,name='drink')
EN(E('alt','date',12.77),blip(1400,0.06,1.1,0.5),0.30,name='date')
EN(E('alt','chew',21.28),swish(0.5,200,1600),0.28,name='chew')
EN(E('alt','bbc',22.87),panel(),0.35,name='bbc')
EN(E('alt','ask',30.32),chime([72,76,79],0.12,0.4),0.40,name='bananas')
EN(E('end','again',0.53),hum(3.0,82),0.30,name='again')
EN(E('end','k',3.72),blip(1100,0.07,0.9,0.5),0.30,name='k-real')
EN(E('end','cho',10.11),slam(),0.50,name='27reason')
EN(E('end','q',19.68),chime([72,76,79,84],0.15,0.45),0.50,name='final-q')

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

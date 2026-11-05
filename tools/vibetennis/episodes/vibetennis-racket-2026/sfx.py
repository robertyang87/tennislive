# vibetennis 球拍篇（三部曲②）音效床：音效用 numpy/scipy 现场合成（音色同第 5～7 集 sfx.py），
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

# 01 钩子：子弹时间里球打在拍面边缘（接触在段内 HIT+3.38 s：慢放 0.18 倍速）→ 拍框扭转 → 恢复常速飞出 → 五支拍 → 大问题
h=SEC['hook']; HIT=E('hook','hit',0.3); FLY=E('hook','fly',5.8); ROW=E('hook','row',9.5); QQ=E('hook','q',13.7); HC=HIT+0.6+0.5/0.18
EN(h['t0']+0.1,hum(HC-h['t0']+0.4,62),0.7,name='hook-drone'); EN(HC-1.2,riser(1.2),0.35)
EN(HC,pock(0.4),1.0,name='HIT-slowmo'); EN(HC+0.05,groan(1.8,90),0.6,name='twist-groan'); EN(HC,sub_boom(),0.45)
EN(FLY,swish(0.7,500,3500),0.5,name='speed-back')
for i in range(5): EN(ROW+i*0.45+0.2,blip(1200+i*300,0.09,1.2,0.6),0.45,name='row-%d'%i)
EN(QQ,sub_boom(),0.5,name='question-hit'); EN(QQ+0.1,chime([76,83,88],0.14,0.4),0.45,name='question')
# 02 木拍：1893 插图 → 木条弯成框 → 年代飞过 → 扫描读数 70 → 想变大就开裂
w=SEC['wood']; LT=E('wood','lt',0.5); BE=E('wood','bend',2.8); YR=E('wood','years',6.5); SC=E('wood','scan',12.3); CR=E('wood','crack',17.6)
EN(LT,page_slide(),0.5,name='lighttable'); EN(BE,creak(1.6,170),0.55,name='ash-bend')
for i in range(6): EN(YR+i*0.35+0.3,tick(),0.5,name='year-%d'%i)
EN(SC,zap(900,2600,0.6),0.35,name='scan'); EN(SC+0.9,ding(1320),0.35,name='lock-70')
EN(CR,creak(0.9,140),0.5,name='try-bigger'); EN(CR+0.6,crackle(0.7),0.6,name='CRACK'); EN(CR+1.4,swish(0.5,300,1500),0.3,name='shrink-back')
# 03 金属拍：孔口特写（线绷紧在 0.6～2.4 s）→ 孔边闪红 → 专利页 → 截面浮起、拆开 → 合拢成 T2000 → 三腔铝框 → 拍面没变
m=SEC['metal']; MH=E('metal','hole',3.9); MP=E('metal','patent',7.3); ML=E('metal','lift',11.2); MJ=E('metal','join',14.7); MA=E('metal','alu',21.8); MS=E('metal','same',25.7)
EN(m['t0']+0.6,metal_scrape(1.8),0.6,name='string-tension'); EN(MH,glitch(0.35),0.4,name='sharp-edge'); EN(MH+0.2,zap(2800,1200,0.3),0.3)
EN(MP,page_slide(),0.5,name='lacoste-patent'); EN(ML-0.4,riser(1.6),0.3,name='section-lift'); EN(ML+1.4,clink(2200),0.5,name='split-beads'); EN(ML+1.5,clink(1700),0.4)
EN(MJ,slam(),0.5,name='JOIN-steel'); EN(MJ+0.9,sparkle(1.2,40),0.3,name='rim-glow')
for i in range(3): EN(MA+0.6+i*0.4,blip(1100+i*250,0.12,1.1,0.5),0.4,name='alu-cell-%d'%i)
EN(MS+0.3,hum(2.5,110),0.45,name='same-area')
# 04 大拍面：专利封面 → 不震手的点在拍喉 → 一串击球点在中央 → 拍面拉长把它包进来 → 面积填亮
o=SEC['oversize']; OP=E('oversize','patent',0.5); OC=E('oversize','cop',6.1); OH=E('oversize','hits',11.1); OS=E('oversize','stretch',16.9); OA=E('oversize','area',22.1)
EN(OP,page_slide(),0.5,name='head-patent'); EN(OP+0.6,slam(),0.35,name='stamp')
EN(OC,heartbeat(),0.5,name='cop-dot')
for i in range(7): EN(OH+0.2+i*0.18,click(),0.35,pan=(i-3)*0.1,name='hit-dot-%d'%i)
EN(OS,swish(2.2,200,1800),0.55,name='STRETCH'); EN(OS+2.0,ding(1175),0.35,name='cop-inside')
EN(OA,number_pop(),0.5,name='area-40pct'); EN(OA+0.2,riser(1.0),0.25)
# 05 甜点：粒子字炸成三颗点 → ①弹得最快 ②节点不振 ③握把不受力 → 节点那圈亮
sw=SEC['sweet']; SP=E('sweet','split',2.3); P1=E('sweet','p1',4.5); P2=E('sweet','p2',6.0); P3=E('sweet','p3',7.7); SN=E('sweet','node',15.7); SG=E('sweet','grip',17.6)
for i in range(3): EN(SP+i*0.12,blip(1500+i*500,0.1,1.3,0.55),0.45,name='split-%d'%i)
EN(P1,pock(1.0),0.6,name='p1-rebound'); EN(P1+0.2,bounce(1.0),0.3); EN(P2,hum(1.6,160),0.4,name='p2-vibration'); EN(P3,heartbeat(),0.45,name='p3-cop')
EN(SN,freeze_in(),0.45,name='node-silence'); EN(SN+0.3,ding(990),0.3); EN(SG,sub_boom(),0.35,name='grip-hand')
# 06 防扭转：分屏两支拍同时被偏心击中（接触在 HB+1.82 s，0.22 倍速）→ 速度条 → 俯视球场 → 落点出界
tw=SEC['twist']; TS=E('twist','split',0.5); TB=E('twist','hitboth',3.8); TV=E('twist','speed',10.8); TC=E('twist','court',13.3); TO=E('twist','out',20.7); THC=TB+0.4/0.22
EN(TS,panel(),0.35,name='split-screen'); EN(THC-1.0,riser(1.0),0.3)
EN(THC,pock(0.45),0.8,pan=-0.5,name='HIT-narrow'); EN(THC+0.02,pock(0.5),0.7,pan=0.5,name='HIT-wide')
EN(THC+0.1,groan(1.8,80),0.55,pan=-0.5,name='twist-big'); EN(THC+0.1,groan(1.0,130),0.3,pan=0.5,name='twist-small')
EN(TV,number_pop(),0.4,name='speed-bars'); EN(TC,swish(1.0,300,2400),0.4,name='court-top')
EN(TC+1.2,pock(1.0),0.5,name='court-hit'); EN(TC+3.2,bounce(1.0),0.5,name='land-in'); EN(TC+4.0,bounce(0.9),0.45,name='land-long')
EN(TO,glitch(0.4),0.5,name='OUT')
# 07 碳纤维：天平同重 → 1980 换代 → 诺阿木拍 → 显微镜放大 → 两条波形 → 热区 → 发球 → 挥拍重量那摞
c=SEC['carbon']; CS=E('carbon','scale',0.5); C80=E('carbon','y1980',5.9); CN=E('carbon','noah',10.3); CM=E('carbon','micro',16.1); CW=E('carbon','wave',18.9); CH=E('carbon','heat',25.7); CV=E('carbon','serve',30.4); CK=E('carbon','stack',33.6); CG=E('carbon','grow',35.2)
EN(CS+0.4,clink(1600),0.45,name='steel-bar'); EN(CS+0.7,click(),0.4,name='fibre-bundle'); EN(CS+2.0,riser(1.2),0.3,name='stiffness-bars')
EN(C80,chime([72,79]),0.4,name='1980'); EN(C80+0.4,swish(1.2,300,2600),0.3)
EN(CN,hum(4.0,73),0.4,name='noah-wood'); EN(CN+1.0,ding(660),0.25)
for i in range(4): EN(CM+i*0.55,blip(900+i*350,0.08,1.4,0.5),0.4,name='zoom-%d'%i)
EN(CW,hum(5.5,100),0.35,name='wave-old'); EN(CW+1.0,hum(4.5,170),0.3,name='wave-new')
EN(CH,panel(),0.35,name='heatmap'); EN(CV,pock(1.0),0.55,name='serve-hit'); EN(CV+0.2,riser(0.8),0.25)
EN(CK,swish(0.6,800,4000),0.45,name='pull-plates'); EN(CG,clink(2600),0.4,name='thin-slice')
# 08 规则：包络框合拢 → 32 收到 29 → 尺寸逐条弹出 → 重量、材料被划掉
r=SEC['rules']; RB=E('rules','box',3.1); RS=E('rules','shrink',6.6); RD=E('rules','dims',8.8); RK=E('rules','strike',9.8)
EN(RB,slam(),0.5,name='BOX-close'); EN(RB,sub_boom(),0.35); EN(RS,swish(1.2,400,1600),0.4,name='32-to-29')
for i in range(3): EN(RD+i*0.4,tick(),0.6,name='dim-%d'%i)
for i in range(2): EN(RK+i*0.3+0.4,zap(1800,600,0.25),0.35,name='strike-%d'%i)
# 09 打法：引语（技术 → 力量和旋转）→ 天平左倾（模拟）→ 回正（实测）→ 拼图咬合
y=SEC['style']; YQ=E('style','quote',0.5); YP=E('style','power',4.1); YS=E('style','sim',6.3); YR2=E('style','real',11.3); YZ=E('style','puzzle',16.3)
EN(YQ,hum(3.6,65),0.45,name='quote'); EN(YP,number_pop(),0.4,name='power-spin')
EN(YS,clink(1400),0.45,name='scale-tilt'); EN(YS+0.3,swish(0.8,300,1500),0.25); EN(YR2,clink(1900),0.45,name='scale-level')
for i in range(2): EN(YZ+0.3+i*0.35,slam(),0.3,name='puzzle-%d'%i)
EN(YZ+1.2,hum(3.0,82),0.35,name='inseparable')
# 10 结尾：回放开场那一球（接触在 1.0 s）→ 玻璃光里两支拍 → 一颗球落下
e=SEC['end']; ER=E('end','replay',3.3); EG=E('end','glass',5.9); EB=E('end','ball',11.5)
EN(e['t0']+1.0,pock(0.5),0.6,name='replay-hit'); EN(e['t0']+1.05,verb(pock(0.5),0.6)[:,0],0.25,name='replay-echo')
EN(ER,panel(),0.3,name='cost-bars'); EN(EG,sparkle(2.0,40),0.3,name='glass-light'); EN(EG+0.5,chime([84,88,91],0.16,0.35),0.4,name='end-question')
EN(EB+0.6,bounce(1.0),0.55,name='ball-land'); EN(EB+1.3,bounce(1.1),0.3)

# ================= BGM（vibeknowledge 库自有） =================
import subprocess, re
BGM=os.environ.get('VT_BGM','/home/user/robertyang87/vibeknowledge/assets/music/we-never-remix-hi-noise-qiucheng.m4a')
BGM_LUFS=-20.0
raw=subprocess.run(['ffmpeg','-v','error','-i',BGM,'-ac','2','-ar',str(SR),'-f','f32le','-'],capture_output=True,check=True).stdout
song=np.frombuffer(raw,np.float32).reshape(-1,2).astype(np.float64)
# 循环＋卡点（所有者 2026-11-04「BGM 要循环，同时看看怎么卡点」）：曲子 112.3 BPM，小节 4×0.53194 s，曲内第一个强拍 0.4757 s（librosa 实测）。
# 小节号 → 段落：0–7 前奏、8–39 主段、40–47 间奏（轻）、48–63 主段、64 起尾段淡出。起点 BGM_OFF 取钩子里柱状图砸下来那一刻＝第 8 小节线，
# 之后按「主段 → 间奏 → 主段 → 再从第 8 小节循环」整小节往后拼，不放尾段；拼缝都在小节线上，10 ms 交叉淡化
BAR=4*0.53194; bar=lambda k: 0.4757+k*BAR; BGM_OFF=bar(8)-HC   # 开场那一球打在拍框上那一刻＝第 8 小节线，主段进来
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

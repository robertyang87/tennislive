# Synthesized SFX bed for tennis v2. Every sound is generated here with numpy/scipy (no downloaded assets).
import numpy as np, soundfile as sf, sys, json, math
from scipy import signal
import os
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.environ.get('VT_WORK',HERE)
sys.path.insert(0,HERE)
os.makedirs(os.path.join(WORK,'sfx'),exist_ok=True)
import overlay as OV
SR=48000; BAR=2.1364; B0=0.46; bar=lambda k:B0+BAR*k; snap=OV.snap
TOTAL=bar(82)+6.5; N=int(TOTAL*SR)+SR
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

# ---------- ball physics (mirror of scene.js serve()) ----------
L_=23.77/2; SW=8.23/2; SEAT=np.array([SW+6,3,0.0])
def serve(tb):
    z0=-L_; tB=0.395; tE=0.714
    if tb<=0: return np.array([0.6,2.8,z0])
    if tb<tB: u=tb/tB; return np.array([0.6-0.9*u,2.8*(1-u)+0.033*u,z0+18*(u*(1.12-0.12*u))])
    u=min(1,(tb-tB)/(tE-tB)); return np.array([-0.3-0.5*u,0.033+1.25*math.sin(math.pi*0.5*u),z0+18+6.8*u*(1.1-0.1*u)])
loop=lambda x,p:((x%p)+p)%p
# shots: (t0,t1,tb(lt),rate,camera(lt) or None,kind)
SH=[
 (0,bar(3),lambda lt:loop(lt*0.22,0.95)-0.1,0.22,None,'far'),
 (bar(3),bar(6),lambda lt:loop(lt,2.3)-0.4,1.0,lambda lt:SEAT+[-0.5,-0.6,2.5+math.sin(lt*0.4)*0.6],'court'),
 (bar(12),bar(15)+1.0,lambda lt:min(0.75,lt*0.12),0.12,None,'slow'),
 (bar(15)+1.0,bar(18),lambda lt:loop(lt,2.0)-0.3,1.0,lambda lt:np.array([26-lt*0.6,14,6]),'near'),
 (bar(18),bar(22),lambda lt:loop(lt*0.5,1.3)-0.2,0.5,None,'far'),
 (bar(22),bar(26),lambda lt:loop(lt*0.6,1.4)-0.2,0.6,None,'far'),
 (bar(26),bar(29),lambda lt:loop(lt,2.0)-0.4,1.0,None,'tv'),
 (bar(29),bar(32),lambda lt:loop(lt,1.6)-0.3,1.0,None,'tv'),
 (bar(32),bar(37),lambda lt:min(0.714,loop(lt*0.35,0.95)),0.35,None,'far'),
 (bar(37),bar(42),lambda lt:loop(lt,2.14)-0.5,1.0,lambda lt:SEAT+[1.5,0.4,2.8],'court'),
 (bar(42),bar(47),lambda lt:loop(lt,2.14)-0.4,1.0,lambda lt:SEAT+[0,0,2.5],'court'),
 (bar(47),bar(51),lambda lt:loop(lt*0.5,1.07)-0.15,0.5,lambda lt:np.array([0,1.6,L_+4]),'depth'),
 (bar(74)+1.4,bar(77),lambda lt:loop(lt,1.6)-0.2,1.0,lambda lt:SEAT+[-0.3,-0.5,0.3],'court'),
]
GAIN={'court':1.0,'near':0.55,'far':0.35,'slow':0.8,'tv':0.4,'depth':0.9}
C=343.0
def ball_track():
    wsrc=hp(lp(rng.standard_normal(int(TOTAL*SR*1.3)),5000),400)   # whoosh source (air)
    for t0,t1,f,rate,camf,kind in SH:
        lt=np.arange(0,t1-t0,1/SR); tb=np.array([f(x) for x in lt[::48]]); tb=np.interp(lt,lt[::48],tb)
        g=GAIN[kind]
        # discrete events
        for i in range(1,len(tb)):
            for thr,fn,nm in ((0.0,pock,'hit'),(0.395,bounce,'bounce')):
                if tb[i-1]<thr<=tb[i]:
                    tm=t0+lt[i]; p=serve(thr); 
                    if camf is not None: r=np.linalg.norm(p-camf(lt[i])); a=min(1.6,8/(r+2))
                    else: a=1.0
                    x=fn(rate if kind!='tv' else 1.0)
                    if kind=='tv': x=tvize(x)
                    x=verb(x,0.22 if kind!='slow' else 0.45)
                    place(x,tm,g*a*(1.0 if nm=='hit' else 0.8),name='%s:%s'%(nm,kind))
        # continuous Doppler whoosh for close camera shots
        if camf is None or kind=='near': continue
        P=np.array([serve(x) for x in tb[::48]]); Cm=np.array([camf(x) for x in lt[::48]])
        r=np.linalg.norm(P-Cm,axis=1); dt=48/SR
        vr=np.gradient(r,dt); vb=np.linalg.norm(np.gradient(P,dt,axis=0),axis=1)
        act=((tb[::48]>0)&(tb[::48]<0.714)).astype(float)
        dop=np.clip(C/(C+vr),0.6,1.8)
        amp=act*np.clip(vb/40,0,1.5)**1.5*np.clip(6/(r+0.5),0,3)
        amp=np.convolve(amp,np.ones(9)/9,'same')
        rate_s=np.interp(lt,lt[::48],dop); amp_s=np.interp(lt,lt[::48],amp)
        # pan from ball x relative to camera (simple: sign of lateral offset across the camera's view)
        pan_s=np.interp(lt,lt[::48],np.tanh((P[:,2]-Cm[:,2])/4.0))*(-1)
        ph=np.cumsum(rate_s); idx=np.clip(ph.astype(int),0,len(wsrc)-2)
        y=wsrc[idx]; y=signal.sosfilt(signal.butter(2,[700,4500],'band',fs=SR,output='sos'),y)
        tone=np.sin(2*np.pi*np.cumsum(330*rate_s)/SR)*0.15          # faint fuzz-spin buzz
        y=(y+tone)*amp_s*0.5*g
        st=np.stack([y*np.sqrt((1-pan_s)/2),y*np.sqrt((1+pan_s)/2)],1)*1.414
        i0=int(t0*SR); out[i0:i0+len(st)]+=st
        EV.append((round(t0,3),'whoosh-track:%s'%kind))

ball_track()
# ---------- crowd ambience for courtside / stadium shots ----------
for t0,t1,g in ((bar(3),bar(6),0.55),(bar(6),bar(9),0.18),(bar(37),bar(47),0.45),(bar(74)+0.8,bar(77),0.55)):
    place(crowd(t1-t0+0.6),t0-0.3,g,name='crowd')
place(applause(2.4),bar(6)-2.2,0.6,name='applause')
place(applause(2.0),bar(42)-1.8,0.5,name='applause')
# ---------- transitions: risers into section cuts, impact on the cut ----------
for k in (12,18,32,42,51,64,69,77):
    place(verb(riser(1.7),0.3),bar(k)-1.7,0.35,name='riser'); place(hit(),bar(k),0.5,name='impact')
# soft swish on every other shot cut
for k in (3,6,9,15,22,26,29,37,47,55,60,74):
    t=bar(k)+(1.0 if k==15 else 0); place(swish(0.8),t-0.45,0.28,pan=rng.uniform(-0.5,0.5),name='swish')
# ---------- low booms for scale reveals ----------
for t,g in ((0.0,1.0),(bar(6),0.7),(bar(51)+1.5,0.9),(bar(64),0.8),(bar(69)+0.5,1.0),(bar(77),0.6)):
    place(boom(4.5),t,g*0.6,name='boom')
place(verb(swish(0.35,1500,7000),0.3),bar(29),0.5,name='flash-zap')     # flash into CAM 1 view
# ---------- HUD / UI sounds synced to overlay events ----------
for s,d,txt,pl in OV.CAPS: place(blip(1900,0.045,1.25,0.35),s,0.5,pan=0.0,name='cap')
hud=[(0.8,'num'),(bar(12),'num'),(snap(29.0),'panel'),(bar(18),'label'),(snap(43.0),'panel'),(bar(22),'panel'),(bar(22)+0.5*(bar(26)-bar(22)),'panel'),
     (bar(26),'label'),(bar(29)+0.8,'panel'),(bar(32),'num'),(bar(37),'panel'),(snap(79.8),'bar'),(snap(82.4),'bar'),(snap(85.2),'bar'),(snap(87.8),'num'),
     (snap(96.3),'panel'),(snap(98.6),'lock'),(snap(107.0),'panel'),(bar(51)+0.5,'label'),(snap(124.8),'num'),(bar(60),'panel'),(bar(64)+0.5,'label'),(snap(144.9),'num'),(bar(82),'panel')]
for t,k in hud:
    if k=='num': place(number_pop(),t,0.7,name='hud-num')
    elif k=='panel': place(panel(),t,0.45,name='hud-panel')
    elif k=='label': place(blip(2600,0.05,1.1,0.5),t,0.45,name='hud-label')
    elif k=='bar':   # bar grows: rising chirp
        d=0.9; tt_=tt(d); x=np.sin(2*np.pi*np.cumsum(500+1500*tt_/d)/SR)*np.exp(-tt_/0.5)*0.25; place(x,t,0.5,name='hud-bar')
    elif k=='lock':
        for j in range(6): place(blip(3000,0.03,1.0,0.4),t+j*0.2,0.35)
        EV.append((round(t,3),'gaze-jumps'))
# counting timer ticks in slow-motion C1, sweep readout ticks in E1
for a,b,st in ((bar(12),bar(15)+1.0,0.25),(bar(32),bar(37),0.33)):
    t=a+0.4
    while t<b-0.2: place(tick(),t,0.25); t+=st
    EV.append((round(a,3),'ticks'))
# closing serif lines: soft bell
def bell(f=660):
    t=tt(3.0); return verb((np.sin(2*np.pi*f*t)+0.4*np.sin(2*np.pi*f*2.76*t)*np.exp(-t/0.3))*np.exp(-t/1.0)*0.3,0.5)
for dt_,f in ((0.4,523),(1.4,587),(3.4,784)): place(bell(f),bar(77)+dt_,0.5,name='bell')
# continuous low 'space' room tone so no section drops to digital silence
t_=tt(TOTAL); bed=lp(rng.standard_normal(len(t_)),220,4)*0.05+np.sin(2*np.pi*55*t_)*0.004*(1+0.3*np.sin(2*np.pi*0.07*t_))
bed*=np.minimum(1,np.minimum(t_/1.5,(TOTAL-t_)/2.0)); out[:len(bed)]+=np.stack([bed,np.roll(bed,700)],1)
# master: gentle limiter-ish soft clip, save
out=out[:int(TOTAL*SR)]
pk=np.abs(out).max(); out=out/pk*0.9; out=np.tanh(out*1.2)/np.tanh(1.2)
sf.write(os.path.join(WORK,'sfx','sfx_bed.wav'),out.astype(np.float32),SR,subtype='FLOAT')
EV.sort(); json.dump(EV,open(os.path.join(WORK,'sfx','sfx_events.json'),'w'),ensure_ascii=False,indent=0)
from collections import Counter; print(len(EV),Counter(e[1].split(':')[0] for e in EV))

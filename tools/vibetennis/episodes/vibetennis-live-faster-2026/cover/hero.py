"""vibetennis 第一集定稿封面（v9，所有者 2026-10-30 审定）的画面层：蓝色全息线稿球场＋金色发球。

按 ITF 球场尺寸经透视相机投影（边线竖向汇聚、中线只在两条发球线之间），球从远端底线
上方发出、朝镜头来。输出 hero7.png 和两处视点/球路的屏幕坐标 geo7.json 到 $VT_COVER_WORK。
"""
import os
os.chdir(os.environ.get("VT_COVER_WORK", "."))
import numpy as np, cv2, math
W,H=2160,2880
rng=np.random.default_rng(3)
zc,hc,pitch=-14.0,12.0,math.radians(42)
f=2286; cx,cy=W/2,2116
cp,sp=math.cos(pitch),math.sin(pitch)
def proj(x,y,z):
    x=np.asarray(x,float); y=np.asarray(y,float); z=np.asarray(z,float)
    Y=y-hc; Z=z-zc
    Yr=Y*cp+Z*sp; Zr=-Y*sp+Z*cp
    return cx+f*x/Zr, cy-f*Yr/Zr, Zr
GOLD=np.array([0.25,0.66,1.0],np.float32)  # court colour: #3fa9ff blue
WARM=np.array([1.0,0.72,0.22],np.float32)
def points(u,v,b,img,col=None):
    m=(u>=0)&(u<W-1)&(v>=0)&(v<H-1)
    u=u[m].astype(int); v=v[m].astype(int); b=b[m]
    plane=np.zeros((H,W),np.float32); np.add.at(plane,(v,u),b)
    img+=plane[...,None]*(GOLD if col is None else col)
acc=np.zeros((H,W,3),np.float32); core=np.zeros_like(acc)
def seg(p,q,width_m=0.06,dens=12000):
    n=int(dens*math.dist(p,q)/10)+200
    t=rng.random(n)
    x=p[0]+(q[0]-p[0])*t; z=p[1]+(q[1]-p[1])*t
    dx=-(q[1]-p[1]); dz=(q[0]-p[0]); L=math.hypot(dx,dz); dx/=L; dz/=L
    j=rng.normal(0,width_m*0.6,n); x+=dx*j; z+=dz*j
    u,v,d=proj(x,0,z)
    points(u,v,(0.5+0.5*rng.random(n))*np.clip(14/d,0.6,1.6)*0.9,acc)
    a=proj(p[0],0,p[1]); b=proj(q[0],0,q[1])
    wpx=max(2,int(round(f*width_m/((a[2]+b[2])/2))))
    cv2.line(core,(int(a[0]),int(a[1])),(int(b[0]),int(b[1])),tuple(float(c*0.42) for c in GOLD),wpx,cv2.LINE_AA)
D=5.485; S=4.115; L=23.77; NZ=L/2; SV1=NZ-6.40; SV2=NZ+6.40
lines=[((-D,0),(-D,L)),((D,0),(D,L)),((-S,0),(-S,L)),((S,0),(S,L)),
       ((0,SV1),(0,SV2)),((0,0),(0,0.15)),((0,L-0.15),(0,L)),
       ((-S,SV1),(S,SV1)),((-S,SV2),(S,SV2))]
for p,q in lines: seg(p,q,0.06)
for z in (0,L): seg((-D,z),(D,z),0.10)
net=np.zeros_like(acc); P=D+0.914
nh=lambda x: 0.914+(1.07-0.914)*(np.abs(x)/P)
for x in np.linspace(-P,P,150):
    a=proj(x,0,NZ); b=proj(x,nh(x),NZ)
    cv2.line(net,(int(a[0]),int(a[1])),(int(b[0]),int(b[1])),tuple(float(c*0.28) for c in GOLD),1,cv2.LINE_AA)
for h in np.linspace(0.06,0.9,13):
    xs=np.linspace(-P,P,80); u,v,_=proj(xs,np.minimum(h,nh(xs)),NZ)
    cv2.polylines(net,[np.stack([u,v],1).astype(np.int32)],False,tuple(float(c*0.28) for c in GOLD),1,cv2.LINE_AA)
xs=np.linspace(-P,P,120); u,v,_=proj(xs,nh(xs),NZ)
cv2.polylines(core,[np.stack([u,v],1).astype(np.int32)],False,tuple(float(c) for c in GOLD),5,cv2.LINE_AA)
for x in (-P,P):
    a=proj(x,0,NZ); b=proj(x,1.07,NZ)
    cv2.line(core,(int(a[0]),int(a[1])),(int(b[0]),int(b[1])),tuple(float(c) for c in GOLD),6,cv2.LINE_AA)
n=700000; x=rng.normal(0,5.5,n); z=rng.normal(12,11,n)
w=np.exp(-((np.abs(x)/7.5)**4))
u,v,d=proj(x,0,z); points(u,v,(0.006+0.35*rng.random(n)**10)*w,acc)
n=6000; x=rng.normal(0,7,n); z=rng.uniform(-2,30,n); y=rng.uniform(0,3.5,n)
u,v,d=proj(x,y,z); points(u,v,0.5*rng.random(n)**3,acc)
x0,y0,z0=1.2,2.9,L+0.3; x1,y1,z1=-0.9,0.0,SV1+1.2
def bpos(t): return x0+(x1-x0)*t, y0+(y1-y0)*t, z0+(z1-z0)*t
tb=0.93
trail=np.zeros_like(acc)
n=160000; t=tb*rng.random(n)**0.55
bx,by,bz=bpos(t); s=0.035+0.02*(t/tb)
u,v,d=proj(bx+rng.normal(0,s,n),by+rng.normal(0,s,n),bz)
br=(0.04+0.96*(t/tb)**3)*(0.4+0.6*rng.random(n))*0.9
m=(u>=0)&(u<W-1)&(v>=0)&(v<H-1)
pl=np.zeros((H,W),np.float32); np.add.at(pl,(v[m].astype(int),u[m].astype(int)),br[m])
trail+=pl[...,None]*np.array([1.0,0.70,0.22],np.float32)
X,Y,Z=bpos(tb); bu,bv,bd=proj(X,Y,Z)
Xa,Ya,Za=bpos(tb-0.10); au,av,_=proj(Xa,Ya,Za)
streak=np.zeros_like(acc)
for k in range(30):
    a=k/30; c=(a**2)
    pu,pv=au+(bu-au)*a, av+(bv-av)*a
    cv2.circle(streak,(int(pu),int(pv)),max(2,int(3+3*a)),(c,c*0.82,c*0.45),-1,cv2.LINE_AA)
ballr=max(9,1.8*f*0.0335/bd)
cv2.circle(streak,(int(bu),int(bv)),int(round(ballr*1.4)),(1.6,1.5,1.2),-1,cv2.LINE_AA)

# floating sparks (short motion streaks) + embers around the trail
spk=np.zeros_like(acc)
for i in range(160):
    uu=rng.normal(W/2,650); vv=rng.uniform(1000,2250)
    L=rng.uniform(4,22); ang=rng.uniform(-0.4,0.4)+math.pi/2
    c=float(rng.uniform(0.15,0.9)**2)
    cv2.line(spk,(int(uu),int(vv)),(int(uu+L*math.cos(ang)),int(vv+L*math.sin(ang))),(c*0.3,c*0.75,c),max(1,int(rng.uniform(1,3))),cv2.LINE_AA)
tt=tb*rng.random(2500)**0.5
ex,ey,ez=bpos(tt)
u,v,d=proj(ex+rng.normal(0,0.35,2500),ey+rng.normal(0,0.35,2500),ez)
points(u,v,rng.random(2500)**2*2.0,spk,WARM)

arc=np.zeros_like(acc)
for R,b in ((19,0.10),(23,0.07),(27,0.05)):
    th=np.linspace(0,2*math.pi,720)
    ax=R*0.75*np.cos(th); az=NZ+R*np.sin(th)
    m=az>-6
    u,v,_=proj(ax[m],0,az[m])
    pts=np.stack([u,v],1).astype(np.int32)
    cv2.polylines(arc,[pts],False,tuple(float(c*b) for c in GOLD),2,cv2.LINE_AA)
glow=lambda img,s,a: cv2.GaussianBlur(img,(0,0),s)*a
lit=acc+core+net+trail+spk+arc
out=lit+glow(lit,5,1.0)+glow(lit,20,0.9)+glow(lit,70,0.5)+streak+glow(streak,8,2.0)+glow(streak,30,1.2)+glow(streak,90,0.6)
bok=np.zeros_like(acc)
for i in range(0):
    uu=rng.uniform(0,W); vv=rng.uniform(1350,H); rr=rng.uniform(8,30)
    cv2.circle(bok,(int(uu),int(vv)),int(rr),tuple(float(c*rng.uniform(0.04,0.18)) for c in GOLD),-1,cv2.LINE_AA)
out+=cv2.GaussianBlur(bok,(0,0),5)
out=1-np.exp(-out*1.5)
out=np.clip(out*255,0,255).astype(np.uint8)

import json
B1=proj(*bpos(0.45)); B2=proj(*bpos(0.93))
C=proj(0,5,-7); E=proj(D+1.0,1.2,NZ-1)
json.dump({'B1':[float(B1[0]),float(B1[1])],'B2':[float(B2[0]),float(B2[1])],'C':[float(C[0]),float(C[1])],'E':[float(E[0]),float(E[1])]},open('geo7.json','w'))
cv2.imwrite('hero7.png',cv2.cvtColor(out,cv2.COLOR_RGB2BGR))
for nm,(x,z) in {'nearL':(-D,0),'nearR':(D,0),'farL':(-D,L),'farR':(D,L),'netC':(0,NZ)}.items():
    u,v,_=proj(x,0,z); print(nm,int(u),int(v))
print('ball',int(bu),int(bv),'r',round(ballr,1))

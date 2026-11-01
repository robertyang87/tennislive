from functools import lru_cache
import random
def game(p):
    q=1-p; return p**4*(1+4*q+10*q*q)+20*p**3*q**3*p*p/(1-2*p*q)
def tiebreak(pa,pb):
    # A serves first point, then alternate every 2; pa=A wins pt on A serve, pb=A wins pt on B serve
    @lru_cache(None)
    def f(a,b):
        if a>=7 and a-b>=2: return 1.0
        if b>=7 and b-a>=2: return 0.0
        if a>=6 and b>=6 and a==b:
            w=pa*pb; l=(1-pa)*(1-pb); return w/(w+l)
        n=a+b; A = (n%4 in (0,3))
        p=pa if A else pb
        return p*f(a+1,b)+(1-p)*f(a,b+1)
    return f(0,0)
def set_(pa,pb):
    h=game(pa); br=game(pb); tb=tiebreak(pa,pb)
    @lru_cache(None)
    def f(a,b):
        if a==7: return 1.0
        if b==7: return 0.0
        if a>=6 and a-b>=2: return 1.0
        if b>=6 and b-a>=2: return 0.0
        if a==6 and b==6: return tb
        g=h if (a+b)%2==0 else br
        return g*f(a+1,b)+(1-g)*f(a,b+1)
    return f(0,0)
def match(s,best):
    need=best//2+1
    @lru_cache(None)
    def f(a,b):
        if a==need: return 1.0
        if b==need: return 0.0
        return s*f(a+1,b)+(1-s)*f(a,b+1)
    return f(0,0)
print("iid ladder")
for p in (0.50,0.51,0.52,0.53,0.54,0.55,0.56):
    s=set_(p,p); print(f" p={p:.2f} game={game(p):.4f} set={s:.4f} bo3={match(s,3):.4f} bo5={match(s,5):.4f}")
print("Federer serve/return (UTS): spw .697 rpw .396")
pa,pb=0.697,0.396
s=set_(pa,pb); print(f" hold={game(pa):.4f} break={game(pb):.4f} set={s:.4f} bo3={match(s,3):.4f} bo5={match(s,5):.4f} avg_game={(game(pa)+game(pb))/2:.4f}")
# Monte Carlo, independent implementation
random.seed(1)
def mc_game(p):
    a=b=0
    while True:
        if random.random()<p: a+=1
        else: b+=1
        if a>=4 and a-b>=2: return 1
        if b>=4 and b-a>=2: return 0
def mc_tb(p):
    a=b=0
    while True:
        if random.random()<p: a+=1
        else: b+=1
        if a>=7 and a-b>=2: return 1
        if b>=7 and b-a>=2: return 0
def mc_set(p):
    a=b=0
    while True:
        if a==6 and b==6: return mc_tb(p)
        if mc_game(p): a+=1
        else: b+=1
        if a>=6 and a-b>=2: return 1
        if b>=6 and b-a>=2: return 0
def mc_match(p,best):
    need=best//2+1; a=b=0
    while a<need and b<need:
        if mc_set(p): a+=1
        else: b+=1
    return int(a==need)
N=200000
for p in (0.51,0.54):
    g=sum(mc_game(p) for _ in range(N))/N; st=sum(mc_set(p) for _ in range(N//4))/(N//4); m3=sum(mc_match(p,3) for _ in range(N//8))/(N//8); m5=sum(mc_match(p,5) for _ in range(N//8))/(N//8)
    print(f" MC p={p}: game={g:.4f} set={st:.4f} bo3={m3:.4f} bo5={m5:.4f}")

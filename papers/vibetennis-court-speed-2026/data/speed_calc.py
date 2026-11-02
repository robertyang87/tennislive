import csv,glob,collections,json,sys
d=sys.argv[1]
def I(x):
    try: return int(float(x))
    except: return None
SL={"Australian Open":"AO","Roland Garros":"RG","Wimbledon":"WIM","Us Open":"USO","US Open":"USO"}
rows=[]
for f in sorted(glob.glob(d+"/atp_*.csv")):
    y=int(f[-8:-4])
    for r in csv.DictReader(open(f,encoding="utf-8",errors="replace")):
        if r["tourney_level"]=="D": continue
        sc=r["score"] or ""
        if any(k in sc for k in("RET","W/O","DEF")): continue
        for s,o in (("w","l"),("l","w")):
            sv,ac,f1,w1,w2=(I(r[f"{s}_{k}"]) for k in("svpt","ace","1stIn","1stWon","2ndWon"))
            if None in(sv,ac,w1,w2) or sv<20: continue
            rows.append(dict(y=y,p=r[("winner" if s=="w" else "loser")+"_name"],opp=r[("winner" if o=="w" else "loser")+"_name"],surf=r["surface"],t=r["tourney_name"],lvl=r["tourney_level"],sv=sv,ac=ac,won=w1+w2))
print("player-matches",len(rows))
# 1 raw by surface
agg=collections.defaultdict(lambda:[0,0,0])
for x in rows:
    a=agg[x["surf"]]; a[0]+=x["sv"];a[1]+=x["ac"];a[2]+=x["won"]
print("surface raw (ace%, serve pts won%)")
for k,a in sorted(agg.items()): print(k,a[0],round(100*a[1]/a[0],2),round(100*a[2]/a[0],2))
# 2 player-adjusted index: server's non-slam ace rate that year (all surfaces) and returner's ace-allowed rate
srv=collections.defaultdict(lambda:[0,0,0]); ret=collections.defaultdict(lambda:[0,0,0])
for x in rows:
    if x["lvl"]=="G": continue
    k=(x["p"],x["y"]); s=srv[k]; s[0]+=x["sv"]; s[1]+=x["ac"]; s[2]+=x["won"]
    k=(x["opp"],x["y"]); s=ret[k]; s[0]+=x["sv"]; s[1]+=x["ac"]; s[2]+=x["won"]
tour=[0,0,0]
for x in rows:
    if x["lvl"]!="G": tour[0]+=x["sv"];tour[1]+=x["ac"];tour[2]+=x["won"]
def idx(filt):
    res=collections.defaultdict(lambda:[0,0,0,0,0])
    for x in rows:
        key=filt(x)
        if key is None: continue
        s=srv.get((x["p"],x["y"])); r=ret.get((x["opp"],x["y"]))
        if not s or not r or s[0]<300 or r[0]<300: continue
        # log5-ish multiplicative expectation per year tour avg
        ty=tavg[x["y"]]
        ea=(s[1]/s[0])*(r[1]/r[0])/ty[0]; ew=(s[2]/s[0])*(r[2]/r[0])/ty[1]
        q=res[key]; q[0]+=x["ac"]; q[1]+=ea*x["sv"]; q[2]+=x["won"]; q[3]+=ew*x["sv"]; q[4]+=1
    return {k:(round(v[0]/v[1],3),round(v[2]/v[3],3),v[4]) for k,v in res.items()}
ty=collections.defaultdict(lambda:[0,0,0])
for x in rows:
    if x["lvl"]!="G": t=ty[x["y"]]; t[0]+=x["sv"];t[1]+=x["ac"];t[2]+=x["won"]
tavg={y:(t[1]/t[0],t[2]/t[0]) for y,t in ty.items()}
out={}
def era(y): return "2021-26" if y>=2021 else "2011-20" if y>=2011 else "2001-10" if y>=2001 else "1991-00"
out["slam_era"]=idx(lambda x: (SL.get(x["t"]),era(x["y"])) if x["lvl"]=="G" and SL.get(x["t"]) else None)
out["slam_all"]=idx(lambda x: SL.get(x["t"]) if x["lvl"]=="G" and SL.get(x["t"]) and x["y"]>=2015 else None)
out["slam_year"]=idx(lambda x: (SL.get(x["t"]),x["y"]) if x["lvl"]=="G" and SL.get(x["t"]) else None)
out["surface_2015"]=idx(lambda x: x["surf"] if x["lvl"]!="G" and x["y"]>=2015 else None)
for k in("slam_all","surface_2015"):
    print(k); [print(" ",a,b) for a,b in sorted(out[k].items(),key=lambda z:-z[1][0])]
print("slam_era")
for a,b in sorted(out["slam_era"].items()): print(" ",a,b)
json.dump({k:{str(a):b for a,b in v.items()} for k,v in out.items()},open(d+"/../speed_result.json","w"),ensure_ascii=False,indent=0)
raw=collections.defaultdict(lambda:[0,0,0])
for x in rows:
    if x["lvl"]=="G" and SL.get(x["t"]):
        a=raw[(SL[x["t"]],era(x["y"]))]; a[0]+=x["sv"];a[1]+=x["ac"];a[2]+=x["won"]
print("raw slam era ace% / svwon%")
for k,a in sorted(raw.items()): print(" ",k,round(100*a[1]/a[0],2),round(100*a[2]/a[0],2))
for s in("WIM","AO","USO","RG"):
    print(s,[ (y,out["slam_year"][(s,y)][0]) for y in range(2015,2027) if (s,y) in out["slam_year"]])

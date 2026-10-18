"""Bounded current-episode contrasts; never regenerates actual production ORIG."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse,json,os,subprocess,sys
ROOT=Path('/workspace/tennislive')
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();job=json.loads((out/'job.json').read_text());script=Path(__file__).with_name('finite_review.py')
env=dict(os.environ);env.update(POLYPHONE_CACHE=str(out/'reference-cache'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
def priority(i):
    t=job['targets'][i]
    return (0 if t['char'] in '地场重冠将长还更给' else 1,i)
def run(i):
    path=out/'targets'/f'{i:03}.json';t=job['targets'][i]
    if path.exists():
        old=json.loads(path.read_text())
        assert all(old.get(k)==t.get(k) for k in ['sentence','at','char','intended','wrong','ok_refs','bad_refs','actual_binding']),'Existing target belongs to changed inputs; use a new review scope.'
        print('EXACT_ALREADY_MEASURED',i,flush=True);return
    r=subprocess.run([sys.executable,str(script),'target','--index',str(i),'--out',str(out)],env=env,capture_output=True,text=True,cwd=ROOT)
    print(r.stdout or r.stderr[-1800:],flush=True)
with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(run,sorted(range(len(job['targets'])),key=priority)))

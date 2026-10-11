from pathlib import Path
import json,re,subprocess,concurrent.futures
root=Path(__file__).parent;src=root/'孙心然成长历程_审片版_1080x1440.mp4'
# Replay adapter: use the exact 32 frozen intervals actually rendered.
# Geometry/filter/encoding settings below are the production settings.
import hashlib
assert hashlib.sha256(src.read_bytes()).hexdigest() == '509cca3263c96588d7726604e5b44b067d803a83867018fcc31dd85558a4bdd4', 'Unexpected source master'
sc=json.loads((root/'repair-scenes.json').read_text())
bounds={'wide680':(0,384,1080,668),'wide532':(0,454,1080,528),'archive':(114,442,852,552),'photo680':(0,384,1080,672),'photo608':(0,420,1080,600),'photo948':(0,260,1080,924),'photo736':(0,364,1080,716),'portrait':(132,160,812,1040)}
(root/'repair-scenes.json').write_text(json.dumps(sc,indent=2))
parts=root/'repair-parts';parts.mkdir(exist_ok=True)
def work(z):
 i,s=z;out=parts/f'{i:02d}.mp4';dur=s['end']-s['start']
 if out.exists() and out.stat().st_size>1000 and subprocess.run(['ffprobe','-v','error',str(out)],capture_output=True).returncode==0:return
 if s['kind']=='native':graph='[0:v]setsar=1[v]'
 else:
  x,y,w,h=bounds[s['kind']]
  split=4 if s['kind'].startswith('wide') else 3
  outputs='[m][h][s][b]' if split==4 else '[m][h][s]'
  graph=f'[0:v]split={split}{outputs};[m]crop={w}:{h}:{x}:{y},scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440,setsar=1[bg];[h]crop=1080:160:0:0,colorkey=0x090D1B:0.08:0.015[header];[s]crop=1080:220:0:1220,colorkey=0x090D1B:0.08:0.015[sub];[bg][header]overlay=0:0[bh];[bh][sub]overlay=0:1080[vs]'
  if split==4:
   score=(230,96,52,900) if s['kind']=='wide680' else (228,68,48,864)
   sw,sh,sx,sy=score
   graph+=f';[b]crop={sw}:{sh}:{sx}:{sy},scale=368:-2[score];[vs][score]overlay=40:965[v]'
  else:graph+=';[vs]null[v]'
 cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-ss',str(s['start']),'-i',str(src),'-t',str(dur),'-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','25','-video_track_timescale','12800',str(out)]
 p=subprocess.run(cmd,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode())
 print(i,s,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(work,enumerate(sc)))
(root/'repair-concat.txt').write_text('\n'.join("file 'repair-parts/%02d.mp4'"%i for i in range(len(sc))))
subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(root/'repair-concat.txt'),'-c','copy',str(root/'repair-body-silent.mp4')],check=True)

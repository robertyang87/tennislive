from pathlib import Path
import json,re,subprocess,concurrent.futures
root=Path(__file__).parent;src=root/'孙心然成长历程_审片版_1080x1440.mp4'
# V2 uses frozen scene intervals; no pasted scoreboard layer.
sc=json.loads((root/'repair-scenes.json').read_text())
bounds={'wide680':(0,384,1080,668),'wide532':(0,454,1080,528),'archive':(114,442,852,552),'photo680':(0,384,1080,672),'photo608':(0,420,1080,600),'photo948':(0,260,1080,924),'photo736':(0,364,1080,716),'portrait':(132,160,812,1040)}
parts=root/'repair-parts-no-pasted-score-v2';parts.mkdir(exist_ok=True)
def work(z):
 i,s=z;out=parts/f'{i:02d}.mp4';dur=s['end']-s['start']
 if not s['kind'].startswith('wide'):
  import shutil
  shutil.copyfile(root/'repair-parts'/f'{i:02d}.mp4',out)
  return
 if out.exists() and out.stat().st_size>1000 and subprocess.run(['ffprobe','-v','error',str(out)],capture_output=True).returncode==0:return
 if s['kind']=='native':graph='[0:v]setsar=1[v]'
 else:
  x,y,w,h=bounds[s['kind']]
  split=3
  outputs='[m][h][s]'
  graph=f'[0:v]split={split}{outputs};[m]crop={w}:{h}:{x}:{y},scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440,setsar=1[bg];[h]crop=1080:160:0:0,colorkey=0x090D1B:0.08:0.015[header];[s]crop=1080:220:0:1220,colorkey=0x090D1B:0.08:0.015[sub];[bg][header]overlay=0:0[bh];[bh][sub]overlay=0:1080[vs]'
  graph+=';[vs]null[v]'
 cmd=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-ss',str(s['start']),'-i',str(src),'-t',str(dur),'-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-pix_fmt','yuv420p','-r','25','-video_track_timescale','12800',str(out)]
 p=subprocess.run(cmd,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode())
 print(i,s,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(work,enumerate(sc)))
(root/'repair-concat-no-pasted-score-v2.txt').write_text('\n'.join("file 'repair-parts-no-pasted-score-v2/%02d.mp4'"%i for i in range(len(sc))))
subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(root/'repair-concat-no-pasted-score-v2.txt'),'-c','copy',str(root/'repair-body-no-pasted-score-v2-silent.mp4')],check=True)

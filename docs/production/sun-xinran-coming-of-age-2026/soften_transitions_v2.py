from pathlib import Path
import subprocess,json,concurrent.futures
p=Path(__file__).parent
rows=json.loads((p/'repair-scenes.json').read_text())
sources=[(p/'cover-silent.mp4',1.2)]+[(p/'repair-parts-no-pasted-score-v2'/f'{i:02d}.mp4',round(r['end']-r['start'],2)) for i,r in enumerate(rows)]
frames=p/'soft-v2-handles';frames.mkdir(exist_ok=True)
out=p/'soft-v2-parts';out.mkdir(exist_ok=True)
def extract(z):
 i,(f,d)=z
 for name,t in [('first',0),('last',max(0,d-.04))]:
  subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-threads','1','-ss',str(t),'-i',str(f),'-frames:v','1',str(frames/f'{i:02d}-{name}.png')],check=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(extract,enumerate(sources)))
def work(z):
 i,(f,d)=z;target=out/f'{i:02d}.mp4'
 if target.exists() and subprocess.run(['ffprobe','-v','error',str(target)],capture_output=True).returncode==0:return
 cmd=['ffmpeg','-nostdin','-v','error','-y','-threads','2','-i',str(f)]
 graph='[0:v]setpts=PTS-STARTPTS,setsar=1[base];';cur='base';idx=1
 if i:
  cmd+=['-loop','1','-framerate','25','-threads','1','-i',str(frames/f'{i-1:02d}-last.png')]
  graph+=f'[{idx}:v]format=rgba,colorchannelmixer=aa=0.5,fade=t=out:st=0:d=0.12:alpha=1[prev];[{cur}][prev]overlay=0:0:shortest=1[incoming];';cur='incoming';idx+=1
 if i<len(sources)-1:
  cmd+=['-loop','1','-framerate','25','-threads','1','-i',str(frames/f'{i+1:02d}-first.png')]
  graph+=f'[{idx}:v]format=rgba,colorchannelmixer=aa=0.5,fade=t=in:st={max(0,d-.12):.2f}:d=0.12:alpha=1[next];[{cur}][next]overlay=0:0:shortest=1[outgoing];';cur='outgoing'
 graph+=f'[{cur}]format=yuv420p[v]'
 cmd+=['-filter_complex_threads','1','-filter_complex',graph,'-map','[v]','-t',str(d),'-an','-r','25','-c:v','libx264','-threads','2','-preset','fast','-crf','21','-video_track_timescale','12800',str(target)]
 subprocess.run(cmd,check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(target)]))
 assert abs(float(probe['format']['duration'])-d)<.001,(i,d,probe)
 print('soft',i,d,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(work,enumerate(sources)))
(p/'soft-v2-concat.txt').write_text('\n'.join("file 'soft-v2-parts/%02d.mp4'"%i for i in range(len(sources))))
subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(p/'soft-v2-concat.txt'),'-itsoffset','1.2','-i',str(p/'孙心然成长历程_审片版_1080x1440.mp4'),'-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart',str(p/'孙心然成长历程_全屏修复审片版_v2_柔和转场去贴比分_1080x1440.mp4')],check=True)

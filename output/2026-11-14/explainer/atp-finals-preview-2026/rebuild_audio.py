from pathlib import Path
import subprocess,json
O=Path('/workspace/atp-finals-2026');R=Path('/workspace/tennislive-sparse');T=json.loads((O/'final-timeline.json').read_text());duration=T[-1]['start']+T[-1]['duration'];film=O/'atp-finals-preview-2026.mp4';old=O/'pre-audio-rebuild.mp4'
if film.exists():film.rename(old)
args=['ffmpeg','-y','-nostdin','-v','error','-filter_complex_threads','1'];f=[]
for i,m in enumerate(T[1:-1]):
 args+=['-i',str(O/f'voice_{i:02d}.mp3')];delay=round((m['start']+.65)*1000);f.append(f'[{i}:a]adelay={delay},apad,atrim=0:{duration},asetpts=PTS-STARTPTS[a{i}]')
n=len(T)-2;args+=['-i',str(R/'assets/brand/outro_story.mp4')];f.append(f'[{n}:a]adelay={round(T[-1]["start"]*1000)},apad,atrim=0:{duration},asetpts=PTS-STARTPTS[a{n}]');f.append(''.join(f'[a{i}]' for i in range(n+1))+f'amix=inputs={n+1}:normalize=0,atrim=0:{duration}[a]')
subprocess.run(args+['-filter_complex',';'.join(f),'-map','[a]','-c:a','pcm_s16le','-ar','48000','-ac','2',str(O/'final-audio.wav')],check=True)
start=float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=start_time','-of','csv=p=0',str(old)]))
subprocess.run(['ffmpeg','-y','-nostdin','-v','error','-itsoffset',str(-start),'-i',str(old),'-i',str(O/'final-audio.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-t',str(duration),'-movflags','+faststart',str(film)],check=True)
print('Rebuilt final audio directly from all exact speech inputs; video packet data unchanged.',flush=True)

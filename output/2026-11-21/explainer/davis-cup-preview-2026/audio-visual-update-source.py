from pathlib import Path
import hashlib,json,subprocess

O=Path('/workspace/davis-cup-preview-2026'); V=O/'audio-fix'
FPS=30; DURATION=288.466667
def run(args,name):
    with (V/name).open('w') as log:
        subprocess.run(['ffmpeg','-y','-nostdin','-v','error','-threads','2','-filter_complex_threads','1',*args],stdout=log,stderr=log,check=True)

timeline=json.loads((O/'final-timeline.json').read_text())
args=[]; filters=[]
sources=[(O/f'voice_{i:02d}.mp3',round((m['start']+.65)*1000)) for i,m in enumerate(timeline[1:-1])]
sources.append((O/'brand/outro.mp4',round(timeline[-1]['start']*1000)))
for i,(path,delay) in enumerate(sources):
    args+=['-i',str(path)]
    # Explicit stereo conversion and all=1 are both necessary: adelay with
    # only one channel value leaves the second channel at time0.
    filters.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}:all=1,apad,atrim=0:{DURATION},asetpts=PTS-STARTPTS[a{i}]')
filters.append(''.join(f'[a{i}]' for i in range(len(sources)))+f'amix=inputs={len(sources)}:normalize=0,atrim=0:{DURATION}[audio]')
run([*args,'-filter_complex',';'.join(filters),'-map','[audio]','-c:a','pcm_s16le','-ar','48000','-ac','2',str(V/'corrected-audio.wav')],'audio-build.log')

# Replace the cover and its existing 15-frame dissolve. In all later frames,
# extend the actual background row over only the12px decorative top stripe;
# no image content below row14 moves, crops or scales.
vf=("[0:v]trim=start_frame=51,setpts=PTS-STARTPTS,fillborders=top=14:mode=smear,scale=iw:ih:out_range=tv,format=yuv420p,setsar=1[body];"
    "[1:v]scale=1080:1440:flags=lanczos:out_range=tv,format=yuv420p,setsar=1,split[p0][p1];"
    "[p0]trim=end_frame=36,setpts=PTS-STARTPTS[head];"
    "[p1]trim=start_frame=36:end_frame=51,setpts=PTS-STARTPTS,settb=1/30[fadecover];"
    "[2:v]trim=end_frame=15,setpts=PTS-STARTPTS,fillborders=top=14:mode=smear,scale=iw:ih:out_range=tv,format=yuv420p,setsar=1,settb=1/30[fadebody];"
    "[fadecover][fadebody]blend=all_expr=A*(1-T/0.5)+B*T/0.5[dissolve];"
    "[head][dissolve][body]concat=n=3:v=1:a=0[video]")
run(['-i',str(V/'previous-film.mp4'),'-loop','1','-framerate','30','-t','1.7','-i',str(O/'poster.jpg'),'-i',str(O/'segment_00.mp4'),'-filter_complex',vf,'-map','[video]','-an','-frames:v','8654','-r','30','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-color_range','tv','-threads','2','-movflags','+faststart',str(V/'corrected-video.mp4')],'video-build.log')
run(['-i',str(V/'corrected-video.mp4'),'-i',str(V/'corrected-audio.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-t',str(DURATION),'-movflags','+faststart',str(O/'davis-cup-preview-2026.mp4')],'final-mux.log')
print('Corrected film',hashlib.sha256((O/'davis-cup-preview-2026.mp4').read_bytes()).hexdigest(),flush=True)

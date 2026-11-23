from pathlib import Path
import json,hashlib
W=Path('/workspace/scratch/davis-update-20261123');p=W/'render-update.py';text=p.read_text();ns={'__file__':str(p)};exec(compile(text[:text.index('timeline=[]')],str(p),'exec'),ns)
O=ns['O'];run=ns['run'];enc=ns['enc'];sec=ns['sec'];t=json.loads((O/'final-timeline.json').read_text());n=len(t)-1
run(['-i',str(O/'brand/outro.mp4'),'-vf','scale=1080:1440,fps=30,setsar=1,fillborders=top=14:mode=smear','-t','4.117']+enc+[str(O/'outro.mp4')],'outro-no-stripe.log')
length=sec(O/'outro.mp4');run(['-ss','0.5','-i',str(O/'outro.mp4'),'-t',str(length-.5),'-frames:v',str(round((length-.5)*30))]+enc+[str(O/f'interior_{n:02d}.mp4')],'outro-interior-no-stripe.log')
prev=O/t[-2]['file'];length=sec(prev);f='[0:v]settb=1/30,setpts=PTS-STARTPTS[v0];[1:v]settb=1/30,setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/0.5)+B*T/0.5[v];[0:a][1:a]amix=inputs=2:normalize=0[a]'
run(['-ss',str(length-.5),'-t','0.5','-i',str(prev),'-t','0.5','-i',str(O/'outro.mp4'),'-filter_complex',f,'-map','[v]','-map','[a]','-t','0.5']+enc+[str(O/f'join_{n-1:02d}.mp4')],'outro-join-no-stripe.log')
run(['-f','concat','-safe','0','-i',str(O/'concat.txt'),'-map','0:v:0','-c','copy',str(O/'video-only.mp4')],'concat-no-outro-stripe.log')
duration=283.73333333333335
run(['-i',str(O/'video-only.mp4'),'-i',str(O/'final-audio.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-t',str(duration),'-movflags','+faststart',str(O/'davis-cup-preview-2026.mp4')],'mux-no-outro-stripe.log')
print('Removed outro stripe without changing actual speech or earlier frames.',flush=True)

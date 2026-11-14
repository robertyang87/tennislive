from pathlib import Path
import subprocess,json,hashlib,shutil
O=Path('/workspace/atp-finals-2026'); V=O/'cover-v2'; film=O/'atp-finals-preview-2026.mp4'
old=V/'previous-film.mp4'
if not old.exists():shutil.copy2(film,old)
def run(args):subprocess.run(['ffmpeg','-y','-nostdin','-v','error','-threads','2','-filter_complex_threads','1']+args,check=True)
enc=['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-r','30','-threads','2','-c:a','aac','-b:a','128k','-ar','48000','-ac','2','-movflags','+faststart']
run(['-i','/workspace/generated_images/exec-ad7ab88c-010e-4022-9904-b8bd1d0c3d1d.png','-vf','scale=1080:1440','-frames:v','1','-q:v','2',str(O/'poster.jpg')])
run(['-loop','1','-framerate','30','-i',str(O/'poster.jpg'),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1.7']+enc+[str(O/'cover.mp4')])
run(['-i',str(O/'cover.mp4'),'-t','1.2','-frames:v','36']+enc+[str(O/'interior_00.mp4')])
blend='[0:v]settb=1/30,setpts=PTS-STARTPTS[v0];[1:v]settb=1/30,setpts=PTS-STARTPTS[v1];[v0][v1]blend=all_expr=A*(1-T/0.5)+B*T/0.5[v];[0:a][1:a]amix=inputs=2:normalize=0[a]'
run(['-ss','1.2','-t','0.5','-i',str(O/'cover.mp4'),'-t','0.5','-i',str(O/'segment_00.mp4'),'-filter_complex',blend,'-map','[v]','-map','[a]','-t','0.5']+enc+[str(O/'join_00.mp4')])
video=V/'revised-video.mp4'
run(['-f','concat','-safe','0','-i',str(O/'concat.txt'),'-map','0:v:0','-c','copy',str(video)])
start=float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=start_time','-of','csv=p=0',str(video)]))
run(['-i',str(video),'-i',str(old),'-map','0:v:0','-map','1:a:0','-c','copy','-t','321.633333','-movflags','+faststart',str(film)])
def packets(p,stream,first=0):
 r=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams',stream,'-show_packets','-show_data_hash','sha256','-show_entries','packet=data_hash','-of','json',str(p)]))
 return [x['data_hash'] for x in r['packets']][first:]
audio_equal=packets(film,'a:0')==packets(old,'a:0')
body_equal=packets(film,'v:0',51)==packets(old,'v:0',51)
assert audio_equal and body_equal
def times(p):
 r=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_packets','-show_entries','packet=pts,dts,duration','-of','json',str(p)]))
 return r['packets']
assert times(film)[51:]==times(old)[51:]
assert times(film)[0]['pts']==0
e={'schema':'tennislive.cover-only-edit.v1','previous_film_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'film_sha256':hashlib.sha256(film.read_bytes()).hexdigest(),'unchanged_aac_packet_hashes':audio_equal,'unchanged_video_packet_hashes_after_frame_51':body_equal,'changed_interval_s':[0,1.7],'poster_sha256':hashlib.sha256((O/'poster.jpg').read_bytes()).hexdigest()}
(V/'packet-verification.json').write_text(json.dumps(e,indent=2));print(json.dumps(e,indent=2))

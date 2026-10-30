# two-pass ffmpeg loudnorm: ln.py in.wav out.wav I TP [prefilter]
import subprocess,json,sys,re
i,o,I,TP=sys.argv[1:5]; pre=(sys.argv[5]+',') if len(sys.argv)>5 else ''
r=subprocess.run(['ffmpeg','-hide_banner','-i',i,'-af',pre+'loudnorm=I=%s:TP=%s:LRA=11:print_format=json'%(I,TP),'-f','null','-'],capture_output=True,text=True).stderr
d=json.loads(re.findall(r'\{[^{}]*\}',r,re.S)[-1])
f=pre+'loudnorm=I=%s:TP=%s:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true,aresample=48000'%(I,TP,d['input_i'],d['input_tp'],d['input_lra'],d['input_thresh'],d['target_offset'])
subprocess.run(['ffmpeg','-y','-loglevel','error','-i',i,'-af',f,'-c:a','pcm_f32le',o],check=True)

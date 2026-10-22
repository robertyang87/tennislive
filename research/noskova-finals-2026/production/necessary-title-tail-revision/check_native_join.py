from pathlib import Path
from dataclasses import replace
import json,sys,hashlib,subprocess
P=Path('/workspace/tennislive-noskova');R=Path('/workspace/noskova-finals-production');sys.path[:0]=[str(P/'tools'),str(P/'src')]
import build_match_reel as reel,preview_reel_captions as pv
from tennislive.video.tts import tts_bundle_session
sp=P/'specs/reels/noskova-finals-2026.json';spec=json.load(open(sp));out=R/'revision-madrid-tail/native-joined';out.mkdir(exist_ok=True)
for key,file in json.load(open(R/'production/native-source-paths.json')).items():
 p=out/f'source_{key}.mp4'
 if not p.exists():p.symlink_to(file)
reel.apply_tts_backend(spec)
def cb(*,spec,segments,sources,source_w,ass,cues,cover_secs,outdir):
 madr=segments[7];rg=segments[8];mini_start=288.2;offset=cover_secs+sum(x.length for x in segments[:7])+mini_start-madr.start;ma=replace(madr,start=mini_start,inset=None);first=out/'part_madrid.mp4';second=out/'part_rg.mp4';reel.cut_segment(sources[madr.source],ma,first,source_w,tail=reel.SEG_FADE,threads=2);reel.cut_still_segment(rg,second,tail=0,threads=2)
 join=out/'native-join-undecorated.mp4';cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-filter_complex_threads','1','-threads','1','-i',str(first),'-i',str(second),'-filter_complex',reel.dissolve_filtergraph([ma.length,rg.length],reel.SEG_FADE),'-map','[vout]','-map','[aout]','-c:v','libx264','-preset','ultrafast','-crf','12','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',str(join)];subprocess.run(cmd,check=True)
 extras,graph=pv.visual_graph(spec,segments,cover_secs,ass,out,2);graph=graph.replace('[0:v]',f'[global0]');graph=f'[0:v]setpts=PTS+{offset:.9f}/TB[global0];'+graph+f';[out]setpts=PTS-{offset:.9f}/TB[video]';filters=[f'[1:a]adelay={int(ma.length*1000)}|{int(ma.length*1000)}[voice]'];audio=reel.duck_filtergraph(filters,['[voice]'],preserve_source_audio=True);final=out/'native-joined-check.mp4';cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-filter_complex_threads','1','-threads','1','-i',str(join),'-i',str(out/'voice_08.mp3'),*extras,'-filter_complex',graph+';'+audio,'-map','[video]','-map','[out]','-t',str(ma.length+rg.length),'-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(final)];subprocess.run(cmd,check=True)
 report={'kind':'actual_native_targeted_join_only_not_finalfilm','spec_sha256':hashlib.sha256(sp.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(sources[madr.source].read_bytes()).hexdigest(),'source_start':mini_start,'nominal_madrid_end':madr.end,'natural_handle':reel.SEG_FADE,'natural_source_until':madr.end+reel.SEG_FADE,'mini_join_time':ma.length,'global_time_offset':offset,'next_chapter_voice':'voice_08.mp3 exactfrozenactualbytes','next_chapter_voice_delay':ma.length,'fps':reel.FPS_EXPR,'file':str(final),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'commands':[cmd]};(out/'join-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return out/'join-manifest.json'
req=json.load(open(R/'production/tts-requests.json'))
with tts_bundle_session(input_path=R/'production/frozen-tts.zip',expected_requests=req):report=reel.render(spec,out,voice='zh-CN-YunjianNeural',rate='+6%',preview_callback=cb)
print(report)

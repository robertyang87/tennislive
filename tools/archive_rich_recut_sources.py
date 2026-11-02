import os,sys,json,hashlib,subprocess,pathlib,requests
from yt_dlp import YoutubeDL
from tennislive.video.official import OfficialVideoCandidate,fetch_tennistv_video_metadata
vid,slug=sys.argv[1:]
assert vid=='6388215420112'
url='https://ausopen.com/video-player#!?videoId='+vid
playback='https://players.brightcove.net/4447531182001/8qx9SyWTb_default/index.html?videoId='+vid
c={'title':'Ben Shelton v Valentin Vacherot Highlights | Australian Open 2026 Third Round'}
p=pathlib.Path(os.environ['RUNNER_TEMP'])/f'{vid}.mp4'
with YoutubeDL({'quiet':True,'format':'bv*[height<=1080]+ba/b[height<=1080]/b','format_sort':['res:1080','vcodec:h264'],'merge_output_format':'mp4','outtmpl':str(p),'noprogress':True,'concurrent_fragment_downloads':4}) as y:y.extract_info(playback,download=True)
rec={'official_url':url,'official_title':c['title'],'source_sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'bytes':p.stat().st_size,'access':'official public Brightcove player, no credentials','probe':json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(p)]))}
r=p.with_suffix('.json');r.write_text(json.dumps(rec,indent=2))
tag='source-'+vid
subprocess.run(['gh','release','view',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0 or subprocess.run(['gh','release','create',tag,'--title',c['title'],'--notes','Official public source: '+url],check=True)
subprocess.run(['gh','release','upload',tag,str(p),str(r)],check=True)
print(json.dumps({'id':vid,'sha256':rec['source_sha256'],'url':url}))

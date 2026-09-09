import json,subprocess
from pathlib import Path
import build_interview_clip as b
s=json.loads(Path('specs/interviews/sabalenka-noskova-usopen-2026-qf-oncourt.json').read_text())
o=(Path('output/interviews')/s['slug']).resolve();film=o/(s['slug']+'.mp4')
old=o/'_previous.mp4';film.replace(old)
poster=b.cover_poster(s,o/'source.mp4',o,'')
cover=b._still_segment(poster,b.COVER_SECONDS,o/'_cover.mp4')
tail=o/'_preserved_tail.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(b.COVER_SECONDS),'-i',str(old),'-map','0','-c','copy',str(tail)],check=True)
lst=o/'_recovery_concat.txt';lst.write_text("file '_cover.mp4'\nfile '_preserved_tail.mp4'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(film)],check=True)
b._record_film_seconds(film,o)
print('Replaced only 1.8-second cover; reused all original body, lead-in, closing footage and audio.')

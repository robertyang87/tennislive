import json,subprocess
from pathlib import Path
import build_interview_clip as b
s=json.loads(Path('specs/interviews/sabalenka-noskova-usopen-2026-qf-oncourt.json').read_text())
o=(Path('output/interviews')/s['slug']).resolve();film=o/(s['slug']+'.mp4')
old=o/'_previous_full.mp4';film.replace(old)
cover=b._still_segment(o/'poster.jpg',b.COVER_SECONDS,o/'_cover.mp4')
lead=b._lead_in_segment(s,o)
tail=o/'_preserved_body_tail.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','33.93','-i',str(old),'-map','0','-c','copy',str(tail)],check=True)
lst=o/'_short_concat.txt';lst.write_text("file '_cover.mp4'\nfile '_lead.mp4'\nfile '_preserved_body_tail.mp4'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(film)],check=True)
b._record_film_seconds(film,o)
print('Shortened same-match lead to 19.23 seconds; all interview body and closing retained.')

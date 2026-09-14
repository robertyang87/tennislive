"""Check the final film against the reviewed web cards before Release."""
import hashlib,json,re,subprocess
from pathlib import Path
from PIL import Image
import numpy as np
import build_shelton_ncaa_story as m

def main():
    out=m.WORK/'render';package=m.ROOT/'output/2026-09-14/explainer/shelton-ncaa-story'
    final=out/'shelton-ncaa-story.mp4';r=json.loads((out/'render.json').read_text())
    assert len(r['beats'])==24
    assert 310<r['duration']<355
    m.run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
    errors=[];card_errors=[]
    for i in range(24):
        markup=(out/f'card_{i:02d}.html').read_text()
        chip=re.search(r'<span class="chip">([^<]*)</span>',markup).group(1)
        assert not re.match(r'[0-9①-⑨]',chip),chip
        card=np.array(Image.open(out/f'card_{i:02d}.png').convert('RGB')).astype(float)
        reviewed=np.array(Image.open(package/f'slide_{i+1:02d}.jpg').convert('RGB')).astype(float)
        # Reproduction of the already reviewed design, allowing JPEG/browser raster variance.
        card_error=float(np.abs(card-reviewed).mean())
        assert card_error<12,(i,'reviewed card difference',card_error)
        card_errors.append(card_error)
        duration=m.seconds(out/f'part_{i:02d}.mp4')
        for pos in [.2,duration/2,duration-.2]:
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(pos),'-i',str(out/f'part_{i:02d}.mp4'),'-frames:v','1','-vf','crop=1080:140:0:0','-f','rawvideo','-pix_fmt','rgb24','-'])
            frame=np.frombuffer(raw,dtype=np.uint8).reshape(140,1080,3).astype(float)
            ref=np.array(Image.open(out/'cover.png').convert('RGB')).astype(float) if i==0 and pos<2.4 else card
            error=float(np.abs(frame-ref[:140]).mean());assert error<8,(i,pos,error);errors.append(error)
    old=json.loads((package/'render.json').read_text())
    r.update(video_url=old['video_url'],video_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),video_bytes=final.stat().st_size,qc='passed',qc_status='ci_reproduction_passed',delivery_status='release_upload_ready',header_samples_checked=len(errors),header_max_error=max(errors),reviewed_card_max_error=max(card_errors),previous_reviewed_sha256=old.get('video_sha256'))
    (package/'render.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print(json.dumps({'duration':r['duration'],'sha256':r['video_sha256'],'header_checks':len(errors),'max_card_error':max(card_errors)}))
if __name__=='__main__':main()

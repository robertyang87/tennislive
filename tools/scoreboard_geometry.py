"""US Open navy score graphic: frame-level alpha masks, never a widest-shot crop.

Require matching top/bottom graphic borders and navy/white interior. The court,
crowd and players are not acceptable right-edge evidence. Unknown graphics fail
closed instead of reverting to the maximum rectangle.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import numpy as np

PROFILE = 'us-open-navy-v1'
EDGE_PAD = 4

def right_edge(band):
    """Return exclusive graphic edge relative to x0, or None when absent."""
    if band.ndim != 3 or band.shape[0] < 16 or band.shape[1] < 100:
        return None
    r,g,b = [band[:,:,i].astype(np.int16) for i in range(3)]
    blue = (b-r > 20) & (b-g > 15) & (r < 150) & (g < 150)
    low = np.minimum(np.minimum(r,g),b)
    high = np.maximum(np.maximum(r,g),b)
    fill = (blue & (r < 100) & (g < 120)) | ((low > 165) & (high-low < 45))
    border = (blue[:6].mean(axis=0) >= .33) & (blue[-6:].mean(axis=0) >= .33)
    present = border[10:300].mean() >= .8 and fill[6:-6,10:300].mean() >= .6
    white=(low>165)&(high-low<60)
    middle=band.shape[0]//2
    present = (present and white[6:middle-3,10:300].mean() >= .03
               and white[middle+3:-6,10:300].mean() >= .03)
    if not present:
        return None
    hit = border & (fill[6:-6].mean(axis=0) >= .60)
    gaps = np.flatnonzero(np.convolve((~hit).astype(np.int8), np.ones(8, dtype=np.int8), 'valid') == 8)
    edge = next((int(x) for x in gaps if x > 300), None)
    return edge if edge is not None else -1


def stabilize(edges, fps):
    """Trust a local majority, never two outliers or the largest observation.

    No interpolation across absent frames. A graphic with unresolved geometry
    for more than two seconds blocks rendering instead of cropping the court.
    """
    radius=max(4,round(fps*.25))
    anchors={}
    for i,e in enumerate(edges):
        if e is None or e < 0:continue
        window=edges[max(0,i-radius):min(len(edges),i+radius+1)]
        near=[v for v in window if v is not None and v>=0 and abs(v-e)<=4]
        if len(near)>=max(6,.8*len(window)):
            anchors[i]=int(round(float(np.median(near))))
    if not anchors:raise RuntimeError('Scoreboard has no stable, majority-supported geometry')
    result=[]
    for i,e in enumerate(edges):
        if e is None:
            result.append(None);continue
        if i in anchors:result.append(anchors[i]);continue
        valid=[j for j in anchors if abs(j-i)<=2*fps and all(v is not None for v in edges[min(j,i):max(j,i)+1])]
        if not valid:raise RuntimeError(f'Unresolved scoreboard geometry at frame {i}; no wide fallback')
        # At real width changes, match the observed graphic to either side.
        nearest=sorted(valid,key=lambda j:abs(j-i))[:max(1,round(fps/2))]
        j=min(nearest,key=lambda j:(abs(anchors[j]-e) if e>=0 else 0,abs(j-i)))
        result.append(anchors[j])
    return result

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def scan_mask(source, box, start, seconds, target, fps='30000/1001', windows=(), body_top=0):
    """Decode and classify EVERY output frame; do not bridge absent frames."""
    x0,y0,x1,y1=box
    width,height=x1-x0,y1-y0
    # Observe beyond the allowed crop so a full-width graphic has a real edge.
    source_width=int(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width','-of','csv=p=0',str(source)],text=True).strip().split(',')[0])
    scan_width=min(source_width-x0,width+100)
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    dec=subprocess.Popen(['ffmpeg','-v','error','-ss',str(start),'-t',str(seconds),'-i',str(source),'-an','-sn','-vf',f'format=rgb24,crop={scan_width}:{height}:{x0}:{y0},fps={fps}','-f','rawvideo','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    from fractions import Fraction
    rate=float(Fraction(fps))
    n=scan_width*height*3;raw_edges=[];headers=[]
    try:
        while True:
            raw=dec.stdout.read(n)
            if not raw:break
            if len(raw)!=n:raise RuntimeError('Short scoreboard RGB frame')
            band=np.frombuffer(raw,np.uint8).reshape(height,scan_width,3)
            t=len(raw_edges)/rate
            allowed=not windows or any(a<=t<b for a,b in windows)
            raw_edges.append(right_edge(band[body_top:]) if allowed else None)
            header_edge=0
            if body_top and allowed:
                r,g,b=[band[:body_top,:,i].astype(np.int16) for i in range(3)]
                yellow=(r>145)&(g>120)&(b<110)&(r-b>60)&(g-b>40)
                cols=yellow.mean(axis=0)>.2
                if cols[:50].sum()>15:
                    gaps=np.flatnonzero(np.convolve((~cols).astype(np.int8),np.ones(20,dtype=np.int8),'valid')==20)
                    header_edge=next((int(x)+2 for x in gaps if x>30),0)
            headers.append(header_edge)
        err=dec.stderr.read();rc=dec.wait()
        if rc:raise RuntimeError(err.decode(errors='replace'))
    finally:
        if dec.poll() is None:dec.kill()
    from fractions import Fraction
    rate=float(Fraction(fps))
    relative=stabilize(raw_edges,rate)
    edges=[None if e is None else x0+e+EDGE_PAD for e in relative]
    if any(e is not None and e>x1 for e in edges):
        raise RuntimeError('Verified graphic exceeds source box; expand bounds, never truncate')
    enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','gray','-video_size',f'{width}x{height}','-framerate',fps,'-i','-','-an','-c:v','ffv1','-threads','1',str(target)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    mask=np.zeros((height,width),np.uint8)
    try:
        for index,edge in enumerate(edges):
            mask.fill(0)
            if edge is not None:
                mask[body_top:,:edge-x0]=255
                if body_top and headers[index]:
                    mask[:body_top,:min(headers[index],edge-x0)]=255
            enc.stdin.write(mask.tobytes())
        enc.stdin.close();err=enc.stderr.read();rc=enc.wait()
        if rc:raise RuntimeError(err.decode(errors='replace'))
    finally:
        if enc.poll() is None:enc.kill()
    if not edges or not any(e is not None for e in edges):
        raise RuntimeError(f'No verified US Open score graphic at {start}; no maximum-width fallback')
    from fractions import Fraction
    rate=float(Fraction(fps))
    runs=[]
    for k,e in enumerate(edges):
        if runs and runs[-1]['edge']==e:runs[-1]['end_frame']=k+1
        else:runs.append({'start_frame':k,'end_frame':k+1,'edge':e})
    # Quantitative proof: transparent on absent frames; <=4 source px margin.
    return {'profile':PROFILE,'source_start':start,'seconds':seconds,'fps':rate,'frames':len(edges),'present_frames':sum(e is not None for e in edges),'max_extra_source_px':EDGE_PAD,'gap_bridge_frames':0,'mask':str(target),'mask_sha256':sha256(target),'box':list(box),'runs':runs}

def resolve_masks(sources,segments,outdir,spec_path,fps,tail):
    records=[]
    source_hashes={k:sha256(v) for k,v in sources.items()}
    for i,seg in enumerate(segments):
        if not seg.score_inset:continue
        dest=Path(outdir)/'score_masks'/f'segment-{i+1:02d}.mkv'
        x0,y0,x1,y1=seg.score_inset
        seg.score_inset=(x0,max(0,y0-36),x1,y1)
        record=scan_mask(sources[seg.source],seg.score_inset,seg.start,seg.end-seg.start+tail*seg.speed,dest,fps,seg.score_inset_windows,body_top=y0-seg.score_inset[1])
        seg.score_inset_mask=str(dest.resolve())
        record['segment']=i
        record['source_sha256']=source_hashes[seg.source]
        records.append(record)
        print(f"[score-mask] segment {i+1}: {record['present_frames']}/{record['frames']} frames; <= {EDGE_PAD}px margin; no gap bridging")
    proof={'status':'pass','profile':PROFILE,'spec_sha256':sha256(spec_path),'segments':records}
    p=Path(outdir)/'scoreboard_qc.json';p.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return p

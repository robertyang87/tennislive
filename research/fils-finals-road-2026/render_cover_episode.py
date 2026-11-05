from pathlib import Path
import sys,json,threading,http.server,os
R=Path('/workspace/fils-finals-production/native');sys.path.insert(0,str(R/'tools'));os.chdir(R)
import versus_poster as vp
from playwright.sync_api import sync_playwright
s=json.loads((R/'specs/reels/fils-finals-road-2026.json').read_text());s['cover']['portrait']['fit']='cover';s['cover'].pop('approved_image',None)
vp.STORYCOPY_TOP=400
out=R/'assets/reel/fils-finals-road-2026/cover-approved.jpg'
def render(html,out):
 out=Path(out);out.with_suffix('.html').write_text(html)
 handler=lambda *a,**k:http.server.SimpleHTTPRequestHandler(*a,directory=str(R),**k)
 srv=http.server.ThreadingHTTPServer(('127.0.0.1',8766),handler);threading.Thread(target=srv.serve_forever,daemon=True).start()
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);t=b.new_page(viewport={'width':1080,'height':1440},device_scale_factor=1);t.goto('http://127.0.0.1:8766/'+str(out.with_suffix('.html').relative_to(R)));t.wait_for_timeout(600);t.screenshot(path=str(out),type='jpeg',quality=95);b.close()
 srv.shutdown();return out
vp._render_html=render
# use native payload builder exactly as standard helper
from build_match_reel import resolve_cover_payload
payload,layout=resolve_cover_payload(s['cover'],Path('/workspace/fils-finals-production/production'),sources=None,primary='',spec=s)
vp.build_poster(payload,out,layout=layout)
print(out)

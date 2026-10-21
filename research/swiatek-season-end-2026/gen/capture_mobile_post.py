"""Capture the real Instagram embed at a mobile viewport, without rewriting it."""
from pathlib import Path
import os,json,hashlib,datetime
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
URL='https://www.instagram.com/p/Det8eWQiW9m/embed/captioned/'
with sync_playwright() as pw:
 proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
 browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'],**({'proxy':{'server':proxy}} if proxy else {}))
 context=browser.new_context(viewport={'width':430,'height':932},device_scale_factor=3,is_mobile=True,has_touch=True,user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
 page=context.new_page();response=page.goto(URL,wait_until='networkidle',timeout=60000)
 page.evaluate("""() => { let meta=document.querySelector('meta[name=viewport]'); if(!meta){meta=document.createElement('meta');meta.name='viewport';document.head.appendChild(meta);}meta.content='width=device-width, initial-scale=1'; }""");page.evaluate('document.fonts.ready');page.wait_for_timeout(1500)
 text=page.locator('body').inner_text()
 if 'iga.swiatek' not in text or 'decided to end my season here' not in text:raise RuntimeError('Original account/caption missing; refusing replacement mockup')
 paths=[]
 for name,full in [('instagram-mobile-full.png',True),('instagram-mobile-top.png',False)]:
  p=ROOT/name;page.screenshot(path=str(p),full_page=full);paths.append(p)
 page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
 p=ROOT/'instagram-mobile-caption.png';page.screenshot(path=str(p),full_page=False);paths.append(p)
 record={'url':URL,'fetched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':response.status if response else None,'viewport_css_px':[430,932],'device_scale_factor':3,'is_mobile':True,'has_touch':True,'method':'Real original Instagram captioned embed; viewport meta set to device width for mobile reflow; post text/UI unchanged; not a native-app screenshot','files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],'visual_review':'pending'}
 (ROOT/'instagram-mobile-evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(record,ensure_ascii=False))
 browser.close()

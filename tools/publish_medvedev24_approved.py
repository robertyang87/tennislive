#!/usr/bin/env python3
"""One-film adapter: native gates/templates/publisher; separate notification and XHS title."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,hashlib,json,os,subprocess,sys
import requests
from auto_push_gate import wants_auto_push,validate_qc
from publication_ledger import blocking_attempt
from push_reel import headline,split_copy,build_html,wait_for_copy_page,wait_for_video,poster_url
from tennislive.render.pushmsg import to_copy_page
from tennislive.publish.pushplus import push,write_receipt,_jsdelivr_delivery,image_sources,check_content_length,wait_for_images
SLUG='medvedev-24-titles-23-cities';DATE='2026-09-30'
EXPECTED='5af14197ef8a2dd2c93ae53ec3870ad8992e9b6b2b2ccfde7af254c8c0512c31';SIZE=242652311
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'/DATE/'reel'/SLUG
SPEC=ROOT/'specs/reels'/f'{SLUG}.json';COPY=ROOT/'specs/reels'/f'{SLUG}.xhs.txt'
BASE=f'https://github.com/robertyang87/tennislive/releases/download/reel-{SLUG}'
os.environ.setdefault('TENNISLIVE_ASSET_REV','793b91eaf2386742ce6d30d39648351bff2544af')
VIDEO=f'{BASE}/{SLUG}.mp4';POSTER=poster_url(Path('output')/DATE/'reel'/SLUG)
PAGE=f'https://robertyang87.github.io/tennislive/output/{DATE}/reel/{SLUG}/copy.html'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
class Fields(HTMLParser):
 def __init__(self):super().__init__();self.active=None;self.fields={}
 def handle_starttag(self,t,a):
  if t=='textarea':self.active=dict(a).get('id');self.fields[self.active]=''
 def handle_data(self,d):
  if self.active:self.fields[self.active]+=d
 def handle_endtag(self,t):
  if t=='textarea':self.active=None
def fields(s):
 p=Fields();p.feed(s);return {k:v.strip() for k,v in p.fields.items()}
def content():
 raw=COPY.read_text();title,body=split_copy(raw)
 assert title=='24冠23城，梅德韦杰夫的冠军地图'
 assert body.count('#')==5
 assert (OUT/'xiaohongshu.txt').read_text()==raw
 assert fields((OUT/'copy.html').read_text())==fields(to_copy_page(raw))
 notify=headline(OUT,'网球有故事','',summary='梅德韦杰夫24冠23城',date=DATE)
 assert (OUT/'wechat_title.txt').read_text().strip()==notify
 html=build_html(VIDEO,PAGE,'',raw,POSTER,'网球有故事')
 assert (OUT/'push.html').read_text()==html
 return title,notify,html

def check():
 assert json.loads(SPEC.read_text())['sources']['compiled_master']['sha256']==EXPECTED
 r=json.loads((OUT/'render.json').read_text());assert r['video_url']==VIDEO and r['video_bytes']==SIZE
 assert validate_qc(ROOT,SLUG,OUT)==EXPECTED
 wants_auto_push(ROOT,SLUG,OUT,forced=True)
 title,notify,_=content()
 subprocess.run([sys.executable,str(ROOT/'tools/push_reel.py'),'--stage','check','--outdir',str(OUT.relative_to(ROOT)),'--copy',str(COPY.relative_to(ROOT)),'--column','网球有故事','--date',DATE],cwd=ROOT,check=True)
 print(json.dumps({'native_gate':'pass','notification_title':notify,'full_xhs_title':title,'film_sha256':EXPECTED},ensure_ascii=False))

def verify_public():
 check()
 film=OUT/f'{SLUG}.mp4'
 with requests.get(VIDEO,stream=True,timeout=(20,180)) as r:
  r.raise_for_status()
  with film.open('wb') as f:
   for b in r.iter_content(1024*1024):f.write(b)
 assert film.stat().st_size==SIZE and sha(film)==EXPECTED,'Public Release bytes differ from QC master'
 # Check the actually downloaded public file with the original native L2 implementation.
 with (OUT/'public_native_l2_check.log').open('w') as log:
  subprocess.run([sys.executable,str(ROOT/'tools/check_reel_landed.py'),'--slug',SLUG,'--date',DATE,'--film',str(film),'--spec',str(SPEC)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert validate_qc(ROOT,SLUG,OUT)==EXPECTED
 title,_,_=content();wait_for_video(VIDEO);wait_for_copy_page(PAGE,title)
 response=requests.get(PAGE,timeout=20);response.raise_for_status();assert fields(response.text)==fields((OUT/'copy.html').read_text()),'Public copy title/body differ'
 response=requests.get(POSTER,timeout=30);response.raise_for_status();assert hashlib.sha256(response.content).hexdigest()==sha(OUT/'poster.jpg'),'Public poster differs'
 proof={'status':'pass','film_sha256':sha(film),'film_bytes':film.stat().st_size,'public_video_url':VIDEO,'public_poster_sha256':sha(OUT/'poster.jpg'),'public_copy_fields_match':True}
 (OUT/'public_asset_verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
 _,_,html=content()
 os.environ.setdefault('TENNISLIVE_ASSET_REV',os.environ.get('GITHUB_SHA','793b91eaf2386742ce6d30d39648351bff2544af'))
 prepared=_jsdelivr_delivery(html,image_sources(html),OUT)
 wait_for_images(prepared);check_content_length(prepared)
 print('Public movie, cover, exact copy and native image delivery verified; no message sent')

def send(receipt,run):
 # Do not repeat wants_auto_push after reservation: same-run sending state is expected.
 assert validate_qc(ROOT,SLUG,OUT)==EXPECTED
 p=json.loads((OUT/'public_asset_verification.json').read_text());assert p['status']=='pass' and p['film_sha256']==EXPECTED
 previous=blocking_attempt(ROOT,'reel',SLUG,EXPECTED)
 assert previous and previous['status']=='sending' and previous.get('run')==run,'No same-run committed reservation'
 assert not (OUT/'pushed.json').exists(),'Already sent'
 _,notify,html=content()
 receipt_value=push(notify,html,asset_dir=OUT)
 write_receipt(receipt,receipt_value)
 print('PushPlus accepted; actual mobile delivery remains unconfirmed')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','verify-public','send']);p.add_argument('--receipt-out');p.add_argument('--run');a=p.parse_args()
 if a.stage=='check':check()
 elif a.stage=='verify-public':verify_public()
 else:
  assert a.receipt_out and a.run
  send(a.receipt_out,a.run)

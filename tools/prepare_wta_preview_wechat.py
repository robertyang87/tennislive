"""Restore the exact prechecked master; native voice gate remains mandatory."""
from pathlib import Path
import os,json,requests,hashlib,base64,subprocess,zipfile
R=Path.cwd();O=R/'output/2026-11-04/explainer/wta-finals-preview-2026';repo='robertyang87/tennislive';tag='wta-finals-preview-2026-no-scoreboards'
m=json.loads((O/'transfer.json').read_text());film=O/'wta-finals-preview-2026.mp4';token=os.environ['GH_TOKEN']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with film.open('wb') as f:
 for c in m['chunks']:
  r=requests.get(f'https://api.github.com/repos/{repo}/git/blobs/{c["sha"]}',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'},timeout=90);r.raise_for_status();b=base64.b64decode(r.json()['content']);assert len(b)==c['bytes'] and hashlib.sha256(b).hexdigest()==c['sha256'];f.write(b)
assert film.stat().st_size==m['film_bytes'] and sha(film)==m['film_sha256']
# Materialize the actual frozen inputs so the unchanged native sender checks them.
with zipfile.ZipFile(O/'tts_bundle.zip') as z:
 bm=json.loads(z.read('manifest.json'));byid={e['request_id']:e for e in bm['entries']}
 for occ in bm['occurrences']:
  rid=occ['request_id'];name=occ['output_name'];assert Path(name).name==name and name.startswith('voice_') and name.endswith('.mp3')
  audio=z.read(f'requests/{rid}/audio.mp3');marks=json.loads(z.read(f'requests/{rid}/marks.json'));assert hashlib.sha256(audio).hexdigest()==byid[rid]['audio_sha256'];(O/name).write_bytes(audio);(O/name).with_suffix('.words.json').write_text(json.dumps(marks,ensure_ascii=False))
import sys
sys.path.insert(0,str(R/'tools'))
from voice_quality_gate import require_publish
require_publish(O)
# Release transfer is allowed only after the exact movie and voice identity pass.
subprocess.run(['gh','release','upload',tag,str(film),str(O/'poster.jpg'),str(O/'analysis.txt'),'--clobber','--repo',repo],check=True)
note=O/'release-notes.txt';note.write_text('网球时差｜2026 WTA年终赛前预测，去左下角比分板版。\n已完成16段实际旁白自动检查，非真人听审。\nSHA256：'+m['film_sha256']+'\n');subprocess.run(['gh','release','edit',tag,'--draft=false','--notes-file',str(note),'--repo',repo],check=True)
u=json.loads((O/'render.json').read_text())['video_url'];res=requests.get(u,headers={'Range':'bytes=0-1023'},stream=True,timeout=90);assert res.status_code in (200,206);res.close()
print('Exact master restored, native voice gate passed, Release asset reachable.',flush=True)

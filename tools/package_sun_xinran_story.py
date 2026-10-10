#!/usr/bin/env python3
"""Package an independently reviewed Sun film; never render, upload, or send."""
import argparse,hashlib,json,shutil
from pathlib import Path
from datetime import date
from tennislive.video import explainer as E
from tennislive.render.pushmsg import to_copy_page
SLUG='sun-xinran-coming-of-age-2026'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_audio_segments(narration, script, manifest_dir):
 rows = narration.get('audio_segments') or []
 if len(rows) != 8: raise ValueError('Eight chapter-bound audio_segments required')
 for row, chapter in zip(rows, script['chapters']):
  if row.get('chapter_id') != chapter['id'] or row.get('text') != chapter['narration']:
   raise ValueError('Audio chapter text/identity mismatch')
  path = Path(row['file'])
  if not path.is_absolute(): path = manifest_dir / path
  if not path.is_file() or sha(path) != row.get('audio_sha256'):
   raise ValueError('Actual chapter audio SHA mismatch')
  provenance = Path(row.get('source_manifest_file', ''))
  if not provenance.is_absolute(): provenance = manifest_dir / provenance
  if not provenance.is_file() or sha(provenance) != row.get('source_manifest_sha256'):
   raise ValueError('Actual component manifest SHA mismatch')
  component = json.loads(provenance.read_text())
  entries = component.get('chapters', component.get('audio_segments', []))
  matches = [item for item in entries if item.get('id', item.get('chapter_id')) == chapter['id']]
  if len(matches) != 1: raise ValueError('Component manifest chapter identity mismatch')
  recorded = matches[0]
  if recorded.get('narration', recorded.get('text')) != chapter['narration'] or recorded.get('sha256', recorded.get('audio_sha256')) != row['audio_sha256']:
   raise ValueError('Component manifest chapter text/audio mismatch')
 # Components may legitimately originate in multiple synthesis runs. Never
 # demand one obsolete full-script hash for all eight unchanged/revised files.
 return rows

def native_copy(publication_date):
 from tennislive.render.tournament_story import find_story_by_slug
 from tennislive.render.copy_title import validate_copy_title
 story = find_story_by_slug(SLUG)
 if story is None: raise ValueError('Registered native story required')
 text = E.explainer_xiaohongshu(story, E.explainer_script(story), f'{publication_date.month}.{publication_date.day}')
 validate_copy_title(text.splitlines()[0], require_prefix=True)
 return text

def main():
 p=argparse.ArgumentParser();p.add_argument('--date',default='today');p.add_argument('--movie',type=Path,required=True);p.add_argument('--qa',type=Path,required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--narration',type=Path,required=True);p.add_argument('--script',type=Path,required=True);p.add_argument('--cover',type=Path,required=True);p.add_argument('--video-url',required=True);p.add_argument('--outdir',type=Path,default=Path('output/2026-10-05/explainer')/SLUG);a=p.parse_args()
 q=json.loads(a.qa.read_text());r=json.loads(a.render.read_text());n=json.loads(a.narration.read_text());s=json.loads(a.script.read_text());digest=sha(a.movie);size=a.movie.stat().st_size
 if q.get('status')!='PASS' or q.get('video_sha256')!=digest or q.get('video_bytes')!=size:raise SystemExit('QA must PASS and bind actual movie SHA256/bytes')
 if r.get('video_sha256')!=digest or r.get('video_bytes')!=size:raise SystemExit('Render movie identity mismatch')
 if (r.get('width'),r.get('height'))!=(1080,1440) or not r.get('duration'):raise SystemExit('Actual 1080x1440 duration metadata required')
 if not a.video_url.startswith('https://github.com/') or '/releases/download/' not in a.video_url:raise SystemExit('Actual GitHub Release URL required; packager does not upload')
 if len(s['chapters'])!=8 or n.get('segments')!=8 or not all(n.get(k) for k in ['voice','rate','pitch']):raise SystemExit('Actual eight-segment narration voice/rate/pitch required')
 validate_audio_segments(n,s,a.narration.parent)
 from PIL import Image
 if Image.open(a.cover).size!=(1080,1440):raise SystemExit('Native cover must be1080x1440')
 a.outdir.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.cover,a.outdir/'slide_00.jpg') if a.cover.suffix.lower()=='.jpg' else Image.open(a.cover).convert('RGB').save(a.outdir/'slide_00.jpg',quality=95)
 shutil.copyfile(a.cover,a.outdir/'cover.png');shutil.copyfile(a.qa,a.outdir/'qc.json');r.update(slug=SLUG,video_url=a.video_url,qc='passed',qc_attestation_sha256=sha(a.qa),cover_sha256=sha(a.cover),source_script_sha256=sha(a.script),delivery_status='reviewed_package_not_sent');(a.outdir/'render.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');(a.outdir/'narration.json').write_text(json.dumps(n,ensure_ascii=False,indent=2)+'\n')
 from tennislive.timeutil import parse_date_arg
 publication_date=parse_date_arg(a.date)
 copy=native_copy(publication_date)
 (a.outdir/'copy.txt').write_text(copy+'\n')
 # Existing explainer publication consumes this canonical filename.
 (a.outdir/'xiaohongshu.txt').write_text(copy+'\n')
 (a.outdir/'copy.html').write_text(to_copy_page(copy));seg=E.ExplainerSegment('cover','网球有故事','孙心然的来时路','');(a.outdir/'push.html').write_text(E.explainer_push_html([seg],a.outdir,date=publication_date,xhs_text=copy));print(a.outdir)
if __name__=='__main__':main()

import argparse,hashlib,json,shutil,zipfile,datetime,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('zip');p.add_argument('--artifact-id',required=True);a=p.parse_args()
r=Path('/workspace/jodar-finals-production/final');d=r/'native-inputs';d.mkdir(parents=True,exist_ok=True)
t=Path('/dev/shm/jodar-production/final');t.mkdir(parents=True,exist_ok=True)
z=zipfile.ZipFile(a.zip);meta=json.loads(z.read('render.json'));movie_name='jodar-finals-road-2026.mp4';h=hashlib.sha256()
for member in z.infolist():
 name=Path(member.filename);assert not name.is_absolute() and '..' not in name.parts
 if member.is_dir():continue
 if name.name==movie_name:
  target=t/movie_name
  assert not target.exists(),'Do not overwrite existingactualmaster'
  with z.open(member) as src,target.open('wb') as out:
   while True:
    b=src.read(1048576)
    if not b:break
    h.update(b);out.write(b)
 else:
  assert member.file_size<8*1048576,('unexpectedlargeinput',member.filename,member.file_size)
  target=d/name;target.parent.mkdir(parents=True,exist_ok=True)
  with z.open(member) as src,target.open('wb') as out:shutil.copyfileobj(src,out)
master=t/movie_name;assert h.hexdigest()==meta['film_sha256'] and master.stat().st_size==meta['film_bytes']
link=r/movie_name;assert not link.exists();link.symlink_to(master)
rep={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'artifact_id':a.artifact_id,'zip_sha256':hashlib.sha256(Path(a.zip).read_bytes()).hexdigest(),'zip_bytes':Path(a.zip).stat().st_size,'master':str(master),'workspace_link':str(link),'film_sha256':h.hexdigest(),'bytes':master.stat().st_size,'source_run':'42330488120','spec_sha256':meta['production_sla']['spec_sha256'],'storage':'SingleactualMP4ontmpfs;smallnativeinputsonworkspace;compressedtransportnotsecondMP4copy'}
(r/'artifact-transport-proof.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rep,ensure_ascii=False))

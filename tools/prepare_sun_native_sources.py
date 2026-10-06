#!/usr/bin/env python3
"""Recover actual narration and clean official sources; never publish."""
from pathlib import Path
import os,json,hashlib,base64,zipfile,io,shutil,requests,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tennislive.video.official import OfficialVideoCandidate,fetch_wta_video_metadata
api='https://api.github.com/repos/robertyang87/tennislive';headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}
work=Path(os.environ['SUN_WORKDIR']);work.mkdir(parents=True,exist_ok=True);audio=work/'audio';audio.mkdir(exist_ok=True);sources=work/'sources';sources.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sets={}
for label,aid in [('base',11379888992),('revision',11380482910)]:
    response=requests.get(f'{api}/actions/artifacts/{aid}/zip',headers=headers,timeout=120);response.raise_for_status()
    dest=work/label;dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:archive.extractall(dest)
    manifest=next(dest.rglob('manifest.json'));sets[label]=(dest,json.loads(manifest.read_text()))
locked=[]
for chapter in [f'S{i:02}' for i in range(1,9)]:
    dest,manifest=sets['revision' if chapter in {'S03','S04'} else 'base'];r=next(x for x in manifest['chapters'] if x['id']==chapter)
    for key,digest in [('audio','sha256'),('words','words_sha256')]:
        src=next(dest.rglob(r[key]));assert sha(src)==r[digest];shutil.copyfile(src,audio/r[key])
    locked.append(r)
(audio/'locked-manifest.json').write_text(json.dumps({'chapters':locked,'actual_listening_complete':False},ensure_ascii=False,indent=2))
path='specs/explainers/sun-xinran-coming-of-age-2026.production.json'
r=requests.get(f'{api}/contents/{path}',headers=headers,params={'ref':'e022abb9fdb7b5c4faef43bf72285f0732646ea5'},timeout=60);r.raise_for_status();data=base64.b64decode(r.json()['content']);target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
photos={
 'sun-usopen-trophy.jpg':'https://photoresources.wtatennis.com/photo-resources/2026/09/12/474cba43-9cf4-4e3a-8aad-a15f2992cf5a/Sun-Xinran-US-Open-2026.jpg?width=2400&height=1600',
 'sun-beijing-photo.jpg':'https://photoresources.wtatennis.com/photo-resources/2026/09/29/fb7f9d8e-8bed-40c1-8268-52f23cd9f928/Xinran_Sun_-_China_Open_2026_-_Monday_Qs-DSC_8060.jpg?width=2400&height=1600'}
for name,url in photos.items():
    response=requests.get(url,timeout=60);response.raise_for_status();(sources/name).write_bytes(response.content)
assert sha(sources/'sun-usopen-trophy.jpg')=='a94f7a3771dcfd3cb9f18dddd7e38e5170ccea8476ce1abed91e1d336868673c'
origins={
 'lys':'https://www.wtatennis.com/videos/4585115/junior-no-1-sun-xinran-advances-on-wta-debut-in-beijing-as-lys-retires',
 'bucsa':'https://www.wtatennis.com/videos/4586047/sun-xinran-16-stuns-bucsa-in-beijing-for-first-top-50-win-to-face-gauff-next'}
records=[]
for name,url in origins.items():
    meta=fetch_wta_video_metadata(OfficialVideoCandidate(title=name,url=url));download=meta.fallback_url or meta.playback_url;target=sources/f'source_{name}.mp4'
    if '.m3u8' in download:subprocess.run(['ffmpeg','-y','-v','error','-i',download,'-c','copy',str(target)],check=True)
    else:
        with requests.get(download,stream=True,timeout=(20,180)) as response:
            response.raise_for_status()
            with target.open('wb') as stream:
                for chunk in response.iter_content(1024*1024):stream.write(chunk)
    records.append(dict(source=name,source_url=url,sha256=sha(target),bytes=target.stat().st_size,claimed_official_identity='WTA original identified page',audio_listening_complete=False))
(sources/'sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print('Actual source/audio recovery complete')

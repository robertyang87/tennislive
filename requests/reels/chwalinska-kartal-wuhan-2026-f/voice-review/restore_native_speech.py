"""Restore exact native MP3/marks from the hash-pinned public production ZIP.

No TTS, re-encoding, gain processing, or pronunciation-status mutation occurs.
"""
from pathlib import Path
import argparse,hashlib,io,json,re,urllib.request,zipfile

def sha(value):return hashlib.sha256(value).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--map',type=Path,required=True);p.add_argument('--outdir',type=Path,required=True);p.add_argument('--bundle',type=Path);a=p.parse_args();m=json.loads(a.map.read_text())
    if a.bundle:raw=a.bundle.read_bytes()
    else:
        # Follow public GitHub redirects only in memory; never persist signed URLs.
        with urllib.request.urlopen(m['public_bundle']['url'],timeout=60) as response:raw=response.read(32*1024*1024+1)
    assert len(raw)<=32*1024*1024 and sha(raw)==m['public_bundle']['sha256'],'Bundle size/hash differs; refuse restoration'
    files={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert len(z.namelist())==len(set(z.namelist())),'Duplicate ZIP members'
        manifest=json.loads(z.read('manifest.json'));assert manifest['schema']=='tennislive.frozen-tts-bundle.v1' and manifest['quality_approval'] is False
        assert manifest['implementation']==m['implementation']
        entries={e['request_id']:e for e in manifest['entries']};assert set(entries)=={x['request_id']for x in m['utterances']}
        for item in m['utterances']:
            assert re.fullmatch(r'[A-Za-z0-9_-]+',item['edit_id'])
            entry=entries[item['request_id']];assert entry['request']==item['exact_request']
            for kind in ['audio','marks']:
                f=item[kind];payload=z.read(f['zip_member']);assert sha(payload)==f['sha256']==entry[f['manifest_hash_field']]
                name=f['local_name'];assert name==Path(name).name and name not in files
                files[name]=payload
    # Verify all members before writing any. Existing mismatched files are errors.
    for name,payload in files.items():
        dest=a.outdir/name
        assert not dest.exists() or dest.read_bytes()==payload,f'Existing {name} differs; use a fresh output directory'
    a.outdir.mkdir(parents=True,exist_ok=True)
    for name,payload in files.items():
        dest=a.outdir/name
        if not dest.exists():dest.write_bytes(payload)
    print(json.dumps(dict(bundle_sha256=sha(raw),utterances=len(m['utterances']),exact_native_files=len(files),synthesis_performed=False,pronunciation_status_changed=False),ensure_ascii=False))
if __name__=='__main__':main()

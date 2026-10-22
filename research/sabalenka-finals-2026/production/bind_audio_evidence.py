from pathlib import Path
import hashlib, json, shutil, sys
from datetime import datetime, timezone

REPO=Path('/workspace/tennislive')
ROOT=Path('/workspace/sabalenka-finals-production')
sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')]
import foreground_audio_gate as gate
slug='sabalenka-finals-2026'
spec=json.loads((REPO/'specs/reels'/f'{slug}.json').read_text())
rows=json.loads((ROOT/'research/production/selections.json').read_text())
assert not spec['_render_blockers']
out=REPO/'data/audio_reviews'/slug
raw=out/'raw';raw.mkdir(parents=True,exist_ok=True)
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
entries,sources=[],{}
for index,seg in enumerate(spec['segments']):
    if 'start' not in seg:continue
    row=rows[seg['_id']]
    file=Path(row.get('source_file') or row.get('local_file') or row['source'])
    source_sha=sha(file)
    assert source_sha==row['source_sha256'],seg['_id']
    sources[seg['source']]=file
    packet_path=row.get('audio_review_packet')
    if packet_path:
        p=Path(packet_path)
        if not p.is_absolute():p=REPO/p
        packet=json.loads(p.read_text())
        assert packet['status']=='complete' and not packet.get('uncertain_spans'),seg['_id']
        assert packet['source_url']==spec['sources'][seg['source']],(seg['_id'],packet['source_url'],spec['sources'][seg['source']])
        assert packet['source_sha256']==source_sha,seg['_id']
        assert packet['reviewed_from']<=seg['start'] and packet['reviewed_to']>=seg['end']
        if row.get('translation_edits'):
            packet['source_packet_sha256']=sha(p)
            packet['translation_edits']=row['translation_edits']
            for edit in row['translation_edits']:
                cue=next(c for c in packet['foreground_english'] if c['start']==edit['start'] and c['end']==edit['end'])
                assert cue['zh']==edit['from_zh'] and cue['en']==edit['en']
                cue['zh']=edit['to_zh']
    else:
        assert row.get('method')=='asr_cross_checked'
        packet={'schema':'tennislive.foreground-audio-packet.v1','source_url':spec['sources'][seg['source']],
                'source_sha256':source_sha,'method':'asr_cross_checked',
                'reviewer':'Codex actual source-frame review and paired ASR cross-check; not human listening',
                'reviewed_at':datetime.now(timezone.utc).isoformat(),'reviewed_from':seg['start'],'reviewed_to':seg['end'],
                'status':'complete','uncertain_spans':[],
                'foreground_english':row.get('captions',[]),
                'no_foreground_english_reason':row.get('no_foreground_english_reason',''),
                'review_notes':row.get('notes',row.get('audio_review_notes',''))}
    evidence=row.get('asr_evidence') or packet.get('asr_evidence') or []
    copied=[]
    for item in evidence:
        p=Path(item['path'] if isinstance(item,dict) else item)
        if not p.is_absolute():p=REPO/p
        h=sha(p)
        if isinstance(item,dict) and item.get('sha256'):assert item['sha256']==h
        dest=raw/(seg['_id']+'-'+h[:10]+'-'+p.name)
        shutil.copy2(p,dest)
        copied.append({'path':str(dest.relative_to(REPO)),'sha256':h,
                       'model':item.get('model') if isinstance(item,dict) else 'medium.en' if 'medium' in p.name else 'small.en'})
    assert copied,seg['_id']
    packet['asr_evidence']=copied
    p=out/f'{index:02d}-{seg["_id"]}.json'
    p.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    entries.append({'index':index,'transcript_path':str(p.relative_to(REPO)),'transcript_sha256':sha(p)})
review={'schema':gate.SCHEMA,'plan_sha256':gate.plan_hash(spec),'segments':entries,
        'method_note':'Actual source bytes, paired ASR and source-frame review. No human listening claim.'}
p=REPO/'data/audio_reviews'/f'{slug}.json';p.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
required=gate.require(spec,root=REPO,sources=sources)
print('Bound actual source windows',len(entries),'complete bilingual cues',len(required))
(ROOT/'native-source-paths.json').write_text(json.dumps({k:str(v) for k,v in sources.items()},indent=2)+'\n')

"""Finite review of this episode's actual frozen bundle, with no listening claim.

Run prepare only after final text is frozen. Acoustic ORIG is always the bundle
MP3 with its paired WordBoundary; controls retain the entire spoken sentence.
ASR provides content/segmentation evidence only and never establishes tone.
"""
from pathlib import Path
import argparse, collections, datetime, hashlib, json, os, re, sys, zipfile
from functools import lru_cache

ROOT=Path('/workspace/tennislive')
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
import check_polyphones as cp
import measure_polyphone as mp
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
from tennislive.video.tts import tts_request
from tennislive.video.tts_bundle import read_bundle
from pypinyin import pinyin,Style

NAMES={'赫瓦林斯卡':['he4','wa3','lin2','si1','ka3'],
       '卡尔塔尔':['ka3','er3','ta3','er3'],
       '大坂直美':['da4','ban3','zhi2','mei3'],
       '安德莱斯库':['an1','de2','lai2','si1','ku4'],
       '姆博科':['mu3','bo2','ke1'],
       '武汉':['wu3','han4'],
       '网球时插':['wang3','qiu2','shi2','cha1']}
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
@lru_cache(maxsize=None)
def refs(reading,ch):
    # These provisional independent characters must pass same-sentence LOO.
    extra={'fa1':['発'],'fa4':['珐'],'chang3':['昶','氅'],
           'shi2':['实','时'],'cha1':['插','锸'],'cha4':['岔','诧']}
    if reading in extra:return [c for c in extra[reading] if c!=ch]
    candidates,_=mp.suggest_homophones(reading,exclude=ch,k=8)
    return [c for c in candidates if pinyin(c,style=Style.TONE3,heteronym=True,neutral_tone_with_five=True)[0]==[reading]][:2]

def prepare(args):
    spec=json.loads(args.spec.read_text());assert spec['slug']=='chwalinska-kartal-wuhan-2026-f'
    rows=[]
    if spec.get('cover',{}).get('narration'):rows.append(('cover',spec['cover']['narration'],spec['cover'].get('voice',{})))
    rows.extend((s['_edit_id'],s['narration'],s.get('voice',{})) for s in spec['segments'] if s.get('narration'))
    if spec.get('outro',True):rows.append(('outro',NARRATION,{}))
    expected=[tts_request(speakable(text),v.get('voice','zh-CN-YunjianNeural'),v.get('rate','+6%'),v.get('pitch','+0Hz'),v.get('style',''),v.get('styledegree',''),v.get('lead_pause',0.0),backend='edge') for _,text,v in rows]
    # Existing verifier checks full exact request set, implementation, member
    # hashes, duration and decode usability. No loudness or silence check.
    read_bundle(args.bundle,expected_requests=expected,decode_audio=True)
    with zipfile.ZipFile(args.bundle) as z:
        manifest=json.loads(z.read('manifest.json'));assert manifest['artifact_kind']=='native_tts_inputs'
        entries=manifest['entries'];assert len(rows)==len(entries)
        bindings=[]
        for edit_id,display,v in rows:
            text=speakable(display);voice=v.get('voice','zh-CN-YunjianNeural');rate=v.get('rate','+6%');pitch=v.get('pitch','+0Hz')
            matches=[e for e in entries if e['request']['text']==text and e['request']['voice']==voice and e['request']['rate']==rate and e['request']['pitch']==pitch]
            assert len(matches)==1,(edit_id,len(matches));e=matches[0];r=e['request']
            assert r['backend']=='edge' and not r['style'] and not r['styledegree'] and not r['lead_pause'] and pitch=='+0Hz'
            rid=e['request_id'];mp3=z.read(f'requests/{rid}/audio.mp3');marks=z.read(f'requests/{rid}/marks.json')
            assert sha(mp3)==e['audio_sha256'] and sha(marks)==e['marks_sha256']
            p=args.out/'native-speech'/f'{edit_id}.mp3';p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(mp3);m=p.with_suffix('.marks.json');m.write_bytes(marks)
            bindings.append(dict(edit_id=edit_id,text=text,display_text=display,voice=voice,rate=rate,pitch=pitch,request_id=rid,actual_mp3_sha256=sha(mp3),actual_marks_sha256=sha(marks),bound_snapshot_path=str(p),marks_snapshot_path=str(m),word_boundary_tokens=[x['text'] for x in json.loads(marks)]))
    targets=[];coverage=[];unknown=[]
    for b in bindings:
        assert '月亮姐' not in b['display_text'], 'Owner forbids nickname in this episode'
    owner_reuse=None
    for b in bindings:
        if b['edit_id']!='outro':continue
        assessment=json.loads((Path(__file__).parent/'brand-reuse-assessment.json').read_text())
        if (b['text']==assessment['exact_request']['text'] and b['voice']==assessment['exact_request']['voice'] and b['rate']==assessment['exact_request']['rate'] and b['pitch']==assessment['exact_request']['pitch'] and b['request_id']==assessment['request_id'] and b['actual_mp3_sha256']==assessment['mp3_sha256'] and b['actual_marks_sha256']==assessment['marks_sha256']):
            owner_path=ROOT/assessment['owner_review_path'];assert sha(owner_path.read_bytes())==assessment['owner_review_sha256']
            owner_reuse=dict(edit_id='outro',status='exact_complete_sentence_owner_confirmation_reused',reviewer=assessment['reviewer'],reply_verbatim=assessment['owner_reply_verbatim'],reviewed_at=assessment['owner_reviewed_at'],source=assessment['owner_review_path'],owner_review_sha256=assessment['owner_review_sha256'],request_id=b['request_id'],actual_mp3_sha256=b['actual_mp3_sha256'],actual_marks_sha256=b['actual_marks_sha256'],assistant_listening_claimed=False)

    for b in bindings:
        text=b['text'];readings,words,*_=cp._readings(text)
        for mt in re.finditer('首冠',text):readings[mt.start()+1]='guan4'
        for name,rs in NAMES.items():
            for mt in re.finditer(re.escape(name),text):
                for j,rd in enumerate(rs):readings[mt.start()+j]=rd
        c=dict(edit_id=b['edit_id'],text=text,polyphones=[],names=[],numbers=[],letters=[],actual_word_boundary_tokens=b['word_boundary_tokens'])
        for name,rs in NAMES.items():
            for mt in re.finditer(re.escape(name),text):c['names'].append(dict(name=name,at=mt.start(),declared_readings=rs,status='pending_actual_content_and_segmentation_ASR_not_tone'))
        c['numbers']=[dict(text=m.group(),at=m.start(),status='pending_actual_content_ASR_not_tone') for m in re.finditer(r'[零一二三四五六七八九十百千万两〇\d]+',text)]
        c['letters']=[dict(text=m.group(),at=m.start(),status='pending_actual_content_ASR') for m in re.finditer(r'[A-Za-z]+',text)]
        for i,ch in enumerate(text):
            yes,defaults,live=cp.poly_info(ch)
            if not yes:continue
            intended=readings[i]
            if ch=='为' and text[max(0,i-2):i+3].endswith('为首盘'):intended='wei4'
            p=dict(at=i,char=ch,word=words[i],declared_intended=intended,live_readings=live)
            c['polyphones'].append(p)
            if b['edit_id']=='outro' and owner_reuse:
                p['actual_sentence_review']='covered_by_exact_complete_sentence_owner_confirmation';continue
            for wrong in live:
                if wrong==intended:continue
                A,B=refs(intended,ch),refs(wrong,ch)
                t=dict(edit_id=b['edit_id'],sentence=text,word=ch,char=ch,at=i,intended=intended,wrong=wrong,ok_refs=A,bad_refs=B,actual_binding=b,kind='common_polyphone',reference_policy='Provisional nonoriginal independent homophones, same-full-sentence LOO calibration required; no dictionary verdict.')
                if not A or not B:unknown.append({**t,'status':'unknown_no_valid_reference'})
                else:targets.append(t)
        # Brand speakable uses 插 instead of 差; no historical sentence verdict.
        if b['edit_id']=='outro' and not owner_reuse:
            for i,ch in enumerate(text):
                if ch=='插':targets.append(dict(edit_id=b['edit_id'],sentence=text,word=ch,char=ch,at=i,intended='cha1',wrong='cha4',ok_refs=['锸','艖'],bad_refs=['岔','诧'],actual_binding=b,kind='brand_homophone',reference_policy='fresh full-sentence single-reading controls; rare controls require self-calibration'))
        coverage.append(c)
    scope=dict(schema='tennislive.finite-frozen-speech-review.v1',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),slug=spec['slug'],bundle_path=str(args.bundle),bundle_sha256=sha(args.bundle.read_bytes()),spec_sha256=sha(args.spec.read_bytes()),bindings=bindings,coverage=coverage,targets=targets,unknown_no_valid_reference=unknown,owner_confirmation_reuse=owner_reuse,human_listening_claimed=False,pronunciation_pass_claimed=False,method='Actual frozen bundle MP3 and native WordBoundary bind ORIG; same-full-sentence MFCC+F0 controlled comparisons with LOO calibration. ASR for content only. No historic episode result is reused.')
    write(args.out/'job.json',scope);print(json.dumps(dict(bundle_sha256=scope['bundle_sha256'],utterances=len(bindings),acoustic_targets=len(targets),unknown_no_valid_reference=len(unknown)),ensure_ascii=False))

def target(args):
    j=json.loads((args.out/'job.json').read_text());t=j['targets'][args.index];b=t['actual_binding'];original=mp.synth
    # One-control sides cannot provide the requested two-sided leave-one-out
    # calibration. Do not spend synthesis calls to obtain a predictable low.
    if min(len(t['ok_refs']),len(t['bad_refs']))<2:
        t['acoustic']=dict(verdict='insufficient_controls',acoustic_measurement_attempted=False,why='Fewer than two independent same-reading controls on a side; no new synthesis or acoustic pass claimed.')
        t['recorded_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();t['human_listening_claimed']=False
        write(args.out/'targets'/f'{args.index:03}.json',t)
        print(json.dumps(dict(index=args.index,edit_id=t['edit_id'],char=t['char'],verdict='insufficient_controls',measurement_attempted=False),ensure_ascii=False),flush=True);return
    def bound(text,voice,rate,pitch='+0Hz'):
        if (text,voice,rate,pitch)==(b['text'],b['voice'],b['rate'],b['pitch']):
            p=Path(b['bound_snapshot_path']);m=Path(b['marks_snapshot_path']);assert sha(p.read_bytes())==b['actual_mp3_sha256'] and sha(m.read_bytes())==b['actual_marks_sha256'];return p,json.loads(m.read_text())
        import fcntl
        locks=args.out/'reference-locks';locks.mkdir(exist_ok=True)
        key=sha('\x1f'.join([text,voice,rate,pitch]).encode())
        with (locks/(key+'.lock')).open('a') as fh:
            fcntl.flock(fh,fcntl.LOCK_EX)
            return original(text,voice,rate,pitch)
    mp.synth=bound
    try:r=mp.measure(t['word'],t['sentence'],t['ok_refs'],t['bad_refs'],b['voice'],b['rate'],char=t['char'],at=t['at']);r['acoustic_measurement_attempted']=True
    except Exception as e:r=dict(verdict='error',why=f'{type(e).__name__}: {e}')
    t['acoustic']=r;t['measured_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();t['human_listening_claimed']=False
    write(args.out/'targets'/f'{args.index:03}.json',t)
    print(json.dumps(dict(index=args.index,edit_id=t['edit_id'],char=t['char'],intended=t['intended'],wrong=t['wrong'],verdict=r['verdict'],confidence=r.get('confidence'),score=r.get('score')),ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','target']);p.add_argument('--bundle',type=Path);p.add_argument('--spec',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--index',type=int);a=p.parse_args()
    prepare(a) if a.stage=='prepare' else target(a)

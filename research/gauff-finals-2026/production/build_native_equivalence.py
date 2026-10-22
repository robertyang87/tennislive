from pathlib import Path
import json,hashlib,datetime
R=Path('/workspace/gauff-finals-production');W=Path('/workspace/tennislive-gauff');oldp=R/'production/native-baseline-spec.json';newp=W/'specs/reels/gauff-finals-2026.json';old=json.load(open(oldp));new=json.load(open(newp))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def starts(d):
 c=1.2;z=[]
 for x in d['segments']:z.append(c);c+=x.get('seconds',x.get('end',0)-x.get('start',0))
 return z
os=starts(old);ns=starts(new);diff=[]
for i,(a,b)in enumerate(zip(old['segments'],new['segments'])):
 ds={k:{'baseline':a.get(k),'current':b.get(k)}for k in a.keys()|b.keys()if a.get(k)!=b.get(k)}
 if ds:diff.append({'index':i,'id':b['_id'],'changed_fields':ds})
def active(s,t):
 dt=t-s['start'];q=[x['text']for x in s.get('quote',[])if x['at']<=dt<x['end']];z=s.get('inset');l=z and z['show_after']<=dt<z['show_after']+z['show_for'];return {'quote':q,'label':{k:z[k]for k in ['image','kind','corner','width','pad','label']}if l else None}
rows=[];mrefs=[]
for j in range(1,5):
 mp=R/f'production/native-preview-batch-{j}/preview_manifest.json';m=json.load(open(mp));assert m['spec_file_sha256']==sha(oldp);mrefs.append({'path':str(mp),'sha256':sha(mp),'input_spec_sha256':m['spec_file_sha256']})
 for s in m['samples']:
  i=s['segment'];a=old['segments'][i];b=new['segments'][i];t=s.get('source_time');p=mp.parent/s['image'];assert sha(p)==s['image_sha256'];reason=None
  if t is not None:
   if not b['start']<=t<b['end']:reason='source time omitted from current window'
   elif active(a,t)!=active(b,t):reason='caption onset corrected; old active caption no longer current'
   for k in ['cx','cx_face','frame','fit','track','source']:
    assert a.get(k)==b.get(k),(i,k)
   nf=ns[i]+t-b['start']
  else:
   if a!=b:reason='closing narration/duration changed; replaced by actual current native focused samples'
   nf=ns[i]+s['segment_time']
  rows.append({'baseline_manifest':str(mp),'baseline_manifest_sha256':sha(mp),'image':str(p),'image_sha256':sha(p),'segment':i,'id':b['_id'],'source_time':t,'baseline_film_time':s['film_time'],'current_mapped_film_time':nf,'status':'superseded'if reason else 'source_time_rendering_equivalent','reason':reason or 'Same actual source SHA/still, same fixed crop geometry and active native bilingual caption/transparent label at mapped source clock; film-time shift is explicitly mapped. This is source-time preview equivalence, not new encoding or final-film QC.'})
out={'schema':'gauff-native-source-time-equivalence/v1','generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_spec_sha256':sha(oldp),'current_spec_sha256':sha(newp),'baseline_manifests':mrefs,'changed_segment_fields':diff,'sample_count':len(rows),'retained_equivalent':sum(x['status']=='source_time_rendering_equivalent'for x in rows),'superseded':sum(x['status']=='superseded'for x in rows),'samples':rows,'final_film_qc':False,'human_listened':False};(R/'production/native-current-equivalence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('spec',sha(newp),'equivalent',out['retained_equivalent'],'superseded',out['superseded']);print([(x['index'],list(x['changed_fields']))for x in diff])

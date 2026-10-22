exec(open('/workspace/noskova-finals-production/production/measure_interviews.py').read().split('model=F.load')[0])
model=F.load(fetch=True);src=R/'sources/wimbledon-dinner.mp4';out=[]
for key,a,b in [('cold-mother',133.7,138.12),('mother-full',133.7,149.42)]:
 xs=[];samples=[];ims=[]
 for i in range(9):
  t=a+.3+(b-a-.6)*i/8;im=_frame(src,t);faces=model.detect(F.read_bgr(im));candidates=[f for f in faces if (float(f.bbox[0])+float(f.bbox[2]))/2/im.width<.5];assert candidates,'No detected Linda on actual left side';face=max(candidates,key=lambda f:(f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]));box=[float(x)for x in face.bbox[:4]];x=(box[0]+box[2])/2/im.width;xs.append(round(x,4));samples.append({'time':round(t,3),'bbox':box,'face_cx':round(x,4),'all_face_centers':[round((float(f.bbox[0])+float(f.bbox[2]))/2/im.width,4)for f in faces]});ims.append(im)
 w,h=ims[0].size;cx=person_center_cx(min(xs),max(xs),w,h);ev={'samples':xs,'frames':9,'detected':9,'source_size':[w,h],'measured_with':'insightface buffalo_s; identity-aware detected Linda on left, not generic largest face (which was host on right)','median':sorted(xs)[4],'spread':round(max(xs)-min(xs),4),'measurements':samples}
 co=Image.new('RGB',(810,1146),'#111');d=ImageDraw.Draw(co)
 for i,im in enumerate(ims):
  cropw=h*.75;left=round(cx*w-cropw/2);im=im.crop((left,0,left+round(cropw),h));im.thumbnail((270,360));x=i%3*270;y=i//3*382;co.paste(im,(x,y));d.text((x+3,y+362),f'{key} {samples[i]["time"]:.3f} cx={cx}',fill='white')
 cp=R/'production/visual'/f'{key}-person9.jpg';co.save(cp,quality=94);out.append({'key':key,'source_name':'wimbledon-dinner','start':a,'end':b,'frame':'person','cx':cx,'cx_face':ev,'contact':str(cp),'face_identity_review':'9 actual identity-aware samples, contact needs actual visual check; earlier largest-face host measurements rejected'})
(R/'production/interview-centers.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print([(x['key'],x['cx'])for x in out],flush=True)

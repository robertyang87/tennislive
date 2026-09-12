from pathlib import Path
import argparse, json, subprocess, os, sys, html, wave, shutil, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
TAG='hewitt-911-25-wawrinka-style-20260912'
REPO='robertyang87/tennislive'
REL=f'https://github.com/{REPO}/releases/download/{TAG}'
COPY='https://robertyang87.github.io/tennislive/output/2026-09-12/explainer/hewitt-911-25/copy.html'
TITLE='🎾9.12 网球有故事｜休伊特的纽约告别'
TEXT='''🎾9.12 网球有故事｜休伊特的纽约告别

🏆20岁，刚刚捧起人生第一座大满贯单打奖杯。
第二天，他抱着奖杯走在纽约街头，随后飞回澳大利亚。
再后来，世界变了。

九一一25周年，重看休伊特2001年的美网之旅。

决赛对面是连过拉夫特、阿加西和萨芬的桑普拉斯。休伊特拿下首盘抢七，随后连赢两个6比1，第一次成为大满贯单打冠军。

📸关于这次冠军拍照，网上流传着“原定9月11日去世贸中心，为戴维斯杯提前一天，因此逃过一劫”的说法。
但参与安排者的回忆，指向的是9月10日、星期一的计划。取消原因有不同版本，日期却不能被悄悄改成11日。

✈️可以确认的是：休伊特回忆，自己在10日下午5点离开纽约，经洛杉矶回悉尼，准备对瑞典的戴维斯杯半决赛。
袭击发生时，他正在返澳。落地后，准备好的庆祝发布会取消了。他牵挂的，是仍留在曼哈顿的朋友是否平安。

后来，他成为世界第一，又拿下温网冠军。但这座美网奖杯，从此连接着竞技之外的记忆。

二十五年后，记住他的幸运，也记住那一天失去生命的人。

#网球时差 #网球有故事 #休伊特 #美网 #九一一25周年'''

def run(cmd,**kw):return subprocess.run(cmd,check=True,**kw)

def prepare(out):
    import numpy as np
    ds=[float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)])) for p in sorted(out.glob('voice_*.mp3'))]
    sr=24000;total=sum(ds)+10;x=np.zeros(int(total*sr),dtype=np.float32)
    chords=[[52,59,64,67],[48,55,60,64],[43,55,59,62],[50,57,62,66]]
    for j,start in enumerate(np.arange(0,total,10)):
        duration=min(13,total-start);t=np.arange(int(duration*sr))/sr;env=np.minimum(t/2,1)*np.minimum((duration-t)/4,1);tone=np.zeros(len(t))
        for n in chords[j%4]:
            f=440*2**((n-69)/12);tone+=(np.sin(2*np.pi*f*t)+.15*np.sin(2*np.pi*f*2*t))*.08
        x[int(start*sr):int(start*sr)+len(t)]+=(tone*env).astype(np.float32)
    for j,start in enumerate(np.arange(3,total-5,7.5)):
        n=[76,71,74,67,72,71,69,74][j%8];t=np.arange(int(5*sr))/sr;f=440*2**((n-69)/12)
        tone=(np.sin(2*np.pi*f*t)+.2*np.sin(2*np.pi*2*f*t))*np.exp(-t/1.4)*(1-np.exp(-t/.03))*.12
        x[int(start*sr):int(start*sr)+len(t)]+=tone.astype(np.float32)
    x*=10**(-34/20)/max(float(np.sqrt(np.mean(x*x))),1e-8);x[:sr*2]*=np.linspace(0,1,sr*2);x[-sr*5:]*=np.linspace(1,0,sr*5)
    with wave.open(str(out/'music.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((np.clip(x,-1,1)*32767).astype('<i2').tobytes())
    run(['ffmpeg','-v','error','-y','-i',str(out/'hewitt-911-25-dry.mp4'),'-i',str(out/'music.wav'),'-filter_complex','[0:a]loudnorm=I=-16:TP=-1.5:LRA=8[voice];[voice][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','128k','-ar','48000','-movflags','+faststart',str(out/'hewitt-911-25.mp4')])
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out/'hewitt-911-25.mp4')]))
    assert abs(float(probe['format']['duration']) - (sum(ds)+6.222)) < 0.5
    v=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height']) == (1080,1920)
    assert len(list(out.glob('slide_*.jpg')))==15
    assert '九一一事件' in (out/'sub_00.ass').read_text()
    shutil.copy(out/'slide_00.jpg',out/'cover.jpg')
    (out/'xiaohongshu.txt').write_text(TEXT)
    from tennislive.render.pushmsg import to_copy_page
    (out/'copy.html').write_text(to_copy_page(TEXT))
    with zipfile.ZipFile(out/'hewitt-911-25-cards.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.glob('slide_*.jpg')):z.write(p,p.name)
        z.write(ROOT/'assets/explainer/hewitt-911-25/sources.json','sources.json')
        z.write(ROOT/'specs/explainers/hewitt-911-25.json','script.json')
    (out/'qc.json').write_text(json.dumps({'status':'passed','duration':probe['format']['duration'],'photos':15,'style_reference':'wawrinka-wildcard 2026-08-27','audience_copy_reviewed':True,'width':1080,'height':1920},ensure_ascii=False))

def push_once(out):
    from tennislive.publish.pushplus import push
    # Persist an intent before the irreversible POST. Uncertain calls are never retried.
    rel=json.loads(subprocess.check_output(['gh','release','view',TAG,'--repo',REPO,'--json','assets']))
    if any(a['name'] in {'push-intent.json','push-receipt.json'} for a in rel['assets']):
        raise SystemExit('Existing delivery attempt: refusing duplicate POST; inspect receipt.')
    rev=os.environ['GITHUB_SHA'];os.environ['TENNISLIVE_ASSET_REV']=rev
    img=f'https://cdn.jsdelivr.net/gh/{REPO}@{rev}/output/2026-09-12/explainer/hewitt-911-25/cover.jpg'
    import requests,time
    for attempt in range(30):
        r=requests.get(COPY,timeout=20)
        if r.status_code==200 and html.escape(TITLE) in r.text:break
        time.sleep(10)
    else:raise RuntimeError('Copy page unavailable; no message sent')
    body='<div style="font-size:16px;line-height:1.8"><h2>'+html.escape(TITLE)+'</h2><img style="width:100%" src="'+img+'"><p><a href="'+REL+'/hewitt-911-25.mp4">▶ 观看 / 下载视频</a>　<a href="'+COPY+'">复制发布文案</a></p><p><a href="'+REL+'/hewitt-911-25-cards.zip">下载15页图卡</a></p>'+''.join('<p>'+html.escape(p)+'</p>' for p in TEXT.split('\n\n')[1:])+'</div>'
    from tennislive.publish.pushplus import prepare_image_delivery,wait_for_images
    body,_=prepare_image_delivery(body,asset_dir=out,token=os.environ['PUSHPLUS_TOKEN']);wait_for_images(body)
    intent={'status':'attempting','run_id':os.environ.get('GITHUB_RUN_ID'),'title':TITLE}
    (out/'push-intent.json').write_text(json.dumps(intent,ensure_ascii=False))
    run(['gh','release','upload',TAG,str(out/'push-intent.json'),'--repo',REPO])
    receipt=push(TITLE,body,asset_dir=out)
    (out/'push-receipt.json').write_text(json.dumps({'status':'accepted','channel':'wechat','receipt':receipt,'run_id':os.environ.get('GITHUB_RUN_ID'),'title':TITLE},ensure_ascii=False))
    run(['gh','release','upload',TAG,str(out/'push-receipt.json'),'--repo',REPO])
    print('WECHAT_ACCEPTED',receipt,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['prepare','push']);ap.add_argument('--outdir',type=Path,required=True);a=ap.parse_args()
    (prepare if a.stage=='prepare' else push_once)(a.outdir)

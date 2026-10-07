import sys,pathlib,json,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import measure_polyphone as mp
out=ROOT/'research/vacherot-acoustic/cover-candidate';out.mkdir(exist_ok=True)
text='险些无缘资格赛。他却拿走上海冠军。'
p,marks=mp.synth(text,'zh-CN-YunjianNeural','+6%');shutil.copy2(p,out/'speech.mp3')
results=[]
for ch,reading,other in [('格','ge2','ge1'),('冠','guan4','guan1')]:
 ok,_=mp.suggest_homophones(reading,exclude=ch,k=3);bad,_=mp.suggest_homophones(other,exclude=ch,k=3)
 results.append(mp.measure(ch,text,ok,bad,'zh-CN-YunjianNeural','+6%',char=ch,at=text.index(ch)))
obj={'text':text,'voice':'zh-CN-YunjianNeural','rate':'+6%','audio':str(out/'speech.mp3'),'marks':marks,'measurement':results,'approval':'not approved; generated alternative for review, full spoken-listening not performed'}
(out/'candidate.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
print([(x['char'],x['verdict'],x['score']) for x in results])

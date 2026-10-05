import json,sys,hashlib,re
from pathlib import Path
root=Path('/workspace/tennislive');f=Path(__file__).parent;p=f/'commentary-inventory.json';d=json.loads(p.read_text())
if 'sentence_groups' not in d:d['sentence_groups']=[dict(r) for r in d['foreground_english']]
old=d['sentence_groups']
parts={
8:[(81.64,84.0,'Dip below sixty degrees Fahrenheit,','气温降到华氏六十度以下'),(84.5,85.62,'low teens Celsius.','也就是摄氏十几度')],
13:[(136.88,139.86,'And Sun is back on the lettering on the court.','孙心然又退到场上字母标志处')],
17:[(194.26,196.24,'And Coco Gauff back out in front','科科·高芙再度领先'),(196.24,197.82,'for the first time in forty minutes,','这是四十分钟来的第一次'),(197.82,199.9,'and she’s got triple set point.','她拿到了三个盘点')],
20:[(205.66,208.2,'The shoulders have fallen for Sun Xinran,','孙心然垂下了肩膀'),(208.2,211.68,'because Coco Gauff finds a way to earn the opening set.','因为科科·高芙设法拿下首盘')],
21:[(211.84,213.64,'It wasn’t easy, but she gets it done','并不容易，但她还是拿下首盘'),(213.64,214.68,'in just short of an hour.','用时不到一小时')],
24:[(243.34,244.4,'Coco, relentless.','科科毫不松懈'),(244.94,246.6,'She loves the middle of the court today.','今天她很喜欢利用场地中路')],
25:[(266.56,269.94,'And Coco Gauff continues to refuse to lose','科科·高芙仍保持不败'),(269.94,272.14,'before the semifinals in Beijing.','在北京的半决赛之前')],
26:[(276.24,277.14,'Well, on paper','从纸面实力看'),(277.14,278.75,'it looked like it was going to be a beatdown.','本该是一场悬殊的较量')],
27:[(279.04,280.18,'Number four in the world','世界第四'),(280.18,281.54,'versus five eighty-two.','对阵世界第五百八十二')],
28:[(281.74,284.12,'The opening set was more competitive','首盘的激烈程度'),(284.12,285.49,'than anyone could have imagined.','超出了所有人的想象')],
29:[(285.54,287.24,'But in the end, it’s Coco Gauff','但最终，是科科·高芙'),(287.24,288.60,'who strikes a commanding pose','展现出了压倒性的优势'),(288.60,290.38,'in the second set,','在第二盘'),(290.38,291.62,'as she runs away with it.','一路拉开了差距')],
30:[(291.62,294.22,'And now she finds her way to the round of sixteen','现在她晋级十六强'),(294.22,295.88,'at this WTA one thousand event','在这站 WTA 一千赛'),(295.88,298.74,'with a seven-five, six-one win.','以七比五、六比一获胜')],
}
rows=[]
for r in old:
 if r['id'] not in parts:rows.append(dict(r));continue
 cuts=parts[r['id']]
 norm=lambda s:re.sub(r'[^A-Za-z0-9]','',s).lower()
 assert norm(' '.join(x[2] for x in cuts))==norm(r['en']),(r['id'],r['en'])
 for n,(a,b,en,zh) in enumerate(cuts):
  v=dict(r);v.update(id=f'{r["id"]}.{n+1}',sentence_group=r['id'],start=a,end=b,en=en,zh=zh)
  rows.append(v)
d['foreground_english']=rows
d['notes'].append('Bilingual display cues split at inspected ASR word/phrase boundaries to fit one Chinese line. Normalized English concatenation of each split group is asserted equal to the original complete sentence; sentence_groups preserves the source sentence evidence, and edit windows still retain the whole sentence.')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print('Inventory split clauses',len(rows))

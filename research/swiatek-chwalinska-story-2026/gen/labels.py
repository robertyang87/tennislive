import json,sys
sys.path.insert(0,'tools')
from render_story_info_band import render_label, label_fields_problem
A='assets/reel/swiatek-chwalinska'
LABELS={
 "jfc16":{"topic":"一起捧起团体冠军","date":"2016.10.02","place":"青少年联合会杯 决赛","people":"波兰 vs 美国","event":"波兰夺冠"},
 "wb18":{"topic":"温网青少年冠军","date":"2018.07.15","place":"温网 青少年女单决赛","people":"斯瓦泰克 vs 屈恩","score":"6-4 6-2"},
 "wb25":{"topic":"第6座大满贯","date":"2025.07.12","place":"温网 决赛","people":"斯瓦泰克 vs 阿尼西莫娃","score":"6-0 6-0"},
 "rgqf":{"topic":"首进大满贯四强","date":"2026.06.03","place":"法网 1/4决赛","people":"赫瓦林斯卡 vs 卡林斯卡娅","score":"7-6(3) 6-3"},
 "rg20":{"topic":"第一座大满贯","date":"2020.10.10","place":"法网 决赛","people":"斯瓦泰克 vs 肯宁","score":"6-4 6-1"},
 "rgsf":{"topic":"资格赛打进决赛","date":"2026.06.04","place":"法网 半决赛","people":"赫瓦林斯卡 vs 施奈德","event":"法网历史第一人"},
 "wuhm":{"topic":"首进1000赛四强","date":"2026.10.16","place":"WTA1000 武汉 1/4决赛","people":"赫瓦林斯卡 vs 萨卡里","score":"6-0 3-6 7-5"},
 "wuhs":{"topic":"10站1000赛都进过四强","date":"2026.10.16","place":"WTA1000 武汉 1/4决赛","people":"斯瓦泰克 vs 李吉妮","score":"6-4 6-1"},
}
if __name__=="__main__":
    for k,l in LABELS.items():
        p=label_fields_problem(l)
        if p: print(k,p); continue
        render_label(l, __import__('pathlib').Path(f"{A}/label-{k}.png")); print('ok',k)
    json.dump(LABELS,open('research/swiatek-chwalinska-story-2026/gen/labels.json','w'),ensure_ascii=False,indent=1)

import json,sys
sys.path.insert(0,'tools')
from render_story_info_band import render_label, label_fields_problem
A='assets/reel/kartal-story'
LABELS={
 "wb24":{"topic":"资格赛打进第三轮","date":"2024.07.05","place":"温网 第三轮","people":"卡尔塔尔 vs 高芙","event":"27年来英国第一人"},
 "iw":{"topic":"伤前最后一胜","date":"2026.03.09","place":"WTA1000 印第安维尔斯","people":"卡尔塔尔 vs 凯斯","score":"2-6 6-2 6-3"},
 "qf":{"topic":"首进1000赛四强","date":"2026.10.16","place":"WTA1000 武汉 1/4决赛","people":"卡尔塔尔 vs 斯维托丽娜","score":"6-2 2-6 6-4"},
 "sf":{"topic":"救下6个盘点","date":"2026.10.17","place":"WTA1000 武汉 半决赛","people":"卡尔塔尔 vs 奥斯塔彭科","score":"7-6(9) 7-6(5)"},
}
if __name__=="__main__":
    import pathlib; pathlib.Path(A).mkdir(parents=True,exist_ok=True)
    for k,l in LABELS.items():
        p=label_fields_problem(l)
        if p: print(k,p); continue
        render_label(l, pathlib.Path(f"{A}/label-{k}.png")); print('ok',k)
    json.dump(LABELS,open('research/kartal-story-2026/gen/labels.json','w'),ensure_ascii=False,indent=1)

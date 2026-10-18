import json,sys
sys.path.insert(0,'tools')
from render_story_info_band import render_label, label_fields_problem
A='assets/reel/fokina-story'
LABELS={
 "mcd":{"topic":"破德约9次发球局","date":"2022.04.12","place":"ATP1000 蒙特卡洛 第二轮","people":"福基纳 vs 德约科维奇","score":"6-3 6-7(5) 6-1"},
 "mcf":{"topic":"生涯第一个决赛","date":"2022.04.17","place":"ATP1000 蒙特卡洛 决赛","people":"福基纳 vs 西西帕斯","score":"3-6 6-7(3)"},
 "dr":{"topic":"握到2个冠军点","date":"2025.02.16","place":"ATP250 德尔雷海滩 决赛","people":"福基纳 vs 凯茨马诺维奇","score":"6-3 1-6 5-7"},
 "ac":{"topic":"第3次亚军","date":"2025.03.01","place":"ATP500 阿卡普尔科 决赛","people":"福基纳 vs 马哈奇","score":"6-7(6) 2-6"},
 "wa":{"topic":"3个冠军点被救","date":"2025.07.27","place":"ATP500 华盛顿 决赛","people":"福基纳 vs 德米纳尔","score":"7-5 1-6 6-7(3)"},
 "bs":{"topic":"第5次亚军","date":"2025.10.26","place":"ATP500 巴塞尔 决赛","people":"福基纳 vs 丰塞卡","score":"3-6 4-6"},
 "ml":{"topic":"第6次决赛 终于夺冠","date":"2026.06.27","place":"ATP250 马略卡 决赛","people":"福基纳 vs 奎因","score":"7-6(4) 6-3"},
 "wb":{"topic":"五盘之后网前争执","date":"2026.07.05","place":"温网 第四轮","people":"福基纳 vs 阿利亚西姆","event":"五盘负"},
 "cdr":{"topic":"停赛两个多月后复出","date":"2026.09.26","place":"ATP250 成都 第二轮","people":"福基纳 vs 胡安·塞伦多洛","score":"6-4 6-4"},
 "cdf":{"topic":"复出就夺冠","date":"2026.09.29","place":"ATP250 成都 决赛","people":"福基纳 vs 胡尔卡奇","score":"6-4 7-6(7)"},
 "sh3":{"topic":"救下赛点","date":"2026.10.11","place":"ATP1000 上海 第三轮","people":"福基纳 vs 蒂亚福","score":"7-6(4) 4-6 7-6(6)"},
 "sh4":{"topic":"又是决胜盘抢七","date":"2026.10.13","place":"ATP1000 上海 第四轮","people":"福基纳 vs 胡尔卡奇","score":"1-6 6-3 7-6(6)"},
 "sf":{"topic":"逆转头号种子","date":"2026.10.17","place":"ATP1000 上海 半决赛","people":"福基纳 vs 兹维列夫","score":"5-7 6-4 6-3"},
}
if __name__=="__main__":
    import pathlib; pathlib.Path(A).mkdir(parents=True,exist_ok=True)
    for k,l in LABELS.items():
        p=label_fields_problem(l)
        if p: print(k,p); continue
        render_label(l, pathlib.Path(f"{A}/label-{k}.png")); print('ok',k)
    json.dump(LABELS,open('research/fokina-story-2026/gen/labels.json','w'),ensure_ascii=False,indent=1)

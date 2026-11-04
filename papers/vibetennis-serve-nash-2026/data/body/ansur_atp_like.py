"""ATP 球员体型的比例来源：ANSUR II（2012 美军人体测量，男性公开数据 4,082 人）。
数据：https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv（Penn State OpenLab 转存；原始发布 Army Public Health Center）。
子集：身高 1.83–1.98 m、BMI 20–24、35 岁以下——ATP 前列球员的典型身形；结果 98 人，平均 1.87 m／78 kg。
各部位除以身高取均值，写进 atp_like.json；players.js 的 HUMAN／LEN／BUILD 按它定，模型量出来的比例在 model_measured.json。

    python3 ansur_atp_like.py ANSUR_II_MALE_Public.csv
"""
import csv, json, statistics as st, sys
R = list(csv.DictReader(open(sys.argv[1], encoding='latin-1')))
f = lambda r, k: float(r[k])
S = [r for r in R if 1830 <= f(r, 'stature') <= 1980 and 20 <= (f(r, 'weightkg') / 10) / (f(r, 'stature') / 1000) ** 2 <= 24 and int(r['Age']) <= 35]
keys = ['acromialheight', 'cervicaleheight', 'chestheight', 'waistheightomphalion', 'iliocristaleheight', 'trochanterionheight', 'crotchheight',
        'kneeheightmidpatella', 'lateralmalleolusheight', 'biacromialbreadth', 'bideltoidbreadth', 'chestbreadth', 'chestdepth', 'waistbreadth',
        'waistdepth', 'hipbreadth', 'buttockdepth', 'acromionradialelength', 'radialestylionlength', 'handlength', 'headbreadth', 'headlength',
        'tragiontopofhead', 'mentonsellionlength', 'span', 'thighcircumference', 'calfcircumference', 'bicepscircumferenceflexed',
        'forearmcircumferenceflexed', 'neckcircumference']
out = {k: round(st.mean(f(r, k) / f(r, 'stature') for r in S), 4) for k in keys}
json.dump({'n': len(S), 'stature_mm_mean': round(st.mean(f(r, 'stature') for r in S)), 'mass_kg_mean': round(st.mean(f(r, 'weightkg') / 10 for r in S), 1),
           'filter': 'stature 1830-1980 mm, BMI 20-24, age<=35', 'ratio_to_stature': out}, open('atp_like.json', 'w'), indent=1)
print(len(S))

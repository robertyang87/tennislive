# vibetennis：四大满贯场地快慢 · 资料包（2026-11-02，制作中）

## 原创数据（Sackmann 公开数据，ATP 男单 1991–2026，去退赛与戴维斯杯）
- 脚本 `data/speed_calc.py`，结果 `data/speed_result.json`
- ACE 指数 = 实际 ACE ÷ 按发球人当年非大满贯 ACE 率 × 接发人当年被 ACE 率 ÷ 当年巡回赛均值算出的期望
- 2015–2026：澳网 1.12、温网 1.09、美网 1.02、法网 0.75；发球得分指数温网最高（1.02）
- 法网 2020 = 0.60（近十年最低）；美网 2021 = 1.23
- 局限：是 ACE／发球得分的间接口径，不是测出的球速；只算男子；数据许可 CC BY-NC-SA

## 物理（读过原文）
- Cross, R. "Tennis physics, anyone?" Physics Today, 2008-09：红土滑动摩擦系数小角度可达 0.9；温网草地 0.5–0.6；竖直恢复系数 硬地≈0.75、草地 0.6–0.75、红土≈0.85
- Cross, R. (2003) Sports Engineering 6:95–111, DOI 10.1007/BF02903531：大角度入射时球「咬住」场地但不滚动；低角度更快的场地在高角度不一定更快；红土在所有角度都慢
- ScienceDaily 2001-08-30（Cross, The Physics Teacher）：红土细沙对鞋像滚珠，对球的绒毛像砂纸
- ITF Court Surface Classification Scheme，ISSS Technical Meeting, Nyon 2002：Surface Pace Rating = 100×(1−μ)
- ⚠️ 现行 CPR（含 150×(0.81−e) 项）与五档分级只有二手来源，未上屏前不用

## 场地／场馆事实
- 温网官方 Media Fact Sheet – Grounds 2023：2001 年起 100% 多年生黑麦草（此前 70/30），为耐磨，「不影响场地的体感速度」；弹跳主要由土壤决定；阴冷潮湿时球更重更慢
- 美网：1978–2019 DecoTurf，2020 起 Laykold（维基 + Laykold 官网新闻）
- 澳网：Rebound Ace 1988–2007、Plexicushion 2008–2019、GreenSet 2020 起（维基）；2020/2023 照片场内外同一种蓝
- 法网 2020：9/27–10/11 举行；Babolat 换 Wilson 用球（CNN 2020-09-29，维基）
- 纳达尔法网 14 冠（维基）
- 夏蒂埃顶棚：11 片钢桁架「翼」，2020 年完工（rolandgarros.com 等）；温网中心球场：1922 年十二边形，2009 年折叠式膜顶棚；阿什球场：2016 年顶棚，8 根外柱、2 块活动板；Unisphere 在同一轴线上

## 场馆建模参照
- 维基共享资源照片（RG 2022 航拍、WIM 2019 场内、RLA 2020 外观、Ashe 2016 外观），只作建模参照，不进成片

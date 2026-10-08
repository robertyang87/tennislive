cd /workspace && D=assets/reel/year-end-no1-zverev-2026 && mkdir -p $D && r(){ python3 tools/render_story_info_band.py --align right "$@" | tail -1; } && \
r --out $D/info-00.png --variant player --kicker "2026 上海大师赛" --headline "兹维列夫" --detail "被问到世界第一" && \
r --out $D/info-01.png --variant player --split-metric --kicker "2026 澳网 半决赛" --headline "阿尔卡拉斯胜" --metric "5小时27分" --detail "澳网史上最长半决赛" && \
r --out $D/info-02.png --variant player --split-metric --kicker "2026 蒙特卡洛 半决赛" --headline "辛纳胜" --metric "6-1 6-4" --detail "今年第3次输给辛纳" && \
r --out $D/info-03.png --variant player --split-metric --kicker "2026 法网 决赛" --headline "兹维列夫胜" --metric "4小时16分" --detail "6-1 4-6 6-4 6-7(5) 6-1" && \
r --out $D/info-04.png --variant player --kicker "2026 温网 决赛" --headline "辛纳 4盘胜" --detail "6-7(7) 7-6(2) 6-3 6-4" && \
r --out $D/info-05.png --variant player --split-metric --kicker "2026 美网 决赛" --headline "兹维列夫胜" --metric "6-3 7-6(2) 5-7 6-2" --detail "3个月里第2座大满贯" && \
r --out $D/info-06.png --variant chapter --kicker "2026 美网 颁奖" --headline "三个月两冠" --detail "德国男单30年后再夺大满贯" && \
r --out $D/info-07.png --variant player --split-metric --kicker "2026 中网 1/4决赛" --headline "德约胜" --metric "4-6 6-4 6-4" --detail "今年对三强第7场失利" && \
r --out $D/info-09.png --variant player --kicker "2024 年终第一" --headline "辛纳" --detail "52周稳定的网球" && \
r --out $D/info-10.png --variant player --split-metric --kicker "1977 美网 决赛" --headline "维拉斯胜" --metric "2-6 6-3 7-6 6-0" --detail "年终第一仍是康纳斯" && \
r --out $D/info-11.png --variant timeline --kicker "1989 美网 第二轮" --headline "挽救赛点" --detail "那年他拿下温网和美网" && \
r --out $D/info-12.png --variant player --split-metric --kicker "2016 年终总决赛 决赛" --headline "穆雷胜" --metric "6-3 6-4" --detail "赢下这场就是年终第一" && \
r --out $D/info-13.png --variant stat --kicker "2023 年终第一" --headline "德约第8次" --detail "举起年终第一奖杯"; ls $D
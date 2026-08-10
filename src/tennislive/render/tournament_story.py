"""Curated story cards (tournament archives + player spotlights) with reviewed facts."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..digest import Digest


ASSETS = Path(__file__).resolve().parents[3] / "assets" / "venues"
PLAYER_ASSETS = Path(__file__).resolve().parents[3] / "assets" / "players"

# 同一赛事的故事 30 天内只讲一次（一届赛事约一周，避免赛期内天天重复）
STATE_PATH = Path(__file__).resolve().parents[3] / "data" / "story_state.json"
COOLDOWN_DAYS = 30

# 「历史上的今天」命中正日子时的得分，高于球员特写的 3、赛事档案的 2。
# 纪念日一年只回来一次；昨夜的高光球员明天还有。
ANNIVERSARY_SCORE = 4

# 每个班次的排序结果落在**当日目录**（不是 knowledge/ 里），逐班追加。
# 两条都是 7/25 那次丢失换来的：daily.yml 同日重跑会 `rm -rf "$OUT_DIR/knowledge"`，
# 而第二班次被 pinned 分支直接命中已定的故事、一次拒绝都不会发生——
# 写在里面会被删掉，覆盖写会把上一班的证据擦掉。
SELECTION_LOG_NAME = "story_selection.json"


@dataclass(frozen=True)
class ChampionMoment:
    date: str
    player: str
    age: str
    headline: str
    detail: str
    source_url: str


@dataclass(frozen=True)
class TournamentStory:
    slug: str
    aliases: tuple[str, ...]
    title: str
    location: str
    level: str
    surface: str
    founded: str
    hero_fact: str
    facts: tuple[str, ...]
    moments: tuple[ChampionMoment, ...]
    venue: str
    image: Path
    image_credit: str
    source_url: str
    image_source_url: str
    # kind="player" 时字段语义复用：venue=身份行，level/surface/founded=标签行
    kind: str = "tournament"
    source_label: str = "ATP/WTA 官方资料"
    evidence_urls: tuple[str, ...] = ()
    # Rules must declare a topic-specific diagram. Supported renderers are
    # intentionally explicit so CI fails instead of silently using a stock photo.
    diagram_type: str = ""
    # Explicit cover marker wins over prose inference. Use four digits for years.
    hero_marker: str = ""
    # Optional semantic roles for facts; the renderer still has a keyword fallback.
    fact_roles: tuple[str, ...] = ()


STORIES = (
    TournamentStory(
        slug="umag",
        aliases=("umag", "croatia open", "plava laguna"),
        title="克罗地亚公开赛",
        location="乌马格 · 克罗地亚",
        level="ATP 250",
        surface="室外红土",
        founded="始于 1990",
        hero_fact="从 21 岁的瓦林卡到 18 岁的阿尔卡拉斯，乌马格见证两代巨星捧起生涯首冠。",
        facts=(
            "1990 年首届决赛也是赛事史上唯一一次全克罗地亚决赛：普尔皮奇 6-3、4-6、6-4 击败伊万尼塞维奇。",
            "卡洛斯·莫亚五度夺冠，并以 44 场胜利同时保持赛事男单冠军数与胜场纪录。",
            "2012 年西里奇 6-4、6-2 击败格拉诺勒斯，成为 1990 年普尔皮奇之后首位本土冠军。",
        ),
        moments=(
            ChampionMoment(
                date="2006-07-30",
                player="斯坦·瓦林卡",
                age="21 岁",
                headline="生涯首座 ATP 单打冠军",
                detail=(
                    "决赛对阵诺瓦克·德约科维奇，首盘战至 6-6 时，"
                    "对手因呼吸问题退赛。"
                ),
                source_url=(
                    "https://umag-ed.atptour.com/-/media/sites/tournaments/umag/"
                    "dn-pdfs/2023/dailynews_4_eng_smanjeno.pdf"
                ),
            ),
            ChampionMoment(
                date="2021-07-25",
                player="卡洛斯·阿尔卡拉斯",
                age="18 岁 2 个月",
                headline="生涯首座 ATP 冠军 · 赛事最年轻冠军",
                detail="仅用 77 分钟，以 6-2、6-2 击败理查德·加斯奎特。",
                source_url=(
                    "https://www.croatiaopen.hr/media/580852/"
                    "daily_news_2021_ponedjeljak_en.pdf"
                ),
            ),
        ),
        venue="ATP Stadium Goran Ivanišević · 4,032 席",
        image=ASSETS / "umag-goran-ivanisevic-centre-court.jpg",
        image_credit="Silverije / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://www.croatiaopen.hr/en/tournament/history",
        image_source_url=(
            "https://commons.wikimedia.org/wiki/File:Teniski_stadion_"
            "%27Goran_Ivani%C5%A1evi%C4%87%27,_Umag.jpg"
        ),
        source_label="ATP Tour / Croatia Open",
    ),
    TournamentStory(
        slug="washington",
        aliases=("washington", "dc open", "citi open", "mubadala citi"),
        title="华盛顿公开赛",
        location="华盛顿特区 · 美国",
        level="ATP 500 / WTA 500",
        surface="室外硬地",
        founded="始于 1969",
        hero_fact=(
            "这项赛事因平权而生：1969 年阿瑟·阿什坚持把它办进对所有人开放的"
            "公共公园，一座网球场从此写进美国民权史。"
        ),
        facts=(
            "1969 年阿瑟·阿什与经纪人唐纳德·戴尔共同创办，条件只有一个："
            "必须落户不分种族、人人可入场的岩溪公园，而非私人俱乐部。",
            "它是美国夏季硬地赛季里唯一一站 ATP 500 与 WTA 500 合办的比赛，"
            "常被视作美网前哨战的起点。",
            "德尔波特罗、兹维列夫都在这里两连冠；2019 年佩古拉在此拿到"
            "生涯首个巡回赛冠军。",
        ),
        moments=(
            ChampionMoment(
                date="2021-08-08",
                player="扬尼克·辛纳",
                age="19 岁",
                headline="生涯首个 ATP 500 冠军",
                detail=(
                    "决赛三盘险胜麦克唐纳。那年他世界排名还在 20 开外，"
                    "华盛顿的奖杯是他冲向大满贯的第一块跳板。"
                ),
                source_url="https://www.atptour.com/en/news/sinner-mcdonald-washington-2021-final",
            ),
            ChampionMoment(
                date="2023-08-06",
                player="科科·高芙",
                age="19 岁",
                headline="美网夺冠前的预演",
                detail=(
                    "6-2、6-3 干脆利落击败萨卡里夺冠。四周之后，"
                    "她在纽约捧起了自己的第一座大满贯。"
                ),
                source_url="https://www.wtatennis.com/news/3660060/gauff-beats-sakkari-to-win-washington-title",
            ),
        ),
        venue="岩溪公园 FitzGerald 网球中心 · 7,500 席",
        image=ASSETS / "washington-fitzgerald-tennis-center.jpg",
        image_credit="Asolsma1988 / Wikimedia Commons · CC0",
        source_url="https://mubadalacitidcopen.com/history/",
        image_source_url="https://commons.wikimedia.org/wiki/File:FitzGerald_Tennis_Center.jpg",
    ),
    TournamentStory(
        slug="canada",
        aliases=("canadian open", "national bank open", "toronto", "montreal", "canada masters"),
        title="加拿大国家银行公开赛",
        location="多伦多 / 蒙特利尔 · 两城轮办",
        level="ATP 1000 / WTA 1000",
        surface="室外硬地",
        founded="始于 1881",
        hero_fact=(
            "创办于 1881 年、与美网同龄的百年老店：男女分驻多伦多与蒙特利尔，"
            "隔年互换城市，是网坛独一份的'双城记'。"
        ),
        facts=(
            "1881 年首届比赛在多伦多举行，比温网只晚四年，"
            "是仍在举办的最古老网球赛事之一。",
            "男女赛事分别落户多伦多与蒙特利尔，每年互换主场——"
            "同一项赛事、两座城市、两种气质。",
            "2019 年安德莱斯库成为 50 年来首位在家门口夺冠的加拿大人，"
            "'She the North' 从这里喊响，六周后她又在美网掀翻小威。",
        ),
        moments=(
            ChampionMoment(
                date="2019-08-11",
                player="比安卡·安德莱斯库",
                age="19 岁",
                headline="50 年来首位本土冠军",
                detail=(
                    "决赛小威因背伤含泪退赛，安德莱斯库走到网前拥抱安慰偶像——"
                    "那个画面成了当年网坛最动人的瞬间之一。"
                ),
                source_url="https://www.wtatennis.com/news/1445162/andreescu-wins-home-title-in-toronto",
            ),
            ChampionMoment(
                date="2023-08-13",
                player="扬尼克·辛纳",
                age="21 岁",
                headline="生涯首座大师赛奖杯",
                detail=(
                    "决赛直落两盘击败德米纳尔。多伦多是他登顶之路的重要一站——"
                    "五个月后他拿下澳网，登上世界第一只用了不到一年。"
                ),
                source_url="https://www.atptour.com/en/news/sinner-de-minaur-toronto-2023-final",
            ),
        ),
        venue="Sobeys 球场（多伦多）/ IGA 球场（蒙特利尔）",
        image=ASSETS / "canada-sobeys-centre-court.jpg",
        image_credit="Raysonho / Wikimedia Commons · CC BY 3.0",
        source_url="https://nationalbankopen.com/history/",
        image_source_url="https://commons.wikimedia.org/wiki/File:RogersCup2011-2.jpg",
    ),
    TournamentStory(
        slug="cincinnati",
        aliases=("cincinnati", "western & southern", "western and southern"),
        title="辛辛那提公开赛",
        location="梅森 · 美国俄亥俄州",
        level="ATP 1000 / WTA 1000",
        surface="室外硬地",
        founded="始于 1899",
        hero_fact=(
            "1899 年开打，是全美仍留在创办城市的最古老网球赛事——"
            "比美网搬进纽约法拉盛还早了大半个世纪。"
        ),
        facts=(
            "费德勒在这里七次夺冠，至今无人接近这一纪录；"
            "他职业生涯对阵前十胜率最高的赛事就是辛辛那提。",
            "2023 年男单决赛德约科维奇 vs 阿尔卡拉斯鏖战 3 小时 49 分，"
            "是 ATP 史上最长的三盘制决赛之一。",
            "球场建在俄亥俄州小城梅森的玉米地旁，"
            "却是美网前最重要的风向标——冠军常常直通纽约决赛周。",
        ),
        moments=(
            ChampionMoment(
                date="2023-08-20",
                player="诺瓦克·德约科维奇",
                age="36 岁",
                headline="挽救赛点的史诗逆转",
                detail=(
                    "对阵阿尔卡拉斯，第二盘一度濒临出局，5-7、7-6、7-6 翻盘，"
                    "3 小时 49 分钟打完，两人赛后相拥致意。"
                ),
                source_url="https://www.atptour.com/en/news/djokovic-alcaraz-cincinnati-2023-final",
            ),
            ChampionMoment(
                date="2023-08-20",
                player="科科·高芙",
                age="19 岁",
                headline="同一天的另一座奖杯",
                detail=(
                    "击败穆霍娃拿下生涯首个 WTA 1000 冠军——"
                    "三周后她在美网决赛再次击败同一个对手夺冠。"
                ),
                source_url="https://www.wtatennis.com/news/3676176/gauff-beats-muchova-cincinnati-title",
            ),
        ),
        venue="Lindner 家族网球中心 · 中央球场 11,435 席",
        image=ASSETS / "cincinnati-centre-court-full.jpg",
        image_credit="RandyFitz / Wikimedia Commons · CC0",
        source_url="https://www.cincinnatiopen.com/history/",
        image_source_url="https://commons.wikimedia.org/wiki/File:Lindner_Family_Tennis_Center_2025.jpg",
    ),
    TournamentStory(
        slug="usopen",
        aliases=("us open", "flushing meadows"),
        title="美国网球公开赛",
        location="纽约 · 美国",
        level="大满贯",
        surface="室外硬地",
        founded="始于 1881",
        hero_fact=(
            "全世界最大的网球场、第一个男女同酬的大满贯、第一个打夜场的大满贯——"
            "美网的关键词从来都是'第一'。"
        ),
        facts=(
            "1973 年美网成为第一个男女奖金完全平等的大满贯，"
            "推动者正是比利·简·金——阿瑟·阿什球场旁的整片园区以她命名。",
            "阿瑟·阿什球场可容纳 23,771 人，是世界上最大的网球场；"
            "1975 年美网还率先把大满贯带进了灯光下的夜场。",
            "这里出产过无数'第一次'：1999 年 17 岁的小威、"
            "2022 年 19 岁的阿尔卡拉斯，都在纽约拿到生涯首座大满贯。",
        ),
        moments=(
            ChampionMoment(
                date="1999-09-11",
                player="塞雷娜·威廉姆斯",
                age="17 岁",
                headline="王朝的起点",
                detail=(
                    "决赛击败辛吉斯，17 岁的小威拿下生涯首座大满贯——"
                    "此后二十年，她又添了 22 座。"
                ),
                source_url="https://www.usopen.org/en_US/news/articles/2021-08-30/1999_us_open_serena_williams_first_major.html",
            ),
            ChampionMoment(
                date="2022-09-11",
                player="卡洛斯·阿尔卡拉斯",
                age="19 岁",
                headline="史上最年轻的世界第一",
                detail=(
                    "四盘击败鲁德夺冠，同时登顶 ATP 排名——"
                    "19 岁 4 个月，网球史上最年轻的世界第一就此诞生。"
                ),
                source_url="https://www.atptour.com/en/news/alcaraz-ruud-us-open-2022-final",
            ),
        ),
        venue="阿瑟·阿什球场 · 23,771 席（全球最大网球场）",
        image=ASSETS / "usopen-arthur-ashe-stadium.jpg",
        image_credit="manalahmadkhan / Wikimedia Commons · CC BY 2.0",
        source_url="https://www.usopen.org/en_US/visit/history/ustimeline.html",
        image_source_url="https://commons.wikimedia.org/wiki/File:Arthur_Ashe_Stadium_2010.jpg",
        source_label="美网官网 / USTA",
    ),
    # ---- 球员特写（kind="player"）：当天有球员赢球/出场时按新闻价值优先选用 ----
    # 冠军数、纪录均为截至 2025 年底的已核实事实；选图由 tools/fetch_venues.py
    # 从 Commons 按授权白名单下载，实际作者/许可以 assets/players/credits.json 为准
    TournamentStory(
        slug="zheng-qinwen",
        aliases=("qinwen zheng", "zheng qinwen"),
        title="郑钦文",
        location="中国 · 湖北",
        level="WTA",
        surface="单打最高 No.5",
        founded="2002 年生",
        hero_fact=(
            "因为 8 岁那年看见李娜捧起法网奖杯，她拿起了球拍；"
            "13 年后，她在巴黎把奥运金牌挂上了自己的脖子。"
        ),
        facts=(
            "启蒙自李娜：2011 年李娜法网夺冠点燃了这个湖北姑娘的网球梦，"
            "她先后辗转武汉、北京训练，少年时代便只身远赴欧洲。",
            "外号 'Queen Wen'：2022 年转战成年赛场的首个完整赛季，"
            "她就闯进法网 16 强并当选 WTA 年度最佳新人。",
            "2024 年是她的爆发之年：澳网打进决赛，成为李娜之后首位"
            "闯入大满贯单打决赛的中国球员，年末世界排名升至第 5。",
        ),
        moments=(
            ChampionMoment(
                date="2024-01-27",
                player="郑钦文",
                age="21 岁",
                headline="澳网决赛 · 追赶李娜的脚步",
                detail=(
                    "首次闯入大满贯决赛，虽不敌萨巴伦卡，但让中国球迷"
                    "在李娜之后再次等到了大满贯决赛日的五星红旗。"
                ),
                source_url=(
                    "https://www.wtatennis.com/news/3868599/"
                    "sabalenka-overpowers-zheng-qinwen-to-defend-australian-open-title"
                ),
            ),
            ChampionMoment(
                date="2024-08-03",
                player="郑钦文",
                age="21 岁",
                headline="奥运女单金牌 · 亚洲第一人",
                detail=(
                    "半决赛掀翻红土女王斯瓦泰克，决赛直落两盘击败维基奇——"
                    "亚洲球员的首枚奥运网球单打金牌。"
                ),
                source_url=(
                    "https://www.olympics.com/en/news/"
                    "zheng-qinwen-wins-gold-paris-2024-tennis-women-singles"
                ),
            ),
        ),
        venue="2024 巴黎奥运女单金牌得主",
        image=PLAYER_ASSETS / "zheng-qinwen.jpg",
        image_credit="Australian Open (ausopen.com)",
        source_url="https://www.wtatennis.com/players/328120/qinwen-zheng",
        image_source_url=(
            "https://ausopen.com/articles/news/"
            "rebounding-ao-final-zheng-qinwen-wins-olympic-gold-china"
        ),
        kind="player",
        source_label="WTA / 奥运官方档案",
        evidence_urls=("https://en.wikipedia.org/wiki/Zheng_Qinwen",),
    ),
    TournamentStory(
        slug="sinner",
        aliases=("jannik sinner",),
        title="扬尼克·辛纳",
        location="意大利 · 南蒂罗尔",
        level="ATP",
        surface="四座大满贯",
        founded="2001 年生",
        hero_fact=(
            "8 岁拿意大利少年滑雪冠军，13 岁改行打网球——"
            "十年后，从雪山走下来的少年站上了男子网坛之巅。"
        ),
        facts=(
            "他曾是意大利同龄组的滑雪回转冠军，13 岁才决定全职打网球，"
            "离家搬到滨海小城博尔迪盖拉，师从名帅皮亚蒂。",
            "2019 年 18 岁的他拿下 NextGen 总决赛冠军并当选 ATP 年度最佳新人，"
            "被视作三巨头时代之后的天选之人。",
            "他与阿尔卡拉斯的 'Sincaraz' 对决是新时代最大看点——"
            "近两年大满贯几乎被两人包揽。",
        ),
        moments=(
            ChampionMoment(
                date="2024-01-28",
                player="扬尼克·辛纳",
                age="22 岁",
                headline="澳网首冠 · 惊天逆转",
                detail=(
                    "决赛 0-2 落后梅德韦杰夫连扳三盘，"
                    "为意大利拿下 48 年来首个大满贯男单冠军。"
                ),
                source_url="https://en.wikipedia.org/wiki/2024_Australian_Open_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2024-06-10",
                player="扬尼克·辛纳",
                age="22 岁",
                headline="意大利首位世界第一",
                detail=(
                    "登顶 ATP 排名，成为史上首位来自意大利的世界第一——"
                    "距他放下滑雪板不过十年。"
                ),
                source_url="https://en.wikipedia.org/wiki/Jannik_Sinner",
            ),
        ),
        venue="意大利史上首位 ATP 世界第一",
        image=PLAYER_ASSETS / "jannik-sinner.jpg",
        image_credit="Daniel Cooper / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://www.atptour.com/en/players/jannik-sinner/s0ag/overview",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Jannik_Sinner",
        kind="player",
        source_label="ATP 官方档案",
    ),
    TournamentStory(
        slug="alcaraz",
        aliases=("carlos alcaraz",),
        title="卡洛斯·阿尔卡拉斯",
        location="西班牙 · 穆尔西亚",
        level="ATP",
        surface="六座大满贯",
        founded="2003 年生",
        hero_fact=(
            "祖父在穆尔西亚建起网球俱乐部，父亲是网校教练——"
            "埃尔帕尔马小村的球场上，长出了纳达尔之后西班牙最耀眼的天才。"
        ),
        facts=(
            "网球世家第三代：4 岁握拍，15 岁被前世界第一费雷罗收入门下——"
            "师徒二人一路从青少年赛场走到大满贯。",
            "2021 年 18 岁的他在乌马格拿下生涯首冠；一年后美网"
            "连续三场五盘大战后夺冠，'体能怪物'从此得名。",
            "他是公开赛时代最年轻集齐硬地、草地、红土三种场地大满贯的男球员——"
            "完成这一切时只有 21 岁。",
        ),
        moments=(
            ChampionMoment(
                date="2022-09-11",
                player="卡洛斯·阿尔卡拉斯",
                age="19 岁",
                headline="美网首冠 · 史上最年轻世界第一",
                detail=(
                    "四盘击败鲁德夺冠，同时登上世界第一——"
                    "19 岁 4 个月，男子网坛历史上最年轻的 No.1。"
                ),
                source_url="https://en.wikipedia.org/wiki/2022_US_Open_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2024-06-09",
                player="卡洛斯·阿尔卡拉斯",
                age="21 岁",
                headline="法网夺冠 · 硬地红土草地都拿过大满贯",
                detail=(
                    "五盘击败兹维列夫，集齐三种场地的大满贯冠军，"
                    "公开赛时代无人比他更年轻。"
                ),
                source_url="https://en.wikipedia.org/wiki/2024_French_Open_%E2%80%93_Men%27s_singles",
            ),
        ),
        venue="公开赛时代最年轻的世界第一",
        image=PLAYER_ASSETS / "carlos-alcaraz.jpg",
        image_credit="12121343A / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://www.atptour.com/en/players/carlos-alcaraz/a0e2/overview",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Carlos_Alcaraz",
        kind="player",
        source_label="ATP 官方档案",
    ),
    TournamentStory(
        slug="sabalenka",
        aliases=("aryna sabalenka",),
        title="阿丽娜·萨巴伦卡",
        location="白俄罗斯 · 明斯克",
        level="WTA",
        surface="四座大满贯",
        founded="1998 年生",
        hero_fact=(
            "父亲开车路过网球场的偶然一瞥，把 5 岁的她带进网球——"
            "后来她把'让萨巴伦卡这个姓被记住'打进了每一记重炮。"
        ),
        facts=(
            "她的入行纯属偶然：父亲开车带她路过一片空球场，"
            "下车试了试，从此再没放下球拍。",
            "2022 年她被双误困扰到单赛季 400 多次，痛定思痛重造发球动作——"
            "次年便夺下大满贯并登顶世界第一。",
            "左臂的老虎纹身是她的标志：球场上虎啸庆祝凶悍逼人，"
            "更衣室里她却是公认的开心果。",
        ),
        moments=(
            ChampionMoment(
                date="2023-01-28",
                player="阿丽娜·萨巴伦卡",
                age="24 岁",
                headline="澳网首冠 · 重炮加冕",
                detail=(
                    "决赛 4-6、6-3、6-4 逆转莱巴金娜，拿下生涯首座大满贯——"
                    "那年她刚刚重造了整套发球动作。"
                ),
                source_url="https://en.wikipedia.org/wiki/2023_Australian_Open_%E2%80%93_Women%27s_singles",
            ),
            ChampionMoment(
                date="2024-09-07",
                player="阿丽娜·萨巴伦卡",
                age="26 岁",
                headline="纽约圆梦",
                detail=(
                    "此前两年先后倒在美网四强与决赛，第三次冲击终于捧杯；"
                    "一年后她在同一块场地成功卫冕。"
                ),
                source_url="https://en.wikipedia.org/wiki/2024_US_Open_%E2%80%93_Women%27s_singles",
            ),
        ),
        venue="2023 年澳网加冕后登顶世界第一",
        image=PLAYER_ASSETS / "aryna-sabalenka.jpg",
        image_credit="Rick Munroe / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Aryna_Sabalenka",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Aryna_Sabalenka",
        kind="player",
        source_label="WTA 官方档案",
    ),
    TournamentStory(
        slug="swiatek",
        aliases=("iga swiatek",),
        title="伊加·斯瓦泰克",
        location="波兰 · 华沙",
        level="WTA",
        surface="六座大满贯",
        founded="2001 年生",
        hero_fact=(
            "父亲是汉城奥运会的赛艇选手，把职业运动员的自律刻进了她的成长——"
            "华沙姑娘后来成了统治红土的'法网女王'。"
        ),
        facts=(
            "2020 年法网她以世界第 54 的排名一盘未失夺冠，"
            "成为波兰史上首位大满贯单打冠军——那年她才 19 岁。",
            "2022 年她豪取 37 连胜，追平 21 世纪 WTA 最长连胜纪录，"
            "单赛季八冠登顶世界第一。",
            "运动心理师常年随队是她的坚持——她把心理训练当作日常功课，"
            "也因此在关键分上有超越年龄的冷静。",
        ),
        moments=(
            ChampionMoment(
                date="2020-10-10",
                player="伊加·斯瓦泰克",
                age="19 岁",
                headline="法网首冠 · 王朝开篇",
                detail=(
                    "一盘未失夺冠，波兰史上首位大满贯单打冠军——"
                    "此后她又在这里三度捧杯。"
                ),
                source_url="https://en.wikipedia.org/wiki/2020_French_Open_%E2%80%93_Women%27s_singles",
            ),
            ChampionMoment(
                date="2025-07-12",
                player="伊加·斯瓦泰克",
                age="24 岁",
                headline="温网 6-0、6-0",
                detail=(
                    "决赛双蛋横扫安妮西莫娃，一百多年来首见的温网决赛比分——"
                    "她终于补上了生涯最缺的草地拼图。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/2025_Wimbledon_Championships_"
                    "%E2%80%93_Women%27s_singles"
                ),
            ),
        ),
        venue="四冠法网的'红土女王'",
        image=PLAYER_ASSETS / "iga-swiatek.jpg",
        image_credit="QWisps / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Iga_%C5%9Awi%C4%85tek",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Iga_%C5%9Awi%C4%85tek",
        kind="player",
        source_label="WTA 官方档案",
    ),
    TournamentStory(
        slug="gauff",
        aliases=("coco gauff", "cori gauff"),
        title="科科·高芙",
        location="美国 · 佛罗里达",
        level="WTA",
        surface="两座大满贯",
        founded="2004 年生",
        hero_fact=(
            "15 岁在温网击败偶像维纳斯一战成名；"
            "二十岁出头，她已经把美网和法网的奖杯都搬回了家。"
        ),
        facts=(
            "父亲打过大学篮球、母亲练过田径，全家搬到佛罗里达陪她逐梦——"
            "她 15 岁就通过资格赛闯进温网 16 强。",
            "2019 年温网首轮击败五届冠军维纳斯后，"
            "她隔网向偶像致谢的一幕感动全场，'天才少女'从此进入大众视野。",
            "她还是双打好手，曾登顶双打世界第一——"
            "单双打通吃的全面性在新生代中独一份。",
        ),
        moments=(
            ChampionMoment(
                date="2023-09-09",
                player="科科·高芙",
                age="19 岁",
                headline="美网夺冠 · 主场圆梦",
                detail=(
                    "决赛先失一盘后连扳两盘逆转萨巴伦卡，"
                    "在阿瑟·阿什球场两万人的欢呼声中拿下首个大满贯。"
                ),
                source_url="https://en.wikipedia.org/wiki/2023_US_Open_%E2%80%93_Women%27s_singles",
            ),
            ChampionMoment(
                date="2025-06-07",
                player="科科·高芙",
                age="21 岁",
                headline="法网再下一城",
                detail=(
                    "又是决赛、又是逆转、又是萨巴伦卡——她成为 2015 年小威之后"
                    "首位在罗兰·加洛斯夺冠的美国女球员。"
                ),
                source_url="https://en.wikipedia.org/wiki/2025_French_Open_%E2%80%93_Women%27s_singles",
            ),
        ),
        venue="美网 · 法网双冠的美国新领军",
        image=PLAYER_ASSETS / "coco-gauff.jpg",
        image_credit="Hameltion / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Coco_Gauff",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Coco_Gauff",
        kind="player",
        source_label="WTA 官方档案",
    ),
    TournamentStory(
        slug="djokovic",
        aliases=("novak djokovic",),
        title="诺瓦克·德约科维奇",
        location="塞尔维亚 · 贝尔格莱德",
        level="ATP",
        surface="24 座大满贯",
        founded="1987 年生",
        hero_fact=(
            "在轰炸中的贝尔格莱德长大，防空警报是他童年训练的背景音——"
            "后来他把男子网坛的纪录几乎改写了一遍。"
        ),
        facts=(
            "1999 年北约轰炸期间，12 岁的他每天照常训练，启蒙教练根契奇"
            "带他专挑刚被炸过的地方练球——'同一处不会被炸第二次'。",
            "428 周世界第一、24 座大满贯、两度集齐全部九站大师赛冠军——"
            "这三项男子纪录全部由他保持。",
            "他是史上唯一在四大满贯各夺三冠以上的男球员——"
            "硬地、红土、草地，没有他攻不下的场地。",
        ),
        moments=(
            ChampionMoment(
                date="2008-01-27",
                player="诺瓦克·德约科维奇",
                age="20 岁",
                headline="澳网首冠 · 王朝序章",
                detail=(
                    "击败特松加拿下生涯首座大满贯——"
                    "当时没人想到，这只是 24 座中的第 1 座。"
                ),
                source_url="https://en.wikipedia.org/wiki/2008_Australian_Open_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2024-08-04",
                player="诺瓦克·德约科维奇",
                age="37 岁",
                headline="巴黎奥运 · 最后一块拼图",
                detail=(
                    "决赛两个抢七险胜阿尔卡拉斯，终于集齐'金满贯'——"
                    "赛后他跪地掩面而泣。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_"
                    "%E2%80%93_Men%27s_singles"
                ),
            ),
        ),
        venue="24 座大满贯 · 男子网坛纪录保持者",
        image=PLAYER_ASSETS / "novak-djokovic.jpg",
        image_credit="Kuberzog / Wikimedia Commons · CC BY 4.0",
        source_url="https://www.atptour.com/en/players/novak-djokovic/d643/overview",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Novak_Djokovic",
        kind="player",
        source_label="ATP 官方档案",
    ),
    TournamentStory(
        slug="tsitsipas",
        aliases=("stefanos tsitsipas",),
        title="斯特凡诺斯·西西帕斯",
        location="希腊 · 雅典",
        level="ATP",
        surface="两届大满贯亚军",
        founded="1998 年生",
        hero_fact=(
            "21岁成为ATP年终总决赛冠军，随后两次站上大满贯决赛；"
            "当排名和信心一起下滑，他仍在寻找重返最高舞台的路。"
        ),
        facts=(
            "2019年首次参加ATP年终总决赛便夺冠，决赛三盘击败蒂姆，"
            "那是他从新生代代表迈向顶尖球员的标志。",
            "2021年法网决赛一度大比分2比0领先德约科维奇，最终遭到逆转；"
            "2023年澳网，他第二次获得大满贯亚军。",
            "2026年格施塔德冠军结束了长达16个月的冠军等待，"
            "这座ATP 250奖杯更像一次重新出发，而非已经回到巅峰。",
        ),
        moments=(
            ChampionMoment(
                date="2019-11-17",
                player="斯特凡诺斯·西西帕斯",
                age="21 岁",
                headline="初登年终总决赛便夺冠",
                detail="决赛逆转蒂姆，成为当时十八年来最年轻的赛事冠军。",
                source_url="https://www.atptour.com/en/news/tsitsipas-thiem-nitto-atp-finals-2019-final",
            ),
            ChampionMoment(
                date="2026-07-19",
                player="斯特凡诺斯·西西帕斯",
                age="27 岁",
                headline="格施塔德夺冠 · 结束16个月等待",
                detail="三盘击败科利尼翁，拿到生涯第13座巡回赛单打冠军。",
                source_url="https://www.atptour.com/en/scores/current/gstaad/314/results",
            ),
        ),
        venue="前世界第三 · 2019 ATP年终总决赛冠军",
        image=PLAYER_ASSETS / "stefanos-tsitsipas.jpg",
        image_credit="si.robi / Wikimedia Commons · CC BY-SA 2.0",
        source_url="https://www.atptour.com/en/players/stefanos-tsitsipas/te51/overview",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Stefanos_Tsitsipas",
        kind="player",
        source_label="ATP Tour / 审核媒体简报",
    ),
    TournamentStory(
        slug="yuan-yue",
        aliases=("yuan yue", "yue yuan"),
        title="袁悦",
        location="中国 · 江苏",
        level="WTA",
        surface="巡回赛冠军",
        founded="1998 年生",
        hero_fact=(
            "2024年奥斯汀，袁悦在一场中国德比中拿到生涯首座WTA单打冠军；"
            "那座奖杯也把她第一次送进世界前50。"
        ),
        facts=(
            "2023年首尔站获得亚军，几个月后在奥斯汀第二次站上巡回赛决赛，终于捧杯。",
            "奥斯汀决赛面对王曦雨，她在错过多个冠军点后稳住抢七，拿下首冠。",
            "这段经历让她的比赛不只剩排名：真正值得追踪的是低谷之后还能否重新建立连续胜场。",
        ),
        moments=(
            ChampionMoment(
                date="2024-03-03",
                player="袁悦",
                age="25 岁",
                headline="奥斯汀首冠 · 首进世界前50",
                detail="在首次于亚洲以外举行的中国球员WTA决赛中击败王曦雨。",
                source_url="https://www.wtatennis.com/news/3921438/yuan-battles-to-first-career-title-in-austin",
            ),
        ),
        venue="2024 奥斯汀 WTA 250 冠军",
        image=PLAYER_ASSETS / "yuan-yue.jpg",
        image_credit="",
        source_url="https://www.wtatennis.com/news/3921438/yuan-battles-to-first-career-title-in-austin",
        image_source_url="",
        kind="player",
        source_label="WTA 官方报道",
    ),
    TournamentStory(
        slug="gao-xinyu",
        aliases=("gao xinyu", "xinyu gao"),
        title="高馨妤",
        location="中国",
        level="WTA",
        surface="联合杯代表",
        founded="1997 年生",
        hero_fact=(
            "高馨妤的巡回赛履历并不显眼，但2025年联合杯连续击败两位世界前100，"
            "其中包括当时世界第17的玛雅，第一次让更多人看见她。"
        ),
        facts=(
            "2024年从资格赛突围，在华欣拿到生涯首场巡回赛正赛胜利。",
            "2025年联合杯首次面对世界前50便击败玛雅，随后又战胜西格蒙德。",
            "她的看点不是一张排名表，而是能否把国家队比赛里证明过的韧性带回巡回赛。",
        ),
        moments=(
            ChampionMoment(
                date="2024-12-27",
                player="高馨妤",
                age="27 岁",
                headline="联合杯爆冷世界第17",
                detail="苦战三盘击败玛雅，拿到生涯首次对阵世界前50的胜利。",
                source_url="https://www.wtatennis.com/players/322925/xinyu-gao",
            ),
        ),
        venue="2025 联合杯中国队成员",
        image=PLAYER_ASSETS / "gao-xinyu.jpg",
        image_credit="",
        source_url="https://www.wtatennis.com/players/322925/xinyu-gao",
        image_source_url="",
        kind="player",
        source_label="WTA 官方球员档案",
    ),
    TournamentStory(
        slug="barbora-krejcikova",
        aliases=("barbora krejcikova",),
        title="巴尔博拉·克雷吉茨科娃",
        location="捷克",
        level="WTA",
        surface="两届大满贯单打冠军",
        founded="1995 年生",
        hero_fact=(
            "从2021年法网到2024年温网，克雷吉茨科娃在两种完全不同的场地上赢下大满贯，"
            "双打锻造的手感最终也成为她的单打武器。"
        ),
        facts=(
            "2021年法网首夺大满贯单打冠军，同届还与西尼亚科娃赢得女双冠军。",
            "2024年温网决赛三盘击败保利尼，成为公开赛年代少数兼夺法网和温网的女单球员。",
            "她的比赛值得看的是变化与手感，而不是把大满贯冠军简化成一个种子号。",
        ),
        moments=(
            ChampionMoment(
                date="2024-07-13",
                player="巴尔博拉·克雷吉茨科娃",
                age="28 岁",
                headline="温网夺冠 · 第二座大满贯",
                detail="三盘击败保利尼，把红土大满贯冠军的履历延伸到草地。",
                source_url="https://www.wtatennis.com/news/4057719/krejcikova-overcomes-paolini-in-three-sets-for-wimbledon-crown",
            ),
        ),
        venue="2021 法网 / 2024 温网女单冠军",
        image=PLAYER_ASSETS / "barbora-krejcikova.jpg",
        image_credit="",
        source_url="https://www.wtatennis.com/news/4057719/krejcikova-overcomes-paolini-in-three-sets-for-wimbledon-crown",
        image_source_url="",
        kind="player",
        source_label="WTA 官方报道",
    ),
)


# ---- 网球冷知识（kind="trivia"）：没有赛事/球员可讲时的兜底，板块永不空着 ----
# 配图从已入库的场馆图中就近取用，署名跟随所选图片

_STOCK_IMAGES = {
    "umag": (
        ASSETS / "umag-goran-ivanisevic-centre-court.jpg",
        "Silverije / Wikimedia Commons · CC BY-SA 4.0",
    ),
    "washington": (
        ASSETS / "washington-fitzgerald-tennis-center.jpg",
        "Asolsma1988 / Wikimedia Commons · CC0",
    ),
    "canada": (
        ASSETS / "canada-sobeys-centre-court.jpg",
        "Raysonho / Wikimedia Commons · CC BY 3.0",
    ),
    "cincinnati": (
        ASSETS / "cincinnati-centre-court-full.jpg",
        "RandyFitz / Wikimedia Commons · CC0",
    ),
    "usopen": (
        ASSETS / "usopen-arthur-ashe-stadium.jpg",
        "manalahmadkhan / Wikimedia Commons · CC BY 2.0",
    ),
}


TRIVIA_ASSETS = Path(__file__).resolve().parents[3] / "assets" / "trivia"


def _stock_image(*keys: str) -> tuple[Path, str]:
    """按偏好顺序取第一张已存在的库存图（乌马格图随仓库分发，始终可用）."""
    for key in (*keys, "umag"):
        path, credit = _STOCK_IMAGES[key]
        if path.exists():
            return path, credit
    return _STOCK_IMAGES["umag"]


def _trivia_story(
    slug: str,
    title: str,
    subtitle: str,
    identity: str,
    chips: tuple[str, str, str],
    hero: str,
    facts: tuple[str, ...],
    moments: tuple[ChampionMoment, ...],
    image_keys: tuple[str, ...],
    source_label: str,
    source_url: str,
    image_credit: str = "Wikimedia Commons",
    evidence_urls: tuple[str, ...] = (),
    diagram_type: str = "",
    hero_marker: str = "",
    fact_roles: tuple[str, ...] = (),
) -> TournamentStory:
    # 优先用主题相关的专属图（assets/trivia/，由 fetch_venues.py 抓取）；
    # 未入库时仅在场馆库存图与主题贴合时兜底（image_keys 为空 = 宁缺毋滥，
    # 图缺失则该故事暂不参选），署名永远跟随实际所用图片
    dedicated = TRIVIA_ASSETS / f"trivia-{slug}.jpg"
    image_source_url = source_url
    if dedicated.exists() or not image_keys:
        image, credit = dedicated, image_credit
        try:
            credits = json.loads((TRIVIA_ASSETS / "credits.json").read_text(encoding="utf-8"))
            image_source_url = str((credits.get(dedicated.name) or {}).get("page") or source_url)
        except (OSError, ValueError):
            pass
    else:
        image, credit = _stock_image(*image_keys)
    return TournamentStory(
        slug=slug,
        aliases=(),
        title=title,
        location=subtitle,
        level=chips[0],
        surface=chips[1],
        founded=chips[2],
        hero_fact=hero,
        facts=facts,
        moments=moments,
        venue=identity,
        image=image,
        image_credit=credit,
        source_url=source_url,
        image_source_url=image_source_url,
        kind="trivia",
        source_label=source_label,
        evidence_urls=evidence_urls,
        diagram_type=diagram_type,
        hero_marker=hero_marker,
        fact_roles=fact_roles,
    )


# ---- 历史上的今天（slug=otd-MMDD，仅当日参选，逐步补齐 365 天）----
STORIES = STORIES + (
    _trivia_story(
        slug="otd-0725",
        title="18 岁的第一冠",
        subtitle="历史上的今天 · 7 月 25 日",
        identity="2021 · 阿尔卡拉斯生涯首冠",
        chips=("历史上的今天", "2021", "乌马格"),
        hero="2021 年的今天，18 岁的阿尔卡拉斯在乌马格拿下生涯首冠——四年后，他已是多座大满贯得主。",
        facts=(
            "决赛仅用 77 分钟，6-2、6-2 击败加斯奎特——对手比他大 17 岁。",
            "他就此成为赛会史上最年轻冠军；一年后的美网，他登顶世界第一。",
            "同一片球场也见证过 2006 年瓦林卡的生涯首冠——乌马格是首冠福地。",
        ),
        moments=(
            ChampionMoment(
                date="2021-07-25", player="卡洛斯·阿尔卡拉斯", age="18 岁 2 个月",
                headline="生涯首座 ATP 冠军",
                detail="从这座 250 赛奖杯到史上最年轻世界第一，他只用了 14 个月。",
                source_url="https://en.wikipedia.org/wiki/2021_Croatia_Open_Umag",
            ),
        ),
        image_keys=("umag",),
        source_label="ATP 官方档案",
        source_url="https://en.wikipedia.org/wiki/2021_Croatia_Open_Umag",
    ),
    # 配图是这条自己那天的实拍：Commons 上传者写明「first round match against
    # Sara Errani at the 2024 Paris Olympics」，EXIF 时间 2024-07-28 14:27——
    # 时间/地点/人物/事件四要素由来源和文件自己写死，不靠看图推断。画面里
    # 场边板上的「2024」和五环还在，属于「能自证的元素比看着像值钱」。
    _trivia_story(
        slug="otd-0728",
        title="6-0、6-0",
        subtitle="历史上的今天 · 7 月 28 日",
        identity="2024 · 郑钦文奥运首战",
        chips=("历史上的今天", "2024", "巴黎"),
        hero=(
            "2024 年的今天，郑钦文在罗兰·加洛斯打出 6-0、6-0——"
            "她那届奥运，是从一场双蛋开始的。"
        ),
        facts=(
            "首轮对手埃拉尼是前世界前十，那天一局没拿到。",
            "头两场比赛加起来，她只丢了六局。",
            "六天后的同一片红土，她拿到亚洲第一块奥运网球单打金牌。",
        ),
        moments=(
            ChampionMoment(
                date="2024-07-28", player="郑钦文", age="21 岁",
                headline="奥运首战 6-0、6-0",
                detail="六天之后，同一片红土上换成了金牌。",
                source_url="https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_%E2%80%93_Women%27s_singles",
            ),
        ),
        image_keys=(),
        image_credit="Kuberzog / Wikimedia Commons · CC BY-SA 4.0",
        source_label="奥运官方档案",
        source_url="https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_%E2%80%93_Women%27s_singles",
    ),
    _trivia_story(
        slug="otd-0803",
        title="巴黎的金牌",
        subtitle="历史上的今天 · 8 月 3 日",
        identity="2024 · 郑钦文奥运夺金",
        chips=("历史上的今天", "2024", "巴黎"),
        hero="2024 年的今天，郑钦文在巴黎为中国拿下奥运网球单打首金——亚洲球员的第一次。",
        # 「掀翻红土女王」是形容词，「交手六次输六次」是可核的数字——
        # 后者更抓人，因为它具体、能查、自带画面（CLAUDE.md：煽情不是靠
        # 形容词堆出来的，是把最硬的那个事实摆到最前面）。原来第三条那句
        # 「刷遍全网热搜」查不到出处，删掉。
        facts=(
            "半决赛之前，她和斯瓦泰克交手六次、输了六次；那天 6-2、7-5。",
            "决赛直落两盘击败维基奇，6-2、6-3。",
            "距离李婷/孙甜甜的雅典女双首金，恰好二十年。",
        ),
        moments=(
            ChampionMoment(
                date="2024-08-03", player="郑钦文", age="21 岁",
                headline="奥运女单金牌 · 亚洲第一人",
                detail="从武汉的训练场到罗兰·加洛斯的最高领奖台。",
                source_url="https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_%E2%80%93_Women%27s_singles",
            ),
        ),
        # 这里原来兜底到蒙特利尔的球场空镜——讲巴黎奥运配加拿大站，正是
        # 「讲法网配温网草地」那条错误。Commons 三个查法（按分类、按对手、
        # 按领奖）都证实那天没有自由授权的实拍，最后用的是 WTA 图库当天的
        # 领奖台照（2024/08/03，Getty via WTA，**非自由授权，发布前需人工过权利**）。
        #
        # 裁法是试出来的：满高裁 3:4 会把维基奇和斯瓦泰克的脸切在两边，
        # 「真裁不下就换一张，别硬切」；收到 1399×1866 才成立——郑钦文居中、
        # 金牌举在脸侧、胸前国旗和五环都在，另外两人在画面里但明显是配角。
        image_keys=(),
        source_label="奥运官方档案",
        source_url="https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_%E2%80%93_Women%27s_singles",
    ),
    _trivia_story(
        slug="otd-0820",
        title="3 小时 49 分",
        subtitle="历史上的今天 · 8 月 20 日",
        identity="2023 · 辛辛那提史诗决赛",
        chips=("历史上的今天", "2023", "辛辛那提"),
        hero="2023 年的今天，德约科维奇与阿尔卡拉斯鏖战 3 小时 49 分——ATP 史上最长的三盘制决赛之一。",
        facts=(
            "德约第二盘濒临出局，5-7、7-6、7-6 完成翻盘，赛后两人相拥致意。",
            "同一天高芙拿下生涯首个 WTA 1000 冠军——三周后她在美网再胜同一对手夺冠。",
            "这场决赛被视作'德阿对决'系列的巅峰之作。",
        ),
        moments=(
            ChampionMoment(
                date="2023-08-20", player="德约科维奇 vs 阿尔卡拉斯", age="36 岁 vs 20 岁",
                headline="挽救赛点的史诗逆转",
                detail="打完最后一分，两代天王在网前抱在一起。",
                source_url="https://en.wikipedia.org/wiki/2023_Cincinnati_Masters",
            ),
        ),
        image_keys=("cincinnati",),
        source_label="ATP 官方档案",
        source_url="https://en.wikipedia.org/wiki/2023_Cincinnati_Masters",
    ),
    # 这条是靠 Openverse 找到的：同一批照片就在 Commons 上，但 Commons 自己的
    # 检索把它们埋了。图注写「playing US Open Final 2024」、EXIF 2024-09-07 16:45，
    # 而且是 **CC0**——不像 8/3 与 9/10 那两张 Getty via WTA 还要过权利。
    _trivia_story(
        slug="otd-0907",
        title="连丢五局之后",
        subtitle="历史上的今天 · 9 月 7 日",
        identity="2024 · 萨巴伦卡美网首冠",
        chips=("历史上的今天", "2024", "纽约"),
        hero=(
            "2024 年的今天，萨巴伦卡拿下第一座美网——"
            "一年前的同一片场地，她领先一盘却把决赛输掉了。"
        ),
        facts=(
            "决赛 7-5、7-5 击败佩古拉，第三座大满贯。",
            "第二盘她 3-0 领先，被连追五局到 3-5，然后连下四局收掉比赛。",
            "2023 年这片场地上，她领先一盘输给了高芙。",
        ),
        moments=(
            ChampionMoment(
                date="2024-09-07", player="萨巴伦卡", age="26 岁",
                headline="生涯首座美网",
                detail="上一年的决赛她也站在这儿，领先一盘之后输掉了。",
                source_url="https://en.wikipedia.org/wiki/2024_US_Open_%E2%80%93_Women%27s_singles",
            ),
        ),
        image_keys=(),
        image_credit="Ocoudis / Wikimedia Commons · CC0",
        source_label="美网官方档案",
        source_url="https://en.wikipedia.org/wiki/2024_US_Open_%E2%80%93_Women%27s_singles",
    ),
    # 配图来自 WTA 官方战报（按文章 ID 取；带 slug 的旧链接已 404）。杯身刻着
    # US OPEN TENNIS CHAMPIONSHIPS / WOMEN'S SINGLES——赛事与项目由画面自证。
    _trivia_story(
        slug="otd-0910",
        title="纽约的第一座",
        subtitle="历史上的今天 · 9 月 10 日",
        identity="2022 · 斯瓦泰克美网首冠",
        chips=("历史上的今天", "2022", "纽约"),
        hero=(
            "2022 年的今天，斯瓦泰克拿下生涯第一座美网奖杯——"
            "在这之前，她在纽约从没走过第四轮。"
        ),
        facts=(
            "决赛 6-2、7-6(5) 击败贾巴尔，这是她的第三座大满贯。",
            "第一盘她接了 19 个发球，19 个都回到了场内。",
            "同一年她还拿了法网；上一个单赛季两满贯，是 2016 年的科贝尔。",
        ),
        moments=(
            ChampionMoment(
                date="2022-09-10", player="斯瓦泰克", age="21 岁",
                headline="生涯首座美网",
                detail="此前她在这片场地从没打进过第四轮。",
                source_url="https://en.wikipedia.org/wiki/2022_US_Open_%E2%80%93_Women%27s_singles",
            ),
        ),
        image_keys=(),
        image_credit="Getty Images via WTA · 官方媒体供图",
        source_label="WTA 官方战报",
        source_url="https://en.wikipedia.org/wiki/2022_US_Open_%E2%80%93_Women%27s_singles",
    ),
    _trivia_story(
        slug="otd-0909",
        title="主场圆梦夜",
        subtitle="历史上的今天 · 9 月 9 日",
        identity="2023 · 高芙美网夺冠",
        chips=("历史上的今天", "2023", "纽约"),
        hero="2023 年的今天，19 岁的高芙在阿瑟·阿什球场逆转萨巴伦卡，美国主场沸腾。",
        facts=(
            "决赛先丢一盘后连扳两盘——她两座大满贯决赛都是逆转同一个对手。",
            "15 岁温网击败偶像维纳斯一战成名，四年后主场圆梦。",
            "两万人的欢呼声中，她跪地掩面——那一晚纽约属于她。",
        ),
        moments=(
            ChampionMoment(
                date="2023-09-09", player="科科·高芙", age="19 岁",
                headline="生涯首座大满贯",
                detail="从天才少女到美网冠军，她只让美国等了四年。",
                source_url="https://en.wikipedia.org/wiki/2023_US_Open_%E2%80%93_Women%27s_singles",
            ),
        ),
        image_keys=("usopen",),
        source_label="美网官方档案",
        source_url="https://en.wikipedia.org/wiki/2023_US_Open_%E2%80%93_Women%27s_singles",
    ),

    _trivia_story(
        slug="scoring-history",
        title="15、30、40 的秘密",
        subtitle="网球冷知识 · 起源篇",
        identity="从法国宫廷游戏到现代网球",
        chips=("冷知识", "规则起源", "中世纪法国"),
        hero=(
            "为什么不是 1、2、3，而是 15、30、40？"
            "网球最常被问起的谜题，答案要回到 600 年前的法国宫廷。"
        ),
        facts=(
            "最主流的考证指向钟面计分：得一分拨一刻钟，15、30、45——"
            "后来 45 念着拗口，被简化成了 40。",
            "0 分叫 'love'，流传最广的说法源自法语 l'œuf（鸡蛋，形似 0）；"
            "'deuce' 则来自 à deux，意为'还差两分'。",
            "连 tennis 一词都来自法语 'Tenez!'（接住！）——"
            "中世纪发球前的一声提醒，喊了几百年喊成了运动的名字。",
        ),
        moments=(
            ChampionMoment(
                date="1877-07-09",
                player="全英俱乐部",
                age="1877 年",
                headline="首届温网开打",
                detail=(
                    "22 名选手、一座木看台——现代网球从这里开始，"
                    "计分规则一路沿用至今。"
                ),
                source_url="https://en.wikipedia.org/wiki/1877_Wimbledon_Championship",
            ),
            ChampionMoment(
                date="1970-09-02",
                player="吉米·范艾伦",
                age="1970 年",
                headline="抢七登场",
                detail=(
                    "美网率先启用范艾伦发明的抢七制，终结无限拖长的盘分——"
                    "当年它有个吓人的名字：'猝死局'。"
                ),
                source_url="https://en.wikipedia.org/wiki/Tiebreaker",
            ),
        ),
        image_keys=("washington",),
        source_label="温网 / 美网官方史料",
        image_credit="Gary Houston / Wikimedia Commons · CC0",
        source_url="https://en.wikipedia.org/wiki/Tennis_scoring_system",
    ),
    _trivia_story(
        slug="wildcard",
        # 台头和封面那一问会被拼成微信标题 `title｜question`。封面那一问
        # 加了「签表里」之后，原来的台头「签表上那个 WC」就让「签表」和「WC」
        # 在同一行里各出现两次。换成 identity 那句，两半各说一件事：
        # 「一张不设上限的入场券｜签表里名字旁的 WC，是谁给的？」
        title="一张不设上限的入场券",
        subtitle="网球冷知识 · 规则篇",
        identity="一张不设上限的入场券",
        # chips[2] 会变成 `founded`，而故事卡的时间轴把它抠数字当**起点年份**用：
        # 写「正赛 8 张」抠出来是「8」，时间轴就成了 8 → 2001 → 2009，
        # 而且把 2026 那条挤了出去。外卡这条没有可核的起源年份，**不能编一个**，
        # 所以用非数字标签（和已发的 scoring-history 同一套路，起点显示 NOW）。
        chips=("冷知识", "规则原文", "不设上限"),
        hero=(
            "名字旁边那个 WC，是赛事自己发的一张入场券。"
            "它有多硬？世界第 125 靠它拿过温网冠军。"
        ),
        # 每条事实的**第一句必须在 38 字内收住**：图解卡走
        # `_card_excerpt(fact, 38)`，而它截的是「窗口内最后一个分句符」，
        # 不是最后一个句号。原来第三条写成「…不能再拿正赛外卡；而报名过了
        # 截止日的人，只能靠外卡或资格赛进正赛。」，截出来是
        # 「…不能再拿正赛外卡；而报名过了截止日的人。」——**一个没有谓语的病句**，
        # 渲出来才看见。判据见 test_render 里那条同名测试。
        facts=(
            "大满贯正赛 128 个签位里，只有外卡固定 8 张。"
            "加上资格赛的 8 到 9 张、双打 7 张、混双 8 张，一届发出去三十张出头。",
            "规则书里有整整一节叫「外卡 / 不设上限」：一辈子能领多少张，没有限制。"
            "发给谁由赛事独自决定，条件一个都没写。",
            "打过本届资格赛的人，不能再拿正赛外卡。外卡还可以被列为种子。",
        ),
        moments=(
            ChampionMoment(
                date="2001-07-09",
                player="伊万尼塞维奇",
                age="2001 年",
                headline="世界第 125，靠外卡拿下温网",
                detail=(
                    "他本该去打资格赛，温网直接给了正赛外卡；"
                    "决赛第五盘 9-7 胜拉夫特，那天因雨改在周一，"
                    "中央球场的票当天现卖。男子公开赛年代唯一以外卡夺得大满贯的人。"
                ),
                source_url="https://en.wikipedia.org/wiki/2001_Wimbledon_Championships_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2009-09-13",
                player="克里斯特尔斯",
                age="2009 年",
                headline="连世界排名都没有的美网冠军",
                detail=(
                    "那是她生完孩子复出后的第三站比赛：八强淘汰李娜，"
                    "四强淘汰卫冕冠军小威廉姆斯，决赛 7-5 6-3 胜沃兹尼亚奇——"
                    "首位以外卡拿下美网的球员。"
                ),
                source_url="https://en.wikipedia.org/wiki/2009_US_Open_%E2%80%93_Women%27s_singles",
            ),
            ChampionMoment(
                date="2026-07-10",
                player="费里",
                age="2026 年",
                headline="25 年来第一个闯进温网四强的外卡",
                detail=(
                    "世界第 114 的他 1/4 决赛 6-4 7-6 6-0 横扫 10 号种子科博利，"
                    "四强负于兹维列夫；赛后排名从 114 升到生涯最高第 36。"
                ),
                source_url="https://en.wikipedia.org/wiki/Arthur_Fery",
            ),
        ),
        image_keys=(),
        # 封面角标必须显式给，而且**不能是年份**。不给的话会退回
        # `moments[0].date[:4]` = 2001，而封面那张照片是 **2004** 年温网的
        # （2001 年那届在自由图源里一张都没有）——等于在一张 2004 年的照片上
        # 印「2001」。改成这条选题最硬的那个非年份数字：正赛固定 8 张。
        hero_marker="8 张",
        source_label="2026 官方大满贯规则书",
        image_credit="daramot / Wikimedia Commons · CC BY 2.0",
        source_url="https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf",
        evidence_urls=(
            "https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf",
            "https://www.france24.com/en/live-news/20260708-britain-s-fery-becomes-first-wildcard-to-reach-wimbledon-semis-in-25-years",
            "https://www.tennismajors.com/wimbledon-news/july-9-2001-the-day-goran-ivanisevic-finally-won-wimbledon-270642.html",
            "https://www.tennismajors.com/us-open-news/september-12-2009-the-day-kim-clijsters-became-the-first-wildcard-to-win-the-us-open-491468.html",
        ),
    ),
    _trivia_story(
        slug="yellow-ball",
        title="网球为什么是黄色的",
        subtitle="网球冷知识 · 装备篇",
        identity="一颗小球的电视时代",
        chips=("冷知识", "装备演化", "1972 改色"),
        hero=(
            "网球并非从来都是黄的——1972 年之前它是白色或黑色。"
            "改变它颜色的，是你家客厅里的彩色电视机。"
        ),
        facts=(
            "彩色电视普及后，研究发现白球在屏幕上最难追踪，"
            "荧光黄辨识度最高——ITF 于 1972 年正式为比赛用球改色。",
            "最矜持的是温网：坚持用白球到 1986 年才改用黄球，"
            "是四大满贯里最后一个'松口'的。",
            "比赛用球每 7 局、9 局交替换新，"
            "转播里那句 'new balls please' 正源于此。",
        ),
        moments=(
            ChampionMoment(
                date="1972-01-01",
                player="国际网联",
                age="1972 年",
                headline="比赛用球正式改色",
                detail=(
                    "彩色电视普及后，白球在屏幕上难以追踪；"
                    "ITF 正式把荧光黄写进比赛用球标准。"
                ),
                source_url="https://en.wikipedia.org/wiki/Tennis_ball",
            ),
            ChampionMoment(
                date="1986-06-23",
                player="温布尔登",
                age="1986 年",
                headline="白球谢幕",
                detail="草地上最后的白色网球退役，从此四大满贯统一荧光黄。",
                source_url="https://en.wikipedia.org/wiki/1986_Wimbledon_Championships",
            ),
        ),
        image_keys=(),
        source_label="ITF / 温网官方史料",
        image_credit="Acabashi / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Tennis_ball",
    ),
    _trivia_story(
        slug="equal-pay",
        # 品牌语固定占 9.5 字，20 字上限里留给尾巴十字出头——「同工同酬」占 4，宽裕。
        title="同工同酬",
        subtitle="网球观察 · 规则篇",
        identity="同工同酬",
        chips=("奖金与账本", "同工同酬", "2026"),
        hero=(
            "**大满贯 2007 年就同酬了**，所以「网球早就同酬」这句话只对了一半——"
            "巡回赛这条线**要到 2033 年才走完**。而差得最多的那一格，"
            "**不是冠军，是人最多的第一轮**。"
        ),
        facts=(
            "**辛辛那提 2025**（男女同一周、同一块场地）逐轮奖金：冠军 "
            "$1,124,380 / $752,275，女子拿到 **66.9%**；到第一轮变成 "
            "$23,760 / $11,270，只剩 **47.4%**——**八格单调下降，没有一格例外**。"
            "总奖金 $9,193,540 / $5,152,599，女子占 56.0%。"
            "⚠️ WTA 那一列出自赛事官方页（那年是 **94 签**，不是 96）；"
            "ATP 那一列两处独立来源互印，ATP 官方页对本环境 403。",
            "**反方的账本是真的，必须原样摆出来**：两家 2024 财年的 Form 990 原件——"
            "ATP Tour Inc（EIN 95-2833251）营收 **$293,710,037**、支出 $241,591,331，"
            "盈余 $52,118,706；WTA Tour Inc（EIN 13-3792400）营收 **$142,609,065**，"
            "**女子只有男子的 48.6%**，且报道称那年亏损 $490 万。"
            "⚠️ 可是把奖金比例摆到旁边就反过来了：**辛辛那提女子拿走奖金的 56.0%、"
            "进账却只占 48.6%**——按「谁挣得多谁拿得多」这条理由自己的算法，"
            "女子现在拿的反而偏多。",
            "**而在男女合办的赛事上，这笔钱本来就分不开**：一张票进场两边都能看，"
            "转播是一路信号。**两个巡回赛自己也没算清楚**——2025 年底谈合并商业权益，"
            "谈判停住了，**卡的正是「估值和未来收入怎么分」**。"
            "⚠️ 坊间说的「ATP 要 80-20」不准确：来源原文是 "
            "`the discussions started with an 80-20 ratio`，而且出自一名未具名消息人士，"
            "说的是**谈判起点**不是一方的正式要求。",
            "**「男子收视更高」不是定律**：2023 年美网决赛，同一口径（full telecast "
            "window）女单 **342 万**、男单 **232 万**，女子是男子的 **1.47 倍**，"
            "且是 ESPN 有记录以来女子大满贯决赛的最高。"
            "⚠️ 2024 年那组数（女约 180 万 / 男未过 200 万）**分不出高低，不引用**；"
            "2025 年反过来（男 330 万 / 女 240 万）。**所以只说「会翻转」，"
            "不说「女子更高」**——反方那条要的是「男子恒定更高」，一年翻转就够推翻它。",
            "**路线图只有两个点**：WTA 2023 年 6 月 27 日公告，男女同场的 1000／500 站 "
            "**2027 年**补齐，女子单独办的 **2033 年**。"
            "⚠️ **公告通篇没有任何中间刻度**——没有分年目标也没有百分比，"
            "原话只有一句 `will happen over time, to ensure the changes are sustainable`。"
            "所以到 2033 年之前，外面的人没有办法对表。"
            "顺带：那份公告里**大满贯一个字都没提**（不归 WTA 排期）。",
        ),
        # ⚠️ 这条没有 ChampionMoment，是**故意的**：它讲的是一张奖金表和一份
        # 路线图，没有哪一场比赛、哪一个人是它的落点。硬塞一个球员时刻会把
        # 「差得最多的是第一轮出局的人」这个论点缩回到某一个明星身上——
        # 而那正好是这条选题要反对的看法。
        moments=(),
        image_keys=(),
        source_label="Form 990（ProPublica）/ WTA 官方 / Sports Media Watch",
        image_credit="示意图 · 网球时差绘制",
        source_url="https://www.wtatennis.com/news/3557739/"
                   "wta-announces-new-tour-calendar-and-pathway-to-equal-prize-money",
    ),
    _trivia_story(
        slug="nadal-academy",
        # 前面那截品牌语固定占 9.5 字，20 字上限里留给尾巴的只有十字出头。
        # 「纳达尔学院」占 5 字，宽裕。
        title="纳达尔学院",
        subtitle="网球观察 · 人物篇",
        identity="纳达尔学院",
        chips=("七条来时路", "纳达尔学院", "2026"),
        hero=(
            "学院自己宣布「**史上第一次六人同时进前 100**」——**八周之后这个数字就不对了**。"
            "而把七个人的来时路排开会看见：**从 13 岁到 21 岁**，"
            "「学院培养的」这五个字，公告里**没有定义**。"
        ),
        facts=(
            "**2026 年 6 月 9 日**，拉法·纳达尔学院发公告：史上第一次，"
            "同时有六名学院培养的球员进入 ATP／WTA 前 100——"
            "鲁德 14、伊埃拉 33、穆纳尔 44、谢拉 56、兰达卢塞 58、科尔涅娃 96。"
            "⚠️ **那篇公告通篇没有定义什么叫「学院培养的」**，"
            "也没区分住了七年的和来集训一周的。",
            "**8 月 3 日周一，这个数字变成七个**。那天更新的 ATP 官方排名里，"
            "**黄泽林第 91**——1973 年有排名以来代表中国香港进前 100 的第一人。"
            "⚠️ 坊间流传的「第 90」是**实时排名**（7 月 31 日打进半决赛当下），"
            "两者是两个口径不是两个版本；「第一个进前 100」按官方榜说。"
            "⚠️ 「第七个」是按学院自己的口径数的，学院至今没发过「七个」的稿子。",
            "**同一个周一，伊埃拉在华盛顿拿下生涯首冠**，"
            "4-6 6-4 6-0 逆转佩古拉，一周内连过 2、3、1 号种子"
            "（斯维托丽娜、大坂直美、佩古拉）。这是**菲律宾史上第一个 WTA 巡回赛冠军**。"
            "⚠️ 她此前有两个 WTA125（瓜达拉哈拉、伯明翰），"
            "但那是**低于巡回赛的独立一档**，不计进这本账。",
            "**七条来时路差得很远**：伊埃拉 13 岁拿奖学金从马尼拉去、住了七年；"
            "兰达卢塞 14 岁从马德里去；黄泽林 17 岁从香港去；"
            "**鲁德 19 岁去时已是职业球员，父亲克里斯蒂安·鲁德至今是他的主教练**；"
            "穆纳尔 20 岁「回」马略卡——**他本来就是本地人**；"
            "谢拉 2025 年 3 月才搬去，那年 21 岁。"
            "⚠️ 科尔涅娃到学院的年份**没查到**，不编。",
        ),
        moments=(
            ChampionMoment(
                date="2026-08-03", player="黄泽林", age="22 岁",
                headline="香港第一个 ATP 前 100",
                detail=(
                    "洛斯卡沃斯 ATP250 掀翻头号种子莱赫奇卡（世界第 12，生涯最大胜绩），"
                    "再胜布鲁克斯比进生涯首个巡回赛半决赛。"
                    "周一官方排名第 **91**，赛季开局时他还排在 150。"
                    "**2021 年、17 岁**去的马纳科尔——他跟父母说，不去西班牙就成不了职业球员。"
                ),
                source_url="https://www.rafanadalacademy.com/en/"
                           "rafa-nadal-academy-by-movistar-en/"
                           "coleman-wong-breaks-into-the-atp-top-100-for-the-first-time/",
            ),
            ChampionMoment(
                date="2026-08-03", player="伊埃拉", age="21 岁",
                headline="菲律宾第一个 WTA 巡回赛冠军",
                detail=(
                    "华盛顿女单决赛被雨劈成两天，周一打完：4-6 6-4 6-0 逆转佩古拉。"
                    "**2018 年、13 岁**从马尼拉去的学院，拿的是奖学金，一住七年，"
                    "2023 年毕业。她管那儿叫「第二个家」。"
                ),
                source_url="https://www.wtatennis.com/news/4553195/"
                           "eala-completes-pegula-comeback-to-win-washington-"
                           "first-wta-title-for-the-philippines",
            ),
        ),
        image_keys=(),
        source_label="拉法·纳达尔学院官网 / ATP / WTA",
        image_credit="待补",
        source_url="https://www.rafanadalacademy.com/en/news/"
                   "rafa-nadal-academy-places-six-players-in-atp-and-wta-top-100-for-the-first-time/",
    ),
    _trivia_story(
        slug="special-exempt",
        # 账号所有者 2026-08-03 定的：`🎾8.3 网球有故事｜SE 特殊豁免`。
        # 这一段是微信/小红书标题的尾巴，前面那截品牌语固定占 9.5 字，
        # 20 字上限里留给它的只有十字出头——`SE 特殊豁免` 占 5.5，宽裕。
        title="SE 特殊豁免",
        subtitle="网球观察 · 规则篇",
        identity="特殊豁免",
        chips=("规则与代价", "特殊豁免", "2026"),
        hero=(
            "上一站还没打完，下一站的资格赛已经开始了——这道二选一，规则给它留了"
            "**一个位置**，叫特殊豁免。**大师赛 1 个，500 赛 1 个**，"
            "250 赛和挑战赛各 2 个。"
        ),
        facts=(
            "**ATP 规则书 §7.10**（2026 版 p85–86）：特殊豁免发给"
            "「因为还在上一站比赛、所以无法参加本站资格赛」的球员。"
            "所谓「还在比赛」，条文的定义是**在资格赛签表公布那天的赛程里"
            "开始或者恢复一场比赛**——⚠️ **「或恢复」这三个字才是雨天那一支**，"
            "ATP 全文没有出现「天气」这个词。",
            # ⚠️ 长引注不能顶在最前面：卡片按 40 字切，而
            # 「（WTA 官方规则书 Section V vii Special Exempt Spots）」里一个断句
            # 标点都没有，于是那一刀正好落在半句里（test_knowledge_card_facts_
            # never_hard_truncate_mid_clause 抓到的就是这个）。出处挪到句子中段。
            "**WTA 那本把天气写进了条文**，ATP 那本没有。"
            "WTA 官方规则书 Section V vii 写着：她的比赛**因天气**被改期到资格赛第一天，"
            "就够格；而且另有一条更松的——**只要进了决赛就够格，不用赢**。"
            "两场决赛分属两个协会，别混着讲。",
            "**拿到它有一道一小时的线**：球员关系部门在本周三、周四把下周可能够格的人"
            "列成表，交给他们当前所在赛事的监督挨个联系；而球员**赢下那场决定性的比赛之后"
            "一小时之内**必须联系监督或球员关系部门确认接受，否则从名单上拿掉。",
            "**中国球员用过**：2024 年上海大师赛，布云朝克特拿到的外卡"
            "**后来被改成了特殊豁免，理由是他在北京还没打完**。"
            "那一周他在中网胜商竣程拿下生涯首个 ATP 500 级别胜利，"
            "爆冷 6 号种子穆塞蒂进 1/4 决赛，再掀翻 4 号种子、世界第 6 的卢布列夫，"
            "成为第一个在这一级别打进半决赛的中国男子球员。",
        ),
        moments=(
            ChampionMoment(
                date="2026-08-02", player="华盛顿", age="ATP/WTA 500",
                headline="两场决赛，一场都没打完",
                detail=(
                    "男单弗里茨对霍达尔、女单佩古拉对伊埃拉，双双被雨顺延到周一。"
                    "而加拿大站的资格赛决胜轮 8 月 1–2 日就打完了，正赛首轮已到第三天。"
                    "这四个人的排名都够直接进正赛——**没被困住的原因不是运气**。"
                ),
                source_url="https://www.mubadaladcopen.com/en/wta-news/4552345/"
                           "live-updates-alexandra-eala-jessica-pegula-washington-dc-final-weather-delay",
            ),
            ChampionMoment(
                date="2025-07-28", player="卡佐", age="22 岁",
                headline="靠那一个位置，打进生涯第一个决赛",
                detail=(
                    "上一周格施塔德打进生涯首个巡回赛半决赛、重回前 100；"
                    "下一周以特殊豁免进基茨比厄尔正赛，连胜三场进生涯首个巡回赛决赛，"
                    "7 月 28 日回到前 75。决赛再负布勃利克——连续两周输给同一个人。"
                ),
                source_url="https://en.wikipedia.org/wiki/Arthur_Cazaux",
            ),
        ),
        image_keys=(),
        source_label="ATP 2026 官方规则书 §7.10 Special Exempts",
        image_credit="Tennis TV 官方集锦画面",
        source_url="https://www.atptour.com/en/players/rulebook",
    ),
    _trivia_story(
        slug="pr-allowance",
        title="它能用几次",
        subtitle="网球观察 · 规则篇",
        identity="保护排名的额度",
        chips=("规则与代价", "保护排名", "2026"),
        hero=(
            "保护排名不是一张年卡。ATP 规则书写着：停赛 6–12 个月给 **9 站或 9 个月**，"
            "停满 12 个月给 12 站或 12 个月——**两个上限同时在倒计时，谁先到算谁**。"
            "而进了签表就扣掉一站，不看输赢。"
        ),
        facts=(
            "**ATP 规则书第九章 F 节**（2026 版第 136 页，2025 版逐字相同）："
            "停赛满 6 个月不足 12 个月，保护排名给 **9 站或 9 个月**；满 12 个月给 12 站或 12 个月。"
            "中间那个「或」不是二选一，**是两个上限并排走，谁先到谁算数**。"
            "另有一条：每个大满贯只能用它进一次。",
            "**九站怎么算**：条文原话是「用保护排名参赛的头九站」，"
            "括号里排除了拿外卡进的和按真实排名直入的——那两种不占额度。"
            "但只要名字进了签表，这一站就扣掉，**不看输赢**；"
            "在赛地退赛并领了奖金，同样算一站。",
            "**门槛要先付一笔更长的空白**：连续 6 个月不参加任何比赛，表演赛也算。"
            "2025 年 1 月澳网首轮之后，商竣程做了右脚第五跖骨手术，取碎骨、切断一半肌腱。"
            "他缺席法网；**那年温网他站得上场，但打了就凑不满 6 个月**——他没打。"
            "7 月 28 日多伦多复出，首轮负于达克沃斯，那口钟从这一天开始走。",
            "**钟可以按暂停**。规则书第五款「再伤保护」：复出后再次受伤可申请冻结剩余的站数和周数，"
            "条件是这次至少停满 3 个月且申请要在这期间交上去，复出时剩多少还是多少，最多冻两次。"
            "2026 年 2 月迪拜之后，商竣程的脚伤又犯了，一停 5 个月，时间上正好越过那道门槛。"
            "⚠️ 他有没有提交申请、ATP 有没有批，没有公开记录，这一层是照条文算出来的。",
            "**8 月 2 日蒙特利尔大师赛正赛首轮，他 6-3 6-3 赢了巴列霍**，用时 1 小时 21 分——"
            "伤停后的第一场胜利，上一次赢球还要追到 1 月 19 日的澳网。"
            "**世界第 270 出现在一站大师赛的正赛里**，那就是这张凭证在做的事："
            "把他从报名这一关送进来，剩下的还得自己打。次轮对 10 号种子卢布列夫。",
        ),
        moments=(
            ChampionMoment(
                date="2025-07-28", player="商竣程", age="20 岁",
                headline="为了这张凭证，他放弃了温网",
                detail=(
                    "手术后恢复不到位缺席法网；温网他站得上场，"
                    "但打了就凑不满连续 6 个月，保护排名就没了。"
                    "多伦多复出首轮负于达克沃斯——那口 9 个月的钟，从这天起走。"
                ),
                source_url="https://www.atptour.com/en/scores/archive/toronto/421/2025/results",
            ),
            ChampionMoment(
                date="2026-08-02", player="商竣程", age="21 岁",
                headline="世界第 270，站在大师赛正赛里",
                detail=(
                    "蒙特利尔首轮 6-3 6-3 胜巴列霍，1 小时 21 分，"
                    "伤停后第一胜。生涯最高第 47 是 2024 年 10 月的事。"
                ),
                source_url="https://www.nationalbankopen.com/en/",
            ),
        ),
        image_keys=(),
        source_label="ATP 2026 官方规则书 IX.F Entry Protection",
        image_credit="Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://www.atptour.com/en/players/rulebook",
    ),
    _trivia_story(
        slug="challenger-climb",
        title="难的不是对手",
        subtitle="网球观察 · 规则篇",
        identity="低级别为什么爬不上来",
        chips=("规则与代价", "挑战赛", "2026"),
        hero=(
            "同一周，ATP250 洛斯卡沃斯的 8 号种子（第 67）比挑战赛温哥华的"
            "1 号种子（第 103）还高 36 位——**低级别的对手并没有更强**。"
            "难的是兑换率、那道门，和一块只够一个人站的地板。"
        ),
        facts=(
            "同一周、同一片大陆、同样的室外硬地：**ATP250 洛斯卡沃斯的种子从第 12 到第 67，"
            "挑战赛 125 温哥华的种子从第 103 到第 150**，两条线中间没有交叠。"
            "女子那边同样 32 签，WTA250 孟菲斯的 8 号种子第 59，WTA125 温哥华的 1 号种子第 110。",
            "**兑换率**：挑战赛 125 冠军要赢 5 场，125 分；ATP250 赢 2 场进四强，100 分。"
            "挑战赛 50 的冠军（赢 5 场）50 分，等于在 1000 赛赢一场球。"
            "**挑战赛／500／250 输第一轮零分**，而大满贯和 96 签的 1000 赛输第一轮还有 10 分。",
            "**那道门**：邦齐世界第 103，在温哥华是 1 号种子；同一周的洛斯卡沃斯，"
            "8 号种子已经是第 67。**第 103 这个排名在那一站连正赛都够不着**——"
            "「更难」的不是这一站，是你进不去另一站。",
            "温哥华那张 32 人签表里坐着：波皮林（第 104，两年前的蒙特利尔大师赛冠军，靠外卡来打）、"
            "张之臻（第 158，曾进世界前 30），还有人用保护排名来打。"
            "**往上爬的人和刚掉下来的人挤在同一张签表里。**",
            "ATP 从 2024 年起给前 250 设了收入下限，2025 年的档位是前 100 保 30 万美元、"
            "101–175 保 20 万、176–250 保 10 万，那一年补出去 200 多万；"
            "挑战赛还必须提供免费住宿。**但一年开销最省 4 万、常见 7 万+、带教练加体能师 20 万**"
            "——规则书写的是「每位球员一间双床房」，教练住进去自己付。"
            "**而女子那边至今没有对应的保底收入计划。**",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-27", player="邦齐", age="—",
                headline="第 103 名的两种身份",
                detail=(
                    "同一周，他在温哥华挑战赛是 1 号种子；"
                    "在洛斯卡沃斯 ATP250，这个排名连正赛都进不去。"
                ),
                source_url="https://en.wikipedia.org/wiki/2026_Odlum_Brown_Vancouver_Open",
            ),
            ChampionMoment(
                date="2024-01-01", player="ATP", age="—",
                headline="Baseline 保底计划上线",
                detail=(
                    "给前 250 位设收入下限，2025 年补出去 200 多万美元。"
                    "而 2013 年，能靠打球收支平衡的男子只有 336 人。"
                ),
                source_url="https://www.atptour.com/en/news/baseline-financial-security-programme-august-2023",
            ),
        ),
        image_keys=(),
        image_credit="Wikimedia Commons · CC BY-SA 4.0",
        source_label="ATP 2026 官方规则书 / 赛事签表",
        source_url="https://en.wikipedia.org/wiki/2026_Odlum_Brown_Vancouver_Open",
    ),
    _trivia_story(
        slug="entry-deadline",
        title="名单六周前就锁上了",
        subtitle="网球观察 · 规则篇",
        identity="报名截止线：只认那一天的排名",
        chips=("规则与代价", "报名截止", "2026 美网"),
        hero=(
            "2026 美网的正赛名单是 7 月 20 日锁上的——正赛周周一往前推六周。"
            "那天男子的直入线在第 101、女子在第 102；"
            "之后你涨多少跌多少，这张名单一个字都不改。"
        ),
        facts=(
            "条文写在两本规则书里，三条线长短不一样：**大满贯正赛提前 6 周、"
            "巡回赛正赛 4 周、资格赛 3 周**。WTA 2026 第三节原话是 `Main Draw Entry "
            "Deadlines for Grand Slams are six (6) weeks prior to the Monday of the week "
            "in which each event's Main Draw starts`；ATP 7.03 写成天数（28 天 / 21 天），算下来一样。",
            "2026 美网正赛 8 月 30 日开打，正赛周周一是 8 月 31 日，"
            "往前推六周正是 **7 月 20 日**。资格赛 8 月 24 日开打——"
            "**从锁名单到开赛，中间隔着整整六周的比赛。**",
            "那天男子直入线落在第 101，最后一个直入的是科梅萨尼亚；女子的线在第 102。"
            "**郑钦文第 123，差 22 位；德雷珀第 147，差 46 位**——"
            "德雷珀今年只打了 13 场巡回赛正赛（手臂伤缺澳网、法网前伤膝、温网再缺席）。",
            "线右边也有人进得去：**男子全场只有 3 人靠保护排名进正赛，商竣程是其中之一**，女子那边 5 人。"
            "保护排名不是外卡，它只是那张用旧排名报名的凭证。",
            "**同一条线，两个中国球员落在两边**：商竣程拿着凭证进了正赛，"
            "郑钦文因为去年九月硬撑着打了中网那两场、把停赛切成两截而够不上，"
            "只能靠外卡或资格赛。",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-20", player="科梅萨尼亚", age="—",
                headline="最后一个直入的人",
                detail=(
                    "美东下午 5 点名单锁上，世界第 101 的他是男子最后一个"
                    "直接进入正赛的球员。"
                ),
                source_url="https://www.puntodebreak.com/en/2026/07/22/the-us-open-2026-gets-underway-surprises-among-the-registered-tennis-players",
            ),
            ChampionMoment(
                date="2026-07-20", player="商竣程", age="20 岁",
                headline="用保护排名够着了那条线",
                detail=(
                    "男子签表里只有三个人靠保护排名进正赛，他是其中之一；"
                    "同一天，郑钦文只有真实排名第 123 可用。"
                ),
                source_url="https://www.puntodebreak.com/en/2026/07/22/the-us-open-2026-gets-underway-surprises-among-the-registered-tennis-players",
            ),
        ),
        image_keys=(),
        image_credit="香港网球公开赛官方",
        source_label="WTA / ATP 2026 官方规则书 · 美网报名名单",
        source_url="https://www.puntodebreak.com/en/2026/07/22/the-us-open-2026-gets-underway-surprises-among-the-registered-tennis-players",
    ),
    _trivia_story(
        slug="mandatory-1000",
        title="强制赛，辛纳跳了两次",
        subtitle="网球观察 · 规则篇",
        identity="连缺两站大师赛，账单是多少",
        chips=("规则与代价", "ATP 大师赛", "2026 两连跳"),
        hero=(
            "辛纳把 2026 年打过的五个大师赛全赢了，第六个没去；"
            "德约科维奇和阿尔卡拉斯也不在蒙特利尔的签表上。"
            "大师赛是强制的，ATP 规则书写着处罚自动生效、不可申诉——"
            "可这三个人去年在多伦多也没打，那一站记的同样是 0。"
        ),
        facts=(
            "辛纳把 2026 年打过的五个大师赛全赢了：印第安维尔斯、迈阿密、蒙特卡洛、"
            "马德里、罗马。**史上第一个赢下赛季前四站的人**，也是第一个五连冠。"
            "7 月 12 日他温网卫冕，20 天后蒙特利尔开打，签表上没有他。",
            "2026 ATP 规则书第八章：从大师赛正赛退赛**一律记一次排名处罚**，"
            "原话是 `Ranking penalties are automatic and cannot be appealed`。"
            "**ATP 500 可以靠推广活动、停赛 30 天或育儿身份豁免免掉，大师赛不行。**",
            "第二笔在奖金池（大师赛＋年终总决赛共 2153.7 万美元）：缺 1 站扣 25%，"
            "缺 2 站 50%，缺 3 站 75%，缺 4 站清零。**到场做推广能把 25% 减到 12.5%，"
            "但规则书同一段写死了它不解除排名处罚**，且最多赎回 20 万美元。",
            "去年加拿大站在多伦多，三个人同样缺席。排名是 52 周滚动的，"
            "**今年这个 0 顶掉去年那个 0——排名上一分不差。**",
            "唯一的出口在 9.03 Note 3：**连着缺两个或以上的强制赛**，大师赛、大满贯、"
            "年终总决赛都算，可向医疗委员会申请抹掉最多 3 个零分。"
            "阿尔卡拉斯手腕伤缺了法网、温网，够得着；**8 月 9 日辛纳也退出了辛辛那提**——"
            "蒙特利尔、辛辛那提连着两站，他现在同样够得着这扇门。",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-24", player="辛纳", age="24 岁",
                headline="赛前一周退出蒙特利尔",
                detail=(
                    "「我们认为把健康放在第一位是正确的决定。」"
                    "德约科维奇同日退赛；阿尔卡拉斯因右手腕伤本就不在名单上。"
                ),
                source_url="https://www.cbc.ca/lite/story/9.7282909",
            ),
            ChampionMoment(
                date="2026-08-01", player="兹维列夫", age="29 岁",
                headline="顶替成为头号种子",
                detail=(
                    "蒙特利尔 8 月 1 日开打，法网冠军兹维列夫升为头号种子，"
                    "阿利亚西姆第二——加拿大选手史上最高种子位。"
                ),
                source_url="https://en.wikipedia.org/wiki/2026_National_Bank_Open_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2026-08-09", player="辛纳", age="24 岁",
                headline="接着退出辛辛那提",
                detail=(
                    "「右膝的问题一直困扰着我，尽管医疗团队一直在努力，"
                    "我必须接受自己还没准备好回到赛场。」阿尔卡拉斯 8 月 4 日"
                    "因手腕伤先一步退赛——蒙特利尔、辛辛那提连着两站，"
                    "他也够上了 9.03 Note 3 那扇门。"
                ),
                source_url="https://www.aljazeera.com/sports/2026/8/9/jannik-sinner-withdraws-from-cincinnati-open-with-knee-injury",
            ),
        ),
        image_keys=(),
        image_credit="AELTC / Joel Marklund · wimbledon.com 官方图",
        source_label="ATP 2026 官方规则书 / CBC",
        source_url="https://www.atptour.com/-/media/files/rulebook/2026/2026-rulebook_19dec25.pdf",
        evidence_urls=(
            "https://www.cbc.ca/lite/story/9.7282909",
            "https://en.wikipedia.org/wiki/2026_National_Bank_Open_%E2%80%93_Men%27s_singles",
            "https://www.aljazeera.com/sports/2026/8/9/jannik-sinner-withdraws-from-cincinnati-open-with-knee-injury",
        ),
    ),
    _trivia_story(
        slug="comeback-middle",
        title="中段长得一模一样",
        subtitle="网球观察 · 人物篇",
        identity="同一台手术，两个相反的结局",
        chips=("伤病与复出", "同一个部位", "当时分不出来"),
        hero=(
            "德约科维奇 2018 年 2 月做右肘手术，那个春天跌到世界第 22；"
            "锦织圭 2019 年 10 月做右肘手术，世界第 8。前者五个月后拿下温网，"
            "后者再没回到前列——而在中段那几个月，两条路长得一模一样。"
        ),
        facts=(
            "德约科维奇 2018 年 2 月手术后连败：印第安维尔斯 2 轮负**世界第 109 位**"
            "的丹尼尔太郎，巴塞罗那负克利赞，马德里负埃德蒙德后跌至第 18，"
            "罗马之后第 22——**上一次跌出前 20 是 2006 年 10 月**。",
            "五个月后他拿下温网（决赛 6-2 6-2 7-6 胜安德森），同年再夺美网"
            "（6-3 7-6 6-3 胜德尔波特罗），年底重回世界第一。",
            "锦织圭 2019 年 10 月做右肘手术清除两块骨刺，当时世界第 8、生涯最高第 4，"
            "停赛 10 个月。**2021 年他一度打进法网 16 强、东京奥运八强、华盛顿四强**，"
            "看起来正在回来；2022 年 1 月左髋手术报销整季，2023 年 6 月才重返巡回赛。",
            "分岔不在肘：德约科维奇身上只有那一处伤，锦织圭在此之后还有新冠、"
            "肩伤与髋部手术。**中段无法预判**——这是这条故事唯一的结论。",
            "郑钦文 2025 年 7 月右肘手术，术前一个月世界第 4；一年之后排名第 123，2026 年 8 月 1 日多伦多资格赛首轮出局。**她正走在那一段里。**",
        ),
        moments=(
            ChampionMoment(
                date="2018-05-19",
                player="德约科维奇",
                age="30 岁",
                headline="跌出前 20",
                detail=(
                    "罗马大师赛四强负于纳达尔后，世界排名跌至第 22，"
                    "是他自 2006 年 10 月以来第一次跌出前 20。"
                ),
                source_url="https://en.wikipedia.org/wiki/2018_Novak_Djokovic_tennis_season",
            ),
            ChampionMoment(
                date="2018-07-15",
                player="德约科维奇",
                age="31 岁",
                headline="温网夺冠",
                detail=(
                    "手术后第五个月，决赛 6-2、6-2、7-6(3) 击败安德森，"
                    "拿下两年来第一个大满贯；同年美网再胜德尔波特罗，年底重回世界第一。"
                ),
                source_url="https://en.wikipedia.org/wiki/2018_Novak_Djokovic_tennis_season",
            ),
        ),
        image_keys=(),
        source_label="Wikipedia 2018 Djokovic season / ESPN / The Japan Times",
        source_url="https://en.wikipedia.org/wiki/2018_Novak_Djokovic_tennis_season",
        image_credit="Carine06 · Wikimedia Commons · CC BY-SA 2.0",
    ),
    _trivia_story(
        slug="protected-ranking",
        title="保护的不是排名",
        subtitle="网球观察 · 规则篇",
        identity="保护排名：它保的是报名，不是排名",
        chips=("规则冷知识", "连续 26 周", "两截不累加"),
        hero=(
            "长期伤停的球员可以用停赛前的旧排名报名，这张凭证 ATP 叫 "
            "Entry Protection、WTA 叫 Special Ranking；它只管报名，"
            "不管种子、不管幸运落败者顺位，也不会让真实排名停下来。"
        ),
        facts=(
            "ATP 2026 规则书 IX.F 的正式名是 **Entry Protection**（进赛保护）："
            "停赛满 6 个月、期间一场不打（含表演赛）才可申请，且明写不得用于种子"
            "与幸运落败者顺位。",
            "WTA 2026 规则书 VIII.C 叫 **Special Ranking**，门槛是连续 26 周；"
            "适用情形比 ATP 多出怀孕与成为父母。种子上两家分叉：WTA 允许复出后"
            "前 8 站当额外种子，ATP 一律不给。",
            "26 周必须连续，**不累加**。郑钦文 2025 温网后至 2026 多哈复出之间"
            "只打过一站中网，把停赛切成 10.7 周加 18.1 周；合计 28.8 周已过门槛，"
            "两截却各自不够。",
            "⚠️ 上述推算依据两家规则书条文，不是 WTA 的公开裁定；她是否申请过、"
            "是否获得过豁免，均无公开记录。",
        ),
        # 这两个时刻不是"夺冠瞬间"，是这条规则在她身上落地的两个端点。
        # ⚠️ 不能留空：moments 为空时文案模板会回退到 `founded`，而 trivia 的
        # founded 取自 chips，于是拼出「从两截不累加年的…」这种坏句子，
        # 而且只有把整段渲出来才看得见。lucky-loser 没踩到是因为它有两个 moment。
        moments=(
            ChampionMoment(
                date="2025-09-24",
                player="郑钦文",
                age="22 岁",
                headline="那两场中网",
                detail=(
                    "右肘手术两个多月后回到北京，轮空后胜阿朗戈，"
                    "次战对诺斯科娃中途退赛——一整段停赛被这一站切成两半。"
                ),
                source_url="https://www.wtatennis.com/players/328120/qinwen-zheng",
            ),
            ChampionMoment(
                date="2026-07-17",
                player="郑钦文",
                age="23 岁",
                headline="雅典八强",
                detail=(
                    "4-6、4-6 负于克雷吉茨科娃，那是美网正赛直入线锁定前"
                    "最后的机会；三天后线锁在约前 104，她排在第 123。"
                ),
                source_url="https://athens-open.com/gallery/day-7",
            ),
        ),
        image_keys=(),
        source_label="ATP 2026 官方规则书 IX.F / WTA 2026 规则书 VIII.C",
        image_credit="athens-open.com 官方图库",
        source_url="https://www.wtatennis.com/players/328120/qinwen-zheng",
    ),
    _trivia_story(
        slug="lucky-loser",
        title="输了才有的名额",
        subtitle="网球观察 · 规则篇",
        identity="幸运落败者：资格赛输了也能进正赛",
        chips=("规则冷知识", "抽签还是排名", "大满贯 0 人进八强"),
        hero=(
            "资格赛最后一轮输掉的人，可以因为正赛有人退出而递补进正赛；"
            "这个身份叫幸运落败者，卢布列夫和高芙的第一个冠军都是这么来的。"
        ),
        facts=(
            "ATP 7.20 A.1：末轮失利者按资格赛种子排名排序；但**资格赛打完那一刻正赛"
            "已有空缺**时，排名最高的两人抽签决定，空 N 个位置就抽 N+1 人。"
            "WTA 2026 规则书 V.A.1.b.vi 的触发条件相同。",
            "WTA 把三种情形写全（lost, retired, or withdrawn），并加三道闸："
            "签到、赛会医生检查、正赛不得排在退赛当天；ATP 全本 210 页、123 处提到"
            "lucky loser，这三条一条都没有，医疗条款反而明写「同一天或之后」皆可。",
            "至今没有人以幸运落败者身份打进大满贯八强，第四轮是天花板："
            "1995 温网诺曼、2023 法网阿瓦涅相、2025 澳网利斯、2025 温网谢拉、"
            "2026 法网德容；利斯那次再赢一场就是史上第一个。",
        ),
        moments=(
            ChampionMoment(
                date="2017-07-23",
                player="卢布列夫",
                age="19 岁",
                headline="「输的那个人是幸运的」",
                detail=(
                    "资格赛末轮输掉，因丘里奇退赛递补进正赛，一路赢到决赛，"
                    "6-4、6-2 击败四号种子洛伦齐，拿下生涯第一个 ATP 冠军；"
                    "颁奖人是伊万尼塞维奇。他当天在社媒写下 Loser is lucky!"
                ),
                source_url="https://www.atptour.com/en/news/rublev-lorenzi-umag-2017-final",
            ),
            ChampionMoment(
                date="2019-10-13",
                player="高芙",
                age="15 岁 7 个月",
                headline="开赛前 15 分钟被叫回球场",
                detail=(
                    "资格赛直落两盘负于科尔帕奇后已出局；首轮开打前 15 分钟"
                    "萨卡里手腕伤退，她递补上场，连赢五场（含头号种子贝尔腾斯），"
                    "决赛 6-3、1-6、6-2 胜奥斯塔彭科，成为 2004 年以来最年轻的 WTA 冠军。"
                ),
                source_url="https://www.wtatennis.com/news/1485527",
            ),
        ),
        image_keys=(),
        source_label="ATP 2026 官方规则书 7.20 / WTA 2026 规则书 V.A.1.b / ATP / WTA",
        image_credit="Merlo de Graia · 卢布列夫本人社媒",
        source_url="https://en.wikipedia.org/wiki/Lucky_loser",
    ),
    _trivia_story(
        slug="roof",
        title="温网屋顶谁说了算",
        subtitle="网球观察 · 规则篇",
        identity="「光线不足」没有写时间",
        chips=("规则争议", "19:40 对 20:30", "2009 装成"),
        hero=(
            "中央球场屋顶只在下雨或光线不足时关闭；2025 年 20:30 关，"
            "2026 年 19:40 关，德约科维奇当场质问执行标准。"
        ),
        facts=(
            "中央球场可开合屋顶装成于 2009 年，规则只允许两种情形关闭：降雨，或光线不足；"
            "关闭后可开灯续赛，直至当地议会规定的 23:00 宵禁。",
            "2026 年温网第四轮，辛纳与望月慎太郎在第二盘 4-4 时意见相反："
            "辛纳要求关顶，望月希望续打，官方选择关闭；辛纳随后以 7-0 拿下该盘抢七，"
            "全场 6-3、7-6(0)、6-3 获胜。",
            "两天后的四分之一决赛，赛事主管于 19:40、第三盘开始前通知关顶，"
            "德约科维奇当场质疑执行不一；该场耗时 5 小时 15 分，为温网史上最长的四分之一决赛。",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-07",
                player="德约科维奇",
                age="19:40",
                headline="「我们是户外赛事」",
                detail=(
                    "第三盘开始前被通知关顶，他回应称前几日到 20:30 都未关，"
                    "当时完全可以在户外再打一盘。"
                ),
                source_url=(
                    "https://www.foxnews.com/sports/"
                    "novak-djokovic-heated-argument-wimbledon-roof-quarterfinal-win"
                ),
            ),
            ChampionMoment(
                date="2025-07-07",
                player="迪米特洛夫",
                age="20:30",
                headline="领先两盘后退赛",
                detail=(
                    "第二盘后因光线关顶、中断约 10 分钟；复赛后第三盘他胸肌撕裂退赛。"
                    "其教练德尔加多向 BBC 表示，转入室内并非受伤原因。"
                ),
                source_url=(
                    "https://www.tennis365.com/tennis-news/"
                    "grigor-dimitrov-wimbledon-injury-coach-roof-closure-jannik-sinner-"
                    "andy-murray-criticism"
                ),
            ),
        ),
        image_keys=(),
        source_label="温网官方规则 / Fox Sports / BBC / ATP",
        image_credit="Carine06 / Wikimedia Commons · CC BY-SA 2.0",
        source_url="https://en.wikipedia.org/wiki/Centre_Court",
    ),
    _trivia_story(
        slug="ten-champions",
        title="十届温网十个女冠军",
        subtitle="网球观察 · 格局篇",
        identity="同样十届，男单只有五人",
        chips=("女单 10 人", "男单 5 人", "无人卫冕"),
        hero=(
            "2016 至 2026 年共十届温网（2020 年停办），女单出了十个不同的冠军、"
            "无人卫冕；男单同期只有五个人分走十座冠军。"
        ),
        facts=(
            "女单十届出了十个不同的冠军：小威、穆古鲁扎、科贝尔、哈勒普、巴蒂，"
            "以及莱巴金娜、万卓索娃、克雷吉茨科娃、斯瓦泰克、诺斯科娃；"
            "上一次有人卫冕温网女单，正是这十届的第一届、2016 年的小威。",
            "男单同期只有五人：德约科维奇 4 冠（2018、2019、2021、2022），"
            "阿尔卡拉斯 2 冠（2023、2024），辛纳 2 冠（2025、2026），"
            "穆雷与费德勒各 1 冠。",
            "捷克球员占了女单这十席中的三席（万卓索娃、克雷吉茨科娃、诺斯科娃）；"
            "2026 年决赛为捷克内战，捷克成为公开赛年代第六个由两名本国女将会师"
            "大满贯单打决赛的国家。",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-11",
                player="诺斯科娃",
                age="21 岁 236 天",
                headline="首进大满贯决赛即夺冠",
                detail=(
                    "6-2、5-7、6-3 击败同胞穆霍娃夺得温网女单冠军，"
                    "第三轮曾救下一个赛点；为 2011 年科维托娃之后最年轻的温网女单冠军。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/"
                    "2026_Wimbledon_Championships_%E2%80%93_Women%27s_singles"
                ),
            ),
            ChampionMoment(
                date="2026-07-12",
                player="辛纳",
                age="2026 年",
                headline="男单卫冕，十届只有五人",
                detail=(
                    "6-7(7-9)、7-6(7-2)、6-3、6-4 击败兹维列夫成功卫冕；"
                    "在此之前上一位卫冕温网男单的是 2022 年的德约科维奇。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/"
                    "2026_Wimbledon_Championships_%E2%80%93_Men%27s_singles"
                ),
            ),
        ),
        image_keys=(),
        source_label="各届温网维基百科条目",
        image_credit="Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/List_of_Wimbledon_ladies%27_singles_champions",
    ),
    _trivia_story(
        slug="thiem-football",
        # 标题连着品牌语一起进小红书的 20 字上限（`🎾7.26 网球有故事｜` 占 9.5）。
        # 原来写「美网冠军去踢第八级联赛」是 20.5 字，会被截断——而截掉的正好是
        # 「联赛」那两个字，读者看到的会是「美网冠军去踢第八级」。砍掉「去」。
        title="美网冠军踢第八级联赛",
        subtitle="网球观察 · 退役篇",
        identity="从大满贯到第八级",
        # chips[2] 会变成 `founded`，故事卡的时间轴把它抠数字当起点年份用。
        # 写「第 8 级」抠出来是 8，时间轴就成了 8 → 2020 → 2024。用非数字标签
        # （和 wildcard、scoring-history 同一套路），起点显示 NOW。
        chips=("退役之后", "两个 9.13", "第八级"),
        hero=(
            "2020 年美网冠军蒂姆 2024 年 10 月退役，2026 年 7 月 15 日在奥地利足协"
            "重新登记为球员，转会 Badener AC，打第八级的 2. Klasse Triestingtal。"
        ),
        facts=(
            "蒂姆 2026 年 7 月 15 日在奥地利足协完成注册，转入 Badener AC；"
            "该队打 2. Klasse Triestingtal，是奥地利联赛金字塔的第八级。"
            "促成转会的是一位已在队中的朋友。",
            "2025 年 9 月 13 日，他为原队利希滕韦特替补上场 12 分钟后打进一球，"
            "把比分改写为 3:2——踢球以来第 8 场正式比赛的第一粒进球，"
            "而那一天正是他在纽约夺得美网五周年。",
            "Badener AC 1899 年 2 月 19 日成立，是今天下奥地利州最古老的俱乐部，"
            "1934/35 赛季拿过奥地利业余全国冠军。足球部负责人对他的表态是："
            "在我们这儿，谁都得自己去争首发。",
        ),
        moments=(
            ChampionMoment(
                date="2020-09-13",
                player="蒂姆",
                age="27 岁",
                headline="0-2 落后翻盘，拿下美网",
                detail=(
                    "决赛先丢两盘后连扳三盘，第五盘抢七 8-6 胜兹维列夫，"
                    "拿到生涯唯一一座大满贯；生涯最高世界第三，17 个巡回赛冠军。"
                ),
                source_url="https://en.wikipedia.org/wiki/2020_US_Open_%E2%80%93_Men%27s_singles",
            ),
            ChampionMoment(
                date="2024-10-22",
                player="蒂姆",
                age="31 岁",
                headline="维也纳首轮出局，就此退役",
                detail=(
                    "主场首轮 6-7(6) 2-6 负于达尔代里，91 分钟；"
                    "长期的手腕伤让他再没回到从前的水准。"
                ),
                source_url="https://www.atptour.com/en/news/darderi-thiem-vienna-2024-tuesday",
            ),
            ChampionMoment(
                date="2026-07-15",
                player="蒂姆",
                age="32 岁",
                headline="在足协登记为球员，转会 Badener AC",
                detail=(
                    "打第八级的 2. Klasse Triestingtal；此前两个赛季效力家乡队"
                    "利希滕韦特，上赛季 10 场 1 球。他同时是自己创办的"
                    "维也纳小场联赛球队 Ecoballers 的合伙人之一。"
                ),
                source_url="https://www.laola1.at/de/red/fussball/unterhaus/nicht-mehr-lichtenwoerth--dominic-thiem-wechselt-fussballverein/",
            ),
        ),
        image_keys=(),
        # 封面角标不能是年份：这条片子里有两个 9.13，印任何一个都会和另一屏打架。
        # 用那个非年份的数字——他现在打第几级。
        hero_marker="第 8 级",
        source_label="laola1 / NÖN / 奥地利联赛体系",
        image_credit="GEPA pictures 经 laola1 转载（unverified）",
        source_url="https://www.laola1.at/de/red/fussball/unterhaus/nicht-mehr-lichtenwoerth--dominic-thiem-wechselt-fussballverein/",
        evidence_urls=(
            "https://www.laola1.at/de/red/fussball/unterhaus/nicht-mehr-lichtenwoerth--dominic-thiem-wechselt-fussballverein/",
            "https://www.atptour.com/en/news/darderi-thiem-vienna-2024-tuesday",
            "https://de.wikipedia.org/wiki/Fu%C3%9Fball-Ligasystem_in_%C3%96sterreich",
            "https://de.wikipedia.org/wiki/Badener_AC",
            "https://sportbusinessmagazin.com/ecoballers-dominic-thiem-amateurfussball/",
        ),
    ),
    _trivia_story(
        slug="ball-pick",
        title="发球前为什么要挑球",
        subtitle="网球观察 · 规则篇",
        identity="挑的是毛，也是时间",
        chips=("场上仪式", "7 局 / 9 局", "毛毡"),
        hero=(
            "球员发球前从球童手里挑球，找的是毛最少、阻力最小的一颗；"
            "比赛用球第一次换在 7 局后，此后每 9 局一次，差的两局在赛前热身里。"
        ),
        facts=(
            "WTA 官方说明：球员发球前查看数颗球，是在找空气动力学上最好、也就是毛起得最少的那一颗，"
            "以求把发球的优势拉到最大。",
            "换球节奏为「先七局、之后每九局」；两个数字之所以不同，"
            "是因为开赛这一批球在赛前热身时就已经用过，上场时并非全新。",
            "网球由充压橡胶壳外粘一层羊毛、尼龙与棉的混纺毛毡构成，"
            "内部气压比外界高约 80 千帕；毛毡被击打后逐渐松散，球随之变蓬、变慢。",
        ),
        moments=(
            ChampionMoment(
                date="",
                player="WTA 官方",
                age="规则",
                headline="先 7 局，之后每 9 局",
                detail=(
                    "主裁喊「新球」即为换球节点；差的两局计入赛前热身，"
                    "换球的目的是避免用过蓬、过慢的球比赛。"
                ),
                source_url="https://www.wtatennis.com/news/3043764/tennis-explained-learn-the-game",
            ),
            ChampionMoment(
                date="",
                player="ITF",
                age="球体规格",
                headline="充压橡胶壳外粘毛毡",
                detail=(
                    "直径 6.54–6.86 厘米、质量 56.0–59.4 克；内部气压比外界高约 80 千帕，"
                    "封罐后即持续外漏。"
                ),
                source_url="https://en.wikipedia.org/wiki/Tennis_ball",
            ),
        ),
        image_keys=(),
        source_label="WTA 官方规则说明 / ITF 球体规格",
        image_credit="Steven Pisano / Wikimedia Commons · CC BY 2.0",
        source_url="https://www.wtatennis.com/news/3043764/tennis-explained-learn-the-game",
    ),
    _trivia_story(
        slug="shot-clock",
        title="发球 25 秒是怎么来的",
        subtitle="网球观察 · 规则篇",
        identity="2018 年上墙，2026 年自动",
        chips=("20 秒 → 25 秒", "2018 美网", "2026 全自动"),
        hero=(
            "2018 年美网成为首个在正赛使用 25 秒发球计时器的大满贯，"
            "大满贯同期由 20 秒改为 25 秒；2026 年 ATP 改为自动计时，一分结束即起算。"
        ),
        facts=(
            "2018 年之前，大满贯的分间时限为 20 秒、巡回赛为 25 秒，没有可视计时器，"
            "是否超时由主裁判断；2018 年四大满贯统一改为 25 秒并引入计时器。",
            "2018 年美网是首个在正赛使用 25 秒计时器的大满贯，此前仅在 2017 年美网资格赛试行；"
            "计时器由主裁在报分之后启动，掌声不计入其中。",
            "超时罚则为首次警告，此后每次罚掉一个一发；2026 年 ATP 改为自动计时，"
            "一分结束后几乎立刻起算、不再等报分，阿尔卡拉斯与辛纳均公开提出异议。",
        ),
        moments=(
            ChampionMoment(
                date="2018-08-27",
                player="美网",
                age="2018 年",
                headline="首个用上计时器的大满贯正赛",
                detail=(
                    "25 秒计时器在 2018 年美网正赛启用，此前于 2017 年美网资格赛试行；"
                    "同年四大满贯将分间时限由 20 秒统一为 25 秒。"
                ),
                source_url=(
                    "https://www.guinnessworldrecords.com/world-records/"
                    "544272-first-grand-slam-to-adopt-a-shot-clock-for-the-main-draws"
                ),
            ),
            ChampionMoment(
                date="2026-06",
                player="阿尔卡拉斯",
                age="女王杯",
                headline="「钟不停，我全程都在赶」",
                detail=(
                    "负于德拉珀后他表示：主裁告知有新规则，一分结束后计时立即开始；"
                    "他称分与分之间没有恢复时间。此前在迈阿密对戈芬一场，"
                    "他因超时被罚，当场称在网前结束一分时根本无法赶上。"
                ),
                source_url=(
                    "https://www.skysports.com/tennis/news/12110/13156552/"
                    "carlos-alcaraz-plans-atp-talks-over-new-shot-clock-rule-after-defeat-at-queens-club"
                ),
            ),
        ),
        image_keys=(),
        source_label="Guinness World Records / LTA 裁判手册 / Sky Sports",
        image_credit="AELTC/Ben Solomon · wimbledon.com 官方图",
        source_url=(
            "https://www.lta.org.uk/494f0e/siteassets/lta-officials/my-resources/"
            "role-specific-resources/serve-shot-clock-procedures-2023.pdf"
        ),
    ),
    _trivia_story(
        slug="zheng-eala",
        title="郑钦文首轮VS伊埃拉",
        subtitle="赛事前瞻 · WTA 500",
        identity="三年前的亚运会半决赛之后",
        chips=("WTA 500", "首轮", "第二次交手"),
        hero=(
            "郑钦文以外卡身份出战华盛顿站，首轮对阵生涯新高世界第 28 的伊埃拉；"
            "两人上一次交手是 2023 年杭州亚运会半决赛，郑钦文取胜后夺金。"
        ),
        facts=(
            "伊埃拉 2005 年 5 月生，2022 年成为菲律宾首位青少年大满贯单打冠军；"
            "2025 年迈阿密以外卡身份连胜奥斯塔彭科、凯斯与斯瓦泰克闯入四强。",
            "2026 年 7 月 13 日，伊埃拉升至生涯新高世界第 28 位，为菲律宾球员在 WTA 巡回赛的历史最高排名；"
            "本届温网她第三轮再胜斯瓦泰克，首次打进大满贯第二周。",
            "郑钦文 2024 年巴黎奥运会夺得女单金牌，为亚洲首位奥运网球单打冠军；"
            "生涯最高排名世界第 4（2025 年 6 月），2025 年温网后接受右肘手术，2026 年 2 月复出。",
        ),
        moments=(
            ChampionMoment(
                date="2023-09",
                player="郑钦文",
                age="杭州亚运会",
                headline="半决赛 6-1、6-7(5)、6-3 胜伊埃拉",
                detail="该届郑钦文夺得女单金牌，伊埃拉获得铜牌；这是两人此前唯一一次交手。",
                source_url="https://en.wikipedia.org/wiki/Zheng_Qinwen",
            ),
            ChampionMoment(
                date="2026-07-13",
                player="伊埃拉",
                age="21 岁",
                headline="升至世界第 28，菲律宾史上最高",
                detail="本届温网第三轮击败斯瓦泰克，首次打进大满贯第二周后升至生涯新高。",
                source_url="https://en.wikipedia.org/wiki/Alexandra_Eala",
            ),
        ),
        image_keys=(),
        source_label="两人维基百科条目 / WTA 官方赛会信息",
        image_credit="官方媒体供图 · ausopen.com",
        source_url="https://en.wikipedia.org/wiki/Alexandra_Eala",
    ),
    _trivia_story(
        slug="shang-nishikori",
        title="商竣程首轮VS锦织圭",
        subtitle="赛事前瞻 · ATP 500",
        identity="锦织圭退役赛季的华盛顿首轮",
        chips=("ATP 500", "首轮", "第二次交手"),
        hero=(
            "锦织圭以外卡身份出战华盛顿站，首轮对阵商竣程；"
            "锦织圭已宣布 2026 赛季结束后退役，两人上一次交手是 2024 年成都公开赛首轮，"
            "19 岁的商竣程 6-4、6-4 取胜并最终夺冠。"
        ),
        facts=(
            "锦织圭 1989 年 12 月生，生涯最高世界第 4，12 个 ATP 单打冠军；"
            "2014 年美网打进决赛，是公开赛年代唯一一位代表亚洲国家打进大满贯男单决赛的球员。",
            "2026 年 4 月，锦织圭宣布将在赛季结束后退役；髋、腕、背、肩、膝多处伤病长期困扰，"
            "现世界排名四百开外，本站靠外卡进入正赛。",
            "商竣程 2005 年 2 月生，生涯最高世界第 47（2024 年 10 月）；"
            "2024 年成都公开赛夺冠，成为公开赛年代第二位赢得 ATP 单打冠军的中国男子球员，"
            "2026 年 2 月迪拜站后因伤停赛，本站是他五个月来的首场比赛。",
        ),
        moments=(
            ChampionMoment(
                date="2014-09",
                player="锦织圭",
                age="24 岁",
                headline="美网决赛，亚洲男子唯一一次",
                detail="半决赛击败德约科维奇后闯入决赛，最终负于西里奇；这是公开赛年代代表亚洲国家的男子球员唯一一次打进大满贯单打决赛。",
                source_url="https://en.wikipedia.org/wiki/Kei_Nishikori",
            ),
            ChampionMoment(
                date="2024-09",
                player="商竣程",
                age="19 岁",
                headline="成都首轮 6-4、6-4 胜锦织圭",
                detail="那一周他一路夺冠，成为公开赛年代第二位拿到 ATP 单打冠军的中国男子球员。",
                source_url="https://en.wikipedia.org/wiki/Shang_Juncheng",
            ),
        ),
        image_keys=(),
        source_label="两人维基百科条目 / ATP 官方赛会信息",
        image_credit="CGTN / ATP 官方赛会图",
        source_url="https://en.wikipedia.org/wiki/Shang_Juncheng",
    ),
    _trivia_story(
        slug="shang-rublev",
        title="商竣程第二轮VS卢布列夫",
        subtitle="赛事前瞻 · ATP 1000",
        identity="195 天来第一场胜利之后",
        chips=("ATP 1000", "第二轮", "第二次交手"),
        hero=(
            "商竣程在蒙特利尔首轮 6-3、6-3 击败巴列霍，那是他自 1 月澳网首轮以来的第一场胜利；"
            "第二轮对手是赛会 10 号种子卢布列夫，两人上一次交手是 2024 年 1 月香港站半决赛，"
            "18 岁的商竣程逼出第三盘后落败。"
        ),
        facts=(
            "商竣程 2005 年 2 月生，生涯最高世界第 47（2024 年 10 月），本周世界第 281；"
            "右脚伤病连续两个赛季拿走他的上半季，2026 年 2 月迪拜站后停赛五个月，"
            "7 月 27 日华盛顿首轮复出负于锦织圭。",
            "2026 年 8 月 2 日蒙特利尔首轮，商竣程 6-3、6-3 胜巴列霍，用时 1 小时 21 分，"
            "全场只被拿到一个破发点；他是当天第一个也是唯一一个赢下首轮的人，随后大雨中断比赛。",
            "卢布列夫 1997 年 10 月生，生涯 18 个 ATP 单打冠军，2021 年 9 月排到生涯最高世界第 5；"
            "2026 年 7 月 19 日在巴斯塔德夺得本赛季首冠，距上一个冠军已隔一年多。",
        ),
        moments=(
            ChampionMoment(
                date="2024-01",
                player="卢布列夫",
                age="26 岁",
                headline="香港半决赛，三盘胜商竣程",
                detail="两人至今唯一一次交手，卢布列夫打满三盘取胜；当时商竣程刚满 18 岁。",
                source_url="https://en.wikipedia.org/wiki/Shang_Juncheng",
            ),
            ChampionMoment(
                date="2026-08",
                player="商竣程",
                age="21 岁",
                headline="蒙特利尔首轮 6-3、6-3 胜巴列霍",
                detail="自 1 月 19 日澳网首轮之后的第一场胜利，中间隔了 195 天和一次五个月的伤停。",
                source_url="https://en.wikipedia.org/wiki/Shang_Juncheng",
            ),
        ),
        image_keys=(),
        source_label="两人维基百科条目 / ATP 官方赛会信息",
        image_credit="Wikimedia Commons / 加拿大通讯社",
        source_url="https://en.wikipedia.org/wiki/Shang_Juncheng",
    ),
    _trivia_story(
        slug="eala-mcnally",
        title="伊埃拉第三轮VS麦克纳莉",
        subtitle="赛事前瞻 · WTA 1000",
        identity="两条都在往上冲的曲线，首次交手",
        chips=("WTA 1000", "第三轮", "首次交手"),
        hero=(
            "伊埃拉八月三日拿下华盛顿站冠军、生涯首个巡回赛单打冠军，排名从第 28 跳到第 20；"
            "第三轮对手麦克纳莉本站二轮逆转淘汰了卫冕温网冠军诺斯科娃。两人巡回赛生涯从未交手。"
        ),
        facts=(
            "伊埃拉 2005 年 5 月生，2026 年 8 月 3 日华盛顿站决赛 4-6、6-4、6-0 逆转佩古拉夺冠，"
            "是公开赛年代第一位夺得 WTA 单打冠军的菲律宾球员；排名随即从第 28 升到第 20，"
            "为菲律宾历史最高。本站第二轮 6-1、4-6、6-2 胜帕克斯，六连胜，是队史第一次"
            "在本项赛事赢下正赛比赛。",
            "麦克纳莉 2001 年 11 月生，美国人，2023 年 5 月生涯排名升至第 54；随后因肘伤"
            "在 2024 年 3 月接受手术，缺赛九个月，复出时排名跌到一千开外，靠低级别赛事"
            "一点点爬回来。2026 年 6 月 22 日升至生涯新高世界第 50，超过伤前的最高排名。",
            "2026 年 8 月 5 日多伦多第二轮，麦克纳莉首盘一度 1-5 落后，抢七逆转，"
            "7-6(5)、6-1 淘汰卫冕温网冠军诺斯科娃，是她本赛季第 22 场胜利、生涯新高。"
            "两人此前从无交手记录，第三轮是巡回赛生涯第一次正面交锋。",
        ),
        moments=(
            ChampionMoment(
                date="2026-08-03",
                player="伊埃拉",
                age="21 岁",
                headline="华盛顿决赛逆转佩古拉，生涯首冠",
                detail="4-6、6-4、6-0 逆转夺冠，公开赛年代首位夺得 WTA 单打冠军的菲律宾球员，"
                "排名随即从第 28 升到第 20。",
                source_url="https://www.wtatennis.com/news/4555054/"
                "fresh-off-washington-title-eala-powers-into-toronto-third-round",
            ),
            ChampionMoment(
                date="2026-08-05",
                player="麦克纳莉",
                age="24 岁",
                headline="首盘 1-5 落后，抢七逆转诺斯科娃",
                detail="7-6(5)、6-1 淘汰卫冕温网冠军诺斯科娃，本赛季第 22 胜、生涯新高。",
                source_url="https://www.wtatennis.com/players/325725/caty-mcnally",
            ),
        ),
        image_keys=(),
        source_label="WTA 官方新闻稿 / WTA 官方球员资料",
        image_credit="WTA 官方图库",
        source_url="https://www.wtatennis.com/news/4555054/"
        "fresh-off-washington-title-eala-powers-into-toronto-third-round",
    ),
    _trivia_story(
        slug="venus-potapova",
        title="维纳斯首轮VS波塔波娃",
        subtitle="赛事前瞻 · WTA 500",
        identity="46 岁重返华盛顿站",
        chips=("WTA 500", "首轮", "首次交手"),
        hero=(
            "维纳斯·威廉姆斯以外卡身份重返华盛顿站，首轮对阵波塔波娃；"
            "一年前正是在这一站，45 岁的她赢下 2004 年之后 WTA 巡回赛最年长的单打胜利。"
        ),
        facts=(
            "2025 年 7 月华盛顿站，维纳斯 6-3、6-4 战胜斯特恩斯，成为自 2004 年温网"
            "纳芙拉蒂洛娃（47 岁）之后赢下 WTA 巡回赛单打的最年长球员；"
            "那也是她自 2023 年 8 月辛辛那提以来的首场单打胜利。",
            "维纳斯 1980 年 6 月生，7 座大满贯女单冠军（温网 5 次、美网 2 次）、"
            "4 枚奥运金牌，2002 年 2 月登上世界第一；2026 赛季至今尚无巡回赛单打胜绩。",
            "波塔波娃 2001 年 3 月生，2026 赛季起代表奥地利出战；"
            "2026 年马德里站以幸运落败者身份进入正赛并打进四强，"
            "为 1990 年分级制度确立以来首位打进 WTA 1000 四强的幸运落败者。",
        ),
        moments=(
            ChampionMoment(
                date="2025-07",
                player="维纳斯·威廉姆斯",
                age="45 岁",
                headline="华盛顿站 6-3、6-4 胜斯特恩斯",
                detail="2004 年温网纳芙拉蒂洛娃之后，WTA 巡回赛最年长的单打胜者。",
                source_url="https://en.wikipedia.org/wiki/Venus_Williams",
            ),
            ChampionMoment(
                date="2026-04",
                player="波塔波娃",
                age="25 岁",
                headline="马德里站幸运落败者打进四强",
                detail="资格赛末轮出局后递补进正赛，先后战胜莱巴金娜与普利斯科娃。",
                source_url="https://en.wikipedia.org/wiki/Anastasia_Potapova",
            ),
        ),
        image_keys=(),
        source_label="两人维基百科条目 / WTA 官方赛会信息",
        image_credit="Hameltion · CC BY-SA 4.0 · Wikimedia Commons",
        source_url="https://en.wikipedia.org/wiki/Venus_Williams",
    ),
    _trivia_story(
        slug="wong-lehecka",
        title="黄泽林16强VS莱赫奇卡",
        subtitle="赛事前瞻 · ATP 250",
        identity="世界第 108 对世界第 12",
        chips=("ATP 250", "16 强", "首次交手"),
        hero=(
            "洛斯卡沃斯站 16 强，香港一哥黄泽林对上头号种子莱赫奇卡；"
            "官方赛程把这场排在中心球场当地时间 18:00 的第一场，两人此前从未交手。"
        ),
        facts=(
            "黄泽林 2004 年 6 月生，2026 年 6 月 8 日升到生涯最高的世界第 108，"
            "是历来排名最高的香港男子球员；公开赛年代首位打进大满贯正赛、"
            "首位赢下大满贯正赛、首位打进大满贯第三轮、首位夺得挑战赛冠军的香港男子，"
            "四项纪录都在他名下。",
            "莱赫奇卡 2001 年 11 月生，捷克男子头号球员，2026 年 5 月 25 日"
            "升到生涯最高的世界第 12；同年 3 月以 21 号种子打进迈阿密大师赛决赛，"
            "那是他生涯第一个大师赛决赛，晋级路上发球局一次未被破，决赛负于辛纳。",
            "两人的名字此前只在同一张签表上出现过，从未交手；"
            "本站黄泽林签位不带任何标记，是按排名直接进入正赛，"
            "首轮 6-3、6-4 击败世界第 266 的布兰奇。",
        ),
        moments=(
            ChampionMoment(
                date="2023-09",
                player="黄泽林",
                age="19 岁",
                headline="杭州亚运会 16 强救 5 个赛点胜吴易昺",
                detail="6-4、3-6、7-6 淘汰当时世界第 98 的吴易昺，香港球员首次战胜世界前 100。",
                source_url=(
                    "https://www.scmp.com/sport/china/article/3235885/"
                    "asian-games-2023-coleman-wong-upsets-chinas-no-2-wu-yibing-"
                    "mens-singles-tennis-tournament-nail-biter"
                ),
            ),
            ChampionMoment(
                date="2025-08",
                player="黄泽林",
                age="21 岁",
                headline="美网从资格赛打进第三轮",
                detail="以世界第 173 连过三轮资格赛，正赛连胜科瓦切维奇与沃尔顿，"
                "成为首位打进大满贯第三轮的香港男子。",
                source_url="https://en.wikipedia.org/wiki/Coleman_Wong",
            ),
            ChampionMoment(
                date="2026-03",
                player="莱赫奇卡",
                age="24 岁",
                headline="迈阿密打进生涯首个大师赛决赛",
                detail="晋级路上发球局一次未被破发，决赛 4-6、4-6 不敌辛纳。",
                source_url="https://en.wikipedia.org/wiki/Ji%C5%99%C3%AD_Lehe%C4%8Dka",
            ),
        ),
        image_keys=(),
        source_label="两人维基百科条目 / 赛会官方 Order of Play / SCMP",
        image_credit="Eugene Lee · SCMP",
        source_url="https://en.wikipedia.org/wiki/Coleman_Wong",
    ),
    _trivia_story(
        slug="masters-format",
        title="大师赛为什么变两周",
        subtitle="网球观察 · 赛程篇",
        identity="扩容之后的退赛潮",
        chips=("赛程争议", "9 站中 7 站", "56→96"),
        hero=(
            "九站大师赛已有七站从一周改为十二天；2026 年蒙特利尔站开赛前一周，"
            "辛纳与德约科维奇双双退赛。"
        ),
        facts=(
            "九站 ATP 大师赛中已有七站改为十二天赛期，"
            "仅巴黎大师赛与蒙特卡洛大师赛仍保持一周；顶尖球员赛季跨越 11 个月。",
            "2025 年起，加拿大站与辛辛那提站将正赛签表由 56 人扩至 96 人，"
            "赛期相应延长至 12 天。",
            "2026 年蒙特利尔站赛前，辛纳与德约科维奇退赛，此前阿尔卡拉斯已退赛；"
            "赛事总监瓦莱丽·泰特罗表示尊重球员决定，"
            "但指出临时退赛日益频繁已成为项目层面的问题。",
        ),
        moments=(
            ChampionMoment(
                date="2026-07-24",
                player="辛纳 / 德约科维奇",
                age="2026 年",
                headline="双双退出蒙特利尔",
                detail=(
                    "加拿大网球协会宣布两人退出 8 月 1 日开赛的大师赛；"
                    "辛纳称与团队权衡后决定把健康放在第一位。"
                ),
                source_url=(
                    "https://www.nbcsports.com/tennis/news/"
                    "top-ranked-sinner-24-time-grand-slam-champ-djokovic-"
                    "withdraw-from-the-national-bank-open"
                ),
            ),
            ChampionMoment(
                date="2025-01-01",
                player="ATP",
                age="2025 年",
                headline="签表扩容至 96 人",
                detail="加拿大站与辛辛那提站正赛签表由 56 人扩至 96 人，赛期延长至 12 天。",
                source_url="https://en.wikipedia.org/wiki/2025_National_Bank_Open",
            ),
        ),
        image_keys=(),
        source_label="BBC / NBC Sports / 加拿大网协",
        image_credit="Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/ATP_Masters_1000",
    ),
    _trivia_story(
        slug="queue",
        title="温网的队要排一晚上",
        subtitle="网球冷知识 · 观赛篇",
        identity="一条有专名的队：The Queue",
        chips=("冷知识", "温网传统", "2003 编号"),
        hero=(
            "四大满贯里只有温网和法网，当天排队还能坐进主球场；"
            "代价是在草地上睡一晚。"
        ),
        facts=(
            "温网与法网是仅有的两项大满贯，无票观众可当天排队买到三块主球场的座位；"
            "排队卡自 2003 年起编号，2008 年起合并为单一队列，每块主球场约留 500 个座位。",
            "全英俱乐部允许通宵排队并为露宿者提供厕所与饮水；"
            "清晨队伍向场地移动时，引导员沿队发放按球场分色的腕带，"
            "凭腕带与票款在售票处换取门票。",
            "提前离场者退回的门票于下午 2:30 重新发售，所得捐予慈善；"
            "主球场的排队在八强赛结束后停止。",
        ),
        moments=(
            ChampionMoment(
                date="2010-06-28",
                player="Rose Stanley",
                age="2010 年",
                headline="第一百万张排队卡",
                detail=(
                    "2010 年温网第七个比赛日下午 2 点 40，"
                    "第 100 万张编号排队卡发给了来自南非的 Rose Stanley。"
                ),
                source_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
            ),
            ChampionMoment(
                date="2003-01-01",
                player="全英俱乐部",
                age="2003 年",
                headline="排队卡开始编号",
                detail="排队卡自此按顺序编号；2008 年起合并为单一队列。",
                source_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
            ),
        ),
        image_keys=(),
        source_label="全英俱乐部 / 维基百科",
        image_credit="Carine06 / Wikimedia Commons · CC BY-SA 2.0",
        source_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
    ),
    _trivia_story(
        slug="rufus",
        title="温网雇了一只鹰",
        subtitle="网球冷知识 · 园区篇",
        identity="工牌职位：赶鸟员",
        chips=("冷知识", "温网园区", "2008 上岗"),
        hero=(
            "温网有一名员工是哈里斯鹰，工牌上的职位写着 Bird Scarer；"
            "2012 年它被人从车里偷走，三天后在温布尔登公地找回。"
        ),
        facts=(
            "Rufus 生于 2008 年，同年 18 周大时首次在温网上岗，"
            "接替上一只鹰 Hamish；它有推特账号，也有自己的温网工牌，"
            "职位写作 Bird Scarer。",
            "全英俱乐部雇它全年巡视 42 英亩园区，赛期每日到岗；"
            "鸽子尤其爱停在中央球场屋顶。它也在 2012 年伦敦奥运会期间每天工作。",
            "2012 年 6 月 28 日它从车后座被偷，引发全球关注，"
            "三天后在温布尔登公地被找到并交给 RSPCA，仅一条腿略有酸痛。",
        ),
        moments=(
            ChampionMoment(
                date="2012-06-28",
                player="Rufus",
                age="2012 年",
                headline="被偷走三天",
                detail=(
                    "从车后座被偷；它的无线电发射器夜间会取下，因此无法追踪。"
                    "三天后在温布尔登公地被发现，身体健康。"
                ),
                source_url="https://en.wikipedia.org/wiki/Rufus_the_Hawk",
            ),
            ChampionMoment(
                date="2026-01-01",
                player="全英俱乐部",
                age="2026 年",
                headline="无人机会取代它吗",
                detail=(
                    "驯鹰师担心这份工作终将被无人机取代；"
                    "全英俱乐部表示没有替换它的打算。"
                ),
                source_url="https://en.wikipedia.org/wiki/Rufus_the_Hawk",
            ),
        ),
        image_keys=(),
        source_label="全英俱乐部 / 维基百科",
        image_credit="AvianEnvironmental / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Rufus_the_Hawk",
    ),
    _trivia_story(
        slug="wimbledon-whites",
        title="温网为什么只准穿白",
        subtitle="网球冷知识 · 规矩篇",
        identity="一条管到内衣的着装规定",
        chips=("冷知识", "温网传统", "1963 成文"),
        hero=(
            "白衣打网球比规则本身老得多；温网 1963 年把它写成规定，"
            "此后严到彩边不得超过 1 厘米。"
        ),
        facts=(
            "温网要求参赛者穿全白或近乎全白的服装，"
            "这条着装规定于 1963 年首次成文执行。",
            "细则严到：不得有整块色彩，彩色滚边不得超过 1 厘米，"
            "上衣或裙子的后背必须全白；短裤、帽子、发带、袜子与鞋面也须以白为主。",
            "2023 年起，女子选手首次获准穿非白色内衣——"
            "规则写明为“纯色、中/深色打底短裤，长度不超过其短裤或裙子”。",
        ),
        moments=(
            ChampionMoment(
                date="1963-01-01",
                player="全英俱乐部",
                age="1963 年",
                headline="着装规定首次成文",
                detail="温网把沿用已久的白衣传统写成规则，要求全白或近乎全白。",
                source_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
            ),
            ChampionMoment(
                date="2023-07-03",
                player="温布尔登",
                age="2023 年",
                headline="内衣松口",
                detail=(
                    "女子选手首次获准穿中/深色打底短裤，长度不超过短裤或裙子；"
                    "推动修改的是球员对生理期的顾虑。"
                ),
                source_url=(
                    "https://www.nytimes.com/athletic/4634722/2023/07/02/"
                    "wimbledon-period-all-white-dress-code/"
                ),
            ),
        ),
        image_keys=(),
        source_label="温网官方规则 / 维基百科",
        image_credit="Wikimedia Commons",
        source_url="https://en.wikipedia.org/wiki/Wimbledon_Championships",
    ),
    _trivia_story(
        slug="longest-match",
        title="11 小时 5 分钟",
        subtitle="网球冷知识 · 纪录篇",
        identity="一场打了三天的网球赛",
        chips=("网球有故事", "温网纪录", "70-68"),
        hero=(
            "2010 年温网首轮，伊斯内尔与马胡在 18 号球场打了三天："
            "决胜盘 70-68，全场 11 小时 5 分钟。"
        ),
        facts=(
            "五盘总比分是 6-4、3-6、6-7(7)、7-6(3)、70-68；"
            "全场共 183 局，光是决胜盘就打了 8 小时 11 分钟。",
            "决胜盘来到 50-50 时，电子记分牌已经撑不住；"
            "第二晚因天黑暂停时是 59-59，比赛计时刚好走到 10 小时。",
            "伊斯内尔全场发出 113 记 ACE。如今四大满贯若在决胜盘打到 6-6，"
            "统一改打 10 分抢十，必须领先两分才能结束。",
        ),
        moments=(
            ChampionMoment(
                date="2010-06-24",
                player="伊斯内尔 vs 马胡",
                age="第 3 天",
                headline="70-68，终于结束",
                detail=(
                    "马胡在 68-69、30-30 发球；伊斯内尔先用正手穿越拿到第五个赛点，"
                    "再以反手直线穿越结束了这场三日长跑。"
                ),
                source_url="https://www.wimbledon.com/en_GB/about/history/2010s",
            ),
            ChampionMoment(
                date="2022-03-16",
                player="四大满贯",
                age="2022 年",
                headline="决胜盘规则统一",
                detail=(
                    "大满贯委员会宣布统一决胜盘规则：6-6 后打 10 分抢十，"
                    "率先拿到 10 分且领先两分的一方获胜。"
                ),
                source_url=(
                    "https://www.usopen.org/en_US/news/articles/2022-03-16/"
                    "us_open_to_join_all_grand_slams_in_playing_"
                    "10point_final_set_tiebreak.html"
                ),
            ),
        ),
        image_keys=(),
        source_label="温网 / ITF / 大满贯官方档案",
        image_credit="BPI / Panoramic via Tennis Majors",
        source_url="https://www.wimbledon.com/en_GB/about/history/2010s",
        evidence_urls=(
            "https://www.wimbledon.com/en_GB/about/history/2010s",
            "https://www.itftennis.com/media/8242/"
            "2022-wimbledon-day-1-mens-match-notes.pdf",
            "https://www.usopen.org/en_US/news/articles/2022-03-16/"
            "us_open_to_join_all_grand_slams_in_playing_"
            "10point_final_set_tiebreak.html",
        ),
        diagram_type="marathon",
        hero_marker="2010",
        fact_roles=("record", "history", "rule"),
    ),
    _trivia_story(
        slug="hawkeye",
        title="鹰眼是怎么来的",
        subtitle="网球冷知识 · 科技篇",
        identity="从误判之夜到毫米级判罚",
        chips=("冷知识", "科技进化", "误差毫米级"),
        hero=(
            "让网球拥抱科技的，是一场糟糕的误判：2004 年美网小威"
            "遭遇连串错判出局；两年后，鹰眼挑战制走进大满贯。"
        ),
        facts=(
            "Sony/Hawk-Eye 官方说明：球追踪由 2D 视觉处理与 3D 三角测量组成，"
            "通常使用 8 至 12 台摄像机，最高 340fps，系统误差小于 2 毫米。",
            "2006 年国际网球赛事引入挑战规则：球员申请复核后，"
            "系统根据多个机位的数据生成轨迹与落点的 CG 可视化。",
            "截至 2026 年，四大满贯中只有法网仍保留人工司线、"
            "未采用实时电子司线；澳网、美网与温网均已完成转换。",
        ),
        moments=(
            ChampionMoment(
                date="2004-09-07",
                player="小威 vs 卡普里亚蒂",
                age="2004 美网",
                headline="改变历史的误判",
                detail=(
                    "1/4 决赛多个关键球肉眼误判，赛后当值主裁被撤换、"
                    "官方公开道歉——回放技术上马的最后一根稻草。"
                ),
                source_url=(
                    "https://www.usopen.org/en_US/news/articles/2018-04-18/"
                    "50_moments_that_mattered_hawkeye_instant_replay_makes_its_debut.html"
                ),
            ),
            ChampionMoment(
                date="2006-08-28",
                player="美国网球公开赛",
                age="2006 年",
                headline="鹰眼首秀大满贯",
                detail=(
                    "挑战制正式上线，首年球员挑战成功率仅三成上下——"
                    "数据证明，肉眼真的会看错。"
                ),
                source_url=(
                    "https://www.usopen.org/en_US/news/articles/2018-04-18/"
                    "50_moments_that_mattered_hawkeye_instant_replay_makes_its_debut.html"
                ),
            ),
        ),
        image_keys=("usopen",),
        source_label="Sony / ITF / 大满贯资料",
        image_credit="Daniel (Galashiels) / Wikimedia Commons · CC BY 2.0",
        source_url=(
            "https://www.sony.com/en/SonyInfo/technology/stories/entries/Hawk-Eye/"
        ),
        evidence_urls=(
            "https://www.sony.com/en/SonyInfo/technology/stories/entries/Hawk-Eye/",
            "https://www.itftennis.com/media/12242/line-calling.pdf",
            "https://www.usopen.org/en_US/news/articles/2018-04-18/"
            "50_moments_that_mattered_hawkeye_instant_replay_makes_its_debut.html",
            "https://www.wimbledon.com/en_GB/atoz/umpires.html",
            "https://www.lequipe.fr/Tennis/Actualites/-mettre-a-l-honneur-l-excellence-"
            "de-l-arbitrage-francais-le-dernier-bastion-en-grand-chelem-resiste-il-y-aura-"
            "encore-des-juges-de-ligne-a-roland-garros-en-2026/1597696",
        ),
        diagram_type="trajectory",
        fact_roles=("technology", "rule", "today"),
    ),
    _trivia_story(
        slug="golden-slam",
        title="金满贯有多难",
        subtitle="网球冷知识 · 荣誉篇",
        identity="1988 年，格拉芙做到了唯一",
        chips=("冷知识", "荣誉体系", "史上仅 1 人"),
        hero=(
            "同一年拿下四大满贯，再加一枚奥运金牌——'年度金满贯'"
            "网球史上只有一个人做到过：1988 年的格拉芙。"
        ),
        facts=(
            "'大满贯'一词借自桥牌术语，1933 年被记者首次用于网球——"
            "从此成为这项运动的最高标准。",
            "年度全满贯史上仅 5 人：巴奇、康诺利、拉沃尔（两次）、"
            "考特与格拉芙；公开赛时代男子只有拉沃尔在 1969 年完成。",
            "把标准放宽到'生涯金满贯'，男子也只有阿加西、纳达尔、"
            "德约科维奇三人集齐。",
        ),
        moments=(
            ChampionMoment(
                date="1969-09-08",
                player="罗德·拉沃尔",
                age="31 岁",
                headline="第二次年度全满贯",
                detail=(
                    "美网决赛胜罗切封王，公开赛时代唯一的年度全满贯——"
                    "墨尔本的中央球场后来以他命名。"
                ),
                source_url=(
                    "https://www.itftennis.com/en/tournament/us-open/usa/1969/"
                    "m-sl-usa-01a-1969/champions/"
                ),
            ),
            ChampionMoment(
                date="1988-10-01",
                player="施特菲·格拉芙",
                age="19 岁",
                headline="史上唯一金满贯",
                detail=(
                    "汉城奥运决赛击败萨巴蒂尼，把四大满贯与奥运金牌装进同一年——"
                    "19 岁的赛季，前无古人，至今无来者。"
                ),
                source_url="https://www.itftennis.com/en/events/olympics-la-2028/statistics/",
            ),
        ),
        image_keys=("usopen",),
        source_label="US Open / ITF / 奥运官方档案",
        image_credit="Photocapy / Wikimedia Commons · CC BY-SA 2.0",
        source_url=(
            "https://www.usopen.org/en_US/news/articles/2018-08-20/"
            "2018-08-20_50_moments_that_mattered_steffi_graf_wins_"
            "calendaryear_grand_slam.html"
        ),
        evidence_urls=(
            "https://www.usopen.org/en_US/visit/grand_slam_alltime_champions.html",
            "https://www.usopen.org/en_US/visit/year_by_year.html",
            "https://www.itftennis.com/en/tournament/us-open/usa/1969/"
            "m-sl-usa-01a-1969/champions/",
            "https://www.itftennis.com/en/events/olympics-la-2028/statistics/",
            "https://www.itftennis.com/en/news-and-media/articles/"
            "nervous-at-past-olympics-djokovic-primed-for-golden-slam-charge/",
        ),
        hero_marker="1988",
        fact_roles=("surface", "cycle", "trophy"),
    ),
    _trivia_story(
        slug="surfaces",
        title="红土、草地、硬地",
        subtitle="网球冷知识 · 场地篇",
        identity="三种场地，三种网球",
        chips=("冷知识", "场地科学", "三种脾气"),
        hero=(
            "法网的红土其实只有约 2 毫米厚，温网的草被精确修剪到 8 毫米——"
            "场地的物理差异，造就了三种完全不同的网球。"
        ),
        facts=(
            "罗兰·加洛斯的'红土'是白色石灰岩上铺的一层红砖粉——"
            "球速慢、弹跳高，最考验耐心与上旋。",
            "温网草地是 100% 黑麦草、恒定 8 毫米——球速快、弹跳低，"
            "发球上网曾在这里统治几十年。",
            "纳达尔在法网 112 胜 4 负、14 次夺冠——单一赛事的统治力之最，"
            "'红土之王'的战绩大概率无人再能接近。",
        ),
        moments=(
            ChampionMoment(
                date="1988-01-11",
                player="澳大利亚网球公开赛",
                age="1988 年",
                headline="草地改硬地",
                detail=(
                    "澳网告别草地、搬进墨尔本公园——"
                    "四大满贯从此三种材质各领风骚。"
                ),
                source_url="https://en.wikipedia.org/wiki/1988_Australian_Open",
            ),
            ChampionMoment(
                date="2005-06-05",
                player="拉斐尔·纳达尔",
                age="19 岁",
                headline="红土王朝开篇",
                detail=(
                    "首次参加法网即夺冠——此后近二十年，"
                    "他在这片红土上总共只输过 4 场球。"
                ),
                source_url="https://en.wikipedia.org/wiki/2005_French_Open",
            ),
        ),
        image_keys=("canada",),
        source_label="四大满贯官方史料",
        image_credit="JC / Wikimedia Commons · CC BY-SA 2.0",
        source_url="https://en.wikipedia.org/wiki/Tennis_court",
    ),
    _trivia_story(
        slug="big-three",
        title="三巨头的数字",
        subtitle="网球冷知识 · 时代篇",
        identity="费德勒 · 纳达尔 · 德约科维奇",
        chips=("冷知识", "时代档案", "66 座大满贯"),
        hero=(
            "66 座大满贯、连续 18 年的年终第一——'三巨头'统治男子网坛"
            "二十年，这样的时代此前没有过，此后大概率也不会再有。"
        ),
        facts=(
            "费德勒 20 冠、纳达尔 22 冠、德约科维奇 24 冠，"
            "三人合计 66 座大满贯，约占同期大满贯总数的八成。",
            "年终第一连续 18 年被三巨头与穆雷包揽，"
            "直到 2022 年阿尔卡拉斯打破。",
            "德约与纳达尔互为最熟悉的对手，60 次交手创下"
            "男子对决之最（德约 31-29）。",
        ),
        moments=(
            ChampionMoment(
                date="2008-07-06",
                player="费德勒 vs 纳达尔",
                age="温网决赛",
                headline="被称为史上最伟大一战",
                detail=(
                    "4 小时 48 分钟、两度因雨中断，纳达尔暮色中 9-7 "
                    "拿下决胜盘，终结费德勒温网五连冠。"
                ),
                source_url=(
                    "https://www.espn.com/tennis/story/_/id/23977542/"
                    "roger-federer-rafael-nadal-epic-2008-wimbledon-final"
                ),
            ),
            ChampionMoment(
                date="2012-01-29",
                player="德约科维奇 vs 纳达尔",
                age="澳网决赛",
                headline="大满贯最长决赛",
                detail=(
                    "5 小时 53 分钟的鏖战，颁奖礼上两人累得站不住，"
                    "主办方搬来了椅子——这项纪录保持至今。"
                ),
                source_url=(
                    "https://www.espn.com/tennis/aus12/story/_/id/7515950/"
                    "2012-australian-open-novak-djokovic-outlasts-rafael-nadal-"
                    "longest-grand-slam-final"
                ),
            ),
            ChampionMoment(
                date="2019-07-14",
                player="德约科维奇 vs 费德勒",
                age="温网决赛",
                headline="温网首个决胜盘抢七",
                detail=(
                    "费德勒决胜盘曾手握 2 个冠军点未能兑现，德约 13-12(3) "
                    "逆转夺冠，创下温网首个决胜盘抢七。"
                ),
                source_url=(
                    "https://www.forbes.com/sites/adamzagoria/2019/07/14/"
                    "wimbledon-novak-djokovics-championship-win-over-roger-"
                    "federer-by-the-numbers/"
                ),
            ),
        ),
        image_keys=("cincinnati",),
        source_label="ATP / 大满贯官方史料",
        image_credit="Getty Images / Imagn via Sports Illustrated",
        source_url=(
            "https://www.espn.com/tennis/story/_/id/29190340/"
            "novak-djokovic-prediction-breaking-roger-federer-grand-slam-"
            "title-record-point"
        ),
        fact_roles=("", "turning_point", ""),
    ),
    _trivia_story(
        slug="china-tennis",
        title="中国网球这二十年",
        subtitle="网球冷知识 · 中国篇",
        identity="从雅典首金到巴黎单打金牌",
        chips=("冷知识", "中国军团", "2004-2024"),
        hero=(
            "2004 年雅典，李婷/孙甜甜拿下中国网球的奥运首金；"
            "二十年后的巴黎，郑钦文把单打金牌也带回了中国。"
        ),
        facts=(
            "2011 年法网李娜夺冠，成为首位大满贯单打冠军的亚洲球员，"
            "国内超过 1 亿人观看了那场决赛；2019 年她入选国际网球名人堂。",
            "李娜效应带动金花集体爆发：如今每个赛季都有约 10 位"
            "中国女将征战 WTA 巡回赛正赛，武汉、北京均有高级别赛事。",
            "男子也在破冰：2023 年吴易昺在达拉斯夺冠，成为公开赛时代"
            "首位拿到 ATP 巡回赛单打冠军的中国大陆男球员。",
        ),
        moments=(
            ChampionMoment(
                date="2011-06-04",
                player="李娜",
                age="29 岁",
                headline="亚洲首个大满贯单打冠军",
                detail=(
                    "法网决赛击败卫冕冠军斯齐亚沃尼——"
                    "'中国一姐'把亚洲网球带进了新纪元。"
                ),
                source_url="https://en.wikipedia.org/wiki/Li_Na",
            ),
            ChampionMoment(
                date="2024-08-03",
                player="郑钦文",
                age="21 岁",
                headline="奥运单打金牌",
                detail=(
                    "巴黎红土连克强敌，为中国拿下奥运网球单打首金——"
                    "距离雅典的首金恰好二十年。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_"
                    "%E2%80%93_Women%27s_singles"
                ),
            ),
        ),
        image_keys=("canada",),
        source_label="中国网球协会 / 奥运官方档案",
        image_credit="Création CARAVEO / Wikimedia Commons · CC BY 2.0",
        source_url="https://en.wikipedia.org/wiki/Li_Na",
    ),
    _trivia_story(
        slug="svitolina-handshake",
        title="她的握手线，怎么划的",
        subtitle="网球观察 · 人物篇",
        identity="斯维托丽娜的握手界限",
        chips=("网球礼仪", "斯维托丽娜", "2026"),
        hero=(
            "都是俄罗斯出身，为什么握手的只有一个？八月七号，多伦多，"
            "斯维托丽娜六比一、六比一横扫波塔波娃后转身离场——没有握手。"
            "这不是 WTA 的规定，是她四年没变过的一条线，而这条线**不是按国籍画的**。"
        ),
        facts=(
            "斯维托丽娜从 2022 年俄罗斯全面入侵乌克兰起，不与俄罗斯、白俄罗斯出身的"
            "选手握手，四年未变；WTA 没有把这写成规则，也没有因此处罚过任何一方，"
            "官方的说法是尊重选手的选择。",
            "她的界限按时间点和表态画：2018 年就改籍哈萨克斯坦的莱巴金娜、"
            "公开反对战争的卡萨金娜，她都握手；2025 年底才改籍奥地利、"
            "没有公开表过态的波塔波娃，不握。她自己说过，莱巴金娜改籍是"
            "很多年前的事，早在战争和入侵开始之前。",
            "2026 年 1 月 29 日澳网半决赛，她同样没有和萨巴伦卡握手——"
            "这不是这次才有的事，赛事方后来专门在大屏幕上提前告知观众。",
            "同一届澳网第四轮，米拉·安德烈耶娃因为遵守斯维托丽娜的意愿没有上前"
            "握手，反而被不知情的观众当场狂嘘，误以为她耍大牌——这条不成文的"
            "规矩，看台常常猜不透。",
        ),
        moments=(
            ChampionMoment(
                date="2026-08-07", player="斯维托丽娜", age="—",
                headline="多伦多第三轮 6-1 6-1 胜波塔波娃后无握手",
                detail=(
                    "全场用时一小时，赛后她朝观众挥手离场，"
                    "波塔波娃留在网前收拾装备。"
                ),
                source_url="https://www.youtube.com/watch?v=NryVymv9AMY",
            ),
            ChampionMoment(
                date="2026-01-29", player="斯维托丽娜", age="—",
                headline="澳网半决赛负于萨巴伦卡，同样无握手",
                detail="赛事方提前在大屏幕上告知观众，本场赛后不会有握手环节。",
                source_url=(
                    "https://www.foxnews.com/sports/aryna-sabalenka-addresses-"
                    "ukrainian-opponents-decision-skip-handshake-after-australian-"
                    "open-semifinal"
                ),
            ),
            ChampionMoment(
                date="2026-01", player="米拉·安德烈耶娃", age="—",
                headline="澳网第四轮不敌斯维托丽娜后未握手，被观众嘘下场",
                detail="她遵守对方的意愿转身离场，现场观众误以为她失礼。",
                source_url=(
                    "https://www.gbnews.com/sport/tennis/australian-open-mirra-"
                    "andreeva-elina-svitolina-2675023544"
                ),
            ),
        ),
        image_keys=(),
        source_label="WTA 官方 / 澳网官方 / tennis.com 综合整理",
        image_credit="WTA 官方集锦画面",
        source_url="https://www.youtube.com/watch?v=NryVymv9AMY",
    ),
    _trivia_story(
        slug="cramp-timeout",
        title="抽筋，为何叫不来暂停",
        subtitle="网球冷知识 · 规则篇",
        identity="从勒纳·钱的三个赛点说起",
        chips=("冷知识", "医疗暂停", "理疗师说了算"),
        hero=(
            "蒙特利尔第三轮，勒纳·钱在三个赛点上抽筋，一个没保住，最终还是赢下了比赛——"
            "网球规则里，抽筋从来换不来一次医疗暂停，能给的只有换边和盘间那几十秒。"
        ),
        facts=(
            "ATP 2026 规则书原话：球员只能在换边和盘间的时间里接受抽筋治疗，"
            "不能为抽筋申请医疗暂停；一般性体能疲劳同样不算需要治疗的情况。",
            "这条规则始于 2010 年 1 月——此前的旧规则允许抽筋申请完整的医疗暂停，"
            "2009 年美网阿尔马格罗曾据此在比赛中叫停治疗，此后规则被收紧到今天这版。",
            "遇到分不清是急性伤还是抽筋的情况，规则明文交给现场理疗师认定，"
            "理疗师的判断是最终结果——2026 年澳网男单半决赛，"
            "阿尔卡拉斯与兹维列夫就在这条线上当场起过争执。",
        ),
        moments=(
            ChampionMoment(
                date="2026-08-08", player="勒纳·钱 vs 保罗", age="2026 蒙特利尔 R3",
                headline="三个赛点丢在抽筋那一局",
                detail=(
                    "第二盘五比一、四十比零，他的右腿开始抽筋，连丢三个赛点被追至五比二；"
                    "缓过来后破发保罗，第四个赛点六比二锁定比赛。"
                ),
                source_url=(
                    "https://tennisuptodate.com/atp/dont-tell-me-that-why-are-you-"
                    "telling-me-that-now-learner-tien-shares-funny-moment-with-tommy-"
                    "paul-after-ruthless-win"
                ),
            ),
            ChampionMoment(
                date="2026-01", player="阿尔卡拉斯 vs 兹维列夫", age="2026 澳网男单半决赛",
                headline="医疗暂停给没给，现场就吵了起来",
                detail=(
                    "第三盘四比四，阿尔卡拉斯叫了医疗暂停，兹维列夫当场向主裁抗议，"
                    "认定那是不该给暂停的抽筋；阿尔卡拉斯的说法是局部急性痛。"
                ),
                source_url=(
                    "https://www.tennis.com/news/articles/this-is-bulls-alexander-"
                    "zverev-fumes-about-then-accepts-carlos-alcaraz-cramp-drama-at-"
                    "australian-open"
                ),
            ),
        ),
        image_keys=(),
        image_credit="ATP Tour 官方集锦画面",
        source_label="ATP 2026 官方规则书 / Tennis.com",
        source_url="https://www.itftennis.com/media/15604/atp-2026-rulebook.pdf",
        evidence_urls=(
            "https://www.itftennis.com/media/15604/atp-2026-rulebook.pdf",
            "https://tennisuptodate.com/atp/dont-tell-me-that-why-are-you-telling-"
            "me-that-now-learner-tien-shares-funny-moment-with-tommy-paul-after-"
            "ruthless-win",
            "https://www.tennis.com/news/articles/this-is-bulls-alexander-zverev-"
            "fumes-about-then-accepts-carlos-alcaraz-cramp-drama-at-australian-open",
            "https://www.tennis.com/news/articles/new-cramping-rule-in-effect-in-"
            "melbourne",
        ),
        fact_roles=("rule", "history", "today"),
    ),
)


def _load_state() -> dict[str, str]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _recently_used(slug: str, today: date, state: dict[str, str] | None = None) -> bool:
    last_str = (state if state is not None else _load_state()).get(slug)
    if not last_str:
        return False
    try:
        last = date.fromisoformat(last_str)
    except ValueError:
        return False
    return (today - last).days < COOLDOWN_DAYS


def find_story_by_slug(slug: str) -> TournamentStory | None:
    """Look up a curated story by its exact slug, for ad-hoc/manual generation
    outside the normal editorial-relevance ranking."""
    return next((story for story in STORIES if story.slug == slug), None)


def mark_story_used(slug: str, today: date) -> None:
    """记录故事已使用（由 CLI 在生成成功后调用，data/ 随 workflow 提交）."""
    state = _load_state()
    state[slug] = today.isoformat()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


# Reserved (non-slug) marker keys in story_state.json. The leading/trailing
# underscores keep them out of the slug namespace so slug lookups
# (`state.get(story.slug)`) never collide with them.
ADHOC_KNOWLEDGE_KEY = "__knowledge_adhoc_date__"


def mark_adhoc_knowledge_published(today: date) -> None:
    """Record that the manual / hotspot ad-hoc flow published a knowledge post today.

    The daily digest auto-selects and pushes its own knowledge post; the
    manual ad-hoc flow is a second, independent producer. Without a shared
    signal both can land the same day, so a deliberate ad-hoc post gets
    shadowed by an auto-selected one (the owner's "怎么又推了一条" surprise).

    Only the ad-hoc flow WRITES this marker, and only the daily flow READS it
    (see ``adhoc_knowledge_published_on``): the daily auto-knowledge steps down
    when an ad-hoc post already covered today, while a hotspot ad-hoc post can
    always go out regardless of what the daily flow did.
    """
    state = _load_state()
    state[ADHOC_KNOWLEDGE_KEY] = today.isoformat()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def adhoc_knowledge_published_on(today: date) -> bool:
    """True if the ad-hoc flow already published a knowledge post on ``today``."""
    return _load_state().get(ADHOC_KNOWLEDGE_KEY) == today.isoformat()


def _norm(text: str) -> str:
    """去音符 + casefold，与 ESPN 无音符英文名对得上（Świątek → swiatek）."""
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    ).casefold()


def _matched(aliases: tuple[str, ...], names: set[str]) -> bool:
    return any(alias in name for alias in aliases for name in names)


def story_matches_match(story: TournamentStory, match) -> bool:
    """Only attach a story when it directly explains the daily lead match."""
    if story.kind == "trivia":
        return False
    aliases = tuple(_norm(alias) for alias in story.aliases)
    if story.kind == "player":
        subjects = {_norm(player.name) for player in match.home + match.away}
    else:
        subjects = {
            _norm(match.tournament.name),
            _norm(getattr(match.tournament, "name_zh", "") or ""),
        }
    return _matched(aliases, subjects)


def direct_story_for_match(
    match,
    *,
    prefer_player: bool = True,
) -> TournamentStory | None:
    """Return reviewed context directly connected to one match.

    Unlike ``pick_tournament_story`` this helper is deterministic and ignores
    cooldown state, so previews, covers, and evidence pages can reuse the same
    verified player or tournament identity without rotating to unrelated lore.
    """
    matches = [story for story in STORIES if story_matches_match(story, match)]
    if not matches:
        return None
    matches.sort(
        key=lambda story: (
            0 if (prefer_player and story.kind == "player") else 1,
            0 if story.kind == "tournament" else 1,
        )
    )
    return matches[0]


def _match_drama(m) -> float:
    """比赛本身的事件性：伤退、爆冷、鏖战——这些热度同样属于输球一方."""
    from ..models import MatchStatus
    from .rating import is_upset, went_to_deciding_set

    drama = 0.0
    if m.status is MatchStatus.RETIRED:
        drama += 1.5  # 伤退：坚持到退赛的一方往往才是新闻主角
    try:
        if is_upset(m):
            drama += 1.0  # 爆冷：被掀翻的种子也是话题
    except Exception:  # noqa: BLE001
        pass
    sets = m.sets or []
    if went_to_deciding_set(m):
        drama += 0.4  # 打满盘数
        last = sets[-1]
        super_tb = {last.home, last.away} == {1, 0}
        if super_tb or max(last.home, last.away) == 7 or last.home_tiebreak is not None:
            drama += 0.5  # 决胜盘抢七/抢十
    return drama


# 输球方也值得讲的事件性阈值（伤退或爆冷即达标）
DRAMA_THRESHOLD = 1.0


_TRIVIA_TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "scoring-history": (
        "15-30-40",
        "deuce",
        "scoring system",
        "计分",
        "平分",
    ),
    "yellow-ball": ("yellow ball", "white ball", "ball colour", "黄球", "白球"),
    "longest-match": (
        "isner",
        "mahut",
        "longest match",
        "marathon match",
        "70-68",
        "five-set",
        "五盘",
        "长盘",
        "马拉松",
    ),
    "hawkeye": (
        "hawk-eye",
        "hawkeye",
        "electronic line calling",
        "line call",
        "challenge system",
        "鹰眼",
        "电子司线",
        "误判",
    ),
    "golden-slam": (
        "golden slam",
        "olympic",
        "steffi graf",
        "gold medal",
        "金满贯",
        "奥运",
        "格拉芙",
    ),
    "surfaces": (
        "clay court",
        "grass court",
        "hard court",
        "red clay",
        "红土",
        "草地",
        "硬地",
    ),
    "big-three": (
        "federer",
        "nadal",
        "djokovic",
        "费德勒",
        "纳达尔",
        "德约科维奇",
    ),
    "china-tennis": (
        "zheng qinwen",
        "li na",
        "wang xinyu",
        "yuan yue",
        "zhang zhizhen",
        "郑钦文",
        "李娜",
        "王欣瑜",
        "袁悦",
        "张之臻",
    ),
}

# 没有可靠实时信号时，优先选择普通读者一眼能理解、天然有悬念的主题。
_TRIVIA_VIRAL_PRIOR: dict[str, float] = {
    "longest-match": 10.0,
    "golden-slam": 9.0,
    "big-three": 8.0,
    "china-tennis": 7.0,
    "hawkeye": 6.0,
    "scoring-history": 5.0,
    "surfaces": 4.0,
    "yellow-ball": 3.0,
}


def _trivia_topic_score(story: TournamentStory, digest: Digest) -> float:
    """Rank evergreen knowledge by live relevance, then natural shareability."""
    score = _TRIVIA_VIRAL_PRIOR.get(story.slug, 0.0)
    terms = tuple(_norm(term) for term in _TRIVIA_TOPIC_TERMS.get(story.slug, ()))
    best_live_signal = 0.0
    for match in digest.results + digest.live + digest.schedule:
        signals = [item for item in match.trend_signals if isinstance(item, dict)]
        signal_text = " ".join(
            str(value)
            for signal in signals
            for value in signal.values()
            if isinstance(value, (str, int, float))
        )
        players = [*match.home, *match.away]
        context = _norm(
            " ".join(
                [
                    match.tournament.name,
                    *(player.name for player in players),
                    signal_text,
                ]
            )
        )
        heat = min(70.0, float(match.media_heat + match.search_heat))
        source_bonus = min(12.0, len(signals) * 3.0)
        hits = sum(1 for term in terms if term and term in context)
        live_signal = 0.0
        if hits:
            live_signal = 36.0 + heat + source_bonus + min(12.0, hits * 3.0)

        countries = {str(player.country or "").upper() for player in players}
        if story.slug == "china-tennis" and "CHN" in countries:
            live_signal = max(live_signal, 42.0 + heat + source_bonus)
        if story.slug == "longest-match":
            long_set = any(max(item.home, item.away) > 7 for item in (match.sets or []))
            if len(match.sets or []) >= 5 or long_set:
                live_signal = max(live_signal, 38.0 + heat + source_bonus)

        best_live_signal = max(best_live_signal, live_signal)

    # 相关新闻本身也是热点：命中选题关键词的官方/媒体新闻，即使没有绑定到
    # 当日任何一场比赛，也应把该选题顶上来（例如某球员退役公告、某项纪录被
    # 打破、某条规则改革见报）。
    # ⚠️ 这个全局池原来由 `cmd_digest` 从趋势雷达写入，而 cmd_digest 在
    # 2026-07-31 随日报一起删了——**现在没有任何调用方填它**，这一段恒为空。
    # 代码留着是因为它本身是对的（谁填谁受益）。
    #
    # **2026-08-02 账号所有者定了：不接。** 知识帖是常青内容不是新闻；而真正
    # 影响中国观众的那点当日相关性，不吃趋势信号的三条规则已经抓到了——选题词
    # 命中当天赛事/球员名、有中国球员上场 +42、出现五盘或长盘 +38。为一条每天
    # 只出一条、现在跑得稳的线加联网依赖（选题那一刻要抓 feed，慢且会抖）
    # 不划算。所以这一段**是故意空着的，不是漏了**。
    #
    # ⚠️ 哪天改主意，别选「让内容雷达把信号落盘、知识帖读那个文件」那条路——
    # 它看着最省事，但正是 golden-slam 那个 bug 的形状：一条线写、另一条线读
    # 同一份状态，出事的时候两边都觉得自己没错。要接就让这条线自己去抓。
    news_pool = getattr(digest, "trend_signals", None) or []
    news_signal = 0.0
    for signal in news_pool:
        if not isinstance(signal, dict):
            continue
        text = _norm(
            " ".join(
                str(value)
                for value in signal.values()
                if isinstance(value, (str, int, float))
            )
        )
        hits = sum(1 for term in terms if term and term in text)
        if not hits:
            continue
        base = 34.0 if str(signal.get("kind", "")) == "official-news" else 30.0
        news_signal = max(news_signal, base + min(12.0, hits * 4.0))
    best_live_signal = max(best_live_signal, news_signal)
    return score + best_live_signal


def story_selection_evidence(story: TournamentStory, digest: Digest) -> dict:
    """Explain the deterministic editorial signals used by GitHub Actions."""
    evidence = {
        "kind": story.kind,
        "candidate_slug": story.slug,
        "result_count": len(digest.results),
        "live_count": len(digest.live),
        "schedule_count": len(digest.schedule),
    }
    if story.kind != "trivia":
        evidence["selection_basis"] = (
            "current player or tournament relevance, match news value, and recency"
        )
        return evidence

    prior = _TRIVIA_VIRAL_PRIOR.get(story.slug, 0.0)
    topic_score = _trivia_topic_score(story, digest)
    matches = digest.results + digest.live + digest.schedule
    signal_count = sum(len(match.trend_signals) for match in matches)
    heat_total = float(sum(match.media_heat + match.search_heat for match in matches))
    # 说清楚是哪一支在排序。`media_heat` / `search_heat` / `trend_signals`
    # 只有 apply_trend_signals() 会写，而它只挂在 `tennislive content` 上；
    # 知识帖这条路不跑它，于是这三维恒为空——**兜底那一支 100% 命中，
    # 而原来的话术说的是「信号优先」**。两句写死成一句的时候，
    # 「今天没有信号」和「这条路从不看信号」在台账上长得一模一样，
    # 2026-08-02 金满贯那次就是这么混过去的（trend_signal_count 记着 0，
    # 而 basis 还写着 live signals first，没人看得出差别在哪）。
    evidence.update(
        {
            "selection_basis": (
                "live media/search signals first; intrinsic curiosity and "
                "shareability provide the no-signal fallback"
                if signal_count or heat_total
                else "no media/search signals attached on this path; ranked on "
                "match context, intrinsic curiosity, shareability and cooldown"
            ),
            "viral_prior": prior,
            "topic_score": topic_score,
            "live_relevance_score": max(0.0, topic_score - prior),
            "trend_signal_count": signal_count,
            "media_search_heat": heat_total,
        }
    )
    return evidence


def _result_heat(
    digest: Digest,
) -> tuple[dict[str, float], dict[str, float], set[str]]:
    """昨日热度：球员/赛事 -> 最重要一场比赛的评分 + 事件戏剧性.

    返回 (球员热度, 赛事热度, 高事件性比赛的输球方)——伤退、遭爆冷、
    鏖战惜败的一方与胜者同样有新闻价值。
    """
    from .rating import match_score

    player_heat: dict[str, float] = {}
    tournament_heat: dict[str, float] = {}
    newsworthy_losers: set[str] = set()
    for m in digest.results:
        try:
            base = float(match_score(m, cn_boost=False))
        except Exception:  # noqa: BLE001
            base = 0.0
        drama = _match_drama(m)
        heat = base + drama + (m.media_heat + m.search_heat) / 5
        key = _norm(m.tournament.name)
        tournament_heat[key] = max(heat, tournament_heat.get(key, 0.0))
        for p in m.winner_players() or []:
            name = _norm(p.name)
            player_heat[name] = max(heat, player_heat.get(name, 0.0))
        if drama >= DRAMA_THRESHOLD:
            for p in m.loser_players() or []:
                name = _norm(p.name)
                player_heat[name] = max(heat, player_heat.get(name, 0.0))
                newsworthy_losers.add(name)
    return player_heat, tournament_heat, newsworthy_losers


def _alias_heat(aliases: tuple[str, ...], heat: dict[str, float]) -> float:
    return max(
        (value for name, value in heat.items() if any(a in name for a in aliases)),
        default=0.0,
    )


def pick_tournament_story(digest: Digest) -> TournamentStory | None:
    """按新闻价值选故事，板块永不空着.

    昨日高光球员特写 3（赢球，或虽败但比赛本身是事件——伤退/遭爆冷/
    鏖战）> 进行中赛事档案 2 > 仅出场的球员特写 1 > 冷知识兜底 0；
    同级候选按前一天比赛的热度分排序（决赛/爆冷/伤退优先），
    全部处于冷却期时，重讲距上次最久的一条，而不是留白。
    """
    candidates = tournament_story_candidates(digest)
    return candidates[0] if candidates else None


def is_anniversary(story: TournamentStory, today: date) -> bool:
    """今天是不是这条「历史上的今天」的正日子."""
    return (
        story.kind == "trivia"
        and story.slug.startswith("otd-")
        and story.slug.endswith(today.strftime("%m%d"))
    )


def story_ranking(digest: Digest) -> list[dict]:
    """每条故事的参选结果：分档、得分、名次，落选的带原因。

    单独抽出来是因为产物里只留"谁赢了"不够。7/25 那天 `otd-0725` 的四道闸门
    （图在、日期对、未冷却、trivia）离线复算全部通过，却没上；而落盘的
    `rejected_candidates` 是空的——它根本没被生产环节试过。只记胜者的时候，
    "今天没有历史今天"和"有但没轮到它"长得一模一样。
    """
    matches = digest.results + digest.live + digest.schedule
    tournaments = {_norm(m.tournament.name) for m in matches}
    winners = {
        _norm(p.name) for m in digest.results for p in (m.winner_players() or [])
    }
    todays = {_norm(p.name) for m in matches for p in m.home + m.away}
    player_heat, tournament_heat, newsworthy_losers = _result_heat(digest)
    headliners = winners | newsworthy_losers
    state = _load_state()
    today_iso = digest.today.isoformat()

    # 同日重跑幂等：当天已定的故事直接复用，避免重生成时轮换换卡。
    # 纪念日不吃这条——见下面 anniversary 分档。
    pinned_slugs = {
        story.slug
        for story in STORIES
        if state.get(story.slug) == today_iso and story.image.exists()
    }

    records: list[dict] = []
    for order, story in enumerate(STORIES):
        # 每条都带齐同一套字段（落选的 rank/score 留 None）——读这份台账的
        # jq 不该为了"这个键在不在"分两种写法。
        record: dict = {
            "story_slug": story.slug,
            "title": story.title,
            "kind": story.kind,
            "pinned": story.slug in pinned_slugs,
            "last_used": state.get(story.slug, ""),
            "rank": None,
            "score": None,
            "heat": None,
            "reason": "",
        }

        def drop(reason: str) -> None:
            records.append({**record, "bucket": "excluded", "reason": reason})

        if not story.image.exists():
            drop("配图不在仓库里")
            continue
        aliases = tuple(_norm(alias) for alias in story.aliases)
        anniversary = is_anniversary(story, digest.today)
        if story.kind == "player":
            if _matched(aliases, headliners):
                score = 3
            elif _matched(aliases, todays):
                score = 1
            else:
                drop("这名球员今天没有比赛")
                continue
            heat = _alias_heat(aliases, player_heat)
        elif story.kind == "trivia":
            if story.slug.startswith("otd-"):
                # 历史上的今天：只在对应日期参选。命中当日给最高分——
                # 纪念日一年只回来一次，昨夜的高光球员明天还有。
                if not anniversary:
                    drop(f"不是它的正日子（{story.slug.removeprefix('otd-')}）")
                    continue
                score = ANNIVERSARY_SCORE
            else:
                score = 0
            heat = _trivia_topic_score(story, digest)
        else:
            if not _matched(aliases, tournaments):
                drop("这项赛事今天没有比赛")
                continue
            score = 2
            heat = _alias_heat(aliases, tournament_heat)

        if anniversary:
            # 冷却期对纪念日没有意义（一年只回来一次）；同日重跑时也不该被
            # 上一班次钉住的那条挡在后面——后续班次正是它的重试机会。
            bucket = "anniversary"
        elif _recently_used(story.slug, digest.today, state):
            bucket = "cooling"
        else:
            bucket = "fresh"
        records.append(
            {**record, "bucket": bucket, "score": score, "heat": round(float(heat), 4)}
        )

    by_slug = {record["story_slug"]: record for record in records}
    order_of = {story.slug: index for index, story in enumerate(STORIES)}

    def picked(bucket: str) -> list[dict]:
        return [r for r in records if r["bucket"] == bucket]

    anniversaries = sorted(picked("anniversary"), key=lambda r: order_of[r["story_slug"]])
    # 当天已定的故事照样参选，**即使它今天本来会落选**——这是原有的同日重跑
    # 幂等行为，不能因为重算而换卡。分档改标成 pinned（reason 留着），
    # 否则台账里会出现「excluded 却有名次」这种自相矛盾的行。
    pinned = []
    for slug in sorted(pinned_slugs, key=lambda s: order_of[s]):
        record = by_slug[slug]
        if record["bucket"] == "anniversary":
            continue
        record["bucket"] = "pinned"
        pinned.append(record)
    fresh = sorted(
        picked("fresh"),
        key=lambda r: (-r["score"], -r["heat"], order_of[r["story_slug"]]),
    )
    # ISO 日期字符串最小 = 距上次讲述最久；仍保留新闻分作为次级排序。
    cooling = sorted(
        picked("cooling"),
        key=lambda r: (
            r["last_used"],
            -r["score"],
            -r["heat"],
            order_of[r["story_slug"]],
        ),
    )

    rank = 0
    seen: set[str] = set()
    for record in [*anniversaries, *pinned, *fresh, *cooling]:
        if record["story_slug"] in seen:
            continue
        seen.add(record["story_slug"])
        rank += 1
        record["rank"] = rank
    return records


def record_story_selection(
    day_dir: Path | str,
    digest: Digest,
    ranking: list[dict],
    *,
    selected_slug: str | None,
    error: str = "",
) -> Path:
    """把这一班次的排序结果追加进当日目录的 `story_selection.json`.

    刻意不写进 `knowledge/`、刻意不覆盖——理由见 `SELECTION_LOG_NAME` 上面那段。
    `anniversary_missed` 是给 daily.yml 打 `::warning` 用的：当天有纪念日参选、
    最后成稿的却不是它，就该有人被吵醒。
    """
    from datetime import datetime, timezone

    path = Path(day_dir) / SELECTION_LOG_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        shifts = list(payload.get("shifts") or [])
    except (OSError, ValueError):
        shifts = []

    anniversaries = [
        record["story_slug"] for record in ranking if record["bucket"] == "anniversary"
    ]
    shifts.append(
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "selected": selected_slug or "",
            "error": error,
            "anniversary_slugs": anniversaries,
            "anniversary_missed": bool(anniversaries)
            and selected_slug not in anniversaries,
            "ranking": sorted(
                ranking,
                key=lambda record: (record.get("rank") or 10_000, record["story_slug"]),
            ),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "published_for": digest.today.isoformat(),
                "shifts": shifts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def tournament_story_candidates(digest: Digest) -> list[TournamentStory]:
    """Return stories in editorial order so rendering can skip weak visual packages.

    Selection and production are deliberately separate: the hottest subject is
    tried first, but a story without a complete, precisely matched visual set
    must not block a lower-ranked story that can be published well.
    """
    by_slug = {story.slug: story for story in STORIES}
    ranked = [record for record in story_ranking(digest) if record.get("rank")]
    ranked.sort(key=lambda record: record["rank"])
    return [by_slug[record["story_slug"]] for record in ranked]


WISHLIST_PATH = Path(__file__).resolve().parents[3] / "data" / "story_wishlist.json"


def _drama_note(m, loser: bool) -> str:
    """事件标注：为什么这场比赛/这名球员有热度."""
    from ..models import MatchStatus
    from .rating import is_upset

    notes = []
    if m.status is MatchStatus.RETIRED:
        notes.append("伤退惜败" if loser else "对手伤退")
    try:
        if is_upset(m):
            notes.append("遭遇爆冷" if loser else "爆冷取胜")
    except Exception:  # noqa: BLE001
        pass
    if len(m.sets or []) >= 3:
        notes.append("鏖战")
    return " · ".join(notes)


def record_story_wishlist(digest: Digest, top_n: int = 3) -> None:
    """昨日最热、但库里还没有故事的主角记入扩库清单（data/ 随 workflow 提交）.

    选题跟着巡回赛的实际热度走：不但记胜者，伤退/遭爆冷/鏖战惜败的
    输球方同样是新闻主角。清单里 hits 高的球员就是下一批该补写
    "球员特写"的对象，附赛果证据与事件标注，便于核实后成稿。
    """
    from .rating import match_score

    covered = tuple(
        _norm(alias) for story in STORIES for alias in story.aliases if alias
    )
    singles = [
        m for m in digest.results if m.is_singles and m.winner_players() is not None
    ]
    singles.sort(
        key=lambda m: match_score(m, cn_boost=False) + _match_drama(m), reverse=True
    )

    try:
        wishlist = json.loads(WISHLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        wishlist = {}

    changed = False
    # 旧版本在 workflow 重试时会把同一场证据重复计数。先就地归一化，
    # hits 只扣除能明确识别的重复项，不影响已经滚出最近 5 条的历史累计。
    for entry in wishlist.values():
        evidence = entry.get("evidence") or []
        unique: list[dict] = []
        seen: set[str] = set()
        for item in evidence:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        duplicates = len(evidence) - len(unique)
        if duplicates:
            entry["evidence"] = unique[-5:]
            entry["hits"] = len(unique)
            changed = True

    for m in singles[:top_n]:
        sides = [(m.winner_players() or [], False)]
        if _match_drama(m) >= DRAMA_THRESHOLD:
            sides.append((m.loser_players() or [], True))
        for players, is_loser in sides:
            for p in players:
                key = _norm(p.name)
                if any(alias in key for alias in covered):
                    continue
                entry = wishlist.setdefault(
                    key, {"name": p.name, "hits": 0, "evidence": []}
                )
                evidence = {
                    "date": digest.today.isoformat(),
                    "tournament": m.tournament.name,
                    "round": str(m.round_name or ""),
                    "score": m.score_display(),
                }
                note = _drama_note(m, loser=is_loser)
                if note:
                    evidence["note"] = note
                evidence_key = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
                existing = {
                    json.dumps(item, ensure_ascii=False, sort_keys=True)
                    for item in entry["evidence"]
                }
                if evidence_key not in existing:
                    entry["hits"] += 1
                    entry["evidence"] = (entry["evidence"] + [evidence])[-5:]
                    changed = True
    if changed:
        WISHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        WISHLIST_PATH.write_text(
            json.dumps(wishlist, ensure_ascii=False, indent=1), encoding="utf-8"
        )

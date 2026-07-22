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
        image=ASSETS / "umag-goran-ivanisevic-stadium.jpg",
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
        image=ASSETS / "canada-national-bank-open-stadium.jpg",
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
        image=ASSETS / "cincinnati-lindner-tennis-center.jpg",
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
                source_url="https://en.wikipedia.org/wiki/2024_Australian_Open_%E2%80%93_Women%27s_singles",
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
                    "https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_"
                    "%E2%80%93_Women%27s_singles"
                ),
            ),
        ),
        venue="2024 巴黎奥运女单金牌得主",
        image=PLAYER_ASSETS / "zheng-qinwen.jpg",
        image_credit="Hameltion / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://en.wikipedia.org/wiki/Zheng_Qinwen",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Zheng_Qinwen",
        kind="player",
        source_label="WTA / 奥运官方档案",
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
            "他与阿尔卡拉斯的 'Sincaraz' 对决已是新时代最大看点——"
            "2024 到 2025 年的八个大满贯冠军被两人全部瓜分。",
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
                headline="法网折桂 · 三种场地全满贯",
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
        ASSETS / "umag-goran-ivanisevic-stadium.jpg",
        "Silverije / Wikimedia Commons · CC BY-SA 4.0",
    ),
    "washington": (
        ASSETS / "washington-fitzgerald-tennis-center.jpg",
        "Asolsma1988 / Wikimedia Commons · CC0",
    ),
    "canada": (
        ASSETS / "canada-national-bank-open-stadium.jpg",
        "Raysonho / Wikimedia Commons · CC BY 3.0",
    ),
    "cincinnati": (
        ASSETS / "cincinnati-lindner-tennis-center.jpg",
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
    _trivia_story(
        slug="otd-0803",
        title="巴黎的金牌",
        subtitle="历史上的今天 · 8 月 3 日",
        identity="2024 · 郑钦文奥运夺金",
        chips=("历史上的今天", "2024", "巴黎"),
        hero="2024 年的今天，郑钦文在巴黎为中国拿下奥运网球单打首金——亚洲球员的第一次。",
        facts=(
            "半决赛掀翻红土女王斯瓦泰克，决赛直落两盘击败维基奇。",
            "距离李婷/孙甜甜的雅典女双首金，恰好二十年。",
            "她赛后说这是'为中国而战'——那周她的名字刷遍全网热搜。",
        ),
        moments=(
            ChampionMoment(
                date="2024-08-03", player="郑钦文", age="21 岁",
                headline="奥运女单金牌 · 亚洲第一人",
                detail="从武汉的训练场到罗兰·加洛斯的最高领奖台。",
                source_url="https://en.wikipedia.org/wiki/Tennis_at_the_2024_Summer_Olympics_%E2%80%93_Women%27s_singles",
            ),
        ),
        image_keys=("canada",),
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
            "如今的比赛用球以加压罐保存，每 7 局与 9 局交替换新——"
            "转播里那句 'new balls please' 就是为此。",
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
        slug="longest-match",
        title="11 小时 5 分钟",
        subtitle="网球冷知识 · 纪录篇",
        identity="一场打了三天的网球赛",
        chips=("冷知识", "纪录之最", "70-68"),
        hero=(
            "2010 年温网首轮，伊斯内尔与马胡把决胜盘打到 70-68——"
            "11 小时 5 分钟、跨越三天，连记分牌都死机了。"
        ),
        facts=(
            "两人合计轰出 216 记 ACE（伊斯内尔 113、马胡 103），"
            "单场 ACE 纪录至今无人接近。",
            "决胜盘打到 47-47 时，电子记分牌因超出程序设定直接黑屏；"
            "18 号球场如今立着这场比赛的纪念牌。",
            "它直接催生了规则改革——四大满贯自 2022 年起统一"
            "决胜盘 6-6 打 10 分抢十，'无限决胜盘'成为历史。",
        ),
        moments=(
            ChampionMoment(
                date="2010-06-24",
                player="伊斯内尔 vs 马胡",
                age="第 3 天",
                headline="70-68，终于结束",
                detail=(
                    "第三个比赛日，伊斯内尔在决胜盘第 138 局完成致胜破发——"
                    "赛后两位主角与主裁一起在记分牌前合影。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/Isner%E2%80%93Mahut_match_"
                    "at_the_2010_Wimbledon_Championships"
                ),
            ),
            ChampionMoment(
                date="2022-03-16",
                player="四大满贯",
                age="2022 年",
                headline="决胜盘规则统一",
                detail=(
                    "大满贯委员会宣布四项赛事决胜盘 6-6 一律改打 10 分抢十——"
                    "马拉松式对决就此封存进历史。"
                ),
                source_url="https://en.wikipedia.org/wiki/Tiebreaker",
            ),
        ),
        image_keys=("usopen",),
        source_label="温网官方史料",
        image_credit="Pahcal123 / Wikimedia Commons · CC BY-SA 4.0",
        source_url=(
            "https://en.wikipedia.org/wiki/Isner%E2%80%93Mahut_match_"
            "at_the_2010_Wimbledon_Championships"
        ),
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
                source_url="https://www.usopen.org/en_US/visit/grand_slam_alltime_champions.html",
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
            "https://www.itftennis.com/en/events/olympics-la-2028/statistics/",
            "https://www.itftennis.com/en/news-and-media/articles/"
            "nervous-at-past-olympics-djokovic-primed-for-golden-slam-charge/",
        ),
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
            "德约与纳达尔交手 60 次（德约 31-29 领先），"
            "是公开赛时代男子对决次数之最。",
            "2004 到 2021，年终世界第一连续 18 年被三巨头与穆雷包揽——"
            "直到 2022 年才被 19 岁的阿尔卡拉斯打破。",
        ),
        moments=(
            ChampionMoment(
                date="2008-07-06",
                player="费德勒 vs 纳达尔",
                age="温网决赛",
                headline="被称为史上最伟大一战",
                detail=(
                    "4 小时 48 分钟、两度因雨中断，纳达尔在近乎黑暗的暮色里"
                    "9-7 拿下决胜盘，终结费德勒温网五连冠。"
                ),
                source_url=(
                    "https://en.wikipedia.org/wiki/2008_Wimbledon_Championships_"
                    "%E2%80%93_Men%27s_singles_final"
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
                    "https://en.wikipedia.org/wiki/2012_Australian_Open_"
                    "%E2%80%93_Men%27s_singles_final"
                ),
            ),
        ),
        image_keys=("cincinnati",),
        source_label="ATP / 大满贯官方史料",
        image_credit="Tatiana (Moscow) / Wikimedia Commons · CC BY-SA 2.0",
        source_url="https://en.wikipedia.org/wiki/Big_Three_(tennis)",
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


def mark_story_used(slug: str, today: date) -> None:
    """记录故事已使用（由 CLI 在生成成功后调用，data/ 随 workflow 提交）."""
    state = _load_state()
    state[slug] = today.isoformat()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


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


def tournament_story_candidates(digest: Digest) -> list[TournamentStory]:
    """Return stories in editorial order so rendering can skip weak visual packages.

    Selection and production are deliberately separate: the hottest subject is
    tried first, but a story without a complete, precisely matched visual set
    must not block a lower-ranked story that can be published well.
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

    # 同日重跑幂等：当天已定的故事直接复用，避免重生成时轮换换卡
    today_iso = digest.today.isoformat()
    pinned: list[TournamentStory] = []
    for story in STORIES:
        if state.get(story.slug) == today_iso and story.image.exists():
            pinned.append(story)

    fresh: list[tuple[int, float, int, TournamentStory]] = []
    cooling: list[tuple[str, int, float, int, TournamentStory]] = []
    for order, story in enumerate(STORIES):
        if not story.image.exists():
            continue
        aliases = tuple(_norm(alias) for alias in story.aliases)
        if story.kind == "player":
            if _matched(aliases, headliners):
                score = 3
            elif _matched(aliases, todays):
                score = 1
            else:
                continue
            heat = _alias_heat(aliases, player_heat)
        elif story.kind == "trivia":
            if story.slug.startswith("otd-"):
                # 历史上的今天：只在对应日期参选，优先于普通冷知识
                if not story.slug.endswith(digest.today.strftime("%m%d")):
                    continue
                score = 1
            else:
                score = 0
            heat = 0.0
        else:
            if not _matched(aliases, tournaments):
                continue
            score = 2
            heat = _alias_heat(aliases, tournament_heat)
        if _recently_used(story.slug, digest.today, state):
            cooling.append((state.get(story.slug, ""), -score, -heat, order, story))
        else:
            fresh.append((-score, -heat, order, story))
    ordered_fresh = [item[-1] for item in sorted(fresh)]
    # ISO 日期字符串最小 = 距上次讲述最久；仍保留新闻分作为次级排序。
    ordered_cooling = [item[-1] for item in sorted(cooling)]
    ordered: list[TournamentStory] = []
    for story in [*pinned, *ordered_fresh, *ordered_cooling]:
        if story not in ordered:
            ordered.append(story)
    return ordered


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

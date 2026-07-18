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
        image_credit="Wikimedia Commons",
        source_url="https://www.usopen.org/en_US/visit/history/ustimeline.html",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Arthur_Ashe_Stadium",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
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
        image_credit="Wikimedia Commons",
        source_url="https://www.atptour.com/en/players/novak-djokovic/d643/overview",
        image_source_url="https://commons.wikimedia.org/wiki/Category:Novak_Djokovic",
        kind="player",
        source_label="ATP 官方档案",
    ),
)


def _load_state() -> dict[str, str]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _recently_used(slug: str, today: date) -> bool:
    last_str = _load_state().get(slug)
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


def pick_tournament_story(digest: Digest) -> TournamentStory | None:
    """按新闻价值选故事：昨日赢球的球员特写 > 进行中赛事档案 > 仅出场的球员特写."""
    matches = digest.results + digest.live + digest.schedule
    tournaments = {_norm(m.tournament.name) for m in matches}
    winners = {
        _norm(p.name) for m in digest.results for p in (m.winner_players() or [])
    }
    todays = {_norm(p.name) for m in matches for p in m.home + m.away}

    best: tuple[int, TournamentStory] | None = None
    for story in STORIES:
        if not story.image.exists():
            continue
        if _recently_used(story.slug, digest.today):
            continue
        aliases = tuple(_norm(alias) for alias in story.aliases)
        if story.kind == "player":
            if _matched(aliases, winners):
                score = 3
            elif _matched(aliases, todays):
                score = 1
            else:
                continue
        else:
            if not _matched(aliases, tournaments):
                continue
            score = 2
        if best is None or score > best[0]:
            best = (score, story)
    return best[1] if best else None

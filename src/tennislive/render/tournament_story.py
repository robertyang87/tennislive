"""Curated tournament history cards with reviewed facts and licensed images."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..digest import Digest


ASSETS = Path(__file__).resolve().parents[3] / "assets" / "venues"

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


def pick_tournament_story(digest: Digest) -> TournamentStory | None:
    active_names = {
        m.tournament.name.casefold()
        for m in digest.results + digest.live + digest.schedule
    }
    for story in STORIES:
        if not story.image.exists():
            continue
        if _recently_used(story.slug, digest.today):
            continue
        if any(alias in name for alias in story.aliases for name in active_names):
            return story
    return None

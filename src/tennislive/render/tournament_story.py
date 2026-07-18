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

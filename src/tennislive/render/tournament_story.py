"""Curated tournament history cards with reviewed facts and licensed images."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..digest import Digest


ASSETS = Path(__file__).resolve().parents[3] / "assets" / "venues"


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
        hero_fact="瓦林卡与阿尔卡拉斯，都在这里拿到生涯首座 ATP 冠军。",
        facts=(
            "首届决赛上演两位 Goran 的克罗地亚德比。",
            "赛事历史上曾迎来 9 位世界第一与 17 位大满贯冠军。",
            "中央球场自 2016 年起以温网冠军伊万尼塞维奇命名。",
        ),
        venue="ATP Stadium Goran Ivanišević · 4,032 席",
        image=ASSETS / "umag-goran-ivanisevic-stadium.jpg",
        image_credit="Silverije / Wikimedia Commons · CC BY-SA 4.0",
        source_url="https://umag-ed.atptour.com/en/tournament/history",
        image_source_url=(
            "https://commons.wikimedia.org/wiki/File:Teniski_stadion_"
            "%27Goran_Ivani%C5%A1evi%C4%87%27,_Umag.jpg"
        ),
    ),
)


def pick_tournament_story(digest: Digest) -> TournamentStory | None:
    active_names = {
        m.tournament.name.casefold()
        for m in digest.results + digest.live + digest.schedule
    }
    for story in STORIES:
        if not story.image.exists():
            continue
        if any(alias in name for alias in story.aliases for name in active_names):
            return story
    return None

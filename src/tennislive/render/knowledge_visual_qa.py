"""Deterministic visual standards for automated knowledge carousels."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from .tournament_story import TournamentStory


CARD_SIZE = (1080, 1440)
MAX_PHOTO_USES = 4
MAX_TEXT_BLOCK_CHARS = 82
MAX_CARD_TEXT_CHARS = 520
MAX_CARD_BYTES = 950_000
MIN_SOURCE_WIDTH = 900
MIN_SOURCE_HEIGHT = 540
FORBIDDEN_PRODUCTION_LABELS = ("程序生成", "自动生成", "AI生成", "AI 生成")
FORBIDDEN_TEMPLATE_LABELS = (
    "三道窄门",
    "三次转折",
    "三个坐标",
    "把这件事放回历史",
)


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden_depth = 0
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"style", "script", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"style", "script", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        text = " ".join(data.split())
        if text:
            self.blocks.append(text)


def _visible_blocks(body: str) -> list[str]:
    parser = _VisibleText()
    parser.feed(body)
    return parser.blocks


def _photo_count(body: str) -> int:
    return len(re.findall(r'data-photo-source="[^"]+"', body))


def _photo_sources(body: str) -> list[str]:
    return [
        unescape(source.strip())
        for source in re.findall(r'data-photo-source="([^"]+)"', body)
        if source.strip()
    ]


def _visual_value(visual: object, key: str, default: Any = "") -> Any:
    if isinstance(visual, Mapping):
        return visual.get(key, default)
    return getattr(visual, key, default)


def evaluate_knowledge_visuals(
    story: TournamentStory,
    bodies: list[tuple[str, str]],
    card_paths: list[Path] | None = None,
    page_visuals: Mapping[str, object] | None = None,
) -> dict:
    """Return an auditable pass/fail report used by CI before publishing."""
    errors: list[str] = []
    warnings: list[str] = []
    pages: list[dict] = []
    photo_uses = sum(_photo_count(body) for _kind, body in bodies)
    all_photo_sources = [
        source
        for _kind, body in bodies
        for source in _photo_sources(body)
    ]
    resolved_visuals: list[dict] = []

    if photo_uses > MAX_PHOTO_USES:
        errors.append(f"四页共使用 {photo_uses} 张照片，标准上限为 {MAX_PHOTO_USES} 张")
    if photo_uses < 1:
        errors.append("封面必须至少使用一张经过核验的主题图片")
    if len(set(all_photo_sources)) != len(all_photo_sources):
        errors.append("同一套卡片重复使用了相同来源的照片")
    if not story.image.is_file():
        errors.append(f"主图不存在：{story.image}")
    if not story.image_source_url.startswith("https://"):
        errors.append("主图必须有 HTTPS 来源页")
    if not story.image_credit.strip():
        errors.append("主图必须有作者与授权说明")
    if story.image.is_file():
        try:
            with Image.open(story.image) as source:
                if source.width < MIN_SOURCE_WIDTH or source.height < MIN_SOURCE_HEIGHT:
                    errors.append(
                        f"主图分辨率不足：{source.width}x{source.height}，"
                        f"至少 {MIN_SOURCE_WIDTH}x{MIN_SOURCE_HEIGHT}"
                    )
        except OSError as exc:
            errors.append(f"主图无法读取：{exc}")

    for page, visual in (page_visuals or {}).items():
        path = Path(_visual_value(visual, "path"))
        source_url = str(_visual_value(visual, "source_url")).strip()
        credit = str(_visual_value(visual, "credit")).strip()
        license_name = str(_visual_value(visual, "license")).strip()
        if page not in {"cover", "story", "explainer", "today"}:
            errors.append(f"未知的页面配图槽位：{page}")
        if not source_url.startswith("https://"):
            errors.append(f"{page} 页配图缺少 HTTPS 来源页")
        if not credit or not license_name:
            errors.append(f"{page} 页配图缺少作者或授权信息")
        if not path.is_file():
            errors.append(f"{page} 页配图不存在：{path}")
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
        except OSError as exc:
            errors.append(f"{page} 页配图无法读取：{exc}")
            continue
        if width < MIN_SOURCE_WIDTH or height < MIN_SOURCE_HEIGHT:
            errors.append(
                f"{page} 页配图分辨率不足：{width}x{height}，"
                f"至少 {MIN_SOURCE_WIDTH}x{MIN_SOURCE_HEIGHT}"
            )
        resolved_visuals.append(
            {
                "page": page,
                "file": str(path),
                "source_url": source_url,
                "credit": credit,
                "license": license_name,
                "width": width,
                "height": height,
            }
        )

    expected_visuals = {
        "knowledge": "verified-photo",
        "story": "narrative-timeline",
        "today": "history-timeline",
    }
    for kind, body in bodies:
        blocks = _visible_blocks(body)
        visible_text = " ".join(blocks)
        total_chars = sum(len(block) for block in blocks)
        longest = max((len(block) for block in blocks), default=0)
        match = re.search(r'data-visual="([^"]+)"', body)
        visual = match.group(1) if match else ""
        expected = expected_visuals.get(kind)
        page_photo_count = _photo_count(body)
        page_photo_sources = _photo_sources(body)
        if expected and visual != expected:
            errors.append(f"{kind} 页视觉类型应为 {expected}，实际为 {visual or '未声明'}")
        if kind == "explainer" and not (
            visual == "rule-diagram" or visual.endswith("-explainer")
        ):
            errors.append(f"explainer 页未使用示意图/信息图：{visual or '未声明'}")
        if story.diagram_type and kind == "explainer" and visual != "rule-diagram":
            errors.append(
                f"规则主题 {story.diagram_type} 必须使用 rule-diagram，不能使用照片模板"
            )
        if total_chars > MAX_CARD_TEXT_CHARS:
            errors.append(f"{kind} 页文字总量 {total_chars}，超过 {MAX_CARD_TEXT_CHARS}")
        if longest > MAX_TEXT_BLOCK_CHARS:
            errors.append(f"{kind} 页最长文字块 {longest} 字，超过 {MAX_TEXT_BLOCK_CHARS}")
        forbidden = next(
            (label for label in FORBIDDEN_PRODUCTION_LABELS if label in visible_text),
            "",
        )
        if forbidden:
            errors.append(f"{kind} 页含面向内部的生产描述：{forbidden}")
        canned = next(
            (label for label in FORBIDDEN_TEMPLATE_LABELS if label in visible_text),
            "",
        )
        if canned:
            errors.append(f"{kind} 页含固定叙事套话：{canned}")
        if re.search(r"<(?:i|small)[^>]*>\s*0[1-9]\s*</", body):
            errors.append(f"{kind} 页仍使用无语义顺序编号")
        if any(marker in visible_text for marker in ("①", "②", "③", "④")):
            errors.append(f"{kind} 页仍使用带圈顺序编号")
        year_markers = re.findall(
            r'data-marker-kind="year"[^>]*>.*?<small>([^<]+)</small>',
            body,
            flags=re.DOTALL,
        )
        invalid_year = next(
            (
                marker
                for marker in year_markers
                if not re.fullmatch(r"(?:18|19|20)\d{2}", unescape(marker).strip())
            ),
            "",
        )
        if invalid_year:
            errors.append(f"{kind} 页年份标记必须使用四位年份：{invalid_year}")
        if not visual:
            errors.append(f"{kind} 页没有声明视觉主体")
        if page_photo_count > 1:
            errors.append(f"{kind} 页最多使用一张主题照片")
        if page_photo_count and len(page_photo_sources) != page_photo_count:
            errors.append(f"{kind} 页照片缺少可审计的来源链接")
        if kind == "knowledge" and page_photo_count != 1:
            errors.append("封面必须且只能使用一张主题照片")
        pages.append(
            {
                "kind": kind,
                "visual": visual,
                "text_chars": total_chars,
                "longest_text_block": longest,
                "photo_count": page_photo_count,
                "photo_sources": page_photo_sources,
            }
        )

    if story.kind == "player" or story.slug in {"golden-slam", "big-three", "china-tennis"}:
        cover = next((body for kind, body in bodies if kind == "knowledge"), "")
        if not any(
            marker in cover
            for marker in (
                "object-position:50% 24%",
                "--knowledge-cover-focus:50% 22%",
            )
        ):
            errors.append("人物主图未使用头部安全焦点")

    rendered: list[dict] = []
    for path in card_paths or []:
        if not path.is_file():
            errors.append(f"缺少渲染卡片：{path.name}")
            continue
        try:
            with Image.open(path) as image:
                size = image.size
        except OSError as exc:
            errors.append(f"卡片无法读取：{path.name}: {exc}")
            continue
        byte_size = path.stat().st_size
        if size != CARD_SIZE:
            errors.append(f"{path.name} 尺寸为 {size[0]}x{size[1]}，应为 1080x1440")
        if byte_size > MAX_CARD_BYTES:
            errors.append(f"{path.name} 体积 {byte_size}，超过 {MAX_CARD_BYTES}")
        rendered.append({"file": path.name, "width": size[0], "height": size[1], "bytes": byte_size})

    return {
        "schema_version": 1,
        "status": "pass" if not errors else "fail",
        "story_slug": story.slug,
        "standards": {
            "photo_count_max": MAX_PHOTO_USES,
            "photo_source_uniqueness": "same photo/source may appear only once",
            "page_visual": "every page requires a photo or a topic-specific infographic",
            "non_cover_visual": "distinct licensed photo or structured infographic",
            "rule_explainer": "topic-specific diagram required",
            "player_crop": "head-safe object position",
            "production_labels": "internal generation labels are forbidden",
            "story_ordinals": "semantic icons replace ordinal markers",
            "year_markers": "calendar years must use four digits",
            "canned_story_labels": "fixed teaching-style labels are forbidden",
            "max_text_block_chars": MAX_TEXT_BLOCK_CHARS,
            "max_card_text_chars": MAX_CARD_TEXT_CHARS,
            "card_size": list(CARD_SIZE),
            "max_card_bytes": MAX_CARD_BYTES,
        },
        "photo_uses": photo_uses,
        "photo_sources": all_photo_sources,
        "resolved_visuals": resolved_visuals,
        "pages": pages,
        "rendered_cards": rendered,
        "errors": errors,
        "warnings": warnings,
    }

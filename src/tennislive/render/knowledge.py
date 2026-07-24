"""Standalone daily tennis knowledge package.

The morning digest should answer "what happened / what to watch"; this package
keeps the slower historical context as a separate shareable post.
"""

from __future__ import annotations

import html
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

from ..digest import Digest
from ..research.visual_sources import curated_source_urls, resolve_story_visuals
from ..timeutil import WEEKDAY_ZH
from .pushmsg import to_copy_page
from .hashtags import hashtag_count, limit_hashtags
from .knowledge_visual_qa import evaluate_knowledge_visuals
from .tournament_story import (
    TournamentStory,
    story_selection_evidence,
    tournament_story_candidates,
)
from .webcards import _screenshot_pages, knowledge_deck_bodies
from .xiaohongshu import xhs_title_len


_REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_CDN = f"https://cdn.jsdelivr.net/gh/{_REPO}@main"
_OWNER, _REPO_NAME = _REPO.split("/", 1)
_PAGES = os.environ.get(
    "TENNISLIVE_PAGES_URL", f"https://{_OWNER}.github.io/{_REPO_NAME}"
).rstrip("/")


def _date_label(d) -> str:
    return f"{d.month}.{d.day} · {WEEKDAY_ZH[d.weekday()]}"


def knowledge_title(story: TournamentStory, digest: Digest) -> str:
    day = f"{digest.today.month}.{digest.today.day}"
    trivia_hooks = {
        "otd-0725": "18岁第一冠，从乌马格开始",
        "otd-0803": "郑钦文巴黎摘金的那一天",
        "otd-0820": "3小时49分，决赛打到极限",
        "otd-0909": "19岁高芙，主场圆梦夜",
        "scoring-history": "网球为什么是15、30、40？",
        "yellow-ball": "网球为什么从白色变黄？",
        "longest-match": "最长一场网球，到底打了多久？",
        "hawkeye": "误判催生网球鹰眼",
        "golden-slam": "金满贯到底有多难？",
        "surfaces": "三种场地，真像三项运动？",
        "big-three": "三巨头统治了多少年？",
        "china-tennis": "中国网球，从哪一冠开始？",
    }
    if story.kind == "player":
        hook = f"{story.title}，不只是一场比分"
    elif story.kind == "trivia":
        hook = trivia_hooks.get(story.slug, f"{story.title}，你真懂吗？")
    else:
        hook = f"为什么要记住{story.title}？"
    prefix = f"📖{day}网球有故事｜"
    if xhs_title_len(prefix + hook) > 20:
        if story.kind == "player":
            short_name = story.title.rsplit("·", 1)[-1]
            hook = f"{short_name}的来路"
        else:
            hook = f"{story.title}的故事"
    if xhs_title_len(prefix + hook) > 20:
        hook = story.title
    return prefix + hook


def knowledge_wechat_title(story: TournamentStory, digest: Digest) -> str:
    """Use a distinct, fully preserved title for WeChat image posts."""
    title = (
        f"{digest.today.month}.{digest.today.day}网球有故事｜{story.title}"
    )
    if len(title) > 64:
        raise ValueError(f"公众号图片消息标题超长: {len(title)} > 64")
    return title


def _caption_items(story: TournamentStory) -> list[str]:
    items: list[str] = []
    years: set[str] = set()
    for moment in story.moments[:3]:
        year = moment.date.split("-", 1)[0]
        years.add(year)
        item = f"{year}｜{moment.player}：{moment.headline.rstrip('。')}"
        if len(item) > 34:
            short_headline = moment.headline.split("·", 1)[0].rstrip("，；：。 ")
            item = f"{year}｜{moment.player}：{short_headline}。"
        items.append(item)
    candidates: list[tuple[int, int, str, str]] = []
    role_priority = {"technology": 0, "surface": 0, "cycle": 0, "rule": 1}
    for index, fact in enumerate(story.facts):
        if any(year in fact for year in years):
            continue
        role = story.fact_roles[index] if index < len(story.fact_roles) else ""
        first_sentence = fact.split("。", 1)[0].strip()
        clauses = [part.strip() for part in re.split(r"[，；：]", first_sentence) if part.strip()]
        compact: list[str] = []
        for clause in clauses:
            candidate = "，".join([*compact, clause])
            if len(candidate) > 48:
                break
            compact.append(clause)
        brief = "，".join(compact)
        if brief:
            candidates.append(
                (role_priority.get(role, 2), len(brief), _fact_caption_label(fact, role), brief)
            )
    if len(items) < 3 and candidates:
        _priority, _length, label, brief = min(candidates)
        items.append(f"{label}｜{brief}。")
    return items[:3]


def _fact_caption_label(fact: str, role: str = "") -> str:
    role_labels = {
        "technology": "原理",
        "surface": "场地",
        "cycle": "时间",
        "rule": "规则",
        "history": "背景",
        "trophy": "纪录",
        "legacy": "影响",
    }
    if role in role_labels:
        return role_labels[role]
    if any(word in fact for word in ("相机", "系统", "技术", "轨迹", "原理")):
        return "原理"
    if any(word in fact for word in ("冠军", "纪录", "第一", "唯一")):
        return "纪录"
    if any(word in fact for word in ("红土", "草地", "硬地", "场地")):
        return "场地"
    if any(word in fact for word in ("规则", "判罚", "司线")):
        return "规则"
    return "背景"


def _mobile_wrap(text: str) -> str:
    """Add one natural line break to dense openings without dropping words."""
    if len(text) <= 54 or "。" not in text:
        return text
    return text.replace("。", "。\n", 1)


def _plain_language_line(story: TournamentStory) -> str:
    return {
        "hawkeye": "说白了，电子司线就是由系统实时判定界内或界外，不必等球员挑战。",
    }.get(story.slug, "")


def _caption_icon(item: str, index: int) -> str:
    """Use meaning, rather than sequence numbers, to guide mobile readers."""
    icon_rules = (
        (("规则", "判罚", "司线", "鹰眼", "电子", "系统", "技术"), "🎯"),
        (("金牌", "奥运"), "🥇"),
        (("冠军", "夺冠", "捧杯", "满贯"), "🏆"),
        (("红土", "草地", "硬地", "场地"), "🎾"),
        (("小时", "分钟", "三天", "四年"), "⏱️"),
        (("球场", "城市", "赛事", "公开赛"), "🏟️"),
    )
    for keywords, icon in icon_rules:
        if any(keyword in item for keyword in keywords):
            return icon
    return ("🎬", "⚡", "🔎")[min(index, 2)]


_FORBIDDEN_COPY_BOILERPLATE = (
    "先别往下滑",
    "🧠 先猜",
    "🎾 答案",
    "记住这3点",
    "我为什么想讲它",
    "三道窄门",
    "三次转折",
    "三个坐标",
    "把这件事放回历史",
    "①",
    "②",
    "③",
)

_PLAIN_LANGUAGE_RULES = {
    "年度全满贯": ("同一年", "四大满贯"),
    "金满贯": ("四大满贯", "奥运"),
    "电子司线": ("系统", "判定"),
}

_KNOWLEDGE_EMOJI_MARKERS = (
    "🎬",
    "🏆",
    "⚔️",
    "🧩",
    "📚",
    "⏱️",
    "📟",
    "📜",
    "👤",
    "⚡",
    "🔎",
    "🕰️",
    "🏟️",
    "🎾",
    "🧭",
    "🎯",
    "🥇",
    "💬",
)


def _copy_mode(story: TournamentStory, digest: Digest) -> int:
    seed = f"{digest.today.isoformat()}:{story.slug}".encode("utf-8")
    return hashlib.sha256(seed).digest()[0] % 5


def _story_opening(story: TournamentStory, digest: Digest) -> tuple[str, str, str]:
    """Rotate evidence-backed openings that fit the story category."""
    mode = _copy_mode(story, digest)
    first = story.moments[0] if story.moments else None
    last = story.moments[-1] if story.moments else None
    year = first.date[:4] if first else story.founded.replace("始于 ", "")
    first_person = first.player if first else story.title
    first_event = first.headline if first else story.title
    first_detail = first.detail if first else story.hero_fact
    last_year = last.date[:4] if last else year
    last_event = last.headline if last else story.hero_fact
    if story.kind == "player":
        openings = (
            (f"🎬 {year}，故事从这里起拍", f"{first_person}迎来{first_event}。{first_detail}", story.hero_fact),
            ("👤 成名照之外，还有来路", f"先记住{first_person}在{year}年的这一站：{first_event}。", first_detail),
            ("⚡ 生涯里值得停下的一场", first_detail, f"再回看{last_year}年的{last_event}，轨迹已经清楚。"),
            ("🔎 一条生涯线怎样长成", f"{first_event}不是孤立的一晚。{first_detail}", story.hero_fact),
            ("🕰️ 从第一步看到今天", f"故事起于{year}年的{first_event}，后来走到{last_year}年的{last_event}。", story.hero_fact),
        )
    elif story.kind == "tournament":
        openings = (
            (f"🏟️ 先把坐标放在{story.location}", f"{year}年，{first_person}写下{first_event}。{first_detail}", story.hero_fact),
            ("🏆 冠军簿里最值得停的一页", f"翻到{year}年，名字是{first_person}，故事是{first_event}。", first_detail),
            ("🎬 一座球场怎样留下记忆", first_detail, f"到{last_year}年的{last_event}，这项传统有了新的主角。"),
            ("⚡ 年份会过去，传统会留下", f"{first_event}发生在{year}年。{first_detail}", story.hero_fact),
            ("🔎 看懂赛事，不只看签表", f"先从{first_person}和{first_event}讲起。{first_detail}", story.hero_fact),
        )
    else:
        openings = (
            (f"🎬 把时间拨回{year}年", f"{first_person}迎来{first_event}。{first_detail}", story.hero_fact),
            ("⚡ 真正有趣的，在结果之外", first_detail, story.hero_fact),
            ("🎬 镜头先对准这一刻", f"{year}年的{first_event}，把一条知识变成了真实瞬间。", first_detail),
            ("🔎 一条规则或纪录的来路", f"故事从{year}年的{first_event}开始。{first_detail}", story.hero_fact),
            ("🕰️ 当年的一刻，今天的回响", f"从{year}年的{first_event}到{last_year}年的{last_event}，中间不是一句纪录能讲完的。", story.hero_fact),
        )
    return openings[mode]


def _golden_slam_copy(story: TournamentStory, digest: Digest) -> str:
    title = knowledge_title(story, digest)
    question = _knowledge_question(story)
    return (
        f"{title}\n\n"
        "🏆 1988年，格拉芙先后赢下澳网、法网、温网和美网。\n"
        "抵达汉城时，19岁的她只差最后一扇门。\n\n"
        "⚔️ 决赛对面还是萨巴蒂尼。\n"
        "几周前的美网决赛，两人刚打满三盘；这一次，格拉芙用两个6比3结束比赛。\n\n"
        "🧩 真正夸张的，不只是五项冠军都拿到了。\n\n"
        "四大满贯横跨硬地、红土和草地；\n"
        "奥运会却四年才来一次。\n"
        "状态、身体和赛历必须在同一年严丝合缝地对上。\n\n"
        "📚 拉沃尔1969年完成公开赛时代男子唯一一次年度全满贯；\n"
        "格拉芙又往前走了一步。直到今天，年度金满贯仍只有她一人。\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把比分背后的来路讲给你听。\n\n"
        "#网球 #格拉芙 #金满贯 #网球历史 #网球时差"
    )


def _longest_match_copy(story: TournamentStory, digest: Digest) -> str:
    title = knowledge_title(story, digest)
    question = _knowledge_question(story)
    return (
        f"{title}\n\n"
        "🎬 2010年温网首轮，伊斯内尔和马胡只是走上18号球场，"
        "谁也没想到，下场已经是三天以后。\n\n"
        "⏱️ 前四盘打完，两人仍分不出高下。\n"
        "当时决胜盘没有抢七，只能一直打到有人领先两局。\n\n"
        "📟 于是比分从20比20爬到40比40，再到50比50。\n"
        "现场记分牌一度撑不住，比赛却还在继续。\n\n"
        "最终，伊斯内尔在决胜盘第138局完成破发：70比68。\n"
        "整场耗时11小时5分钟、打了183局，两人合计轰出216记ACE。\n\n"
        "📜 这场球后来成了规则改革最有力的理由之一。\n"
        "如今四大满贯决胜盘打到6比6，会用10分抢十收尾。"
        "那种不知道终点在哪的长盘大战，已经留在历史里。\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把比分背后的来路讲给你听。\n\n"
        "#网球 #温网 #伊斯内尔 #马胡 #网球时差"
    )


def _knowledge_question(story: TournamentStory) -> str:
    trivia_questions = {
        "scoring-history": "你第一次学网球记分时，最难理解的是哪一项？",
        "yellow-ball": "如果网球还是白色，你觉得电视上还能看清吗？",
        "longest-match": "一场比赛打到第几小时，你会先撑不住？",
        "hawkeye": "四大满贯只剩法网保留人工司线，红土球印足够可靠吗？",
        "golden-slam": "金满贯和世界第一，你觉得哪个更难？",
        "surfaces": "硬地、红土、草地只能选一种看，你选哪块？",
        "big-three": "三巨头时代，你最先站谁？",
        "china-tennis": "中国网球哪个瞬间，你到现在还记得？",
    }
    if story.kind == "player":
        return f"你第一次记住{story.title}，是哪一场球？"
    if story.kind == "trivia":
        return trivia_questions.get(
            story.slug, "读完这张卡，你最想把哪一条讲给球友听？"
        )
    return f"提到{story.title}，你最先想到哪位冠军？"


def knowledge_pinned_comment(story: TournamentStory) -> str:
    question = _knowledge_question(story)
    if story.slug == "hawkeye":
        reply = "我更看重判罚标准一致：红土有球印，但人工找印和解释球印仍可能出错。"
    elif story.kind == "player":
        reply = "有人记住冠军，有人记住输掉以后重新站起来的那一场。你是哪一种？"
    else:
        reply = "说一场、一个人或一个瞬间都可以，我更想听你自己的看球记忆。"
    return f"{question}\n\n{reply}"


def knowledge_copy(story: TournamentStory, digest: Digest) -> str:
    if story.slug == "golden-slam":
        return _golden_slam_copy(story, digest)
    if story.slug == "longest-match":
        return _longest_match_copy(story, digest)
    title = knowledge_title(story, digest)
    items = _caption_items(story)
    moments = "\n\n".join(
        f"{_caption_icon(item, index)} {item}" for index, item in enumerate(items)
    )
    question = _knowledge_question(story)
    opening_label, opener, bridge = _story_opening(story, digest)
    plain_line = _plain_language_line(story)
    plain_block = f"{plain_line}\n\n" if plain_line else ""
    timeline_label = {
        "player": "🎾 生涯轨迹",
        "tournament": "🏟️ 球场、冠军与传统",
        "trivia": "🧭 这段历史如何走到今天",
    }.get(story.kind, "🧭 故事的来路")
    return (
        f"{title}\n\n"
        f"{opening_label}\n"
        f"{_mobile_wrap(opener)}\n\n"
        f"{bridge}\n\n"
        f"{plain_block}"
        f"{timeline_label}\n"
        f"{moments}\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把比分背后的来路讲给你听。\n\n"
        "#网球 #网球知识 #网球时差 #网球科普 #网球故事"
    )


def _validate_copy_for_publish(copy: str) -> None:
    repeated = [phrase for phrase in _FORBIDDEN_COPY_BOILERPLATE if phrase in copy]
    if repeated:
        raise ValueError("知识帖文案仍含固定模板话术：" + "、".join(repeated))
    body = "\n".join(copy.splitlines()[1:])
    emoji_markers = {
        marker for marker in _KNOWLEDGE_EMOJI_MARKERS if marker in body
    }
    if not 3 <= len(emoji_markers) <= 8:
        raise ValueError(
            "知识帖正文应使用 3 至 8 个不同功能的 emoji 导航，"
            "用于场景、转折、知识点和互动，而不是堆砌装饰"
        )
    for term, explanation in _PLAIN_LANGUAGE_RULES.items():
        if term in copy and not all(word in copy for word in explanation):
            raise ValueError(
                f"知识帖首次使用专业词“{term}”时，必须同时解释："
                + "、".join(explanation)
            )
    if "…" in copy or "..." in copy:
        raise ValueError("知识帖文案不得用省略号掩盖截断内容")
    public_citation_markers = ("资料｜", "来源：", "图源：", "摄影/图源", "非商业资料引用")
    if any(marker in copy for marker in public_citation_markers):
        raise ValueError("知识帖发布文案不得显示资料或图片来源")
    lines = copy.strip().splitlines()
    if not lines or xhs_title_len(lines[0]) > 20:
        raise ValueError("知识帖标题必须完整且不超过小红书 20 字限制")
    paragraphs = [part.strip() for part in copy.split("\n\n") if part.strip()]
    if len(paragraphs) < 6 or any(len(part) > 120 for part in paragraphs[1:]):
        raise ValueError("知识帖正文必须使用适合手机阅读的短段落")
    if "💬" not in copy:
        raise ValueError("知识帖正文缺少可评论的具体问题")
    hashtags = hashtag_count(copy)
    if not 3 <= hashtags <= 5:
        raise ValueError("知识帖话题标签应保持 3 至 5 个")


def knowledge_push_html(
    digest: Digest,
    story: TournamentStory,
    *,
    card_names: list[str],
    xhs_text: str,
    output_dir_name: str = "knowledge",
) -> str:
    """Build the WeChat push HTML.

    ``output_dir_name`` must match the actual leaf directory the caller
    passed to ``generate_knowledge_package`` (``"knowledge"`` for the daily
    auto-selected post, ``"knowledge_adhoc"`` for ad-hoc runs). A hardcoded
    ``"knowledge"`` here would silently point every ad-hoc push at whichever
    story the same-day daily digest happened to generate instead of the
    story actually being pushed.
    """
    d = digest.today
    copy_url = f"{_PAGES}/output/{d.isoformat()}/{output_dir_name}/copy.html"
    lines = xhs_text.strip().splitlines()
    title = html.escape(lines[0] if lines else knowledge_title(story, digest))
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    paragraphs = []
    for paragraph in body.split("\n\n"):
        safe = "<br/>".join(html.escape(line) for line in paragraph.splitlines())
        paragraphs.append(
            '<div style="font-size:15px;line-height:1.85;margin:0 0 13px;">'
            f"{safe}</div>"
        )
    images = []
    for index, card_name in enumerate(card_names, 1):
        card_url = f"{_CDN}/output/{d.isoformat()}/{output_dir_name}/cards/{card_name}"
        images.append(
            f'<img src="{card_url}" data-src="{card_url}" width="100%" '
            f'alt="{title} · 第{index}页" referrerpolicy="no-referrer" '
            'style="width:100%;border-radius:6px;margin:0 0 10px;display:block;" />'
            f'<div style="text-align:center;margin:0 0 16px;"><a href="{card_url}" '
            'style="color:#087747;font-size:13px;text-decoration:none;">'
            f'第{index}张未显示？点此打开原图</a></div>'
        )
    return f"""<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
<div style="max-width:680px;margin:0 auto;background-color:#ffffff;border-top:5px solid #ff2442;padding:18px 16px 22px;">
  <div style="display:inline-block;background-color:#e7f5ea;color:#087747;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">小红书知识帖 · {d.month}.{d.day}</div>
  <div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;margin:10px 0 14px;">{title}</div>
  {''.join(images)}
  {''.join(paragraphs)}
  <div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>
  <a href="{copy_url}" style="display:block;background-color:#ff2442;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;border-radius:6px;margin:0 0 7px;">分别复制标题 / 正文 / 置顶评论</a>
  <div style="text-align:center;color:#7a8580;font-size:12px;">图片长按保存</div>
</div>
</div>"""


def _validate_story_for_publish(story: TournamentStory, digest: Digest) -> None:
    """Fail closed when a story contains unsupported or logically stale claims."""
    errors: list[str] = []
    claims = "\n".join((story.hero_fact, *story.facts))
    if not story.source_url.startswith("https://"):
        errors.append("主来源必须是 HTTPS")
    if "截至" in claims and str(digest.today.year) not in claims:
        errors.append("时效性结论必须包含生成年份")
    forbidden = (
        "目前只剩法网",
        "主裁第一判断，还是鹰眼",
        "技术没有替比赛做决定",
    )
    for phrase in forbidden:
        if phrase in claims:
            errors.append(f"存在范围或角色不清的表述：{phrase}")
    if story.slug == "hawkeye":
        required = ("2D", "3D", "四大满贯中", "实时电子司线", str(digest.today.year))
        for phrase in required:
            if phrase not in claims:
                errors.append(f"鹰眼事实缺少必要范围：{phrase}")
        if len(story.evidence_urls) < 4:
            errors.append("鹰眼故事至少需要四个交叉核验来源")
    if errors:
        raise ValueError("知识帖事实校验失败：" + "；".join(errors))


def _knowledge_evidence(story: TournamentStory, digest: Digest) -> dict:
    source_urls = list(dict.fromkeys(
        [
            story.source_url,
            *story.evidence_urls,
            *(moment.source_url for moment in story.moments),
            story.image_source_url,
        ]
    ))
    source_urls = [url for url in source_urls if url]
    claims = [
        {
            "type": "hero",
            "text": story.hero_fact,
            "source_urls": source_urls[:2] or [story.source_url],
        }
    ]
    for index, fact in enumerate(story.facts):
        if story.slug == "hawkeye":
            mapping = (
                source_urls[:2],
                [url for url in source_urls if "usopen.org" in url or "sony.com" in url],
                [url for url in source_urls if "wimbledon.com" in url or "lequipe.fr" in url],
            )
            urls = mapping[index] if index < len(mapping) else source_urls[:1]
        else:
            urls = source_urls[:1]
        claims.append({"type": "fact", "text": fact, "source_urls": urls})
    claims.extend(
        {
            "type": "moment",
            "date": moment.date,
            "text": f"{moment.player}：{moment.headline}。{moment.detail}",
            "source_urls": [moment.source_url],
        }
        for moment in story.moments
    )
    return {
        "schema_version": 1,
        "generated_for": digest.today.isoformat(),
        "story_slug": story.slug,
        "scope": "已核验事实；观点与互动问题不作为事实结论",
        "claims": claims,
        "sources": source_urls,
    }


def _generate_knowledge_candidate(
    digest: Digest,
    outdir: str | Path,
    *,
    theme: str = "dark",
    story: TournamentStory | None = None,
    excluded_source_urls: set[str] | None = None,
) -> TournamentStory | None:
    candidates = [story] if story is not None else tournament_story_candidates(digest)
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return None
    outdir = Path(outdir)
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("card_*.*"):
        if old.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            old.unlink()
    visuals_dir = outdir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    for old in visuals_dir.iterdir():
        if old.is_file():
            old.unlink()

    rejected_candidates: list[dict] = []
    selected_story: TournamentStory | None = None
    page_visuals = {}
    visual_sources: dict = {}
    max_attempts = max(1, int(os.environ.get("TENNISLIVE_VISUAL_CANDIDATES", "6")))
    for candidate in candidates[:max_attempts]:
        _validate_story_for_publish(candidate, digest)
        for old in visuals_dir.iterdir():
            if old.is_file():
                old.unlink()
        if excluded_source_urls:
            candidate_visuals, candidate_report = resolve_story_visuals(
                candidate,
                visuals_dir,
                excluded_source_urls=excluded_source_urls,
            )
        else:
            candidate_visuals, candidate_report = resolve_story_visuals(
                candidate,
                visuals_dir,
            )
        if candidate_report.get("status") == "pass":
            selected_story = candidate
            page_visuals = candidate_visuals
            visual_sources = candidate_report
            break
        rejected_candidates.append(
            {
                "story_slug": candidate.slug,
                "title": candidate.title,
                "errors": candidate_report.get("errors", []),
                "missing_pages": candidate_report.get("missing_pages", []),
                "input_domains": candidate_report.get("input_domains", []),
                "providers_queried": candidate_report.get(
                    "providers_queried", []
                ),
                "provider_runs": candidate_report.get("provider_runs", []),
                "attempts": candidate_report.get("attempts", []),
            }
        )
    if selected_story is None:
        failure = {
            "schema_version": 1,
            "status": "fail",
            "policy": "精确人物/年份/赛事/地点/授权素材不足时自动换题；候选耗尽则停止发布",
            "rejected_candidates": rejected_candidates,
            "errors": ["候选故事均未通过素材生产性预检"],
            "attempts": [],
        }
        (outdir / "visual_sources.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise ValueError("知识帖素材预检失败：候选故事均没有完整高质量图片包")
    story = selected_story
    selection_evidence = story_selection_evidence(story, digest)
    selection_evidence.update(
        {
            "candidate_rank": candidates.index(story) + 1,
            "candidate_count": len(candidates),
            "visual_preflight_rejections": len(rejected_candidates),
            "visual_preflight_status": "pass",
        }
    )
    visual_sources["selection_evidence"] = selection_evidence
    visual_sources["rejected_candidates"] = rejected_candidates
    (outdir / "visual_sources.json").write_text(
        json.dumps(visual_sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    date_label = _date_label(digest.today)
    question = _knowledge_question(story)
    bodies = knowledge_deck_bodies(
        story,
        date_label,
        question=question,
        year=digest.today.year,
        page_visuals=page_visuals,
    )
    visual_qa = evaluate_knowledge_visuals(
        story,
        bodies,
        page_visuals=page_visuals,
    )
    (outdir / "visual_qa.json").write_text(
        json.dumps(visual_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if visual_qa["status"] != "pass":
        raise ValueError("知识帖视觉校验失败：" + "；".join(visual_qa["errors"]))
    images = _screenshot_pages(bodies, theme)
    from .image_output import save_social_image

    card_stems = {
        "knowledge": "card_00_knowledge",
        "story": "card_01_story",
        "explainer": "card_02_explainer",
        "today": "card_03_today",
    }
    card_paths = [
        save_social_image(image, cards_dir / card_stems[kind])
        for kind, image in images
    ]
    visual_qa = evaluate_knowledge_visuals(
        story,
        bodies,
        card_paths,
        page_visuals=page_visuals,
    )
    (outdir / "visual_qa.json").write_text(
        json.dumps(visual_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if visual_qa["status"] != "pass":
        raise ValueError("知识帖渲染校验失败：" + "；".join(visual_qa["errors"]))
    # The four compressed cards and source manifest are durable artifacts.
    # Raw downloads are only a render cache and would otherwise bloat Git daily.
    shutil.rmtree(visuals_dir, ignore_errors=True)

    xhs_text = limit_hashtags(knowledge_copy(story, digest))
    _validate_copy_for_publish(xhs_text)
    pinned_comment = knowledge_pinned_comment(story)
    (outdir / "xiaohongshu.txt").write_text(xhs_text, encoding="utf-8")
    (outdir / "pinned_comment.txt").write_text(pinned_comment, encoding="utf-8")
    (outdir / "wechat_title.txt").write_text(
        knowledge_wechat_title(story, digest), encoding="utf-8"
    )
    (outdir / "copy.html").write_text(
        to_copy_page(xhs_text, pinned_comment=pinned_comment), encoding="utf-8"
    )
    (outdir / "push.html").write_text(
        knowledge_push_html(
            digest,
            story,
            card_names=[path.name for path in card_paths],
            xhs_text=xhs_text,
            output_dir_name=outdir.name,
        ),
        encoding="utf-8",
    )
    (outdir / "story.json").write_text(
        json.dumps(
            {
                "slug": story.slug,
                "title": story.title,
                "kind": story.kind,
                "source_label": story.source_label,
                "source_url": story.source_url,
                "image": str(story.image),
                "image_credit": story.image_credit,
                "card_count": len(card_paths),
                "visual_qa": "visual_qa.json",
                "visual_sources": "visual_sources.json",
                "resolved_visual_count": len(page_visuals),
                "selection_evidence": selection_evidence,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (outdir / "evidence.json").write_text(
        json.dumps(_knowledge_evidence(story, digest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return story


def _knowledge_failure_stage(message: str) -> str:
    if "事实校验" in message:
        return "fact-validation"
    if "素材预检" in message:
        return "visual-preflight"
    if "视觉校验" in message:
        return "pre-render-qa"
    if "渲染校验" in message:
        return "post-render-qa"
    if "文案" in message or "标题" in message:
        return "copy-validation"
    return "candidate-generation"


def _selected_visual_sources(slug: str, manifest: dict) -> set[str]:
    """Source URLs to exclude on the next retry.

    Curated picks are deliberately excluded from this set: they have no
    alternative candidate to diversify toward, so excluding one just
    strands that page with zero options on the retry that follows an
    unrelated page's failure.
    """
    selected = {
        str(item["source_url"])
        for item in manifest.get("attempts", [])
        if item.get("status") == "selected" and item.get("source_url")
    }
    return selected - curated_source_urls(slug)


def generate_knowledge_package(
    digest: Digest,
    outdir: str | Path,
    *,
    theme: str = "dark",
    story: TournamentStory | None = None,
) -> TournamentStory | None:
    """Generate a publishable package through source retry and topic fallback."""
    candidates = [story] if story is not None else tournament_story_candidates(digest)
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return None

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    max_candidates = max(
        1,
        min(
            len(candidates),
            int(os.environ.get("TENNISLIVE_VISUAL_CANDIDATES", "8")),
        ),
    )
    attempts_per_topic = max(
        1,
        min(
            4,
            int(os.environ.get("TENNISLIVE_VISUAL_RETRIES_PER_TOPIC", "2")),
        ),
    )
    rejected_candidates: list[dict] = []
    publish_files = (
        "copy.html",
        "evidence.json",
        "pinned_comment.txt",
        "push.html",
        "story.json",
        "visual_qa.json",
        "visual_sources.json",
        "wechat_title.txt",
        "xiaohongshu.txt",
    )

    for candidate_rank, candidate in enumerate(
        candidates[:max_candidates],
        start=1,
    ):
        failed_attempts: list[dict] = []
        excluded_source_urls: set[str] = set()
        for attempt_index in range(1, attempts_per_topic + 1):
            for filename in publish_files:
                (outdir / filename).unlink(missing_ok=True)
            try:
                selected = _generate_knowledge_candidate(
                    digest,
                    outdir,
                    theme=theme,
                    story=candidate,
                    excluded_source_urls=excluded_source_urls,
                )
            except Exception as exc:  # noqa: BLE001 - fallback is the contract
                manifest: dict = {}
                manifest_path = outdir / "visual_sources.json"
                if manifest_path.is_file():
                    try:
                        manifest = json.loads(manifest_path.read_text("utf-8"))
                    except (OSError, ValueError):
                        manifest = {}
                visual_qa: dict = {}
                visual_qa_path = outdir / "visual_qa.json"
                if visual_qa_path.is_file():
                    try:
                        visual_qa = json.loads(visual_qa_path.read_text("utf-8"))
                    except (OSError, ValueError):
                        visual_qa = {}
                newly_excluded = _selected_visual_sources(candidate.slug, manifest)
                excluded_source_urls.update(newly_excluded)
                stage = _knowledge_failure_stage(str(exc))
                # The visual-preflight failure path nests the real
                # diagnostics (input_domains/providers_queried/etc.) inside
                # rejected_candidates[-1], not at the manifest's top level --
                # fall back to that so a real cause survives instead of
                # always reading as empty.
                last_rejected = (manifest.get("rejected_candidates") or [{}])[-1]
                failed_attempts.append(
                    {
                        "attempt": attempt_index,
                        "stage": stage,
                        "error": f"{type(exc).__name__}: {exc}",
                        "excluded_after_attempt": sorted(excluded_source_urls),
                        "newly_excluded": sorted(newly_excluded),
                        "input_domains": manifest.get("input_domains")
                        or last_rejected.get("input_domains", []),
                        "providers_queried": manifest.get("providers_queried")
                        or last_rejected.get("providers_queried", []),
                        "provider_runs": manifest.get("provider_runs")
                        or last_rejected.get("provider_runs", []),
                        "missing_pages": manifest.get("missing_pages")
                        or last_rejected.get("missing_pages", []),
                        "attempts": manifest.get("attempts")
                        or last_rejected.get("attempts", []),
                        "visual_qa": visual_qa,
                    }
                )
                # Facts and deterministic copy cannot improve by downloading
                # the same topic again. Move directly to the next topic.
                if stage in {"fact-validation", "copy-validation"}:
                    break
                continue

            if selected is None:
                failed_attempts.append(
                    {
                        "attempt": attempt_index,
                        "stage": "empty-candidate",
                        "error": "候选主题未生成任何内容",
                    }
                )
                continue

            manifest_path = outdir / "visual_sources.json"
            manifest = json.loads(manifest_path.read_text("utf-8"))
            selection_evidence = manifest.get("selection_evidence", {})
            selection_evidence.update(
                {
                    "candidate_rank": candidate_rank,
                    "candidate_count": len(candidates),
                    "visual_preflight_rejections": len(rejected_candidates),
                    "same_topic_attempt": attempt_index,
                    "same_topic_attempt_limit": attempts_per_topic,
                }
            )
            manifest.update(
                {
                    "schema_version": max(
                        2,
                        int(manifest.get("schema_version", 1)),
                    ),
                    "policy": (
                        "事实先交叉核验；图片失败时排除失败来源并同题重试，"
                        "仍失败则按新闻价值切换主题；候选耗尽后交给后续班次。"
                    ),
                    "selection_evidence": selection_evidence,
                    "rejected_candidates": rejected_candidates,
                    "recovery": {
                        "status": (
                            "recovered"
                            if failed_attempts or rejected_candidates
                            else "not-needed"
                        ),
                        "same_topic_attempt": attempt_index,
                        "excluded_source_urls": sorted(excluded_source_urls),
                        "failed_attempts": failed_attempts,
                    },
                }
            )
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            story_path = outdir / "story.json"
            story_payload = json.loads(story_path.read_text("utf-8"))
            story_payload["selection_evidence"] = selection_evidence
            story_payload["recovery"] = manifest["recovery"]
            story_path.write_text(
                json.dumps(story_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return selected

        rejected_candidates.append(
            {
                "story_slug": candidate.slug,
                "title": candidate.title,
                "stage": (
                    failed_attempts[-1]["stage"]
                    if failed_attempts
                    else "unknown"
                ),
                "errors": [
                    attempt.get("error", "")
                    for attempt in failed_attempts
                    if attempt.get("error")
                ],
                "excluded_source_urls": sorted(excluded_source_urls),
                "attempts": failed_attempts,
            }
        )

    for filename in publish_files:
        (outdir / filename).unlink(missing_ok=True)
    cards_dir = outdir / "cards"
    if cards_dir.is_dir():
        for card in cards_dir.glob("card_*.*"):
            card.unlink(missing_ok=True)
    failure = {
        "schema_version": 2,
        "status": "fail",
        "policy": (
            "事实校验失败则换题；图片或渲染失败先排除来源并同题重试，"
            "再切换主题；全部候选耗尽后由后续定时班次重新抓取。"
        ),
        "candidate_limit": max_candidates,
        "same_topic_attempt_limit": attempts_per_topic,
        "rejected_candidates": rejected_candidates,
        "errors": ["本轮所有候选均未通过完整生产与质量门禁"],
        "attempts": [
            attempt
            for candidate in rejected_candidates
            for attempt in candidate.get("attempts", [])
        ],
    }
    (outdir / "visual_sources.json").write_text(
        json.dumps(failure, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    raise ValueError(
        "知识帖自动恢复已耗尽本轮候选：等待后续班次重新抓取事实与图片"
    )

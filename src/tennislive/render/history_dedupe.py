"""Detect repetitive Xiaohongshu copy against the most recent posts.

The checker deliberately uses only the standard library.  It compares semantic
parts of a post instead of its raw text so recurring hashtags, dates and the
account signature do not make every daily digest look alike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import unicodedata


_DATED_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_PREFIX = re.compile(
    r"^[^\w\u4e00-\u9fff]*"
    r"(?:\d{4}[./\-\u5e74])?\d{1,2}[./\-\u6708]\d{1,2}(?:\u65e5)?"
    r"\s*[|\uff5c:\uff1a\u00b7\-]?\s*"
)
_HASHTAG_LINE = re.compile(r"^(?:\s*#[^#\s]+\s*)+$")
_CHAR = re.compile(r"[a-z0-9\u4e00-\u9fff]")
_FIXED_LINES = {
    "\u4eca\u5929\u53ea\u8bb2\u4e09\u4ef6\u4e8b",
    "\u4eca\u5929\u5148\u770b\u8fd9\u4e00\u4ef6\u4e8b",
    "\u4eca\u665a\u7126\u70b9\u5317\u4eac\u65f6\u95f4",
    "\u4eca\u665a\u53ea\u5708\u4e09\u573a",
    "\u4eca\u665a\u53ea\u770b\u8fd9\u4e09\u573a",
    "\u4e2d\u56fd\u7403\u5458\u901f\u62a5",
    "\u4e00\u573a\u7403\u770b\u7ec6\u4e00\u70b9",
    "\u7f51\u7403\u51b7\u77e5\u8bc6",
    "\u6211\u7684\u4e00\u7968",
    "\u7559\u4e2a\u7b54\u6848",
}


@dataclass(frozen=True)
class HistoricalPost:
    """One dated Xiaohongshu post loaded from the generated output."""

    published_on: date
    path: Path
    text: str


@dataclass(frozen=True)
class SimilarityThresholds:
    """Thresholds tuned for short Chinese social copy, in the 0..1 range."""

    title: float = 0.82
    opening: float = 0.72
    body: float = 0.58
    exact_phrase_chars: int = 18

    def __post_init__(self) -> None:
        for name in ("title", "opening", "body"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} threshold must be between 0 and 1")
        if self.exact_phrase_chars < 8:
            raise ValueError("exact_phrase_chars must be at least 8")


@dataclass(frozen=True)
class PostSimilarity:
    """Explainable comparison with one historical post."""

    published_on: date
    path: Path
    title_similarity: float
    opening_similarity: float
    body_similarity: float
    repeated_phrases: tuple[str, ...]
    triggers: tuple[str, ...]

    @property
    def maximum_similarity(self) -> float:
        return max(
            self.title_similarity,
            self.opening_similarity,
            self.body_similarity,
        )


@dataclass(frozen=True)
class DedupeResult:
    """Decision returned to the CLI/QA layer."""

    passed: bool
    history_count: int
    comparisons: tuple[PostSimilarity, ...]
    reason: str

    @property
    def closest(self) -> PostSimilarity | None:
        if not self.comparisons:
            return None
        return max(
            self.comparisons,
            key=lambda item: (
                item.maximum_similarity,
                item.published_on,
                str(item.path),
            ),
        )


@dataclass(frozen=True)
class _PostParts:
    title: str
    opening: str
    body: str
    meaningful_lines: tuple[tuple[str, str], ...]


def load_recent_posts(
    output_root: Path | str,
    *,
    before: date | None = None,
    limit: int = 7,
    filename: str = "xiaohongshu.txt",
) -> list[HistoricalPost]:
    """Load the newest dated posts before ``before`` (exclusive)."""
    if limit < 1:
        return []
    root = Path(output_root)
    if not root.is_dir():
        return []

    found: list[HistoricalPost] = []
    for directory in root.iterdir():
        if not directory.is_dir() or not _DATED_DIR.fullmatch(directory.name):
            continue
        try:
            published_on = date.fromisoformat(directory.name)
        except ValueError:
            continue
        if before is not None and published_on >= before:
            continue
        path = directory / filename
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if text.strip():
            found.append(HistoricalPost(published_on, path, text))

    found.sort(key=lambda post: (post.published_on, str(post.path)), reverse=True)
    return found[:limit]


def check_recent_posts(
    current_text: str,
    output_root: Path | str,
    *,
    current_date: date | None = None,
    history_limit: int = 7,
    minimum_history: int = 1,
    thresholds: SimilarityThresholds | None = None,
) -> DedupeResult:
    """Check copy against the latest generated posts on disk."""
    history = load_recent_posts(
        output_root,
        before=current_date,
        limit=history_limit,
    )
    return check_against_history(
        current_text,
        history,
        minimum_history=minimum_history,
        thresholds=thresholds,
    )


def check_against_history(
    current_text: str,
    history: list[HistoricalPost] | tuple[HistoricalPost, ...],
    *,
    minimum_history: int = 1,
    thresholds: SimilarityThresholds | None = None,
) -> DedupeResult:
    """Compare copy with supplied history and return a deterministic decision."""
    if minimum_history < 0:
        raise ValueError("minimum_history cannot be negative")
    thresholds = thresholds or SimilarityThresholds()
    usable = tuple(post for post in history if post.text.strip())
    if len(usable) < minimum_history:
        return DedupeResult(
            passed=True,
            history_count=len(usable),
            comparisons=(),
            reason=(
                f"\u53ef\u7528\u5386\u53f2\u4e0d\u8db3\uff08{len(usable)}/{minimum_history}\uff09\uff0c"
                "\u5b89\u5168\u653e\u884c"
            ),
        )

    current = _parts(current_text)
    comparisons = tuple(
        _compare(current, post, thresholds)
        for post in sorted(
            usable,
            key=lambda item: (item.published_on, str(item.path)),
            reverse=True,
        )
    )
    failed = [item for item in comparisons if item.triggers]
    if failed:
        worst = max(
            failed,
            key=lambda item: (
                len(item.triggers),
                item.maximum_similarity,
                item.published_on,
            ),
        )
        return DedupeResult(
            passed=False,
            history_count=len(usable),
            comparisons=comparisons,
            reason=(
                f"\u4e0e {worst.published_on.isoformat()} \u6587\u6848\u91cd\u590d\uff1a"
                + "\uff1b".join(worst.triggers)
            ),
        )

    closest = max(
        comparisons,
        key=lambda item: (item.maximum_similarity, item.published_on),
    )
    return DedupeResult(
        passed=True,
        history_count=len(usable),
        comparisons=comparisons,
        reason=(
            f"\u6700\u63a5\u8fd1 {closest.published_on.isoformat()}\uff0c"
            f"\u6700\u9ad8\u76f8\u4f3c\u5ea6 {closest.maximum_similarity:.0%}\uff0c\u4f4e\u4e8e\u9608\u503c"
        ),
    )


def _compare(
    current: _PostParts,
    historical: HistoricalPost,
    thresholds: SimilarityThresholds,
) -> PostSimilarity:
    old = _parts(historical.text)
    title_score = _ngram_jaccard(current.title, old.title, 2)
    opening_score = _ngram_jaccard(current.opening, old.opening, 3)
    body_score = _ngram_jaccard(current.body, old.body, 3)
    repeated = _repeated_lines(
        current.meaningful_lines,
        old.meaningful_lines,
        thresholds.exact_phrase_chars,
    )

    triggers: list[str] = []
    if min(len(current.title), len(old.title)) >= 6 and title_score >= thresholds.title:
        triggers.append(
            f"\u6807\u9898\u94a9\u5b50 {title_score:.0%}\u2265{thresholds.title:.0%}"
        )
    if (
        min(len(current.opening), len(old.opening)) >= 12
        and opening_score >= thresholds.opening
    ):
        triggers.append(
            f"\u5f00\u573a {opening_score:.0%}\u2265{thresholds.opening:.0%}"
        )
    if min(len(current.body), len(old.body)) >= 40 and body_score >= thresholds.body:
        triggers.append(
            f"\u6b63\u6587 {body_score:.0%}\u2265{thresholds.body:.0%}"
        )
    if repeated:
        triggers.append(f"\u590d\u7528\u957f\u53e5\u201c{repeated[0]}\u201d")

    return PostSimilarity(
        published_on=historical.published_on,
        path=historical.path,
        title_similarity=title_score,
        opening_similarity=opening_score,
        body_similarity=body_score,
        repeated_phrases=repeated,
        triggers=tuple(triggers),
    )


def _parts(text: str) -> _PostParts:
    raw_lines = [line.strip() for line in _normal_unicode(text).splitlines()]
    raw_lines = [line for line in raw_lines if line]
    title_raw = raw_lines[0] if raw_lines else ""
    title = _signature(_DATE_PREFIX.sub("", title_raw))

    meaningful: list[tuple[str, str]] = []
    for index, raw in enumerate(raw_lines):
        if index == 0 or _is_noise_line(raw):
            continue
        signature = _signature(raw)
        if len(signature) >= 2 and signature not in _FIXED_LINES:
            meaningful.append((raw, signature))

    opening = "".join(signature for _, signature in meaningful[:2])
    body = "".join(signature for _, signature in meaningful)
    return _PostParts(title, opening, body, tuple(meaningful))


def _normal_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").replace("\r\n", "\n")


def _signature(text: str) -> str:
    return "".join(_CHAR.findall(_normal_unicode(text).lower()))


def _is_noise_line(line: str) -> bool:
    compact = line.strip()
    if not compact or _HASHTAG_LINE.fullmatch(compact):
        return True
    signature = _signature(compact)
    if signature in _FIXED_LINES:
        return True
    return (
        signature.startswith("\u5173\u6ce8\u7f51\u7403\u65f6\u5dee")
        or signature.startswith("\u5173\u6ce8at\u7f51\u7403\u65f6\u5dee")
        or signature.startswith("\u8fd9\u91cc\u662fat\u7f51\u7403\u65f6\u5dee")
        or signature.startswith("\u8fd9\u91cc\u662f\u7f51\u7403\u65f6\u5dee")
    )


def _ngrams(text: str, width: int) -> set[str]:
    if not text:
        return set()
    if len(text) <= width:
        return {text}
    return {text[index : index + width] for index in range(len(text) - width + 1)}


def _ngram_jaccard(left: str, right: str, width: int) -> float:
    a = _ngrams(left, width)
    b = _ngrams(right, width)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _repeated_lines(
    current: tuple[tuple[str, str], ...],
    historical: tuple[tuple[str, str], ...],
    minimum_chars: int,
) -> tuple[str, ...]:
    old_signatures = {signature for _, signature in historical}
    repeated: list[str] = []
    for raw, signature in current:
        # Score/results metadata can legitimately recur on adjacent days.  A
        # reused prose sentence, identified by sentence punctuation, is the
        # editorial repetition this signal is intended to catch.
        prose_marks = ("。", "！", "？", "!", "?", "，", ",", "；", ";")
        is_prose = any(mark in raw for mark in prose_marks)
        if (
            is_prose
            and len(signature) >= minimum_chars
            and signature in old_signatures
        ):
            cleaned = re.sub(r"\s+", " ", raw).strip()
            if cleaned not in repeated:
                repeated.append(cleaned)
    return tuple(repeated[:3])

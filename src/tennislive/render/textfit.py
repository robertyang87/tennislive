"""把一句话裁到给定字数，且只在"话说完了"的地方裁。

原来只有小红书正文用得上，所以放在 xiaohongshu.py 里。卡片层也需要同一套
规则——今晚焦点卡的"看点"行是交给 CSS 的 line-clamp 去截的，会从词中间切开
并留下半个引号（"…后来她把'让萨巴伦卡这个姓被记…"）。两处用同一份逻辑，
就不会一边说得完整、另一边印半句。
"""

from __future__ import annotations

import re


# 一条被截断的文案要能独立读完。下面这些收尾方式在生产环境里真的印出来过，
# 每一条都是"字数够了但话没说完"：
#   看点｜7月24日。                      -> 只剩日期，主句被砍掉
#   看点｜结束16个月冠军等待后。          -> 状语从句，正文没了
#   看点｜……和阿利斯（世界第83）         -> 括号没闭合 / 冒号后的答案丢了
_MIN_TRUNCATED_CHARS = 8
# 纯日期/比分/序号，没有任何叙述成分
_BARE_FACT_RE = re.compile(r"^[\d\s年月日号时分秒点第.:：、\-—~～/]+$")
# 悬空的连接词、介词、副词、系动词：中文句子不会停在这些字上
_DANGLING_TAIL = frozenset("的地得和与及或但而却则并把被让使从向对为于是在有就才也还都很更最会能要想将已又再")
_DANGLING_SUFFIX = (
    "之后", "以后", "过后", "之前", "以前", "的时候", "之时", "之际",
    "以来", "的话", "不仅", "不但", "因为", "虽然", "尽管", "随着",
)
# "后/时/前"多数情况下是状语从句的尾巴，但这几个词组本身就是完整收尾
_COMPLETE_TIME_TAIL = frozenset(
    {"最后", "落后", "身后", "背后", "滞后", "当时", "准时", "及时", "按时",
     "当前", "目前", "眼前", "面前", "空前"}
)
# 以介词/从属连词开头、又没有下一个分句的片段，本身只是状语，不是话
_SUBORDINATE_OPENER = (
    "从", "自", "随着", "在", "当", "如果", "虽然", "尽管", "因为",
    "为了", "除了", "若", "一旦", "结束", "等到", "直到",
)
_BRACKET_PAIRS = (("（", "）"), ("(", ")"), ("「", "」"), ("《", "》"), ("【", "】"))
_QUOTE_MARKS = ("“", "”", "‘", "’")
_CUT_PUNCT = "。！？；;，,"
_KEEP_TAIL_PUNCT = "？！"


_CJK_RE = re.compile(r"[一-鿿]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _is_complete_thought(piece: str, *, truncated: bool) -> bool:
    """Can this fragment be read on its own without the text we cut away?"""
    if not truncated:
        return True
    if len(piece) < _MIN_TRUNCATED_CHARS or _BARE_FACT_RE.match(piece):
        return False
    # 冒号是在许下承诺（"只剩最后一问："），答案被截掉就只剩半句话
    if "：" in piece or ":" in piece:
        return False
    for opener, closer in _BRACKET_PAIRS:
        if piece.count(opener) != piece.count(closer):
            return False
        # 括号配平还不够：以一个**闭合**的括注收尾同样是半句话。括注是修饰语，
        # 被它修饰的那个成分正要拿去做主语/宾语，谓语却被砍掉了——
        # "……斯尼古尔（世界第54）和塔格尔（世界第74）"就这样印上了 7.26 的
        # 布拉格站和汉堡站（顶头的注释早就把这一形状列为反例，只是当时只查了配平）。
        if piece.endswith(closer):
            return False
    if piece.count(_QUOTE_MARKS[0]) != piece.count(_QUOTE_MARKS[1]):
        return False
    if piece.count(_QUOTE_MARKS[2]) != piece.count(_QUOTE_MARKS[3]):
        return False
    if piece.endswith(_DANGLING_SUFFIX):
        return False
    if piece[-1] in _DANGLING_TAIL:
        return False
    if piece[-1] in "后时前" and piece[-2:] not in _COMPLETE_TIME_TAIL:
        return False
    if piece.startswith(_SUBORDINATE_OPENER) and not re.search(r"[，,]", piece):
        return False
    return True


def _drop_parentheticals(text: str) -> str:
    """Rank/seed asides carry the least meaning per character, so they go first."""
    return " ".join(re.sub(r"[（(][^（()）]*[)）]", "", text).split())


def _shorten_candidates(cleaned: str) -> list[tuple[str, bool]]:
    """Prefix cuts of `cleaned`, longest first, paired with a truncated flag."""
    seen: set[str] = set()
    out: list[tuple[str, bool]] = []
    for source in (cleaned, _drop_parentheticals(cleaned)):
        if not source:
            continue
        trimmed_aside = source != cleaned
        cuts = {m.end() for m in re.finditer(f"[{re.escape(_CUT_PUNCT)}]", source)}
        cuts.add(len(source))
        for cut in sorted(cuts, reverse=True):
            piece = source[:cut].strip().rstrip(_CUT_PUNCT + "、：:")
            if not piece or piece in seen:
                continue
            seen.add(piece)
            out.append((piece, cut < len(source) or trimmed_aside))
    # 留得越多越好；同长度时原文优先于删掉括号的版本
    out.sort(key=lambda row: (len(row[0]), not row[1]), reverse=True)
    return out


def _short_complete(text: str, limit: int) -> str:
    """Shorten to at most `limit` chars, cutting only where the thought ends.

    Returns "" when nothing that fits can be read on its own -- callers that
    have a fallback should use it rather than print a dangling clause.
    """
    cleaned = " ".join(text.strip().split()).rstrip(_CUT_PUNCT)
    if len(cleaned) <= limit:
        return cleaned
    for piece, truncated in _shorten_candidates(cleaned):
        if len(piece) <= limit and _is_complete_thought(piece, truncated=truncated):
            return piece
    words = cleaned.split()
    if len(words) > 1:
        built = ""
        for word in words:
            candidate = f"{built} {word}".strip()
            if len(candidate) > limit:
                break
            built = candidate
        # 按空格拼前缀这一招是给以空格分词的文本准备的。中文句子里唯一带空格的
        # 通常是外文人名，于是它会从人名中间停下来，还因为全是拉丁字母、末字不在
        # 悬空表里而被判成"完整"——"Magali Kempen / Alexandra"就这么当看点印了
        # 出去。中文原句裁出一段纯外文，那不是话，是名字。
        if built and (_has_cjk(built) or not _has_cjk(cleaned)):
            if _is_complete_thought(built, truncated=True):
                return built
    return ""


def _short(text: str, limit: int) -> str:
    """Same as `_short_complete`, but never returns empty.

    The old fallback here returned the untouched string, so a sentence with no
    usable cut point silently blew the caller's limit -- a 49-char preview angle
    reached print under a 34-char budget. `plan_post` rejects any post
    containing an ellipsis, so the last resort cuts rather than elides: a
    punctuation cut if one fits, otherwise a flat cut at the limit. Callers with
    a better line to fall back on should call `_short_complete` and branch.
    """
    picked = _short_complete(text, limit)
    if picked:
        return picked
    cleaned = " ".join(text.strip().split()).rstrip(_CUT_PUNCT)
    if len(cleaned) <= limit:
        return cleaned
    for piece, _ in _shorten_candidates(cleaned):
        if len(piece) <= limit:
            return piece
    return _close_brackets(cleaned[:limit]).rstrip(_CUT_PUNCT + "、：:") or cleaned[:limit]


def _close_brackets(piece: str) -> str:
    """Drop a bracket or quote that a flat cut left hanging open."""
    for opener, closer in _BRACKET_PAIRS:
        if piece.count(opener) > piece.count(closer):
            piece = piece[: piece.rfind(opener)]
    if piece.count(_QUOTE_MARKS[0]) > piece.count(_QUOTE_MARKS[1]):
        piece = piece[: piece.rfind(_QUOTE_MARKS[0])]
    if piece.count(_QUOTE_MARKS[2]) > piece.count(_QUOTE_MARKS[3]):
        piece = piece[: piece.rfind(_QUOTE_MARKS[2])]
    return piece

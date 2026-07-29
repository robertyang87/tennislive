"""中文平台热搜里的网球线索。

英文源回答不了「这件事在**中文舆论场**热不热」。这个号的读者在微博、抖音、
小红书上，而「是不是舆论热点」原来完全由英文媒体的家数决定——中文那边炸了
而英文没报的事（郑钦文相关的尤其多），这套一点都看不见。

四个源实测下来分三档，**照实记，不拿镜像冒充官方**：

| 源 | 路 | 状态 |
|---|---|---|
| 微博热搜 | `weibo.com/ajax/side/hotSearch` | ✅ 官方、免鉴权，51 条 |
| 抖音热搜 | `iesdouyin.com/.../hotsearch/billboard/word/` | ✅ 官方、免鉴权，50 条 |
| 小红书热榜 | 官方两个入口一个 404 一个 500 → 走今日热榜镜像 | ⚠️ 镜像 |
| 微信 | 见下 | ⚠️ 指数拿不到，接的是热文榜镜像 |

⚠️ **微信指数就算拿得到也不是发现工具。** 它是「给词查数」——你得先知道要查
哪个词，它回答不了「今天什么热」。而且 `search.weixin.qq.com/cgi-bin/wxaweb/wxindex`
对无签名请求返回 `{"code":-1,"msg":"process failed."}`，签名要从微信小程序里
取，GitHub runner 上拿不到。所以这儿接的是**微信 24 小时热文榜**（同样走镜像），
并在 `source` 里写清楚它不是指数——它是文章标题榜，反而比一个指数数字更适合
拿来发现话题。

⚠️ **403 是缺请求头，不是被封。** 微博那个接口对 `python-urllib` 的默认 UA
直接 403，同一条 URL 用浏览器 UA + `Referer: https://weibo.com/` 就是 200。
差点据此写下「微博热搜抓不到」——又一次「空结果先自证是真空」。

⚠️ **热度值不能跨平台比。** 微博的 `num`（4642766）、抖音的 `hot_value`
（12012126）、今日热榜的「918.6w」是三套各自的口径，放一起排名毫无意义。
所以只在同一个源内部按榜上顺序取，`heat` 原样记着给人看，不参与打分。
"""

from __future__ import annotations

import html as _html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import requests

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# ------------------------------------------------------------------ 网球线索词

# 一个就够：这些词在中文热搜里只可能是网球。
_STRONG_WORDS: tuple[str, ...] = (
    "网球", "网坛", "网球公开赛",
    "温网", "美网", "法网", "澳网", "中网",
    "温布尔登", "罗兰加洛斯", "罗兰·加洛斯",
    "atp", "wta",
    "戴维斯杯", "台维斯杯", "比利·简·金杯", "联合会杯",
    "上海大师赛", "中国网球公开赛",
)

# 赛事的中文简称 → 英文簇里认得出的那个词。「美网」没有可用的词：
# `US Open` 切出来是 us / open，两个都在 topic_radar 的停用词里。
_TOURNAMENT_TERMS: dict[str, tuple[str, ...]] = {
    "温网": ("wimbledon",),
    "温布尔登": ("wimbledon",),
    "法网": ("roland", "garros", "french"),
    "罗兰加洛斯": ("roland", "garros"),
    "罗兰·加洛斯": ("roland", "garros"),
    "澳网": ("australian",),
    "中网": ("beijing", "china"),
    "中国网球公开赛": ("beijing", "china"),
    "上海大师赛": ("shanghai",),
}

# 单独出现说明不了什么，要另有一个强信号或球员名同现才算。
# 「大满贯」在中文体育报道里乒乓球、游泳、赛车都在用；「大师赛」斯诺克和
# 高尔夫各有一个。「德约」看着像德约科维奇，可它也是「**道德约**束」的中间
# 两个字——这种连字成词的撞法，中文里防不住，只能要求同现。
_WEAK_WORDS: tuple[str, ...] = ("大满贯", "大师赛", "球王", "德约")

# 两个字的译名太容易撞上别人——「保罗」是保罗·乔治，「米勒」满大街，
# 「李娜」首先是歌手。所以两个字的名字默认要同现一个网球语境词，
# **除了这几个：判据是「这两个字在中文里既不是常用词，也不是别的名人的
# 通用简称」**。往里加之前先拿这句话对一遍。
_SHORT_OK: frozenset[str] = frozenset({"辛纳", "小德", "小威", "大威"})

# 译名表里没有、但中文媒体天天在用的简称。**正名一律去表里查**
# （`zh/players.py` + `player_names_top500.json`），这儿只放简称和昵称。
_NICKNAMES: dict[str, str] = {
    "小德": "Novak Djokovic",
    "德约": "Novak Djokovic",
    "小威": "Serena Williams",
    "大威": "Venus Williams",
    "郑钦文": "Qinwen Zheng",   # 表里是 "Qinwen Zheng"，这儿显式钉住，别靠遍历撞
}

_LATIN = re.compile(r"[a-z0-9']+")
# 英文名切出来之后，这些词对不上任何专名，留着只会误配。
_NAME_STOP = frozenset({"the", "van", "der", "den", "del", "dos", "les"})


def _fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def _latin_terms(name_en: str) -> tuple[str, ...]:
    """英文名 → 用来和英文簇的专名取交集的那几个词。

    口径要和 `topic_radar._proper_terms` 一致（小写、长度 > 2），否则
    `Zheng Qinwen` 那一簇明明在，交集却是空的。
    """
    return tuple(
        sorted(
            w for w in _LATIN.findall(_fold(name_en))
            if len(w) > 2 and w not in _NAME_STOP
        )
    )


@lru_cache(maxsize=1)
def _player_index() -> dict[str, tuple[str, ...]]:
    """中文名 → 英文词组。**名字不手打，两张表加简称表**。

    表里同一个中文名可能对应多个英文名（同姓不同人，如「保罗」）。那种情况
    把词并起来——反正下游只拿它去取交集，多一个词只会少配，不会错配。
    """
    from ..zh import PLAYER_ZH
    from ..zh import _ranked_player_names  # noqa: PLC2701 - 同一个包里的内部工具

    pairs: list[tuple[str, str]] = [(zh, en) for en, zh in PLAYER_ZH.items()]
    for en_norm, zh in _ranked_player_names().items():
        pairs.append((zh, en_norm))
    pairs.extend((zh, en) for zh, en in _NICKNAMES.items())

    index: dict[str, set[str]] = {}
    for zh, en in pairs:
        zh = zh.strip()
        # ⚠️ **单字译名一律丢掉。** 排名表里有 18 条机器音译只出了姓
        # （`Jiaqi Wang` → 「王」、`Boyoung Jeong` → 「郑」），拿它当关键词
        # 等于把「郑钦文」「王楚钦」「张泽禹」全判成网球——实测一轮 150 条
        # 榜单里挡出 7 条纯噪声。表里那 18 条本身也该补全，但补的是**真人的
        # 名字**，音译不出唯一写法，不能靠猜。
        if len(zh) < 2:
            continue
        index.setdefault(zh, set()).update(_latin_terms(en))
    # **英文词为空的也留着。** `Na Li` 两个词都只有两个字母，`_latin_terms`
    # 一个都不剩——但「李娜」仍然是一条网球线索，只是没法拿去和英文簇取交集。
    # 一开始把这类过滤掉了，于是它连「差一点」那份清单都进不去，看起来像
    # 「表里根本没有李娜」。
    return {zh: tuple(sorted(terms)) for zh, terms in index.items()}


@dataclass(frozen=True)
class ZhHot:
    """中文平台榜上的一条，且判定为和网球有关。"""

    source: str          # 微博热搜 / 抖音热搜 / 小红书热榜（镜像）…
    word: str            # 榜上的原词，一个字都不改
    rank: int            # 榜上第几位（1 起）
    heat: str            # 平台自己的热度值，**各家口径不同，不跨平台比**
    url: str
    matched: tuple[str, ...] = ()   # 命中的中文线索词——判据要摆得出来
    terms: tuple[str, ...] = ()     # 对应的英文词，供和英文簇的专名取交集
    kind: str = "zh-hot-search"

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source": self.source,
            "word": self.word,
            "rank": self.rank,
            "heat": self.heat,
            "url": self.url,
            "matched": list(self.matched),
            "terms": list(self.terms),
        }


def tennis_clues(word: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """一条热搜词里的网球线索 → (命中的中文词, 对应的英文词)。

    没有线索就返回两个空元组。判定分两步，**先找锚点再收边角**：

    1. **锚点**：强信号词，或三个字以上的球员译名，或 `_SHORT_OK` 里那几个。
       一个都没有，就不算网球——「保罗宣布退役」讲的是保罗·乔治。
    2. 有锚点之后，弱信号词和两个字的名字也一并记进 `matched`：它们本身
       判不了案，但能给下游多带几个可以取交集的英文词。
    """
    folded = _fold(word)
    index = _player_index()

    anchors: list[str] = []
    extras: list[str] = []
    terms: set[str] = set()

    for term in _STRONG_WORDS:
        if _fold(term) in folded:
            anchors.append(term)
    for zh, latin in index.items():
        if zh not in word:
            continue
        if len(zh) >= 3 or zh in _SHORT_OK:
            anchors.append(zh)
        else:
            extras.append(zh)
        terms.update(latin)
    for term in _WEAK_WORDS:
        if term in word:
            extras.append(term)

    if not anchors:
        return (), ()
    matched = tuple(dict.fromkeys(anchors + extras))
    # 强信号里的赛事名也要带上英文词——「温网」那条热搜要能和 Wimbledon
    # 那一簇对上，否则中文源永远只在自己那一栏里孤零零地热着。
    for term in matched:
        terms.update(_TOURNAMENT_TERMS.get(term, ()))
    return matched, tuple(sorted(terms))


def near_miss(word: str) -> tuple[str, ...]:
    """差一点算网球的那些词——**挡掉了什么也要说出来**。

    只有弱信号或两个字的名字、没有锚点的，进这份清单让人扫一眼。
    只在成功时出声的过滤器，没法证明它真的看过。
    """
    if tennis_clues(word)[0]:
        return ()
    hits = [t for t in _WEAK_WORDS if t in word]
    hits += [zh for zh in _player_index() if len(zh) < 3 and zh in word]
    return tuple(dict.fromkeys(hits))


# ------------------------------------------------------------------ 各源抓取


def _weibo(payload: bytes) -> list[tuple[str, str, str]]:
    data = json.loads(payload.decode("utf-8"))
    out = []
    for item in (data.get("data") or {}).get("realtime") or []:
        word = str(item.get("word") or "").strip()
        if word:
            out.append((word, str(item.get("num") or ""),
                        "https://s.weibo.com/weibo?q=" + quote(f"#{word}#")))
    return out


def _douyin(payload: bytes) -> list[tuple[str, str, str]]:
    data = json.loads(payload.decode("utf-8"))
    words = data.get("word_list") or (data.get("data") or {}).get("word_list") or []
    out = []
    for item in words:
        word = str(item.get("word") or "").strip()
        if word:
            out.append((word, str(item.get("hot_value") or ""),
                        "https://www.douyin.com/search/" + quote(word)))
    return out


def _uapis(payload: bytes) -> list[tuple[str, str, str]]:
    """UApiPro 的统一热榜接口 → (词, 热度, 链接)。

    小红书原来是抓今日热榜的 HTML `<table>`，现在改走这个 JSON 接口：
    **同一份上游数据**（实测当天第一条一字不差），但契约是 JSON 而不是
    一段会随时被改掉的 HTML。免注册、免 key。

    ⚠️ **它没有微信**（`type=weixin` / `wechat` / `wxhot` 一律
    `invalid hotboard type`），所以微信那一路仍然只能走镜像。
    """
    data = json.loads(payload.decode("utf-8"))
    out = []
    for item in data.get("list") or []:
        word = str(item.get("title") or "").strip()
        if word:
            out.append((word, str(item.get("hot_value") or ""),
                        str(item.get("url") or "")))
    return out


_ROW = re.compile(
    r'<td align="center">(\d+)\.</td>\s*<td><a href="([^"]+)"[^>]*>(.*?)</a></td>'
    r'\s*(?:<td class="ws">([^<]*)</td>)?',
    re.S,
)
_TAG = re.compile(r"<[^>]+>")


def _tophub(payload: bytes) -> list[tuple[str, str, str]]:
    """今日热榜的榜单页 → (词, 热度, 链接)。

    页面就一张 `<table>`，每行「序号 / 带链接的词 / 热度」。**别用整页正则去
    捞 `<a>`**：导航和广告也是 `<a>`，捞出来一堆噪点。
    """
    text = payload.decode("utf-8", errors="replace")
    table = re.search(r"<table[^>]*>(.*?)</table>", text, re.S)
    if not table:
        return []
    out = []
    for _rank, url, label, heat in _ROW.findall(table.group(1)):
        word = _html.unescape(_TAG.sub("", label)).strip()
        if word:
            out.append((word, _html.unescape(heat or "").strip(), url))
    return out


@dataclass(frozen=True)
class _Board:
    label: str
    url: str
    referer: str
    parse: object
    note: str = ""
    # 主源取不到（或解析出 0 行）时退到这一路。**只给第三方源配**：
    # 官方接口挂了就该报降级，拿镜像顶上去等于把「官方变了」这件事藏起来。
    fallback: "tuple[str, str, object] | None" = None


_BOARDS: tuple[_Board, ...] = (
    _Board("微博热搜", "https://weibo.com/ajax/side/hotSearch",
           "https://weibo.com/", _weibo),
    _Board("抖音热搜",
           "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
           "https://www.douyin.com/", _douyin),
    # 小红书官方两个入口：`edith.xiaohongshu.com/api/sns/web/v1/search/hot_list`
    # 返回 404，`www.xiaohongshu.com/api/sns/web/v1/search/hot_list` 返回 500
    # （`create invoker failed, service: jarvis-gateway-default`）——都要签名。
    # 主源改走 UApiPro 的 JSON，今日热榜的 HTML 退居备用：两边是同一份上游
    # 数据，但 JSON 的契约比一段随时会被改掉的 `<table>` 稳。
    _Board("小红书热榜", "https://uapis.cn/api/v1/misc/hotboard?type=xiaohongshu",
           "https://uapis.cn/", _uapis, note="第三方聚合，非官方接口",
           fallback=("https://tophub.today/n/L4MdA5ldxD",
                     "https://tophub.today/", _tophub)),
    # ⚠️ **「微信热搜」至少是五种不同的东西**，接之前先想清楚要哪一种：
    #   ① 搜一搜热点词  ② 公众号热点话题榜  ③ 公众号 24h 热文榜
    #   ④ 微信指数（给词查数）  ⑤ 视频号热点榜
    # 我们接的是 ③。想要的其实更接近 ①/②，但那两种目前只有付费接口
    # （聚合数据卖的是 ②，无 key 返回「错误的请求KEY」）。
    # ④ 无签名一律 `{"code":-1}`，而且它回答不了「今天什么热」。
    _Board("微信热文榜", "https://tophub.today/n/WnBe01o371",
           "https://tophub.today/", _tophub,
           note="经今日热榜镜像；这是 24h 热文榜，不是微信指数"),
    # 这两路是顺手加的，走的是小红书那同一个接口，各一行的成本。
    # 它们各代表中文舆论的另一面：知乎是**讨论**（问题标题本身就带着争议点），
    # 百度是**搜索**（和 Google 每日热搜同一个性质，但看的是国内的搜法）。
    _Board("知乎热榜", "https://uapis.cn/api/v1/misc/hotboard?type=zhihu",
           "https://uapis.cn/", _uapis, note="第三方聚合，非官方接口"),
    _Board("百度热搜", "https://uapis.cn/api/v1/misc/hotboard?type=baidu",
           "https://uapis.cn/", _uapis, note="第三方聚合，非官方接口"),
)

# 拿不到、且**短期内也不打算再试**的源。写进产物里，别让它悄悄消失。
UNAVAILABLE: dict[str, str] = {
    "微信指数": (
        "拿不到 · search.weixin.qq.com 无签名返回 {\"code\":-1}，"
        "签名要从微信小程序里取；且它是「给词查数」，回答不了「今天什么热」"
    ),
    "小红书官方接口": (
        "拿不到 · edith 域 404、www 域 500，两条都要签名；"
        "已改走 UApiPro（主）+ 今日热榜镜像（备）"
    ),
    "微信搜一搜热点词 / 公众号热点话题榜": (
        "拿不到 · 只有付费接口（聚合数据卖的是话题榜，无 key 返回「错误的请求KEY」；"
        "百度千帆 401）。免费那几家都没有微信：UApiPro 的 weixin/wechat/wxhot "
        "一律 invalid hotboard type，DailyHotApi 公开支持列表里也没有"
    ),
}


@dataclass
class ZhTrendResult:
    hits: list[ZhHot] = field(default_factory=list)
    status: dict[str, str] = field(default_factory=dict)
    scanned: int = 0
    near: list[dict] = field(default_factory=list)


def _pull(url: str, referer: str, parse, get, timeout: int, top: int):
    response = get(
        url,
        headers={
            "User-Agent": _UA,
            "Referer": referer,
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    rows = parse(response.content)[:top]
    if not rows:
        # **一张热榜不会是空的。** 解析出 0 行只有一个意思：结构变了。
        # 当成异常抛，好让它和「取不到」走同一条退路——「扫 0 条」和
        # 「今天榜上没有网球」在状态里长得一模一样，能静默好几个月。
        raise ValueError("解析出 0 行")
    return rows


def _fetch_board(board: _Board, get, timeout: int, top: int):
    note = board.note
    try:
        rows = _pull(board.url, board.referer, board.parse, get, timeout, top)
    except Exception as exc:  # noqa: BLE001 - 每个源都是可选信号，一个挂了不能挡住别的
        why = "解析出 0 行，结构可能变了" if isinstance(exc, ValueError) else type(exc).__name__
        if board.fallback is None:
            return board, [], [], 0, f"降级 · {why}"
        url, referer, parse = board.fallback
        try:
            rows = _pull(url, referer, parse, get, timeout, top)
        except Exception as exc2:  # noqa: BLE001
            return board, [], [], 0, f"降级 · 主源 {why}／备用 {type(exc2).__name__}"
        # **退到备用了要说出来。** 悄悄换源等于把「主源已经坏了」藏起来，
        # 下次它彻底不能用的时候没人知道它坏了多久。
        note = (note + "；" if note else "") + f"主源 {why}，本次走备用源"

    label = board.label + (f"（{note}）" if note else "")
    hits: list[ZhHot] = []
    near: list[dict] = []
    for rank, (word, heat, url) in enumerate(rows, 1):
        matched, terms = tennis_clues(word)
        if matched:
            hits.append(ZhHot(source=label, word=word, rank=rank, heat=heat,
                              url=url, matched=matched, terms=terms))
            continue
        missed = near_miss(word)
        if missed:
            near.append({"source": label, "word": word, "clues": list(missed)})
    # 榜上一条网球都没有是**常态**（微博 51 条里通常 0～1 条），所以状态里要
    # 同时报「扫了几条」和「中了几条」——只报后者的话，0 条看起来和抓挂了
    # 一模一样。
    return board, hits, near, len(rows), f"正常 · 扫 {len(rows)} 条 / 网球 {len(hits)} 条"


def fetch_zh_hot(
    *,
    get=requests.get,
    timeout: int = 20,
    top: int = 60,
) -> ZhTrendResult:
    """四个中文平台的榜单 → 其中和网球有关的那几条。

    并发抓，**一个源挂了不挡住别的**——和 `fetch_trend_signals` 同一个规矩。
    拿不到的源照实记进 `status`，包括那两个需要签名的（见 `UNAVAILABLE`）。
    """
    result = ZhTrendResult()
    with ThreadPoolExecutor(max_workers=len(_BOARDS)) as pool:
        futures = [pool.submit(_fetch_board, b, get, timeout, top) for b in _BOARDS]
        for future in as_completed(futures):
            board, hits, near, scanned, detail = future.result()
            result.hits.extend(hits)
            result.near.extend(near)
            result.scanned += scanned
            result.status[board.label] = detail
    result.status.update(UNAVAILABLE)
    result.hits.sort(key=lambda h: (h.source, h.rank))
    return result

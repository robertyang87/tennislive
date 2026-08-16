#!/usr/bin/env python3
"""按球员／赛事／单场，从 Tennis TV 的公开内容 API 找免费短集锦——**不用人去翻网页**。

账号所有者 2026-08-16：「**你要研究一下怎么去 Tennis TV 官网下载对应的这种
short 的集锦。不要以后每次都用，我去找完把链接给你，这不符合自动化的能力呀**」。

在这之前找一条短集锦只有一条路：打开 `library/short-highlights` 用眼睛翻第一页
——**而那一页只有最新 20 条，最老到不了一天前**（`shang-sonego` 那次就是这么
差点被判成「没有」的）。这个模块把那一步换成一次 HTTP。

## 接口

    GET https://api.tennistv.com/content/atpmedia/video/EN/          列表
    GET https://api.tennistv.com/content/atpmedia/video/EN/<id>      单条
    Header: account: atpmedia          ← 不带这个头拿不到

**实测生效的查询参数只有四个**（2026-08-16，逐个拿「响应内容真的变了」验的）：

| 参数 | 作用 |
|---|---|
| `page` / `pageSize` | 翻页。不给的话 pageSize=10，全库 58226 条 / 5823 页 |
| `tagIds` | 按标签 id 过滤。**`6795` = `video-type:short-highlights`**、`6788` = `entitlement:free`、`6970` = `video-type:match-highlights` |
| `references` | 按引用过滤，形如 `ATP_PLAYER:S0RE` / `ATP_TOURNAMENT:422_2026` / `ATP_MATCH:422_2026_MS122` |

⚠️ **下面这些是我试过、不生效的，别再试一遍**：`p` `pageNumber` `offset` `size`
`tag` `tagLabel` `tagLabels` `filter` `videoType` `q` `search` `query` `sid`
`atpPlayer` `reference`（单数）——一律**静默忽略**，返回和不带参数一模一样。

⚠️ **`tags[]=...` 会返回 HTTP 400 的 HTML 错误页。** 我第一轮是按「响应的 md5
变了没有」判参数生不生效的，于是**把一个 400 判成了「✅生效」**——错误页当然和
正常响应不一样。判据必须是「**返回的内容真的被过滤了**」（条数变少、每条都带
着那个标签），不是「响应变了」。这跟 CLAUDE.md 那条「`?extended=true` 被静默
忽略，别被 200 骗了」是同一个形状的两头：一头是 200 但没过滤，一头是变了但根本
不是数据。

⚠️ **标签在源头就会打错，所以不能只信 `tagIds`。** 辛辛那提 2026 那 48 条
「短集锦」里有一条是 `cincinnati-2026-r2-jiri-lehecka-interview`（210 秒的
采访），它自己带着 `video-type:short-highlights` 标签。**过滤是对的，数据是错
的**——所以这里另外按「标题以 Short Highlights 结尾」和「有 ATP_MATCH 引用」
再筛一道。

## 怎么拿到 sid

- **`ATP_MATCH` 是最准的一把钥匙**：一场球通常有三条（`replay` 付费、
  `match-highlights` 付费、**`short-highlights` 免费**）
- 不知道 match sid 就按**赛事**查（`ATP_TOURNAMENT:<atp赛事id>_<年>`，
  辛辛那提是 `422_2026`），再按姓氏挑——`--who` 就是干这个的
- 赛事 id 不知道就先 `recent`，它把最近的条目连同城市和赛事 sid 一起打出来
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

API = "https://api.tennistv.com/content/atpmedia/video/EN/"
# 这两个 id 是从一条已知条目的 tags 里读出来的（`4559761` 的
# `(6795, 'video-type:short-highlights')`、`(6788, 'entitlement:free')`），
# 不是猜的。⚠️ 哪天对不上了就重新读一条，别在这儿改数字硬凑。
TAG_SHORT_HIGHLIGHTS = 6795
TAG_FREE = 6788
_HEADERS = {"User-Agent": "tennislive/0.1", "account": "atpmedia"}


def _get(path: str = "", **params: object) -> dict:
    query = urllib.parse.urlencode(
        {k: v for k, v in params.items() if v not in (None, "")})
    url = API + path + (("?" + query) if query else "")
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:  # 400 会回一整页 HTML，别让它变成一句 JSON 错
        raise SystemExit(
            f"Tennis TV 内容接口没回 JSON（{url}）：{body[:200]!r}\n"
            "——多半是参数名不对。这个接口对不认识的参数是**静默忽略**，"
            "只有 `tags[]` 这种会真的 400；生效的只有 page/pageSize/tagIds/references。"
        ) from exc


def video_url(item: dict) -> str:
    """条目 → 页面地址。**spec 里放的就是它**（不带令牌，解析在下载那一刻做）。"""
    slug = str(item.get("titleUrlSegment") or "").strip()
    return f"https://www.tennistv.com/videos/{item.get('id')}" + (f"/{slug}" if slug else "")


def _labels(item: dict) -> set[str]:
    return {str(t.get("label") or "") for t in item.get("tags") or []
            if isinstance(t, dict)}


def _ref(item: dict, kind: str) -> str:
    return next((str(r.get("sid") or "") for r in item.get("references") or []
                 if isinstance(r, dict) and r.get("type") == kind), "")


def is_real_short_highlight(item: dict) -> bool:
    """真的是一场球的短集锦吗。

    ⚠️ **不能只看标签**：`cincinnati-2026-r2-jiri-lehecka-interview`（210 秒的
    采访）在源头就被打上了 `video-type:short-highlights`。三条一起看——标签、
    标题、以及**有没有挂到一场具体的比赛上**（采访挂不到）。
    """
    if "video-type:short-highlights" not in _labels(item):
        return False
    slug = str(item.get("titleUrlSegment") or "").casefold()
    if "interview" in slug or "press" in slug:
        return False
    return bool(_ref(item, "ATP_MATCH"))


def rows(*, tag_ids: str = "", references: str = "", page_size: int = 100,
         pages: int = 1) -> list[dict]:
    out: list[dict] = []
    for page in range(pages):
        data = _get(tagIds=tag_ids, references=references,
                    pageSize=page_size, page=page)
        content = data.get("content")
        if not isinstance(content, list) or not content:
            break
        out.extend(c for c in content if isinstance(c, dict))
        info = data.get("pageInfo") or {}
        if page + 1 >= int(info.get("numPages") or 1):
            break
    return out


def _describe(item: dict) -> str:
    meta = item.get("metadata") or {}
    free = "免费" if "entitlement:free" in _labels(item) else "**付费**"
    return (f"{str(meta.get('city') or '?'):<12} {str(meta.get('round') or '?'):<6} "
            f"{int(item.get('duration') or 0):>4}s  {free}\n"
            f"    {video_url(item)}\n"
            f"    match={_ref(item, 'ATP_MATCH') or '(无)'}")


def _emit(items: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps([{
            "id": i.get("id"), "url": video_url(i),
            "duration": i.get("duration"),
            "round": (i.get("metadata") or {}).get("round"),
            "city": (i.get("metadata") or {}).get("city"),
            "match_sid": _ref(i, "ATP_MATCH"),
            "players": [r.get("sid") for r in i.get("references") or []
                        if isinstance(r, dict) and r.get("type") == "ATP_PLAYER"],
            "free": "entitlement:free" in _labels(i),
        } for i in items], ensure_ascii=False, indent=1))
        return
    if not items:
        print("  一条都没有。⚠️ **空结果先自证是真空**：换个更宽的口径再查一次"
              "（比如去掉 --who、或者按 ATP_TOURNAMENT 查整站），"
              "别直接当成「这场没发短集锦」。")
        return
    for i in items:
        print("  " + _describe(i))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("player", "tournament", "match", "recent"))
    ap.add_argument("sid", nargs="?", default="",
                    help="player/tournament/match 模式下的 sid，如 S0RE / 422_2026 / 422_2026_MS122")
    ap.add_argument("--who", default="",
                    help="再按姓氏筛一道（大小写不敏感，匹配 slug）")
    ap.add_argument("--all", action="store_true",
                    help="连付费档一起列（默认只列免费的短集锦）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.mode != "recent" and not args.sid:
        ap.error(f"{args.mode} 模式要给 sid")

    ref = {"player": "ATP_PLAYER", "tournament": "ATP_TOURNAMENT",
           "match": "ATP_MATCH"}.get(args.mode, "")
    items = rows(
        # match 模式不加标签过滤：一场球就三条，全列出来让人看见「免费的是哪条」
        tag_ids="" if args.mode == "match" else str(TAG_SHORT_HIGHLIGHTS),
        references=f"{ref}:{args.sid}" if ref else "",
        pages=3 if args.mode == "recent" else 1,
    )
    if args.mode != "match" and not args.all:
        items = [i for i in items if is_real_short_highlight(i)]
    if args.who:
        needle = args.who.casefold()
        items = [i for i in items
                 if needle in str(i.get("titleUrlSegment") or "").casefold()]
    _emit(items, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

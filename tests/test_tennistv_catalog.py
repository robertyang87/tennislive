"""`tools/tennistv_catalog.py` 的判据——按球员／赛事／单场自己找免费短集锦。

这条线存在的理由：在它之前找一条短集锦只有「打开 library 页用眼睛翻第一页」
一条路，而**那一页只有最新 20 条、最老到不了一天前**。账号所有者
2026-08-16：「不要以后每次都用，我去找完把链接给你，这不符合自动化的能力呀」。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tennistv_catalog as cat  # noqa: E402


def _item(slug, *, labels, match_sid="422_2026_MS122", vid=1, duration=157):
    """照真实响应的形状造一条。字段名和层级都取自实测的那份 JSON。"""
    return {
        "id": vid,
        "titleUrlSegment": slug,
        "duration": duration,
        "metadata": {"round": "R1", "city": "Cincinnati"},
        "tags": [{"id": 0, "label": lab} for lab in labels],
        "references": (
            [{"type": "ATP_MATCH", "sid": match_sid}] if match_sid else []
        ) + [{"type": "ATP_PLAYER", "sid": "S0RE"}],
    }


SHORT = "video-type:short-highlights"
FREE = "entitlement:free"


def test_标签在源头打错时不能只信标签():
    """⚠️ **这是实测抓到的，不是假想**：辛辛那提 2026 那 48 条「短集锦」里，
    `cincinnati-2026-r2-jiri-lehecka-interview` 是一条 **210 秒的采访**，
    而它自己带着 `video-type:short-highlights` 标签。

    **过滤是对的，数据是错的。** 只按 `tagIds` 收货的话，选源那一步会拿到一条
    采访当比赛集锦——而它长得和真的一样（同样免费、同样两分半上下、同样挂在
    这一站下面），直到有人打开看才发现。

    判据钉三头：标签、标题、以及**有没有挂到一场具体的比赛上**（采访挂不到
    `ATP_MATCH`）。三条缺一条都不算。
    """
    real = _item("cincinnati-2026-r1-shang-sonego-short-highlights",
                 labels=[SHORT, FREE])
    assert cat.is_real_short_highlight(real)

    # ① 标题带 interview：标签是对的、比赛引用也在，仍然要拦
    fake = _item("cincinnati-2026-r2-jiri-lehecka-interview",
                 labels=[SHORT, FREE], duration=210)
    assert not cat.is_real_short_highlight(fake), (
        "打错标签的采访被当成短集锦收下了——选源那一步会拿它当比赛画面")

    # ② 没有 ATP_MATCH 引用：挂不到具体比赛的一律不算
    loose = _item("cincinnati-2026-season-so-far-short-highlights",
                  labels=[SHORT, FREE], match_sid="")
    assert not cat.is_real_short_highlight(loose)

    # ③ 反面：真短集锦不许被误伤——判据宁可窄，不可宽
    assert cat.is_real_short_highlight(
        _item("montreal-2026-r2-shang-rublev-short-highlights",
              labels=[SHORT, FREE, "series:1000", "year:2026"]))


def test_只有短集锦那个标签才算():
    """全长集锦（`match-highlights`）是付费档，混进来的话选源会拿到一条下不动的。"""
    full = _item("cincinnati-2026-r1-shang-sonego-highlights",
                 labels=["video-type:match-highlights", "entitlement:premium"],
                 duration=602)
    assert not cat.is_real_short_highlight(full)


def test_页面地址是不带令牌的那个():
    """spec 里放的必须是**页面地址**。

    解出来的 HLS 带一个只活 60 秒的令牌，钉进 spec 就是一条一分钟后必死的链接
    ——而它失败的样子和「这条片子被下架了」一模一样（`official.media_url`
    的 docstring 记着这条）。所以这个函数只拼页面地址，一个令牌都不碰。
    """
    url = cat.video_url(_item("cincinnati-2026-r1-shang-sonego-short-highlights",
                              labels=[SHORT], vid=4559761))
    assert url == ("https://www.tennistv.com/videos/4559761/"
                   "cincinnati-2026-r1-shang-sonego-short-highlights")
    assert "token" not in url and ".m3u8" not in url
    # slug 缺了也要拼得出来（页面地址只靠 id 就能打开）
    assert cat.video_url({"id": 42}) == "https://www.tennistv.com/videos/42"


def test_接口回HTML的时候要说人话不是甩JSON错(monkeypatch):
    """`tags[]=…` 会返回一整页 HTTP 400 的 HTML。

    ⚠️ 我第一轮探参数是按「响应的 md5 变了没有」判的，于是**把这个 400 判成了
    「参数生效」**——错误页当然和正常响应不一样。判据必须是「返回的内容真的被
    过滤了」，不是「响应变了」。

    这里钉的是**报错要说出路**：直接让 `json.loads` 抛的话，读到的人只会看见
    `Expecting value: line 1 column 1`，那句话指向的是「接口坏了」，而真相是
    「参数名不对」。
    """
    class _Resp:
        def read(self): return b"<!doctype html><html><title>HTTP Status 400"
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(cat.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(SystemExit) as err:
        cat._get(tagIds="6795")
    text = str(err.value)
    assert "没回 JSON" in text and "参数名" in text, text
    # 出路要点名说清生效的是哪几个，别让下一个人再探一遍
    assert "tagIds" in text and "references" in text, text


def test_那两个标签id要注明是读出来的不是猜的():
    """`6795` / `6788` 是从一条已知条目的 `tags` 里读出来的。

    ⚠️ **一个猜出来的魔数和一个量出来的魔数，写在代码里长得一模一样**——
    这个仓库为「没量过的推断写进注释，之后每个人拿它当判据」栽过。所以要求
    模块文档里把出处写着，改数字的人先看见它。
    """
    assert cat.TAG_SHORT_HIGHLIGHTS == 6795
    assert cat.TAG_FREE == 6788
    doc = Path("tools/tennistv_catalog.py").read_text(encoding="utf-8")
    assert "4559761" in doc, (
        "没写这两个 id 是从哪条条目读出来的——下一个人会以为它们是猜的")


def test_不生效的参数要记在文档里别让人再探一遍():
    """探这个接口花了一轮，**结论里最值钱的是「哪些不行」**。

    CLAUDE.md 那条「探过一轮别再试」说的就是这个：不记下来的话，下一个人会把
    `search` / `q` / `filter` 再试一遍，而它们**静默忽略**——返回 200、
    返回和不带参数一模一样的内容，看起来像「这个接口没有搜索」。
    """
    doc = Path("tools/tennistv_catalog.py").read_text(encoding="utf-8")
    for dead in ("pageNumber", "tagLabel", "videoType", "search", "query"):
        assert dead in doc, f"没记下 `{dead}` 是不生效的，下一个人还要再探一遍"
    assert "静默忽略" in doc

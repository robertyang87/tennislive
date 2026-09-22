"""推送正文里的图片 URL 必须钉在 commit 上，不许停在 `@main`。

来路（2026-09-22，`bouzkova-kartal-bjk-cup-2026-qf` 连推三次量出来的）：
`auto-push-reel.yml` 里 `TENNISLIVE_ASSET_REV: ${{ github.sha }}` 早就设上了，
注释还写着「钉 commit，别停在 @main……微信的图片缓存按路径算」——
**而 `push_reel.poster_url` / `stat_card_url` 写死的是 `BRANCH`**，
于是变量设了等于没设。三条推送的日志里都是

    [数据图] 带上这一屏：…/gh/robertyang87/tennislive@main/output/2026-09-23/…/stat_card.jpg

而同一步的环境里 `TENNISLIVE_ASSET_REV: 606db061b524…` 明明印着。
后果：同一条片子重渲之后路径不变，微信按路径缓存，卡上那张图停在上一版。

⚠️ 这是「一个数写两处必分叉」的又一例，而**分叉的样子是「配好了」**
（yml 里有、注释里也写着为什么要有），只有把真发出去的 URL 抠出来才看得见。
所以这条判据钉的是**函数的返回值**，不是 yml 的文本。
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SHA = "606db061b524c632dc67dd9f2eb0f6fe3f231c83"
OUTDIR = Path("output/2026-09-23/reel/bouzkova-kartal-bjk-cup-2026-qf")


def _fresh(monkeypatch, rev: str | None):
    """带着指定的 `TENNISLIVE_ASSET_REV` 重新导入 `push_reel`。

    ⚠️ 模块级的 `REPO` / `BRANCH` 是导入时从环境读的，所以不能只改环境变量
    就调函数——**必须重新导入**，否则测的是上一次导入留下的那份。
    """
    if rev is None:
        monkeypatch.delenv("TENNISLIVE_ASSET_REV", raising=False)
    else:
        monkeypatch.setenv("TENNISLIVE_ASSET_REV", rev)
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    sys.modules.pop("push_reel", None)
    return importlib.import_module("push_reel")


@pytest.mark.parametrize("builder", ["poster_url", "stat_card_url"])
def test_配了ASSET_REV就要钉在commit上_不许停在main(monkeypatch, builder):
    """两个 URL 构造器**都要**钉——只钉一个就是下一次分叉。"""
    mod = _fresh(monkeypatch, SHA)
    url = getattr(mod, builder)(OUTDIR)

    assert "@main/" not in url, (
        f"{builder}() 还停在 @main：{url}\n"
        "配了 TENNISLIVE_ASSET_REV 就必须钉在 commit 上，否则同一条片子重渲之后"
        "路径不变，微信按路径缓存，卡上那张图停在上一版（而且不吭声）。"
    )
    # `cdn.pin_ref` 把 sha 截到 10 位（实测 jsDelivr 40/12/10/7 位全 200）。
    assert f"@{SHA[:10]}/" in url, (
        f"{builder}() 没有钉成 10 位短 sha：{url}\n"
        "截断只许有 cdn.pin_ref 那一处实现——这儿要的就是它的结果。"
    )
    assert url.endswith(f"/{OUTDIR.as_posix()}/{Path(getattr(mod, 'POSTER_NAME') if builder == 'poster_url' else getattr(mod, 'STAT_CARD_NAME')).name}"), (
        f"{builder}() 的路径部分被改坏了：{url}")


@pytest.mark.parametrize("builder", ["poster_url", "stat_card_url"])
def test_没配ASSET_REV时退回分支名_不许拼出空的ref(monkeypatch, builder):
    """本地手跑、没有这个变量时要退回 `BRANCH`，不是拼出 `@/`。

    ⚠️ 钉住这一头是因为**只钉前一头的话，`return REPO + "@" + rev` 里
    `rev` 取空字符串也能让上一条测试过**，而那会拼出
    `…/tennislive@/output/…`——jsDelivr 404，推送前那道图片探活会拦，
    但那是「靠下游兜住上游的 bug」。
    """
    mod = _fresh(monkeypatch, None)
    url = getattr(mod, builder)(OUTDIR)
    assert "@main/" in url, f"{builder}() 没有退回分支名：{url}"
    assert "@/" not in url, f"{builder}() 拼出了空 ref：{url}"


def test_两个构造器共用同一个ref来源(monkeypatch):
    """海报和数据图必须是同一个 ref——一条消息里两张图钉在不同版本上更难查。"""
    mod = _fresh(monkeypatch, SHA)
    a = mod.poster_url(OUTDIR).split("/output/")[0]
    b = mod.stat_card_url(OUTDIR).split("/output/")[0]
    assert a == b, f"海报和数据图的 ref 不一致：\n  {a}\n  {b}"

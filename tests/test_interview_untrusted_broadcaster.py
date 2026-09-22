"""`broadcaster_interview` 用**非受信频道**当源时，缺口必须逐条认领。

来路（2026-09-22，`wang-vekic-singapore-2026-r1-interview`）：WTA500 新加坡
女单第一轮王欣瑜 6-1 6-2 胜 8 号种子维基奇，**官方没有这场的赛后采访**，
而这是查过的不是没查到——同日同站 WTA 官方集锦时长自证（这场 306s、沃尔夫
307s、帕克斯 304s，全压在纯集锦 310s 基线内；而冈村-费尔南德斯那场 458s
尾巴上就有场上采访，是现成的控制组），`@WTA` 最近 40 条上传里没有任何独立
采访条目，赛事本身没有官方频道（三个句柄全 404）。

唯一的素材是 Tennis Asia TV（7.59K 订阅的亚洲网球自媒体）在赛事官方媒体墙
前做的 274 秒专访。抽帧逐格看过（frame-grab run 35722763221），它**不满足
`broadcaster_interview` 判据里的两条**：不是受信转播商、话筒是裸的 RODE 没有
台标、而且她已经换下了当场比赛服（比赛是酒红无袖连衣裙，采访里是深蓝 adidas
短袖）。账号所有者 2026-09-22 明确授权这一条采用。

⚠️ **授权的是这一条，不是把口径整体放宽。** 这份判据要挡住的正是「下一个人
照着它抄」——`interview_source_gate` 机械上认 `human_visual_verdict`，它没法
分辨台标话筒和裸话筒，所以「签一个证据不支持的目视判定」这件事只有判据拦得住。
形状照仓库里那些 `_LEGACY` 表：**表里这几条只许减不许加，表自带自检**，
新加一条就要有新的授权，而且缺口要逐条写出来。

⚠️ 这条**不是**「非官方来源也能用」的许可。它要求的恰恰相反：一旦源不在
`data/oncourt_sources.json` 里，就必须在 `source_verification.evidence` 里
留下一条 `gaps_declared_by_hand`，把**缺了哪几条判据**和**谁在哪天授权的**
写清楚——让「想清楚了还是凑合一下」在产物上分得开
（和 `_layout_why` / `_tennistv_trim` / `_tactics_why` 一个形状）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs" / "interviews"
SOURCES = ROOT / "data" / "oncourt_sources.json"

#: 经账号所有者逐条授权、源不在受信来源库里的 `broadcaster_interview`。
#: **只许减不许加**——加一条就要有一次新的授权，并把缺口写进那条 spec。
_AUTHORISED_UNTRUSTED = {
    "wang-vekic-singapore-2026-r1-interview": "2026-09-22",
}

#: 缺口认领那条 evidence 的 kind，和 spec 里写的必须是同一个串。
_GAP_KIND = "gaps_declared_by_hand"


def _trusted_names() -> set[str]:
    data = json.loads(SOURCES.read_text(encoding="utf-8"))
    return {str(s.get("name", "")).strip().casefold()
            for s in data["sources"] if str(s.get("name", "")).strip()}


def _broadcaster_specs() -> list[tuple[str, dict]]:
    out = []
    for path in sorted(SPECS.glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("requested_content_type") == "broadcaster_interview":
            out.append((path.stem, spec))
    return out


def test_授权表只许减不许加_表自带自检():
    """表里每个 slug 都必须真的存在，而且真的是转播商专访。

    自检的意义是：这张表会随着条目被修好而**变短**，而一个指向不存在的 slug
    的豁免会静静地长期留着——那正是本仓库反复记的「豁免表自己烂掉」的形状。
    """
    present = {slug for slug, _ in _broadcaster_specs()}
    stale = sorted(set(_AUTHORISED_UNTRUSTED) - present)
    assert not stale, (
        f"授权表里这些 slug 已经不是 broadcaster_interview 了（或文件没了）：{stale}。"
        "把它们从 `_AUTHORISED_UNTRUSTED` 删掉——这张表只许减不许加。"
    )


def test_非受信来源的转播商专访必须逐条认领缺口():
    """源不在 `data/oncourt_sources.json` 里，就必须写明缺了哪几条判据。

    ⚠️ 机械上 `human_visual_verdict` 是白名单里的方法，闸分辨不出「站在赛场边、
    手持台标话筒、穿当场比赛服」和「换完装、拿着裸话筒、在媒体墙前」——两者在
    `source_verification` 里长得一模一样。这条把差别逼到台面上。
    """
    trusted = _trusted_names()
    problems: list[str] = []
    for slug, spec in _broadcaster_specs():
        verification = spec.get("source_verification") or {}
        source = str(verification.get("source", "")).strip()
        if source.casefold() in trusted:
            continue
        if slug not in _AUTHORISED_UNTRUSTED:
            problems.append(
                f"{slug}：来源「{source}」不在 data/oncourt_sources.json 里，"
                "也不在 `_AUTHORISED_UNTRUSTED` 里。这条线默认只做官方/受信来源的"
                "采访；真要用非受信来源，先拿到授权，再把 slug 和日期加进表里。"
            )
            continue
        gaps = [e for e in (verification.get("evidence") or [])
                if isinstance(e, dict) and e.get("kind") == _GAP_KIND]
        if not gaps:
            problems.append(
                f"{slug}：授权过了，但 `source_verification.evidence` 里没有一条"
                f" `kind={_GAP_KIND}` 的缺口认领。把「缺了哪几条判据」「谁在哪天"
                "授权的」写进去——不写的话，它和一条合格来源在产物上分不出来。"
            )
            continue
        why = str(gaps[0].get("why", ""))
        if _AUTHORISED_UNTRUSTED[slug] not in why:
            problems.append(
                f"{slug}：缺口认领里没写授权日期 {_AUTHORISED_UNTRUSTED[slug]}。"
            )
    assert not problems, "\n".join(problems)


def test_缺口认领要说清官方那条路是查过的不是没查():
    """「官方没有」和「我没找」在 `_why` 里长得一模一样，这条把前者钉住。

    判据是那段话里要出现**可复核的数字**：官方集锦的时长（310 秒基线那套）
    或者扫过的上传条数。写「没找到官方采访」不算——本仓库
    「空结果先自证是真空」记的就是这件事。
    """
    for slug, spec in _broadcaster_specs():
        if slug not in _AUTHORISED_UNTRUSTED:
            continue
        gaps = [e for e in (spec.get("source_verification") or {}).get("evidence") or []
                if isinstance(e, dict) and e.get("kind") == _GAP_KIND]
        assert gaps, slug
        why = str(gaps[0].get("why", ""))
        assert any(mark in why for mark in ("310", "秒", "条")), (
            f"{slug}：缺口认领里没有可复核的数字，看不出官方那条路是真空还是没查。"
        )


@pytest.mark.parametrize("slug", sorted(_AUTHORISED_UNTRUSTED))
def test_授权过的那几条仍然要接冷开场(slug: str):
    """`NO_LEAD_EXCEPTION_METHOD['broadcaster_interview']` 是 `None`——专访在
    赛场里录，同场比赛画面官方集锦里就有，借得到。放宽来源**不放宽这一条**：
    账号所有者 2026-08-16 定的「赛后采访片从比赛结束那一刻开头」照旧成立。
    """
    spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    opening = spec.get("opening") or {}
    lead = spec.get("lead_in")
    assert opening.get("kind") == "none", f"{slug}: 媒体墙专访没有比赛画面，opening 应为 none"
    assert isinstance(lead, dict) and lead.get("url"), (
        f"{slug}: 非受信来源的专访照旧必须用 `lead_in` 从同场官方集锦接比赛结尾。"
    )

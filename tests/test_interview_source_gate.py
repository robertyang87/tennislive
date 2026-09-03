"""赛后开麦 L0 内容身份契约：不联网的正反向判据。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import interview_source_gate as gate  # noqa: E402


def _item(**extra) -> dict:
    row = {
        "id": "vid1",
        "url": "https://example.test/vid1",
        "title": "Alexander Zverev On-Court Interview | Cincinnati 2026",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_spec() -> dict:
    verification = gate.candidate_verification(_item(), verdicts={})
    spec = {
        "slug": "zverev-cincinnati-2026-qf",
        "url": "https://example.test/vid1",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:qf:alexander-zverev",
            "event": "辛辛那提大师赛",
            "round": "四分之一决赛",
            "winner": "兹维列夫",
            "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
        },
    }
    return gate.finalize_source_contract(spec)


def _ceremony_item(**extra) -> dict:
    """颁奖典礼致辞的候选素材——`ceremony` 是这道闸认的第二种合法类型，
    不是 `_item()` 那种 on_court 的降级版，所以单独一份 fixture。
    """
    row = {
        "id": "vid-ceremony-1",
        "url": "https://example.test/vid-ceremony-1",
        "title": "Arthur Fils Champion Speech | 2026 Cincinnati Open",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_ceremony_spec() -> dict:
    verification = gate.candidate_verification(_ceremony_item(), verdicts={})
    spec = {
        "slug": "fils-cincinnati-2026-final-ceremony",
        "url": "https://example.test/vid-ceremony-1",
        "requested_content_type": "ceremony",
        "interview_kind": "赛后捧杯致辞",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:final:arthur-fils",
            "event": "辛辛那提大师赛",
            "round": "决赛",
            "winner": "菲斯",
            "loser": "蒂亚福",
            "participants": ["菲斯", "蒂亚福"],
        },
    }
    return gate.finalize_source_contract(spec)


def test_未知频道标题写oncourt也只能待复核():
    got = gate.candidate_verification(_item(source="Unknown Uploads"), verdicts={})
    assert got["status"] == "pending" and got["method"] == "needs_visual_review"


def test_注册官方源且标题明确场上采访可进入生产():
    got = gate.candidate_verification(_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_oncourt"


def test_WTA集锦片尾含采访但起点未知只能待复核():
    got = gate.candidate_verification(_item(
        source="WTA", tail_interview=True, duration_s=347,
        title="MATCH HIGHLIGHTS | Cincinnati 2026"), verdicts={})
    assert got["status"] == "pending"
    assert got["method"] == "wta_highlight_tail"
    assert "起点" in got["reason"]


def test_人工判成发布会优先级高于标题规则():
    got = gate.candidate_verification(
        _item(), verdicts={"vid1": {"verdict": "press", "by": "reviewer"}})
    assert got["status"] == "rejected" and got["detected_type"] == "press"


def test_正式契约绑定来源与比赛且改字即失效():
    spec = _formal_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_演播室不能靠重新签名伪装成场上采访():
    spec = _formal_spec()
    spec["source_verification"].update({
        "status": "rejected", "detected_type": "studio", "method": "human_visual_verdict",
    })
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="status.*verified|detected_type"):
        gate.validate_source_contract(spec)


def test_轮次或逐场ID仍是unknown不能签成正式来源():
    spec = _formal_spec()
    spec["match"]["round"] = "unknown"
    spec["match"]["id"] = "2026:cincinnati:unknown:alexander-zverev"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="占位值|unknown"):
        gate.validate_source_contract(spec)


def test_官方源标题明确颁奖致辞可进入生产():
    """ceremony 不是被这道闸拦下的例外，是它认的第二种合法类型——账号所有者
    原话「颁奖致辞就是赛后开麦场上采访的一种形式而已，都要做」。受信官方
    频道 + 标题明确写着冠军致辞，应该直接给出 verified，不用等人工判词。
    """
    got = gate.candidate_verification(_ceremony_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_ceremony"
    assert got["detected_type"] == "ceremony"


def test_亚军致辞和冠军致辞同一道闸():
    """同一场颁奖典礼上，亚军和冠军站在同一个台上讲话——Cincinnati Open
    官方频道给两人的标题是同一套写法但不含「champion」，正则要单独认
    「runner-up speech」，连字符可有可无（Pegula 那条带连字符，Tiafoe
    那条不带）。亚军致辞不是低一档的素材，落不进这条正则就会被误判成
    「标题没写明确」而卡进待复核队列。"""
    for title in (
        "Pegula runner-up speech - Cincinnati 2026",
        "Frances Tiafoe Runner Up Speech | 2026 Cincinnati Open",
    ):
        got = gate.candidate_verification(_ceremony_item(title=title), verdicts={})
        assert got["status"] == "verified", title
        assert got["method"] == "official_explicit_ceremony", title
        assert got["detected_type"] == "ceremony", title


def test_人工判成颁奖致辞也能进入生产():
    """标题不满足任何正则时，人工看过画面记进 oncourt_verify.json 同样能让
    ceremony 走到 verified——跟 on_court 的 human_visual_verdict 是同一条路，
    不是只给 on_court 开的后门。"""
    got = gate.candidate_verification(
        _ceremony_item(title="没有任何标题正则能命中的一句话"),
        verdicts={"vid-ceremony-1": {"verdict": "ceremony", "by": "reviewer"}})
    assert got["status"] == "verified"
    assert got["detected_type"] == "ceremony"
    assert got["method"] == "human_visual_verdict"


def test_颁奖致辞的正式契约通过验证且改字即失效():
    spec = _formal_ceremony_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_ceremony素材不能签成on_court发布():
    """来源被核验成 ceremony，却在 spec 里声明 requested_content_type=on_court——
    这不是同一件事升级／降级，是两种不同的合法类型，混着用要当场报错，
    不能靠重新签名把不匹配的类型盖过去（这条测试特意在改字段**之后**才
    调用 `finalize_source_contract`，模拟"攻击者也会重新签名"，逼判据落在
    detected_type 本身，而不是侥幸靠一个过期的哈希拦下来）。
    """
    verification = gate.candidate_verification(_ceremony_item(), verdicts={})
    spec = {
        "slug": "mismatched-ceremony-as-on-court",
        "url": _ceremony_item()["url"],
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:final:arthur-fils",
            "event": "辛辛那提大师赛",
            "round": "决赛",
            "winner": "菲斯",
            "loser": "蒂亚福",
            "participants": ["菲斯", "蒂亚福"],
        },
    }
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_on_court素材不能签成ceremony发布():
    """反过来同理：on_court 已核验的素材，不能靠改个字段名和重新签名就冒充
    颁奖致辞。两个方向都要测，只测一个方向拦不住"generalization 只对了一半"。
    """
    verification = gate.candidate_verification(_item(), verdicts={})
    spec = {
        "slug": "mismatched-on-court-as-ceremony",
        "url": _item()["url"],
        "requested_content_type": "ceremony",
        "interview_kind": "赛后捧杯致辞",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:qf:alexander-zverev",
            "event": "辛辛那提大师赛",
            "round": "四分之一决赛",
            "winner": "兹维列夫",
            "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
        },
    }
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_requested_content_type不在登记表里直接报错():
    """`REQUESTED_KINDS` 只登记了 on_court／ceremony 两种；写第三个值
    （比如发布会 press）不能靠重新签名蒙混过去。"""
    spec = _formal_spec()
    spec["requested_content_type"] = "press"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="on_court/ceremony 之一"):
        gate.validate_source_contract(spec)


def _walk_on_item(**extra) -> dict:
    """赛前出场秀的候选素材——`walk_on` 是这道闸认的第四种合法类型。

    ⚠️ **`source` 用 Cincinnati Open 而不是 US Open**：`_trusted_source_names()`
    只收 `verified: true` 的源，而 `data/oncourt_sources.json` 里 US Open 那行
    现在是 `false`。这条测的是「官方源 + 标题明确 → verified」这条路本身，
    换一个已登记为受信的官方源才测得到它；真实那条 spec
    （`osaka-walkout-us-open-2026-r1`）是手写的，走的是
    `validate_source_contract`，不查这张受信表。
    """
    row = {
        "id": "vid-walkon-1",
        "url": "https://example.test/vid-walkon-1",
        "title": "Naomi Osaka Stuns in her Walk-Out Outfit! | 2026 Cincinnati Open",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_walk_on_spec() -> dict:
    verification = gate.candidate_verification(_walk_on_item(), verdicts={})
    spec = {
        "slug": "osaka-walkout-cincinnati-2026-r1",
        "url": _walk_on_item()["url"],
        "requested_content_type": "walk_on",
        "interview_kind": "赛前出场秀",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:r1:naomi-osaka",
            "event": "辛辛那提大师赛",
            "round": "第一轮",
            "winner": "大坂直美",
            "loser": "扎哈罗娃",
            "participants": ["大坂直美", "扎哈罗娃"],
        },
    }
    return gate.finalize_source_contract(spec)


def test_官方源标题明确出场秀可进入生产():
    """出场秀不是被这道闸拦下的例外，是它认的第四种合法类型——账号所有者
    2026-09-01「做大坂直美的出场秀视频，可以用赛后开麦的模板」。形状和加
    `ceremony`、`farewell` 那两次一样：球员穿着定制出场服走进球场是这个栏目
    下另一种真实存在的内容，受信官方频道 + 标题明确写着 walk-out，应该直接
    给出 verified，不用等人工判词。
    """
    got = gate.candidate_verification(_walk_on_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_walk_on"
    assert got["detected_type"] == "walk_on"


def test_出场秀那条正则只认出场不认退赛和走开():
    """**反向：这条正则最容易误伤的三个词，逐个钉住。**

    `walkover`（不战而胜）、`walked out of`（伤退走人）、`walk on court`
    （走上球场，任何一条比赛报道都会写）——三个都长得像「walk + out/on」，
    而它们一个都不是出场秀。判据宁可窄不可宽：**扩大化的判据不吭声**，
    它会把一条退赛报道签成 verified 的出场秀，而 `method` 那一栏还写着
    `official_explicit_walk_on`，回头查来源的人看不出哪里错了。
    """
    for title in (
        "Naomi Osaka Stuns in her Walk-Out Outfit! | 2026 US Open",
        "Osaka walkout look | US Open 2026",
        "Coco Gauff Walk On Moment | 2026 US Open",
        "Sinner walk-out ahead of the final",
    ):
        assert gate.explicit_title_type(title) == "walk_on", title
    for title in (
        "Zverev advances after Medvedev walkover",
        "Nadal walked out of the match with injury",
        "Djokovic walk out of the tunnel",
        "She walks on court to a huge ovation",
        "Players walk on court for the coin toss",
    ):
        assert gate.explicit_title_type(title) == "", title


def test_出场秀的正式契约通过验证且改字即失效():
    spec = _formal_walk_on_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_出场秀素材不能签成on_court发布():
    """来源被核验成 walk_on 却声明成 on_court——出场秀里根本没有人拿话筒问
    问题，混着用要当场报错，不能靠重新签名盖过去。和 ceremony 那条同一个
    形状：判据落在 detected_type 本身，不是侥幸靠一个过期的哈希。
    """
    spec = _formal_walk_on_spec()
    spec["requested_content_type"] = "on_court"
    spec["interview_kind"] = "赛后场上采访"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_出场秀的观众可见叫法必须写成赛前出场秀():
    """`interview_kind` 是印在顶栏上给观众看的那一句。出场秀发生在**开赛之前**，
    照抄「赛后场上采访」就是印一句假话——四种类型里只有它不是「赛后…」，
    所以这条单独钉住。
    """
    assert gate.REQUESTED_KINDS["walk_on"] == "赛前出场秀"
    spec = _formal_walk_on_spec()
    spec["interview_kind"] = "赛后场上采访"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="赛前出场秀"):
        gate.validate_source_contract(spec)


def _formal_presser_spec() -> dict:
    """赛后新闻发布会——这道闸认的第五种类型（2026-09-03 加）。

    ⚠️ **它的 `source_verification` 是手写的，不走 `candidate_verification()`**：
    那个函数是**自动链**用的（把采访库条目判成 verified），而发布会永远不该由
    自动链自己认领——它只在人手写 spec、显式声明 `press_conference` 时才成立。
    """
    spec = {
        "slug": "bu-jodar-us-open-2026-r1-presser",
        "url": "https://example.test/vid-presser-1",
        "requested_content_type": "press_conference",
        "interview_kind": "赛后新闻发布会",
        "source_verification": {
            "source_id": "youtube:vid-presser-1",
            "source_url": "https://example.test/vid-presser-1",
            "source": "US Open",
            "title": "Yunchaokete Bu Press Conference | 2026 US Open Round 1",
            "status": "verified",
            "detected_type": "press_conference",
            "method": "official_explicit_press_conference",
            "evidence": [{"kind": "official_explicit_title",
                          "title": "Yunchaokete Bu Press Conference | 2026 US Open Round 1"}],
        },
        "match": {
            "id": "2026:us-open:mens-first-round:yunchaokete-bu-rafael-jodar",
            "event": "2026 US Open",
            "round": "Men's Singles First Round",
            "winner": "布云朝克特",
            "loser": "霍达尔",
            "participants": ["布云朝克特", "霍达尔"],
        },
    }
    return gate.finalize_source_contract(spec)


def test_赛后新闻发布会可进入生产():
    """发布会是这个栏目本来就在做的内容（`specs/interviews/` 里已发过 10 条
    `*-presser`），而闸 2026-08-23 立起来时漏了这一种，于是那 10 条从那天起
    全部渲不出来。这条钉住第五种类型确实认得出来。
    """
    spec = _formal_presser_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_加了发布会之后自动链一个字都不许变():
    """⚠️⚠️ **这条是加 `press_conference` 的全部风险所在。**

    `explicit_title_type()` 和 `candidate_verification()` 是**自动链**用的：
    前者从标题猜类型，后者把采访库条目判成 verified。往它们里加一支 press，
    自动链扫到任何标题带 "Press Conference" 的官方视频就会直接标
    `status: verified`——等于给「这条线只做场上采访」那道闸捅个洞。

    所以加类型时只动了 `REQUESTED_KINDS`/`DETECTED_TYPES`/`APPROVED_METHODS`
    三处，这两个函数一个字没碰。三头分别钉住。
    """
    # ① 官方标题写着 Press Conference，自动链仍然猜不出类型（返回空串）
    assert gate.explicit_title_type(
        "Yunchaokete Bu Press Conference | 2026 US Open Round 1") == ""
    # ② 人工判成 press 的条目，照旧 rejected——`press` 不在 REQUESTED_KINDS 里
    assert "press" not in gate.REQUESTED_KINDS
    got = gate.candidate_verification(
        _item(), verdicts={"vid1": {"verdict": "press", "by": "reviewer"}})
    assert got["status"] == "rejected" and got["detected_type"] == "press"
    # ③ 受信官方源 + 明确标题这条自动路径，产出的类型里不会有发布会
    assert gate.candidate_verification(
        _item(title="Yunchaokete Bu Press Conference | 2026 US Open Round 1"),
        verdicts={})["detected_type"] == "unknown"


def test_发布会素材不能签成on_court发布():
    """和 ceremony／walk_on 那两条同一个形状：来源核验成发布会却声明成场上
    采访，要当场报错——发布厅里没有人在球场上拿话筒问问题。
    """
    spec = _formal_presser_spec()
    spec["requested_content_type"] = "on_court"
    spec["interview_kind"] = "赛后场上采访"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_发布会的观众可见叫法必须写成赛后新闻发布会():
    """`interview_kind` 印在顶栏上给观众看。画面是发布会背板和记者提问，
    顶栏却印「赛后场上采访」就是印一句假话——这个坑 `build_interview_clip`
    的注释里记过一次（谢尔顿×门西克那条 232 行问答就这么印错过）。
    """
    assert gate.REQUESTED_KINDS["press_conference"] == "赛后新闻发布会"
    spec = _formal_presser_spec()
    spec["interview_kind"] = "赛后场上采访"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="赛后新闻发布会"):
        gate.validate_source_contract(spec)

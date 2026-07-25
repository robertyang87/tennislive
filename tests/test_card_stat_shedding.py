"""技术对比表的自适应收行：放不下就丢最次要的一行，而不是被裁断。

2026-07-25 的成品即使把行数砍到上限 4，第四行仍在中间被裁开、"编辑锐评"被顶
出画面——放得下几行取决于它上方那句头条折了几行，那是文本，长度不固定，在
Python 侧算不准。所以真正的收行发生在渲染之后、截图之前，用实测高度决定。

这里用一个最小 DOM 桩在 node 里跑 *线上那份* JS，不依赖 Chromium。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

from tennislive.render.webcards import _SHED_STAT_ROWS_JS, _stat_rank, card_stat_rows


ROW_HEIGHT = 59
FOOTER_TOP = 1266  # 实测：正文可用到 footer 上方 12px


def _run_shed(ranks: list[int], other_bottom: int) -> dict:
    """在 node 里跑线上那份 JS，返回 {dropped, overflow, remaining, head_removed}."""
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:  # pragma: no cover - 本地没装 node 时跳过
        pytest.skip("需要 node 才能执行卡片渲染层的 JS")

    script = textwrap.dedent(
        """
        const shed = SHED_FN;
        const ROW = %d;
        const ranks = %s;
        const otherBottom = %d;
        const footerTop = %d;

        let headRemoved = false;
        const rows = ranks.map((r) => ({
          dataset: {rank: String(r)},
          remove() { grid.rows = grid.rows.filter((x) => x !== this); },
        }));
        const grid = {
          rows,
          removed: false,
          querySelectorAll: () => grid.rows,
          remove() { grid.removed = true; grid.rows = []; },
          previousElementSibling: {
            classList: {contains: (c) => c === 'compare-head'},
            remove() { headRemoved = true; },
          },
        };
        const footer = {getBoundingClientRect: () => ({top: footerTop})};
        const poster = {
          children: [{getBoundingClientRect: () =>
            ({bottom: otherBottom + grid.rows.length * ROW})}],
          getBoundingClientRect: () => ({top: 0, bottom: 1440}),
          querySelector: (sel) => {
            if (sel === '.compare-grid') return grid.removed ? null : grid;
            if (sel.indexOf('footer') !== -1) return footer;
            return null;
          },
        };
        global.document = {querySelector: (s) =>
          s.indexOf('.poster') === 0 ? poster : null};
        global.getComputedStyle = () => ({position: 'static', display: 'block'});

        const result = shed();
        console.log(JSON.stringify({
          dropped: result.dropped,
          overflow: result.overflow,
          remaining: grid.rows.map((r) => Number(r.dataset.rank)),
          head_removed: headRemoved,
        }));
        """
        % (ROW_HEIGHT, json.dumps(ranks), other_bottom, FOOTER_TOP)
    ).replace("SHED_FN", _SHED_STAT_ROWS_JS)

    proc = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


def test_rows_that_fit_are_left_alone():
    out = _run_shed([0, 3, 2, 1], other_bottom=1000)
    assert out["dropped"] == 0
    assert out["remaining"] == [0, 3, 2, 1]
    assert out["overflow"] == 0


def test_the_least_important_row_goes_first_not_the_last_one():
    """线上那张卡的最后一行是"破发兑现"——排第二重要，绝不能因为排在末尾被丢。"""
    out = _run_shed([0, 3, 2, 1], other_bottom=1030)
    assert out["dropped"] == 1
    assert 3 not in out["remaining"]  # 丢掉的是最次要的
    assert 1 in out["remaining"]  # 破发兑现留下
    assert out["overflow"] == 0


def test_shedding_stops_at_two_rows_then_drops_the_whole_block():
    """一行对比说明不了胜负，与其留半张表，不如把版面还给"编辑锐评"。"""
    tight = _run_shed([0, 3, 2, 1], other_bottom=1120)
    assert tight["remaining"] == [0, 1]  # 只留最重要的两项

    impossible = _run_shed([0, 3, 2, 1], other_bottom=1240)
    assert impossible["remaining"] == []
    assert impossible["head_removed"] is True  # 表头不能孤零零留着


def test_card_stat_rows_and_rank_agree_on_what_matters():
    """Python 侧的取舍顺序和 JS 侧的丢弃顺序必须是同一套优先级。"""
    rows = [
        ("一发成功率", "60%", "70%"),
        ("总得分", "43", "63"),
        ("破发兑现", "1/3", "6/12"),
        ("二发得分率", "40%", "55%"),
        ("ACE / 双误", "3 / 1", "0 / 2"),
        ("一发得分率", "50%", "77%"),
    ]
    picked = card_stat_rows(rows, limit=4)
    assert len(picked) == 4
    labels = [label for label, _, _ in picked]
    assert "总得分" in labels and "破发兑现" in labels
    assert "二发得分率" not in labels  # 优先级最低的先出局
    # 入选行保持原表顺序，读起来不跳
    assert labels == [label for label, _, _ in rows if label in labels]
    # 排名越小越重要，未知项排到最后
    assert _stat_rank("总得分") < _stat_rank("破发兑现") < _stat_rank("一发成功率")
    assert _stat_rank("某个新指标") == _stat_rank("一发成功率") + 1

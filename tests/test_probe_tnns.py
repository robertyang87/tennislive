"""probe_tnns.py 的 `_dump_objects`：真实响应是压缩 JSON，匹配也必须按压缩比.

2026-08-07 栽过一次：真响应里明明打印着 `"p":[{"k":972327,…`，`_dump_objects`
却报「命中 0 个」——因为它拿 `json.dumps(node, ...)` 默认分隔符（冒号后加空格）
重新序列化再去找 `"p":[`，而重序列化出来的是 `"p": [`，永远对不上压缩 JSON
里的写法。判据钉住这条路径不再回归。
"""

from __future__ import annotations

import json

from tools.probe_tnns import _dump_objects, _print_top_keys, _text_context


def test_dump_finds_object_by_compact_key_colon_bracket_pattern(capsys):
    """`"p":[` 这种紧贴冒号的结构化查询词，必须能命中压缩 JSON 里的真实写法."""
    payload = {
        "all_matches": [
            {"k": "1", "p": [{"n": "Jodar R."}, {"n": "Musetti L."}]},
        ]
    }
    body = json.dumps(payload, separators=(",", ":"))  # 真实接口就是这样压缩的
    assert '"p":[' in body  # 先确认 fixture 本身没写错

    _dump_objects(body, '"p":[', limit=3)
    out = capsys.readouterr().out
    assert "含 '\"p\":[' 的最小对象 1 个" in out
    assert "Jodar R." in out


def test_dump_still_finds_plain_word(capsys):
    """普通词（没有冒号/逗号边界）不受这次改动影响，仍然找得到."""
    body = json.dumps({"all_matches": [{"n": "Coleman Wong"}]}, separators=(",", ":"))
    _dump_objects(body, "Wong", limit=3)
    out = capsys.readouterr().out
    assert "Coleman Wong" in out


def test_top_keys_reports_every_root_key_and_its_shape(capsys):
    """`--top-keys` 要把根对象的每个键都列出来，别只挑看着重要的那几个."""
    body = json.dumps(
        {"panels": {"72": {"t": "UTR"}}, "all_matches": [1, 2, 3], "ver": "1.0"},
        separators=(",", ":"),
    )
    _print_top_keys(body)
    out = capsys.readouterr().out
    assert "'panels': dict[1]" in out
    assert "'all_matches': list[3]" in out
    assert "'ver': str='1.0'" in out


def test_top_keys_on_non_json_says_so_instead_of_crashing(capsys):
    _print_top_keys("<!doctype html>not json")
    out = capsys.readouterr().out
    assert "不是 JSON 对象" in out


def test_text_context_strips_tags_and_keeps_nearby_words():
    """标签压成 `|`，附近的可读文字（比如赛事名）要留下来."""
    html = (
        "<div>filler</div>"
        "<h2>ATP Montreal</h2>"
        "<span>Rafael Jodar</span> <span>Lorenzo Musetti</span>"
    )
    ctx = _text_context(html, "Rafael Jodar", radius=100)
    assert "ATP Montreal" in ctx
    assert "Lorenzo Musetti" in ctx
    assert "<" not in ctx and ">" not in ctx


def test_text_context_missing_word_returns_empty():
    assert _text_context("<div>hi</div>", "not there") == ""

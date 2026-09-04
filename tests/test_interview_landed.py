"""tools/check_interview_landed.py —— 采访片 L2 成片落地闸。

只测**不联网/不碰成片**的半截：ass_has_dialogue、check_offline 的记分。
check_film 要 ffprobe + 成片，交给真实环境（和 check_reel_landed 同理由）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_interview_landed as ci  # noqa: PLC0415

    return ci


def _cover_tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import audit_interview_cover as cover

    return cover


def _cover_spec(*, close_up: bool = True) -> dict:
    return {
        "slug": "demo",
        "subject": {"name": "费德勒"},
        "cover": {
            "frame_at": 200.6,
            "shot_type": "close_up" if close_up else "medium",
            "zoom": 1.9 if close_up else 1.2,
            "focus_y": 0.9,
        },
    }


def _good_cover_result(*, close_up: bool = True) -> dict:
    spec = _cover_spec(close_up=close_up)
    return {
        "poster": {
            "decodable": True,
            "format": "JPEG",
            "width": 1080,
            "height": 1440,
            "photo_region": [0, 150, 1080, 810],
        },
        "contract": {
            "frame_at": 200.6,
            "shot_type": "close_up" if close_up else "medium",
            "zoom": 1.9 if close_up else 1.2,
            "focus_y": 0.9,
        },
        "face": {
            "detector": "frontal-default",
            "box": [380, 230, 180, 180],
            "detected_faces": 1,
            "eyes": 2,
            "face_height_ratio": 0.2222 if close_up else 0.10,
            "face_area_ratio": 0.037,
            "center_x_ratio": 0.435,
            "center_y_ratio": 0.21,
            "sharpness": 120.0,
            "contrast": 96.0,
        },
    }


def test_ffprobe的csv输出带尾随逗号也解析得出来():
    """2026-08-20 撞的：`pegula-cirstea-cincinnati-2026-r16` 那趟 render 在
    最后一步（`check_interview_landed.check_film`）崩掉——`ffprobe`
    对 `-of csv=p=0` 吐出 `291.880000,`（带一个尾随空字段），裸的
    `float()` 直接 `ValueError`（run 32319565674）。

    `check_reel_landed.py` 早为同一个坑加过 `_ffprobe_float()`（见
    `test_match_reel.py::test_ffprobe的csv输出带尾随逗号也解析得出来`），
    这个文件是姊妹工具，当时没跟着改。补上同名同形状的辅助函数。
    """
    ci = _tool()

    # ① 正常的干净输出
    assert ci._ffprobe_float("291.880000\n") == pytest.approx(291.88)
    # ② 当天真炸的那个字符串——多一个尾随逗号（空字段）
    assert ci._ffprobe_float("291.880000,\n") == pytest.approx(291.88)
    # ③ 反向验证：换回没有这层保护的写法，②这个真实样本会崩
    with pytest.raises(ValueError):
        float("291.880000,\n".strip())


def test_音轨峰值解析能识别数字静音():
    ci = _tool()
    assert ci._max_volume_db("[Parsed] max_volume: -3.2 dB") == pytest.approx(-3.2)
    assert ci._max_volume_db("[Parsed] max_volume: -inf dB") == float("-inf")
    assert ci._max_volume_db("没有这项") is None


def test_ass_has_dialogue认得Dialogue行(tmp_path):
    ci = _tool()
    ass = tmp_path / "x.ass"
    ass.write_text("[Events]\nDialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,你好\n",
                   encoding="utf-8")
    assert ci.ass_has_dialogue(ass) is True
    ass.write_text("[Script Info]\nTitle: x\n", encoding="utf-8")
    assert ci.ass_has_dialogue(ass) is False
    assert ci.ass_has_dialogue(tmp_path / "不存在.ass") is False


def test_check_offline全绿返回0(tmp_path, capsys):
    ci = _tool()
    spec = {"slug": "demo", "zh": ["你好"]}
    (tmp_path / "render.json").write_text(
        json.dumps({"video_url": "https://x/demo.mp4", "video_bytes": 12345}),
        encoding="utf-8")
    (tmp_path / "demo.ass").write_text("Dialogue: 0,0:00:00,0:00:01,,x\n",
                                       encoding="utf-8")
    bad = ci.check_offline(spec, tmp_path)
    assert bad == 0
    out = capsys.readouterr().out
    assert "成片在 Release 上" in out and "字幕 有 Dialogue" in out


def test_check_offline缺啥记啥(tmp_path, capsys):
    """每缺一样计 1 项不合格，且要出声——「没判」和「判了没问题」分得开。"""
    ci = _tool()
    spec = {"slug": "demo", "zh": []}
    bad = ci.check_offline(spec, tmp_path)  # 空目录：ass 无 + zh 空 = 2（render.json 无是"跳过"）
    assert bad == 2, f"ass 无 + zh 空应记 2，实际 {bad}"
    out = capsys.readouterr().out
    assert "不合格" in out


def test_bilingual_body只认正文同时间码双语不认顶栏(tmp_path):
    ci = _tool()
    ass = tmp_path / "x.ass"
    ass.write_text(
        "Dialogue: 0,0:00:00.00,0:00:10.00,HEADA,,0,0,0,,栏目顶栏\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Question\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,ZH,,0,0,0,,问题\n",
        encoding="utf-8")
    ok, detail = ci.bilingual_body_ok(ass, {"zh": ["问题"]})
    assert ok, detail

    ass.write_text(
        "Dialogue: 0,0:00:00.00,0:00:10.00,HEADA,,0,0,0,,栏目顶栏\n",
        encoding="utf-8")
    ok, _ = ci.bilingual_body_ok(ass, {"zh": ["问题"]})
    assert not ok, "顶栏有字不能冒充正文中英字幕"


def test_冷开场原解说也必须逐cue中英成对(tmp_path):
    ci = _tool()
    ass = tmp_path / "_lead.ass"
    ass.write_text(
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Match point\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,ZH,,0,0,0,,赛点\n",
        encoding="utf-8")
    spec = {"lead_in": {"subs": [{"en": "Match point", "zh": "赛点"}]}}
    assert ci.bilingual_lead_ok(ass, spec)[0]

    ass.write_text(
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Match point\n",
        encoding="utf-8")
    assert not ci.bilingual_lead_ok(ass, spec)[0], "只有英文不能通过冷开场双语质检"


def test_封面预期人物不能一律拿赢家_亚军与告别要取败者():
    cover = _cover_tool()
    assert cover.expected_subject({"subject": {"name": "费德勒"}}) == "费德勒"
    runner_up = {
        "requested_content_type": "ceremony", "interview_kind": "赛后亚军致辞",
        "winner": "高芙",
        "match": {"winner": "高芙", "loser": "佩古拉",
                  "participants": ["高芙", "佩古拉"]},
    }
    assert cover.expected_subject(runner_up) == "佩古拉"
    farewell = {
        "requested_content_type": "farewell", "interview_kind": "赛后告别仪式",
        "match": {"winner": "坂本怜", "loser": "锦织圭"},
    }
    assert cover.expected_subject(farewell) == "锦织圭"
    assert cover.expected_subject({}) == "", "没有事实字段时必须停，不能从标题猜"


def test_本地封面证据缺字段非正脸闭眼太小或模糊都失败():
    cover = _cover_tool()
    spec = _cover_spec()
    assert cover.validate_result(_good_cover_result(), spec) == []

    missing = _good_cover_result()
    del missing["face"]
    assert any("缺本地正面人脸" in x for x in cover.validate_result(missing, spec))

    profile = _good_cover_result()
    profile["face"]["detector"] = "profile"
    assert any("正面人脸" in x for x in cover.validate_result(profile, spec))

    closed = _good_cover_result()
    closed["face"]["eyes"] = 1
    assert any("只检出 1 只眼" in x for x in cover.validate_result(closed, spec))

    wide = _good_cover_result()
    wide["face"].update({"face_height_ratio": 0.08, "face_area_ratio": 0.005})
    issues = cover.validate_result(wide, spec)
    assert any("近景" in x and "14%" in x for x in issues)
    assert any("主体大小" in x for x in issues)

    blurry = _good_cover_result()
    blurry["face"]["sharpness"] = 20
    assert any("清晰度" in x for x in cover.validate_result(blurry, spec))

    weak_contract = _cover_spec()
    weak_contract["cover"]["zoom"] = 1.2
    proof = _good_cover_result()
    proof["contract"]["zoom"] = 1.2
    assert any("近景封面 zoom" in x for x in cover.validate_result(
        proof, weak_contract))


def test_封面视觉凭证同时绑定当前spec和最终poster(tmp_path):
    ci, cover = _tool(), _cover_tool()
    spec = _cover_spec()
    spec_path = tmp_path / "demo.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    poster = tmp_path / "poster.jpg"
    poster.write_bytes(b"first-poster")
    proof = tmp_path / cover.REPORT_NAME
    cover.write_report(
        proof, spec_path, poster, "费德勒", _good_cover_result(), [])

    ok, detail, _ = ci.cover_visual_ok(spec_path, spec, tmp_path)
    assert ok, detail

    poster.write_bytes(b"changed-poster")
    ok, detail, _ = ci.cover_visual_ok(spec_path, spec, tmp_path)
    assert not ok and "不是当前 poster" in detail

    # 恢复海报再改 spec：两种输入任何一种变化都必须让旧凭证失效。
    poster.write_bytes(b"first-poster")
    spec["cover"] = {"frame_at": 180}
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    ok, detail, _ = ci.cover_visual_ok(spec_path, spec, tmp_path)
    assert not ok and "不是当前 spec" in detail


def test_本地审核不需要外部key_像素分析失败则fail_closed(tmp_path, monkeypatch):
    cover = _cover_tool()
    spec_path = tmp_path / "demo.json"
    spec = _cover_spec()
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    poster = tmp_path / "poster.jpg"
    poster.write_bytes(b"poster")
    report = tmp_path / "proof.json"
    argv = ["audit_interview_cover.py", "--spec", str(spec_path),
            "--poster", str(poster), "--out", str(report)]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(cover, "analyze_poster", lambda _poster: _good_cover_result())
    assert cover.main() == 0
    passed = json.loads(report.read_text(encoding="utf-8"))
    assert passed["status"] == "pass"
    assert passed["auditor"] == cover.LOCAL_AUDITOR

    monkeypatch.setattr(
        cover,
        "analyze_poster",
        lambda _poster: (_ for _ in ()).throw(RuntimeError("opencv failed")),
    )
    assert cover.main() == 1
    failed = json.loads(report.read_text(encoding="utf-8"))
    assert failed["status"] == "fail" and "opencv failed" in failed["error"]


def test_QC凭证记录poster与视觉凭证hash(tmp_path, monkeypatch):
    ci, cover = _tool(), _cover_tool()
    spec = {
        "slug": "demo", "requested_content_type": "ceremony",
        "subject": {"name": "费德勒"}, "zh": ["你好"],
        "cover": _cover_spec()["cover"],
    }
    spec_path = tmp_path / "demo.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    poster = tmp_path / "poster.jpg"
    poster.write_bytes(b"poster-v1")
    visual = tmp_path / cover.REPORT_NAME
    cover.write_report(visual, spec_path, poster, "费德勒",
                       _good_cover_result(), [])
    ass = tmp_path / "demo.ass"
    ass.write_text(
        "Dialogue: 0,0:00:01.00,0:00:03.00,EN,,0,0,0,,Hello\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,ZH,,0,0,0,,你好\n",
        encoding="utf-8")
    film = tmp_path / "demo.mp4"
    film.write_bytes(b"film")

    import interview_source_gate
    monkeypatch.setattr(interview_source_gate, "validate_source_contract",
                        lambda _spec: "source-attestation")
    monkeypatch.setattr(interview_source_gate, "content_identity_id",
                        lambda _spec: "content-id")
    qc_path = ci.write_attestation(film, spec_path, spec, ass, tmp_path)
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    assert qc["spec_sha256"] == ci._sha256(spec_path)
    assert qc["poster_sha256"] == ci._sha256(poster)
    assert qc["cover_visual_attestation_sha256"] == ci._sha256(visual)
    assert qc["checks"]["cover_subject"] == "费德勒"
    assert qc["checks"]["cover_subject_prominent"] is True


def test_正式采访工作流在技术L2之前运行完全本地封面硬闸():
    body = Path(".github/workflows/interview-clip.yml").read_text(encoding="utf-8")
    visual = body.index("python tools/audit_interview_cover.py")
    landed = body.index("python tools/check_interview_landed.py")
    assert visual < landed, "必须先取得并验证封面视觉凭证，再写技术 QC pass"
    block = body[body.rfind("- name:", 0, visual):visual + 500]
    assert "MINIMAX_API_KEY" not in block and "DEEPSEEK" not in block
    assert "完全本地" in block
    assert "mode == 'render'" in block and "mode == 'cover'" in block, (
        "完整渲染和只换海报都必须审核，不能让 cover 模式成为绕闸入口")
    assert "|| true" not in block and "continue-on-error" not in block, (
        "视觉调用失败必须 fail closed")


def test_封面闸不合格也要把量到的数打出来(tmp_path, monkeypatch, capsys):
    """红灯那一支必须印证据，不能只印判词。

    来路：2026-09-04 孟菲尔斯那条封面连红四趟，每趟只换回一个比特——
    「这一版不行」。而脸多大、几只眼、清不清楚，`analyze_poster` 早就算完
    了就在手里，只是不合格那一支没打印，于是下一版改 `frame_at` 还是改
    `zoom` 全靠猜，每猜一次 2 分钟一趟 run。

    ⚠️ 判据不许因此变松：这里只断言「量到的数出现在输出里」，
    一个阈值都没动。
    """
    cover = _cover_tool()
    spec = _cover_spec()
    spec_path = tmp_path / "demo.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    poster = tmp_path / "poster.jpg"
    poster.write_bytes(b"poster")
    report = tmp_path / "proof.json"
    monkeypatch.setattr(sys, "argv", [
        "audit_interview_cover.py", "--spec", str(spec_path),
        "--poster", str(poster), "--out", str(report)])

    bad = _good_cover_result()
    bad["face"]["eyes"] = 1          # 只检出一只眼，正是当时那一趟
    monkeypatch.setattr(cover, "analyze_poster", lambda _poster: bad)
    assert cover.main() == 1
    out = capsys.readouterr().out
    assert "只检出 1 只眼" in out, "判词还是要有"
    # 证据那几项：脸多大、几只眼、清不清楚、明暗跨度——缺一项就还得靠猜
    for token in ("脸 ", "px", "眼 1 只", "清晰度", "明暗跨度", "脸心"):
        assert token in out, f"不合格那一支没把「{token}」打出来：{out}"

    # 一张正面脸都没检出时，读数那一行也要说人话，不能崩
    assert "没有人脸证据" in cover._evidence_line({"poster": {}})
    assert cover._evidence_line(None)

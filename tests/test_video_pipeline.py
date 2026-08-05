import ast
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest

from tennislive.research.brief import Chat
from tennislive.video.pipeline import (
    ChatTranslator,
    RightsError,
    VideoPipelineError,
    burn_subtitles,
    load_rights_manifest,
    localize_video,
    parse_srt,
    render_srt,
    translate_cues,
)


SRT = """1
00:00:00,000 --> 00:00:01,500
He saved 2 break points.

2
00:00:01,500 --> 00:00:03,000
That changed the match.
"""


class FakeTranslator:
    def translate(self, cues):
        return {
            cues[0].index: "他挽救了2个破发点。",
            cues[1].index: "这改变了比赛走势。",
        }


def _write_inputs(tmp_path: Path, **overrides):
    video = tmp_path / "interview.mp4"
    video.write_bytes(b"local authorized video")
    subtitles = tmp_path / "interview.en.srt"
    subtitles.write_text(SRT, encoding="utf-8")
    rights = {
        "asset_id": "interview-1",
        "source_file": video.name,
        "rights_basis": "written_permission",
        "rights_holder": "Rights holder",
        "allow_translation": True,
        "allow_republish": True,
        "source_url": "https://example.com/interview",
        "license": "",
        "permission_reference": "permission-email-2026-07-20",
        "attribution": "Video: Rights holder",
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "expires_at": "2027-07-20",
        "notes": "test",
    }
    rights.update(overrides)
    rights_path = tmp_path / "rights.json"
    rights_path.write_text(json.dumps(rights), encoding="utf-8")
    return video, subtitles, rights_path


def test_srt_round_trip_and_translation_preserve_timing():
    cues = parse_srt(SRT)
    translated = translate_cues(cues, FakeTranslator())

    assert len(cues) == 2
    assert translated[0].text == "他挽救了2个破发点。"
    assert translated[0].start_ms == 0
    assert translated[1].end_ms == 3000
    assert parse_srt(render_srt(translated)) == translated


def test_srt_rejects_overlapping_cues():
    overlapping = SRT.replace("00:00:01,500 --> 00:00:03,000", "00:00:01,400 --> 00:00:03,000")

    with pytest.raises(VideoPipelineError, match="overlaps"):
        parse_srt(overlapping)


def test_rights_manifest_is_bound_to_video_and_checksum(tmp_path):
    video, _, rights_path = _write_inputs(tmp_path)

    manifest = load_rights_manifest(rights_path, video, today=date(2026, 7, 20))

    assert manifest.asset_id == "interview-1"
    other = tmp_path / "other.mp4"
    other.write_bytes(video.read_bytes())
    with pytest.raises(RightsError, match="source_file"):
        load_rights_manifest(rights_path, other, today=date(2026, 7, 20))


def test_rights_manifest_rejects_expired_and_no_derivatives(tmp_path):
    video, _, expired_path = _write_inputs(tmp_path, expires_at="2026-07-19")
    with pytest.raises(RightsError, match="expired"):
        load_rights_manifest(expired_path, video, today=date(2026, 7, 20))

    video, _, nd_path = _write_inputs(
        tmp_path,
        rights_basis="creative_commons",
        license="CC BY-ND 4.0",
        permission_reference="",
    )
    with pytest.raises(RightsError, match="NoDerivatives"):
        load_rights_manifest(nd_path, video, today=date(2026, 7, 20))


class _StubChat(Chat):
    """不联网的模型替身，顺手把 system prompt 记下来。"""

    def __init__(self, reply=None):
        super().__init__(api_key="t")
        self._reply = reply
        self.prompts: list[tuple[str, str]] = []

    def ask(self, system, user, **kw):
        self.prompts.append((system, user))
        return self._reply


def test_字幕翻译走的是简报那条通道():
    chat = _StubChat(
        {"items": [{"id": 1, "zh": "他挽救了2个破发点。"}, {"id": 2, "zh": "这改变了比赛走势。"}]}
    )
    translator = ChatTranslator(chat=chat)
    result = translator.translate(parse_srt(SRT))

    assert result[1] == "他挽救了2个破发点。"
    assert result[2] == "这改变了比赛走势。"
    # 按 id 对回去，不是按顺序——乱序返回也要认得出
    payload = json.loads(chat.prompts[0][1])
    assert [row["id"] for row in payload] == [1, 2]


def test_没配密钥时报错要说出路():
    """「报错要说出路，不能只说不行」——而且要点名那个作废的变量。

    ⚠️ 老变量 `GITHUB_MODELS_TOKEN` 现在配了也没用（端点 410 退役中）。
    只说「要配密钥」的话，手里正拿着旧变量的人会以为自己已经配好了。
    """
    with pytest.raises(VideoPipelineError) as err:
        ChatTranslator(chat=Chat(api_key=""))
    text = str(err.value)
    assert "DEEPSEEK_API_KEY" in text and "ANTHROPIC_API_KEY" in text
    assert "GITHUB_MODELS_TOKEN" in text, "没点名那个作废的变量"


def test_字幕漏一条要报错不许静默跳过():
    """和标题中译的口径**相反**：标题译不出来就留英文，字幕漏一条是一段没字幕的画面。"""
    chat = _StubChat({"items": [{"id": 1, "zh": "他挽救了2个破发点。"}]})  # 少了 id=2
    with pytest.raises(VideoPipelineError, match="Missing translation for subtitle cue 2"):
        ChatTranslator(chat=chat).translate(parse_srt(SRT))


def test_模型没返回时要说清是哪一批():
    """一整条片子报「翻译失败」，不说清哪几条就只能整条重跑。"""
    with pytest.raises(VideoPipelineError) as err:
        ChatTranslator(chat=_StubChat(None)).translate(parse_srt(SRT))
    assert "1~2" in str(err.value) and "batch_size" in str(err.value)


def test_translation_rejects_changed_numeric_facts():
    class HallucinatingTranslator:
        def translate(self, cues):
            return {1: "他挽救了3个破发点。", 2: "这改变了比赛走势。"}

    with pytest.raises(VideoPipelineError, match="changed numeric facts"):
        translate_cues(parse_srt(SRT), HallucinatingTranslator())


def test_localize_video_without_burn_writes_srt_and_rights_audit(tmp_path):
    video, subtitles, rights_path = _write_inputs(tmp_path)
    outdir = tmp_path / "output"

    audit = localize_video(
        video_path=video,
        subtitle_path=subtitles,
        rights_path=rights_path,
        output_dir=outdir,
        translator=FakeTranslator(),
        burn=False,
    )

    localized = outdir / "interview.zh-CN.srt"
    assert "挽救了2个破发点" in localized.read_text(encoding="utf-8")
    assert audit["outputs"]["video"] is None
    assert (outdir / "attribution.txt").read_text(encoding="utf-8") == "Video: Rights holder\n"
    saved_audit = json.loads((outdir / "rights-audit.json").read_text(encoding="utf-8"))
    assert saved_audit["source_sha256"] == hashlib.sha256(video.read_bytes()).hexdigest()
    assert saved_audit["rights"]["permission_reference"] == "permission-email-2026-07-20"


def test_burn_subtitles_calls_ffmpeg_without_a_shell(tmp_path, monkeypatch):
    video, subtitles, _ = _write_inputs(tmp_path)
    output = tmp_path / "localized.mp4"
    commands = []
    monkeypatch.setattr("tennislive.video.pipeline.shutil.which", lambda _: "ffmpeg")

    def runner(command, check):
        commands.append((command, check))
        output.write_bytes(b"rendered")

    assert burn_subtitles(video, subtitles, output, runner=runner) == output.resolve()
    command, check = commands[0]
    assert check is True
    assert command[0] == "ffmpeg"
    assert "-vf" in command
    assert "subtitles=filename=" in command[command.index("-vf") + 1]
    assert all(not isinstance(part, Path) for part in command)


# ---------------------------------------------------------------------------
# 已退役的 GitHub Models 端点：不许回来
# ---------------------------------------------------------------------------
def _live_strings(path: Path) -> list[str]:
    """这个文件里**会被执行到**的字符串字面量（docstring 不算）。

    ⚠️ **用 AST 不用正则**，而且这一条是必须的：`models.github.ai` 这个
    URL 正写在 `pipeline.py` 的 docstring 和好几处注释里——那是这个仓库
    记教训的地方。按文本扫的话，「把坑记下来」会被判成「又踩了这个坑」，
    同一个错这个仓库犯过五次。

    注释根本不进 AST，所以只要再把 docstring 摘掉就够了。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_不许再指向已退役的GitHub_Models端点():
    """`models.github.ai/inference` 2026-08-05 实测 HTTP 410，正在退役。

    ⚠️ 它坏起来的样子**不是**「端点没了」，是一句「翻译失败」——读到的人
    第一反应会去查网络或 token。所以这道闸拦的是「有人照着旧代码又接一次」。

    判据两头都钉：**代码里不许有那个 host**，**工作流里不许再配那个 token**。
    """
    root = Path("src/tennislive")
    offenders = [
        f"{path}: {text}"
        for path in sorted(root.rglob("*.py"))
        for text in _live_strings(path)
        if "models.github.ai" in text
    ]
    assert not offenders, "还有活代码指着退役端点：\n" + "\n".join(offenders)

    # 工作流那头：配着一个作废的 token，看起来像「配好了」
    for workflow in sorted(Path(".github/workflows").glob("*.yml")):
        body = "\n".join(
            line for line in workflow.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        assert "GITHUB_MODELS_TOKEN" not in body, f"{workflow.name} 还配着作废的 token"


def test_做视频中文化的工作流要配模型密钥():
    """判据**自己推导，不维护白名单**：凡是跑 `tennislive video` 的都要配。

    「一个会过期的名单和一条常年红的检查是同一个毛病」——手写文件名的话，
    下次多一条出中文字幕的线，这道闸对它就是哑的。
    """
    checked = 0
    for workflow in sorted(Path(".github/workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        body = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        if not re.search(r"tennislive\s+video\b", body):
            continue
        checked += 1
        assert "DEEPSEEK_API_KEY" in body, f"{workflow.name} 没配 DEEPSEEK_API_KEY"
        assert "ANTHROPIC_API_KEY" in body, f"{workflow.name} 没配 ANTHROPIC_API_KEY"
    assert checked, "一条跑 tennislive video 的工作流都没扫到——判据的主语没了"


def test_配了Anthropic通道就要装它的SDK():
    """「加新能力就要同时改三处：代码、工作流的依赖、开跑前的预检」。

    ⚠️ `anthropic` 在 `Chat` 里是**延迟导入**的（没配密钥的那条路不该要求
    装这个包），所以不装也能一路跑到调模型那一步才炸——而那一步排在
    checkout、装依赖、校验路径之后。DeepSeek 那条只要 `requests`（主依赖），
    两条通道装的东西不一样，**而工作流两个密钥都配着**。

    判据**自己推导**：凡是配了 `ANTHROPIC_API_KEY` 的工作流都要装 `[brief]`。
    """
    checked = 0
    for workflow in sorted(Path(".github/workflows").glob("*.yml")):
        body = "\n".join(
            line for line in workflow.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        if "ANTHROPIC_API_KEY" not in body:
            continue
        checked += 1
        assert re.search(r"pip install[^\n]*\[brief\]", body), (
            f"{workflow.name} 配了 ANTHROPIC_API_KEY 却没装 [brief]，"
            "那条通道会在调模型那一步才炸"
        )
    assert checked, "一条配了 ANTHROPIC_API_KEY 的工作流都没扫到——判据的主语没了"

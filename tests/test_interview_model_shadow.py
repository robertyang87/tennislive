from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load(name: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_deepseek(bench):
    return {
        "translations": [
            {"speaker": "Coco Gauff", "en": bench.QUOTES[0]["en"],
             "zh": "我不喜欢看到你站在球网的另一边"},
            {"speaker": "Coco Gauff", "en": bench.QUOTES[1]["en"],
             "zh": "去年我还在停车场里哭 一年真的能带来很大变化"},
            {"speaker": "Coco Gauff", "en": bench.QUOTES[2]["en"],
             "zh": "这一周我有两次在房间里哭 就因为收到这些支持"},
        ],
        "takeaway": {
            "point": "去年停车场哭 今年一年大不同",
            "ask": "带着这份支持，她下一站会打出什么？",
        },
        "push": {
            "summary": "高芙一年走出停车场",
            "lead": "高芙 6-2 6-4 击败佩古拉，她谈到去年停车场的眼泪和这一年的变化。",
        },
    }


def good_minimax():
    return {
        "content_type": {
            "value": "ceremony", "reason": "颁奖台与奖杯清晰可见", "confidence": .95,
        },
        "interviewee": {
            "value": "高芙", "visible": True, "speaking_or_receiving_trophy": True,
            "reason": "高芙在话筒前讲话并接过奖杯", "confidence": .95,
        },
        "same_match_lead_in": {
            "value": True, "reason": "开场记分牌和随后颁奖服装一致", "confidence": .9,
        },
        "mirrored": {
            "value": False, "reason": "赛事台标文字方向正常可读", "confidence": .95,
        },
        "bilingual_subtitles": {
            "value": True, "reason": "英文与中文字幕上下两行同时可读", "confidence": .95,
        },
        "cover": {
            "subject": "高芙", "same_program": True, "frontal": True,
            "eyes_open": True, "clear": True,
            "reason": "封面为高芙正面睁眼清晰讲话帧", "confidence": .95,
        },
    }


def test_interview_skill注入deepseek正式翻译入口():
    skill = load("interview_skill")
    prompt = skill.model_instructions("deepseek")
    assert "name: tennis-interview-production" in prompt
    assert "gauff-pegula-cin2026-final" in prompt
    assert "主持人与球员不混淆" in prompt

    draft = load("draft_interview_spec")

    class Chat:
        system = ""

        def ask(self, system, _user, **_kwargs):
            self.system = system
            return {"lines": ["译文"]}

    chat = Chat()
    assert draft.translate([{"t": 0, "text": "English"}], chat) == ["译文"]
    assert "赛后开麦制作 Skill" in chat.system
    assert "英文原话与顺序" in chat.system


def test_deepseek影子基准满分要求逐句忠实和具体收口():
    bench = load("benchmark_interview_models")
    score, issues = bench.deepseek_score(good_deepseek(bench))
    assert score == 100
    assert issues == []


def test_deepseek改写英文或混淆说话人不能达标():
    bench = load("benchmark_interview_models")
    result = good_deepseek(bench)
    result["translations"][0]["en"] = "Gauff dislikes Pegula."
    result["translations"][1]["speaker"] = "Interviewer"
    score, issues = bench.deepseek_score(result)
    assert score < 85
    assert any("说话人" in issue for issue in issues)


def test_deepseek事实包外情节不能靠其他项拿高分():
    bench = load("benchmark_interview_models")
    result = good_deepseek(bench)
    result["push"]["lead"] += "她带伤三盘复仇并登上世界第一。"
    score, issues = bench.deepseek_score(result)
    assert score < 85
    assert any("事实包" in issue for issue in issues)


def test_minimax影子基准必须给完整视觉证据():
    bench = load("benchmark_interview_models")
    score, issues = bench.minimax_score(good_minimax())
    assert score == 100
    assert issues == []


def test_minimax把发布会当场上内容或封面闭眼不能晋级():
    bench = load("benchmark_interview_models")
    result = good_minimax()
    result["content_type"]["value"] = "press"
    result["cover"]["eyes_open"] = False
    score, issues = bench.minimax_score(result)
    assert score < 90
    assert any("ceremony" in issue for issue in issues)
    assert any("封面" in issue for issue in issues)


def test_minimax缺理由或低置信度不能显示满分():
    bench = load("benchmark_interview_models")
    result = good_minimax()
    result["mirrored"]["reason"] = ""
    result["bilingual_subtitles"]["confidence"] = .5
    score, issues = bench.minimax_score(result)
    assert score < 90
    assert any("置信度" in issue for issue in issues)


def test_interview影子工作流只读且不发布():
    body = (ROOT / ".github/workflows/interview-model-benchmark.yml").read_text(
        encoding="utf-8")
    assert "contents: read" in body
    assert "PUSHPLUS_TOKEN" not in body
    assert "git push" not in body
    assert "gh workflow run" not in body
    assert "tools/benchmark_interview_models.py" in body
    assert "gauff-pegula-cin2026-final.mp4" in body
    assert "source tools/ci_apt_install.sh" in body
    assert "ensure_ffmpeg" in body
    assert "timeout-minutes: 15" in body
    assert "branches: [main]" in body


def test_interview影子脚本不含生产副作用入口():
    body = (TOOLS / "benchmark_interview_models.py").read_text(encoding="utf-8")
    for forbidden in ("PUSHPLUS_TOKEN", "gh workflow run", "git push",
                      "pushed.json", "workflow_dispatch"):
        assert forbidden not in body
    assert "auto\": False" in body

"""Production timing must be carried across dispatch and remain observable."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
MATCH = ROOT / ".github/workflows/match-reel.yml"
INTERVIEW = ROOT / ".github/workflows/interview-clip.yml"
AUTO = ROOT / ".github/workflows/interview-auto-render.yml"
COLLECT = ROOT / ".github/workflows/oncourt-interviews.yml"


def _doc(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_both_production_workflows_accept_and_record_the_original_clock():
    for path in (MATCH, INTERVIEW):
        doc = _doc(path)
        inputs = doc["on"]["workflow_dispatch"]["inputs"]
        assert "received_at" in inputs
        body = path.read_text(encoding="utf-8")
        assert body.index("10 分钟成片时钟起点") < body.index("actions/checkout@v4")
        assert "tools/video_sla.py finish" in body
        assert "--artifact" in body and "--metadata" in body


def test_late_video_warns_but_is_not_killed_or_blocked_from_qc():
    tool = (ROOT / "tools/video_sla.py").read_text(encoding="utf-8")
    assert "::warning::owned MP4 missed" in tool
    assert "automatic publishing is blocked" not in tool
    for path, qc_name in ((MATCH, "查成片本身合不合格"),
                          (INTERVIEW, "验成片（L2 成片落地闸）")):
        body = path.read_text(encoding="utf-8")
        finish = body.index("tools/video_sla.py finish")
        assert finish < body.index(qc_name)
        render_block = body[body.rfind("- name:", 0, finish):finish]
        assert "timeout --foreground" not in render_block


def test_dispatchers_pass_one_clock_edge_into_parallel_renders():
    queue = (ROOT / "tools/dispatch_reel_queue.py").read_text(encoding="utf-8")
    auto = AUTO.read_text(encoding="utf-8")
    assert "received_at={received_at}" in queue
    assert '-f "received_at=$RECEIVED_AT"' in auto
    assert '--mark-one "$slug" --at "$RECEIVED_AT"' in auto


def test_interview_heavy_dependencies_are_cached_without_quality_downgrade():
    body = INTERVIEW.read_text(encoding="utf-8")
    assert "~/.cache/huggingface/hub" in body
    assert "faster-whisper-${{ runner.os }}-${{ steps.second_asr.outputs.model }}" in body
    assert "~/.cache/ms-playwright" in body
    assert 'spec.get("whisper_model", "small.en")' in body


def test_draft_batch_immediately_wakes_promotion_instead_of_waiting_for_cron():
    doc = _doc(COLLECT)
    assert doc["permissions"]["actions"] == "write"
    kick = doc["jobs"]["kick-render"]
    assert kick["needs"] == "draft"
    assert "gh workflow run interview-auto-render.yml" in COLLECT.read_text(encoding="utf-8")


def test_source_scan_has_a_bounded_parallelism_control():
    body = (ROOT / "tools/collect_oncourt_interviews.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--max-parallel", type=int, default=4' in body
    assert "ThreadPoolExecutor(max_workers=min(args.max_parallel, len(sources)))" in body
    assert 'ap.error("--max-parallel 必须在 1..8' in body

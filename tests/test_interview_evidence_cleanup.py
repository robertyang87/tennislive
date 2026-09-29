"""The actual workflow cleanup must preserve subtitle evidence used by L2."""
from pathlib import Path
import os
import re
import subprocess


def test_cleanup_keeps_side_subtitle_evidence_and_removes_media(tmp_path):
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/interview-clip.yml"
    text = workflow.read_text(encoding="utf-8")
    loop = re.search(r'          for intermediate in .*?          done', text, re.S)
    assert loop, "Use the actual cleanup loop, not a test-only copy"
    for name in ("_lead.ass", "_trail.ass", "_body.mp4", "_logo_mask.png"):
        (tmp_path / name).write_text("evidence or temporary bytes")
    voice = tmp_path / "_tkvoice_01"
    voice.mkdir()
    (voice / "voice.mp3").write_text("temporary")
    subprocess.run(["bash", "-eu", "-c", loop.group()],
                   env={**os.environ, "D": str(tmp_path)}, check=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["_lead.ass", "_trail.ass"]

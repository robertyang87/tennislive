"""GitHub Actions 原始视频归档的合同判据。"""

import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/download-video.yml")


def _body() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_手动入口只要视频链接():
    body = _body()
    assert "workflow_dispatch:" in body
    assert re.search(r"\n\s+url:\n\s+description:", body)
    assert re.search(r"\n\s+url:.*?\n\s+required:\s*true", body, re.S)


def test_下载复用现有youtube解锁链路():
    body = _body()
    assert '"yt-dlp[default]"' in body
    assert "YT_COOKIES_TXT" in body
    assert "bgutil-ytdlp-pot-provider" in body
    assert "--js-runtimes node" in body


def test_分轨视频下载前必须安装ffmpeg才能合并成mp4():
    body = _body()
    install = body.find("sudo apt-get install -y ffmpeg")
    download = body.find('yt-dlp "${ARGS[@]}"')
    assert install != -1, "runner 没安装 ffmpeg，分开的视频/音频轨不会合并"
    assert download != -1, "找不到实际下载命令"
    assert install < download, "ffmpeg 必须在 yt-dlp 下载分轨格式之前安装"


def test_原片上传release并在摘要输出直链():
    body = _body()
    assert "GH_REPO: ${{ github.repository }}" in body, (
        "工作流没有 checkout，gh release 必须用 GH_REPO 明确仓库"
    )
    assert "gh release upload" in body
    assert "--clobber" in body
    assert re.search(r"for attempt in 1 2 3 4", body)
    assert "releases/download/$TAG/$ASSET" in body
    assert "GITHUB_STEP_SUMMARY" in body
    assert "-r 0-99" in body


def test_归档名按youtube视频id隔离():
    body = _body()
    assert "--print id" in body
    assert 'TAG="source-$VIDEO_ID"' in body
    assert 'ASSET="$VIDEO_ID.mp4"' in body

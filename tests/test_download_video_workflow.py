"""GitHub Actions 原始视频归档的合同判据。"""

import json
import os
import re
import subprocess

import pytest
import yaml
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
    # 与共享安装链一致；只认实际命令行，不让注释里的名字冒充安装。
    checkout = body.find("uses: actions/checkout@v4")
    script = body.find("/tools/ci_apt_install.sh")
    source = re.search(r"^\s+source tools/ci_apt_install\.sh\s*$", body, re.M)
    ensure = re.search(r"^\s+ensure_ffmpeg\s*$", body, re.M)
    assert checkout != -1 and script > checkout, "共享脚本必须先从仓库检出"
    assert source and ensure, "ffmpeg 必须调用共享安装脚本"
    install = ensure.start()
    assert script < source.start() < install, "必须先检出并 source 共享脚本，再安装 ffmpeg"
    download = body.find('yt-dlp "${ARGS[@]}"')
    assert install != -1, "runner 没安装 ffmpeg，分开的视频/音频轨不会合并"
    assert download != -1, "找不到实际下载命令"
    assert install < download, "ffmpeg 必须在 yt-dlp 下载分轨格式之前安装"


def test_原片上传release并在摘要输出直链():
    body = _body()
    assert "GH_REPO: ${{ github.repository }}" in body, (
        "gh release 必须用 GH_REPO 明确仓库"
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


def _step(step_id):
    workflow = yaml.safe_load(_body())
    return next(step for step in workflow["jobs"]["archive"]["steps"]
                if step.get("id") == step_id)


@pytest.mark.parametrize(("url", "expected"), [
    ("https://www.tennistv.com/videos/4599139/basel-2026-r1", "kind=tennistv\nid=4599139\n"),
    ("https://www.youtube.com/watch?v=CGsiDxZqdzA", "kind=youtube\nid=\n"),
    ("https://example.com/?ref=tennistv.com/videos/4599139", "kind=youtube\nid=\n"),
])
def test_实际识别脚本只按官方主机与数字ID认TennisTV(tmp_path, url, expected):
    output = tmp_path / "output"
    env = dict(os.environ, VIDEO_URL=url, GITHUB_OUTPUT=str(output))
    subprocess.run(["bash", "-e", "-c", _step("source")["run"]], env=env, check=True)
    assert output.read_text() == expected


def _fake_tennis_modules(tmp_path):
    """Run the real workflow shell with a public resolver and downloader stand-in."""
    package = tmp_path / "modules"
    official = package / "tennislive/video"
    official.mkdir(parents=True)
    (package / "tennislive/__init__.py").write_text("")
    (official / "__init__.py").write_text("")
    (official / "official.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "def media_url(url):\n"
        "    Path(os.environ['RESOLVER_LOG']).write_text(url)\n"
        "    if os.environ.get('DENY_PUBLIC') == '1':\n"
        "        raise RuntimeError('public entitlement returned HTTP 401')\n"
        "    return 'https://media.example/video.m3u8?token=ephemeral-secret'\n"
    )
    downloader = package / "yt_dlp"
    downloader.mkdir()
    (downloader / "__init__.py").write_text("")
    (downloader / "__main__.py").write_text(
        "import os,sys,json\nfrom pathlib import Path\n"
        "Path(os.environ['DOWNLOADER_LOG']).write_text(json.dumps(sys.argv))\n"
        "target=sys.argv[sys.argv.index('-o')+1].replace('%(ext)s','mp4')\n"
        "Path(target).write_bytes(b'x'*60000)\n"
    )
    return dict(os.environ, PYTHONPATH=str(package), RUNNER_TEMP=str(tmp_path),
                VIDEO_URL="https://www.tennistv.com/videos/4599139/short-highlights",
                SOURCE_KIND="tennistv", ARCHIVE_VIDEO_ID="4599139", YT_COOKIES="",
                GITHUB_OUTPUT=str(tmp_path / "output"),
                RESOLVER_LOG=str(tmp_path / "resolver.log"),
                DOWNLOADER_LOG=str(tmp_path / "downloader.log"))


def test_实际TennisTV归档用共享解析器且保留稳定页面ID(tmp_path):
    env = _fake_tennis_modules(tmp_path)
    result = subprocess.run(["bash", "-e", "-c", _step("video")["run"]],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "resolver.log").read_text() == env["VIDEO_URL"]
    args = json.loads((tmp_path / "downloader.log").read_text())
    assert args[-1] == "https://media.example/video.m3u8?token=ephemeral-secret"
    assert "--cookies" not in args and "--js-runtimes" not in args
    assert (tmp_path / "download/4599139.mp4").stat().st_size == 60000
    assert "id=4599139\n" in (tmp_path / "output").read_text()
    assert "ephemeral-secret" not in result.stdout + result.stderr


def test_公开entitlement拒绝时不下载也不造归档凭据(tmp_path):
    env = _fake_tennis_modules(tmp_path)
    env["DENY_PUBLIC"] = "1"
    result = subprocess.run(["bash", "-e", "-c", _step("video")["run"]],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "HTTP 401" in result.stderr
    assert not (tmp_path / "downloader.log").exists()
    assert not (tmp_path / "download/4599139.mp4").exists()
    assert not (tmp_path / "output").exists()


def test_实际YouTube下载仍带node与已配置cookies(tmp_path):
    env = _fake_tennis_modules(tmp_path)
    binary = tmp_path / "bin/yt-dlp"
    binary.parent.mkdir()
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import os,sys,json\nfrom pathlib import Path\n"
        "with open(os.environ['DOWNLOADER_LOG'],'a') as f:f.write(json.dumps(sys.argv)+'\\n')\n"
        "if '--print' in sys.argv:\n"
        "    print('CGsiDxZqdzA' if sys.argv[-2]=='id' else 'Basel final')\n"
        "else:\n"
        "    target=sys.argv[sys.argv.index('-o')+1].replace('%(ext)s','mp4')\n"
        "    Path(target).write_bytes(b'x'*60000)\n"
    )
    binary.chmod(0o755)
    env.update(SOURCE_KIND="youtube", ARCHIVE_VIDEO_ID="", YT_COOKIES="/safe/cookies.txt",
               VIDEO_URL="https://www.youtube.com/watch?v=CGsiDxZqdzA",
               PATH=str(binary.parent) + os.pathsep + env["PATH"])
    result = subprocess.run(["bash", "-e", "-c", _step("video")["run"]],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in (tmp_path / "downloader.log").read_text().splitlines()]
    assert len(calls) == 3
    for args in calls:
        assert args[args.index('--js-runtimes') + 1] == 'node'
        assert args[args.index('--cookies') + 1] == '/safe/cookies.txt'
        assert args[-1] == env["VIDEO_URL"]
    assert not (tmp_path / "resolver.log").exists()
    assert (tmp_path / "download/CGsiDxZqdzA.mp4").stat().st_size == 60000

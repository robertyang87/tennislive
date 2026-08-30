"""赛后开麦「合进 main 就自动发微信」的六道发布闸。

**这条线 2026-08-14 之前一条自动推送都没有**，而且不是配漏了，是
**结构性够不着**：`auto-push-reel` 的路径正则写着
`output/<日期>/reel/<slug>/render.json`，采访产物却在
`output/interviews/<slug>/`——没有日期那一层。量出来的代价是 18 条 spec
里 0 条写了 `push.auto`、18 个产物目录里 0 个 `pushed.json`，而赛后开麦是
时效最紧的一条。

所以这份测试有两件事要盯，缺一不可：

1. **发布闸各自真的在拦**（每道都反向验证：不只验「该发的发了」，
   更要验「不该发的一条都没发」）；
2. **路径正则真的匹配得到这条线的目录形状**——用仓库里**真实的**产物路径验，
   不拿手搓的字符串。手搓的只能证明「我写的正则符合我以为的形状」，
   而这次出事的正是「我以为的形状」本身。
"""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import auto_push_gate as reel_gate  # noqa: E402
import auto_push_interview_gate as gate  # noqa: E402

WORKFLOW = Path(".github/workflows/auto-push-interview.yml")
MANUAL_WORKFLOW = Path(".github/workflows/interview-clip.yml")


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    这个仓库的工作流注释正是记教训的地方，正文里必然写着当年那些错值；
    而这一次更要紧的是反方向：注释里出现 `auto` / `main` / `--record`
    会让漏配的写法**假绿**。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args],
                   check=True, capture_output=True)


def _write_interview(repo: Path, slug: str, push: dict | None) -> Path:
    """造一条带 L0 来源签名、L2 QC 凭证和 Release 指纹的可发布采访。"""
    from interview_source_gate import finalize_source_contract

    spec: dict = {
        "slug": slug,
        "column": "赛后开麦",
        "url": f"https://example.test/{slug}/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "zh": ["正文中文"],
        "cover": {
            "frame_at": 20.0,
            "shot_type": "close_up",
            "zoom": 1.8,
            "focus_y": 0.55,
        },
        "lead_in": {
            "url": f"https://example.test/{slug}/highlight", "start": 10.0, "end": 14.0,
            "subs": [{"a": 10.0, "b": 12.0, "en": "Match point", "zh": "赛点"}],
        },
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict",
            "source_url": f"https://example.test/{slug}/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
        "match": {
            "id": f"2026:test:qf:{slug}", "event": "测试赛", "round": "四分之一决赛",
            "winner": "赢家", "loser": "输家", "participants": ["赢家", "输家"],
        },
    }
    if push is not None:
        spec["push"] = push
    finalize_source_contract(spec)

    spec_dir = repo / "specs/interviews"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / f"{slug}.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    (spec_dir / f"{slug}.xhs.txt").write_text("文案", encoding="utf-8")

    outdir = repo / f"output/interviews/{slug}"
    outdir.mkdir(parents=True, exist_ok=True)
    poster_path = outdir / "poster.jpg"
    poster_path.write_bytes(b"\xff\xd8\xff not-a-real-jpeg")
    spec_sha = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    poster_sha = hashlib.sha256(poster_path.read_bytes()).hexdigest()
    cover_proof_path = outdir / "cover_visual_attestation.json"
    cover_proof_path.write_text(json.dumps({
        "status": "pass", "expected_subject": "赢家",
        "auditor": "opencv-haar-v1",
        "spec_sha256": spec_sha, "poster_sha256": poster_sha,
        "result": {
            "poster": {
                "decodable": True, "format": "JPEG", "width": 1080,
                "height": 1440, "photo_region": [0, 150, 1080, 810],
            },
            "contract": {
                "frame_at": 20.0, "shot_type": "close_up", "zoom": 1.8,
                "focus_y": 0.55,
            },
            "face": {
                "detector": "frontal-default", "box": [380, 230, 180, 180],
                "detected_faces": 1, "eyes": 2, "face_height_ratio": 0.22,
                "face_area_ratio": 0.037, "center_x_ratio": 0.435,
                "center_y_ratio": 0.21, "sharpness": 120.0, "contrast": 96.0,
            },
        },
    }, ensure_ascii=False), encoding="utf-8")
    film_hash = hashlib.sha256(f"{slug}-film".encode()).hexdigest()
    film_bytes = 12345
    qc_path = outdir / "qc_attestation.json"
    qc_path.write_text(json.dumps({
        "status": "pass", "slug": slug, "match_id": spec["match"]["id"],
        "source_attestation_sha256": spec["source_verification"]["attestation_sha256"],
        "spec_sha256": spec_sha,
        "poster_sha256": poster_sha,
        "cover_visual_attestation_sha256": hashlib.sha256(
            cover_proof_path.read_bytes()).hexdigest(),
        "lead_ass_sha256": hashlib.sha256(f"{slug}-lead-ass".encode()).hexdigest(),
        "film_sha256": film_hash, "film_bytes": film_bytes,
        "checks": {"bilingual_body_cues": 1, "bilingual_lead_cues": 1},
    }), encoding="utf-8")
    (outdir / "render.json").write_text(json.dumps({
        "video_url": f"https://example.test/{slug}.mp4",
        "video_bytes": film_bytes,
        "film_sha256": film_hash,
        "release_asset_digest": f"sha256:{film_hash}",
        "qc_attestation_sha256": hashlib.sha256(qc_path.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    return outdir


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """一个最小的**真 git 仓库**：一条 spec、一份文案、一个渲好的 outdir。

    ⚠️ 必须是真 git：「已经推过」和「海报在不在」两道闸查的都是
    `git ls-files`，不是 `test -f`——喂一个普通目录就把它们绕过去了，
    而绕过去之后测试**照样绿**。

    ⚠️ **海报要有。** 一条真渲完的采访必然带着 `poster.jpg`
    （`interview-clip.yml` 的清理那步按后缀删 html、按前缀删 `_*`，
    特意把它留着），所以这个 fixture 也得有——这样「该发的照发」那几条
    验的才是它们各自那道闸，而不是被海报闸拦下。
    """
    _write_interview(tmp_path, "demo", {})
    _git(tmp_path, "init", "-q")
    # render.json 提交进仓库——现实里它就是先由 interview-clip 提交、随 PR
    # 进 main 的；「已删除的产物不算候选」那道闸查的是 git ls-files，
    # 不提交的话所有用这个 fixture 的测试都会被那道闸拦下。
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "base")
    return tmp_path


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c", "commit", "-qm", "x")


def _spec(repo: Path, push: dict | None, slug: str = "demo") -> None:
    _write_interview(repo, slug, push)


def _second_interview(repo: Path, slug: str = "demo2") -> Path:
    """再造一条**渲完的**采访（spec + 文案 + render.json + 海报）。

    海报在这儿是必需品，不是装饰：少了它「海报在仓库里」那道闸会把这条
    候选筛掉，于是「一趟带进来两条」那类测试只剩一个候选、恒绿——一道
    真闸就这么被另一道闸悄悄遮住了。收在一处，别在每个测试里各写一遍。
    """
    return _write_interview(repo, slug, {"auto": True})


CHANGED = ["output/interviews/demo/render.json"]


# ------------------------------------------------- 闸 1：路径（真实产物形状）

def _real_render_json() -> list[str]:
    """仓库里**真实**的采访 render.json 路径。

    ⚠️ 用 `git ls-files`，不是 `Path("output").glob(...)`。两个理由：
    ① CI 的检出是**非 cone 稀疏模式**，而这条线还有别的工作流按别的模式检出
      ——按文件系统扫会随检出方式变；索引不受稀疏影响（条目只是被标了
      skip-worktree），`git ls-files` 在哪种模式下都数得到同一批。
    ② 这正是闸自己判「在不在仓库里」用的那把尺（`tracked()`），
      判据和被判的东西用同一个口径。
    """
    done = subprocess.run(
        ["git", "ls-files", "output/interviews/*/render.json"],
        capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if line.strip()]


def test_路径正则认得出真实的采访产物形状(tmp_path: Path):
    """**这条测试就是这次问题的判据本身。**

    `auto-push-reel` 够不着这条线，不是因为谁把配置写错了，是因为两条线的
    目录形状不一样：reel 是 `output/<日期>/reel/<slug>/`，采访是
    `output/interviews/<slug>/`——**没有日期那一层**（`push_reel.headline`
    的注释写着这是故意的：同一场采访哪天发都可能）。

    所以拿仓库里**真实**的路径来验，不拿手搓的字符串：手搓的只能证明
    「我写的正则符合我以为的形状」，而出事的正是「我以为的形状」。
    """
    real = _real_render_json()
    # **判据自己的判据。** 主语没了（换了目录、glob 写错、CI 上没检出）时
    # 要当场出声，而不是变成一条恒真的绿灯——空列表和「全都匹配」在
    # `all()` 下长得一模一样，这个仓库为它栽过。
    assert len(real) >= 10, (
        f"只数到 {len(real)} 条真实的采访 render.json，判据失效了——"
        "要么路径变了，要么这条 git ls-files 没数到东西")

    for path in real:
        slug, outdir = gate.candidate(path, tmp_path)
        # slug 要和目录名对得上，outdir 要指回同一格
        assert path == f"output/interviews/{slug}/render.json"
        assert outdir == tmp_path / "output" / "interviews" / slug


def test_reel那条路结构性够不着采访产物(tmp_path: Path):
    """**这条钉的是「为什么要单独开一条」，不是重复上一条。**

    如果哪天 `auto_push_gate` 真的兼容了这个形状（比如参数化成一份代码），
    这条会红——那正是该来删掉这份工作流和这份判据的时候，而不是让两条路
    悄悄都能匹配、同一条采访被发两次。
    """
    real = _real_render_json()
    assert len(real) >= 10, "判据失效了：没数到真实的采访 render.json"
    for path in real:
        with pytest.raises(reel_gate.Skip):
            reel_gate.candidate(path, tmp_path)


@pytest.mark.parametrize("path", [
    "output/interviews/demo/poster.jpg",          # 不是 render.json
    "output/interviews/demo/sub/render.json",     # 多了一层
    "output/2026-08-03/reel/demo/render.json",    # 那是 reel，走另一条路
    "output/2026-08-03/knowledge/demo/render.json",
    "specs/interviews/demo.json",                 # 压根不在 output 下
])
def test_形状不对的路径一律不发(repo: Path, path: str):
    _spec(repo, {"auto": True})
    assert gate.pick([path], repo) is None


# ---------------------------------------------------------------- 闸 2：认领

def test_没写auto的一条都不发(repo: Path, capsys):
    """**默认关。** 现在 `specs/interviews/` 下 18 条 spec 一条都没写
    `push.auto`，也就是说这条工作流合并之后**什么都不会发**——要开得再动
    一次手，一条一条想清楚。
    """
    _spec(repo, {"summary": "伊埃拉六连胜"})
    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "没写 push.auto=true" in out, f"跳过了却没说为什么：{out}"
    # 报错要说出路，不能只说不行
    assert '"auto": true' in out


def test_写了auto才发(repo: Path):
    """反向验证上一条：同样的输入，只加一行 `auto: true`，就该发。

    没有这一条的话，「一条都不发」可以由任何一个 bug 造成——**证明不了
    是那道闸在起作用**。
    """
    _spec(repo, {"auto": True})
    picked = gate.pick(CHANGED, repo)
    assert picked is not None, "写了 auto 还是不发，那这个开关根本没接上"
    assert picked[0] == "demo"


def test_auto写成字符串要报错(repo: Path):
    """`"auto": "true"` 在 Python 里是真值，`is True` 判它是假。

    两种处理都说得通，但**悄悄不发**和「这条本来就没开」长得一模一样——
    又一次不吭声的兜底。所以报错。
    """
    _spec(repo, {"auto": "true"})
    with pytest.raises(SystemExit, match="只能是 true 或 false"):
        gate.pick(CHANGED, repo)


# ---------------------------------------------------------------- 闸 3：别重发

def test_已经推过的不许再发一次(repo: Path, capsys):
    """判据是**产物**（`pushed.json` 在仓库里），不是「工作流跑成功过」。

    这条路会被任何一次动到 `render.json` 的提交触发——重渲、改 spec、
    甚至 2026-08-13 那次「历史成片迁上 Release，链接写进 render.json」
    一口气改了 17 份。没有这道闸，已经发过的采访会被再发一次。
    """
    _spec(repo, {"auto": True})
    reel_gate.record(repo / "output/interviews/demo",
                     "https://example/run/1", "2026-08-14T00:00:00Z")
    _commit_all(repo)
    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "已经推过了" in out and "example/run/1" in out, (
        f"跳过了却没说是哪一趟发的，出问题时无从查起：{out}")


def test_没提交的标记不算数(repo: Path):
    """只写在工作区、没进仓库的 `pushed.json` **不能**算「已经发过」。

    如果认它，一次失败的 run 留下的半截文件就会把这条采访永久锁死，
    而且不吭声。反过来说，这也正是它必须查 `git ls-files` 的另一半理由。
    """
    _spec(repo, {"auto": True})
    reel_gate.record(repo / "output/interviews/demo", "run", "now")
    # 故意不提交
    assert gate.pick(CHANGED, repo) is not None


def test_旧成片的pushed标记不能拦住新成片(repo: Path, capsys):
    """同一 slug 修封面重渲后，film hash 已变，必须作为新发布处理。

    旧回执仍由独立 ledger 保存；不能因为 output 里的 pushed.json 还指向
    上一版，就让新成片的自动推送绿着跳过。
    """
    _spec(repo, {"auto": True})
    marker = repo / "output/interviews/demo/pushed.json"
    marker.write_text(json.dumps({
        "status": "sent", "film_sha256": "0" * 64,
        "at": "old", "run": "https://example/old",
    }), encoding="utf-8")
    _commit_all(repo)

    assert gate.pick(CHANGED, repo) is not None
    assert "允许新成片进入发布" in capsys.readouterr().out


def test_稀疏检出下也要拦得住(repo: Path):
    """这条工作流是稀疏检出的：判断的时候 `output/` 那一格还没
    `git sparse-checkout add` 回来，文件根本不在工作区——按
    `(outdir / MARKER).is_file()` 判那道闸**恒为假，会重复发**。

    这条测试把工作区里那份删掉（模拟稀疏检出的样子），索引里留着，
    要求照样拦得住。反向验证过：退回 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    marker = reel_gate.record(repo / "output/interviews/demo", "run", "now")
    _commit_all(repo)
    marker.unlink()  # ← 稀疏检出之后工作区里就是没有它
    assert gate.pick(CHANGED, repo) is None


def test_稀疏检出下独立发布账本也不能失忆(repo: Path, capsys):
    """ledger 在 Git 里、但 data/ 没被检出时，必须从 HEAD 读取并阻断重发。

    只用 ``Path.is_file()`` 会把这种状态当成无账本；采访 output 又可能被重渲，
    旧 pushed.json 不可靠，于是同一份成片会被再次推到微信。
    """
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    ledger = gate.reserve(repo, "demo", outdir, "run-1", "2026-08-23T00:00:00Z")
    _commit_all(repo)
    ledger.unlink()  # 模拟 workflow 的 sparse checkout 没把 data/ 那格落到工作区

    assert gate.pick(CHANGED, repo) is None
    assert "sending" in capsys.readouterr().out


# ---------------------------------------------------------------- 闸 4：海报

def test_海报不在仓库里就不发(repo: Path, capsys):
    """**这条线现在一张海报都没有，所以这道闸上来就会拦下所有存量。**

    2026-08-13 `archive-media.yml mode=purge` 用 git filter-repo 从全史抹掉了
    output/ 下所有 jpg（认领过的取舍，17 GB → 789 MB）。量过（2026-08-14）：
    `git ls-files 'output/interviews/*/poster*'` **零命中**，18 个产物目录
    一张不剩。

    海报是推送正文的第一屏，没有它这条消息只剩两个按钮，看不出这是谁的采访。
    """
    _spec(repo, {"auto": True})
    (repo / "output/interviews/demo/poster.jpg").unlink()
    _git(repo, "rm", "-q", "--cached", "output/interviews/demo/poster.jpg")
    _commit_all(repo)

    assert gate.pick(CHANGED, repo) is None, (
        "海报不在仓库里还照发——推出去就是一条没有第一屏的消息，"
        "而微信那条消息收不回来")
    out = capsys.readouterr().out
    assert "poster.jpg" in out, f"跳过了却没说是海报的问题：{out}"
    # 报错要说出路，不能只说不行。这条线的出路比 reel 便宜：`mode=cover`
    # 下源片、抽帧、渲海报、删源片，一个 mp4 都不产生。
    assert "mode=cover" in out, f"没说怎么把它救回来：{out}"


def test_海报在就照发(repo: Path):
    """反向验证上一条：同样的输入，只把海报放回去，就该发。

    没有这一条的话，「一条都不发」可以由任何一个 bug 造成——**证明不了
    是海报那道闸在起作用**。
    """
    _spec(repo, {"auto": True})
    picked = gate.pick(CHANGED, repo)
    assert picked is not None, "海报好好地在仓库里，却被拦下了"
    assert picked[0] == "demo"


def test_render必须绑定当前QC凭证(repo: Path, capsys):
    """旧 render 不能配一份后来替换的 pass QC 冒充同一轮质检。"""
    _spec(repo, {"auto": True})
    qc = repo / "output/interviews/demo/qc_attestation.json"
    data = json.loads(qc.read_text(encoding="utf-8"))
    data["checks"]["note"] = "replaced-after-release"
    qc.write_text(json.dumps(data), encoding="utf-8")
    assert gate.pick(CHANGED, repo) is None
    assert "当前 QC 凭证" in capsys.readouterr().out


def test_render必须持久绑定Release_asset_digest(repo: Path, capsys):
    """公开 URL 能打开不等于同 slug 附件已经换成本趟成片。"""
    _spec(repo, {"auto": True})
    render_path = repo / "output/interviews/demo/render.json"
    render = json.loads(render_path.read_text(encoding="utf-8"))
    render["release_asset_digest"] = f"sha256:{'0' * 64}"
    render_path.write_text(json.dumps(render), encoding="utf-8")

    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "Release asset" in out and "当前 QC 成片" in out


def test_QC必须逐cue证明冷开场解说双语完整(repo: Path, capsys):
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    qc_path = outdir / "qc_attestation.json"
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    qc["checks"]["bilingual_lead_cues"] = 0
    qc_path.write_text(json.dumps(qc), encoding="utf-8")
    render_path = outdir / "render.json"
    render = json.loads(render_path.read_text(encoding="utf-8"))
    render["qc_attestation_sha256"] = hashlib.sha256(qc_path.read_bytes()).hexdigest()
    render_path.write_text(json.dumps(render), encoding="utf-8")
    assert gate.pick(CHANGED, repo) is None
    assert "获胜画面原解说" in capsys.readouterr().out


def test_稀疏检出下海报也要认得出(repo: Path):
    """**这道闸最容易写错的地方，而写错的后果比漏发大得多。**

    这个脚本排在 `git sparse-checkout add` **之前**——`output/` 那一格根本
    不在工作区。按 `(outdir / "poster.jpg").is_file()` 判就是**恒为假**：
    不是漏发一条，是**每一条都不发**，整条自动推送静静地死掉，而 run 还是绿的。

    这条把工作区里那份删掉（模拟稀疏检出的样子）、索引里留着，要求照常发。
    反向验证过：把 `tracked()` 换成 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    _commit_all(repo)
    (repo / "output/interviews/demo/poster.jpg").unlink()

    picked = gate.pick(CHANGED, repo)
    assert picked is not None, (
        "海报在仓库里、只是没检出到工作区，就被判成「没有海报」——"
        "按 is_file() 判的话每一条都会这样")
    assert picked[0] == "demo"


# ---------------------------------------------------------------- 闸 5：只发一条

def test_一趟带进来两条就一条都不发(repo: Path):
    """批量自动发微信，错一次就是错一片。

    这条线尤其撞得上：2026-08-13 那次「历史成片迁上 Release」一个提交改了
    **17 份** render.json。
    """
    _spec(repo, {"auto": True})
    _second_interview(repo)
    _commit_all(repo)

    with pytest.raises(SystemExit):
        gate.pick(CHANGED + ["output/interviews/demo2/render.json"], repo)


def test_删除的render_json不算候选(repo: Path, capsys):
    """清理旧版产物的合并会把**删除**的 render.json 也带进 changed 列表。
    被删的产物不是新渲完的片子——它的 spec 往往还写着 auto:true、目录里
    又没有 pushed.json，不拦的话会凑成「一次 N 条」把真该发的一起拦死。
    """
    _spec(repo, {"auto": True})
    _commit_all(repo)
    _git(repo, "rm", "-rq", "output/interviews/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")
    assert gate.pick(CHANGED, repo) is None
    assert "不在仓库里" in capsys.readouterr().out, "跳过要说出为什么"


def test_同一批里删一条活一条要发活的那条(repo: Path):
    """删掉被顶替的旧版 + 新渲的一条。删除项被滤掉后，活的那条必须照常发
    ——别把防批量的闸误触发。"""
    _spec(repo, {"auto": True})
    _second_interview(repo)
    _commit_all(repo)
    _git(repo, "rm", "-rq", "output/interviews/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")

    picked = gate.pick(CHANGED + ["output/interviews/demo2/render.json"], repo)
    assert picked is not None and picked[0] == "demo2", (
        "删除项混进来把活的那条也拦死了——防批量的闸不该被幽灵候选触发")


def test_工作流的diff要滤掉删除项():
    """第一层在 workflow：`--diff-filter=AM`。没有它，删除的 render.json
    一样进 changed 列表——闸挡得住，但一趟 run 会红着结束，真该发的那条
    要等人来查。"""
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8")).replace("\\\n", " ")
    line = next(l for l in body.splitlines()
                if "git diff" in l and "render.json" in l)
    assert "--diff-filter=AM" in line, (
        "auto-push-interview 的 diff 少了 --diff-filter=AM：删除的 render.json "
        "会被当成候选")


# ------------------------------------------------- 共用的部分：import，不抄

def test_共用基础判据但采访发布账本独立():
    """路径存在性和旧标记继续共用；发布状态改为 output 外的独立账本。

    判据用 `is`，不是「行为一样」：抄一份的话行为一开始当然一样，
    分叉是后来发生的，而分叉的样子是——改了 reel 那头的标记名，这头静默
    失配，于是同一条采访被发第二次。`Skip` 更硬：抄一份的话
    `except Skip` 根本捕不到对方那个类。
    """
    assert gate.Skip is reel_gate.Skip
    assert gate.tracked is reel_gate.tracked
    assert gate.record is not reel_gate.record
    assert gate.MARKER == reel_gate.MARKER == "pushed.json"
    assert gate.LEDGER_DIR == Path("data/interview_publish_ledger")


def test_两条线分叉的只有路径形状和spec目录():
    """反过来钉一头：真正该各写各的只有这两样。

    没有这条的话，上一条只证明「共用的没抄」，证明不了「没共用的确实
    只有这两样」——下一个人往这个文件里再抄一段 reel 的逻辑，两条都绿。
    """
    assert gate.SPEC_DIR == Path("specs/interviews")
    assert reel_gate.SPEC_DIR == Path("specs/reels")
    assert gate.SPEC_DIR != reel_gate.SPEC_DIR


def test_发布账本预占后阻断自动重发(repo: Path, capsys):
    """发送前先记 sending；进程随后崩溃也不能把同一成片盲发第二次。"""
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    ledger = gate.reserve(repo, "demo", outdir, "https://example/run/1", "2026-08-23T00:00:00Z")
    _commit_all(repo)
    assert json.loads(ledger.read_text())["attempts"][0]["status"] == "sending"
    assert gate.pick(CHANGED, repo) is None
    assert "sending" in capsys.readouterr().out


def test_平台接收和状态不明都绑定同一成片指纹(repo: Path):
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    gate.reserve(repo, "demo", outdir, "run", "t1")
    ledger = gate.record(repo, "demo", outdir, "run", "t2", "receipt-123")
    row = json.loads(ledger.read_text())["attempts"][0]
    assert row["status"] == "accepted" and row["key"].startswith("pushplus:demo:")
    assert row["pushplus_receipt"] == "receipt-123"
    assert row["provider"] == "pushplus"
    assert row["requested_channel"] == "wechat"
    assert row["platform_status"] == "accepted"
    assert row["delivery_status"] == "unverified"
    marker = json.loads((outdir / "pushed.json").read_text(encoding="utf-8"))
    assert marker["status"] == "accepted" and marker["slug"] == "demo"
    assert marker["film_sha256"] == row["film_sha256"]
    assert marker["publication_key"] == row["key"]
    assert marker["pushplus_receipt"] == "receipt-123"
    assert marker["provider"] == "pushplus"
    assert marker["requested_channel"] == "wechat"
    assert marker["platform_status"] == "accepted"
    assert marker["delivery_status"] == "unverified"
    ledger = gate.uncertain(repo, "demo", outdir, "run", "t3")
    rows = json.loads(ledger.read_text())["attempts"]
    assert len(rows) == 1 and rows[0]["status"] == "accepted", \
        "已有平台流水号时，失败收尾不能把 accepted 降级成 uncertain"


def test_没有流水号不许写accepted(repo: Path):
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    with pytest.raises(ValueError, match="必须带非空流水号"):
        gate.record(repo, "demo", outdir, "run", "t2", "")
    with pytest.raises(SystemExit, match="必须同时提供 --receipt-file"):
        gate.main([
            "--record", str(outdir), "--slug", "demo",
            "--repo", str(repo), "--run", "run", "--now", "t2",
        ])


# ------------------------------------------------- 标题日期：算一次，两处共用

def test_标题日期算一次两处共用(tmp_path: Path, monkeypatch):
    """**这条线独有的一个数。**

    采访产物目录里没有日期（故意的），所以 `push_reel` 解不出来、必须显式
    传 `--date`。而 `--stage page` 和真正发微信那次**各算一遍标题**，
    `wait_for_copy_page(expect=title)` 要求两次算出同一句——两步之间跨过
    上海午夜的话，两次 `date +%F` 会给出两个日期，于是复制页去等一句
    **永远不会出现**的话，等满 40 分钟再静静把按钮摘掉，**run 还是绿的**。

    所以日期从 gate 出一次，两步都引它。这条钉两头：gate 真的出了这个值，
    而工作流那两步真的引的是它、不是各自 `date +%F`。
    """
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    gate._emit("demo", Path("output/interviews/demo"))
    written = dict(
        line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    assert written["date"] == gate.shanghai_today()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", written["date"])

    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    dates = re.findall(r"--date [^\n]*", body)
    assert len(dates) == 2, f"写复制页和推送各要一次 --date，数到 {len(dates)} 次"
    for line in dates:
        assert "steps.gate.outputs.date" in line, (
            f"这一步自己算了日期，没引 gate 那一份：{line}\n"
            "两处各算一次，跨过上海午夜就分叉——而分叉的样子是「复制页按钮"
            "偶尔没有」，run 照样绿")
    assert "date +%F" not in body, (
        "工作流里还有人自己算标题日期——这个数只许有一个出处")


def test_上海日期不靠tzdata():
    """用固定的 UTC+8，不用 `ZoneInfo("Asia/Shanghai")`。

    中国 1991 年起不再实行夏令时，这个偏移是恒定的；而 `ZoneInfo` 要系统的
    tzdata，缺了它抛 `ZoneInfoNotFoundError`——排在最前面的一步抛出一个跟
    日期毫无关系的错，表现就是整条自动推送不发。
    """
    body = Path("tools/auto_push_interview_gate.py").read_text(encoding="utf-8")
    src = re.sub(r'"""[\s\S]*?"""', "", body)
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "ZoneInfo" not in src, "别把 tzdata 拖进这条路"
    assert "timedelta(hours=8)" in src


# ---------------------------------------------------------------- 工作流本身

def test_自动推送只在main上跑():
    """GitHub Pages 只服务 main（复制页在分支上永远 404），而海报链接钉在
    commit sha 上——未合并的 commit 有被 GC 的风险。

    ⚠️ **这条判据 2026-08-21 换过主语。** 第一版断言「不许有
    workflow_dispatch」，而它的前提当天被量死了：render 的提交是
    GITHUB_TOKEN 推的，GitHub 明文规定这种 push **不创建 workflow run**
    （防递归）——于是 on:push 从上线起一次都没为 render 醒来过（铁证：
    50 份 render.json / 0 份 pushed.json）。dispatch 从「多余的手动入口」
    变成了**唯一走得通的主路**（interview-clip 渲完来叫醒），前提没了就得
    换判据。「只在 main 上跑」这半句没变，只是落点换成两头：
    push 触发限 main + dispatch 第一步有 main 守卫。
    """
    raw = WORKFLOW.read_text(encoding="utf-8")
    body = _yaml_only(raw)
    trigger = body.split("permissions:")[0]
    assert "branches: [main]" in trigger, "没限定 main"
    assert "output/interviews/*/render.json" in trigger, (
        "触发路径不是采访产物的形状")
    assert "workflow_dispatch" in trigger, (
        "dispatch 入口没了——render 的提交是 GITHUB_TOKEN 推的、触发不了 "
        "on:push，没有 dispatch 这条工作流对 render 是全死的")
    # dispatch 可以选分支，所以要有守卫：不在 main 上当场红，不许静静跑完
    guard = re.search(
        r"github\.event_name == 'workflow_dispatch' &&\s*"
        r"github\.ref_name != 'main'", body)
    assert guard, "dispatch 没有 main 守卫——分支上的复制页和海报永远 404"
    # 守卫要排在 checkout 之前：白拉一次仓库只是慢，守卫排后面则是先干活再拦
    assert body.index("github.ref_name != 'main'") < body.index(
        "actions/checkout"), "main 守卫要排在 checkout 之前"


def test_dispatch两条路都过工具里那套闸():
    """dispatch 点名（--slug）和不点名（git ls-files 扫全部）都必须把判定
    交给 `auto_push_interview_gate.py`——闸写进 YAML 就测不了了。
    on:push 那条兜底路照旧拿 HEAD^ 比（浅克隆下 event.before 可能不在本地）。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    gate_step = body[body.index("挑出该自动发的那一条"):body.index("把这一格放进稀疏范围")]
    assert "--slug" in gate_step, "点名那条路没接 --slug"
    assert "git ls-files 'output/interviews/*/render.json'" in gate_step, (
        "不点名那条路要扫仓库里全部 render.json（ls-files 读 index，"
        "不受稀疏检出影响）——闸会把已推过/没认领的逐条拦掉")
    assert "HEAD^ HEAD" in gate_step, "on:push 兜底路不见了"


def test_render完要叫醒自动推送():
    """render 的成片提交用的是 GITHUB_TOKEN，**永远触发不了** on:push
    （GitHub 防递归）；不叫醒的话 auto-push-interview 对 render 是全死的
    ——量过的铁证：50 份 render.json / 0 份 pushed.json。
    `workflow_dispatch` 正是那条禁令明文列出的例外，所以渲完点一下。
    """
    body = _yaml_only(
        Path(".github/workflows/interview-clip.yml").read_text(encoding="utf-8"))
    m = re.search(r"gh workflow run auto-push-interview\.yml[^\n]*", body)
    assert m, "interview-clip 渲完没有叫醒 auto-push-interview"
    line = m.group(0)
    assert "--ref main" in line, "要点名 main 上那份工作流文件"
    assert "slug=" in line, "叫醒时要把 slug 递过去，省一趟全库扫描"
    # 位置：要排在「提交成片」之后——成片没落库就叫醒，那头扫到的是旧东西
    assert body.index("- name: 提交成片") < body.index("- name: 叫醒自动推送"), (
        "叫醒排在提交成片之前")
    # 条件三头都要有：只有 render 有新东西可发；本趟自己发（push=true）就不许
    # 再叫醒（同一条消息发两遍的竞态）；分支上的产物 Pages 取不到
    blk = body.split("- name: 叫醒自动推送")[1].split("- name:")[0]
    assert "github.event.inputs.mode == 'render'" in blk
    assert "github.event.inputs.push != 'true'" in blk, (
        "本趟自己要发还叫醒自动推送——那头看不到任何「正在发」的标记，"
        "会把同一条消息再发一遍")
    assert "github.ref_name == 'main'" in blk


def test_gate的slug入口只有当前成片accepted才允许成功noop(
        repo: Path, monkeypatch, capsys):
    """`--slug` 不是绕闸的近路：它只是把入参折成那条 render.json 的路径，
    照走 `pick` → 发布门禁。判据两头：合格的这条要 found=true 落进
    GITHUB_OUTPUT；已推过的同一条要被「已经推过」那道闸拦下（拦得住才说明
    真的走的是同一条路，不是另写了一份少闸的判定）。
    """
    _spec(repo, {"auto": True})
    _commit_all(repo)
    out_file = repo / "gh_out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out_file))
    assert gate.main(["--slug", "demo", "--repo", str(repo)]) == 0
    text = out_file.read_text(encoding="utf-8")
    assert "slug=demo" in text and "found=true" in text

    # 当前成片有平台流水号后，点名重放允许 success no-op，但不能再发。
    gate.record(
        repo, "demo", repo / "output/interviews/demo", "r", "t", "receipt-accepted")
    _commit_all(repo)
    out_file.unlink()
    assert gate.main(["--slug", "demo", "--repo", str(repo)]) == 0
    captured = capsys.readouterr().out
    assert "[安全跳过]" in captured and "已由 PushPlus 接收" in captured
    output = out_file.read_text(encoding="utf-8")
    assert "found=false" in output and "already_accepted=true" in output


def test_手动工作流accepted_noop后不许继续发送():
    body = _yaml_only(MANUAL_WORKFLOW.read_text(encoding="utf-8"))
    gate_block = body.split("- name: 推送前通过 L0/L2/幂等门禁", 1)[1]
    assert "id: manual_gate" in gate_block.split("- name:", 1)[0]
    for step_name in ("预占发布账本（发送前）", "推送到微信", "记下平台已经接收"):
        block = body.split(f"- name: {step_name}", 1)[1].split("- name:", 1)[0]
        assert "steps.manual_gate.outputs.found == 'true'" in block, (
            f"{step_name} 没有在 accepted no-op 后停下")


def test_gate的slug入口sending和无回执旧标记必须非零(repo: Path, capsys):
    _spec(repo, {"auto": True})
    outdir = repo / "output/interviews/demo"
    gate.reserve(repo, "demo", outdir, "run", "t1")
    _commit_all(repo)
    assert gate.main(["--slug", "demo", "--repo", str(repo)]) == 1
    assert "点名发布被门禁阻断" in capsys.readouterr().out


def test_gate的slug入口对没render过的条目要出声(repo: Path, capsys):
    """点名一条根本没 render 过的 slug：不许炸、不许假绿地报 found，
    要打出「render.json 不在仓库里」让人看见点错了名。"""
    assert gate.main(["--slug", "ghost", "--repo", str(repo)]) == 1
    out = capsys.readouterr().out
    assert "点名发布被门禁阻断" in out and "render.json 不在仓库里" in out


def test_gate的slug和changed不能同时给(repo: Path):
    """两个入口一起给没有一种读法是对的——宁可当场红。"""
    with pytest.raises(SystemExit) as exc:
        gate.main(["--slug", "demo", "--changed", "x", "--repo", str(repo)])
    assert exc.value.code == 2


def test_自动推送不许取消正在跑的():
    """取消一个已经发出 POST 的 run，只会让「发没发出去」变成未知，
    而 `pushed.json` 那一笔可能没记上——下一次触发就会再发一遍。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert re.search(r"cancel-in-progress:\s*false", body), (
        "自动推送不许 cancel-in-progress: true")


def test_自动推送这条路不装出片那一堆():
    """它不下源片、不转写、不烧字幕、不编码——装那一堆就是白等几分钟，
    而这条路的全部意义就是省掉人的往返。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    for heavy in ("ffmpeg", "playwright", "chromium", "rembg", "yt-dlp",
                  "faster-whisper", "edge-tts", "fonts-noto"):
        assert heavy not in body.lower(), f"自动推送这条路不该出现 {heavy}"


def test_发完要把已推送记进仓库():
    """**记不进仓库就等于没记。** 只活在 runner 工作区里的标记，下一次触发
    读不到——同一个毛病在复制页上踩过两次（日志印着链接、步骤 success、
    人点开是 404）。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    record = body[body.index("--record"):]
    # push 走共享重试脚本（tools/git_push_retry.sh，2026-08-26 收的）：
    # 裸 push 撞上别的自动任务刚推过 main 就红，而这一步红掉的样子是
    # 「微信已发、标记没落库」——下一次触发会再发一遍。
    assert "git commit" in record and "push_with_rebase_retry" in record, (
        "记了 pushed.json 却没提交/没推——下一次触发会再发一遍")
    assert "--receipt-out" in body and "pushed.json" in record \
        and "--receipt-file" in record, (
        "accepted 账本没有同时提交 pushed.json / PushPlus 流水号，L4 证据不完整")


def test_自动和手动推送都必须保存回执且失败恢复按回执分流():
    """两条入口都要能在“平台已接收、后续补账失败”时只补 accepted。"""
    for path in (WORKFLOW, MANUAL_WORKFLOW):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        assert "--receipt-out" in body, f"{path} 推送成功后没有保存 PushPlus 流水号"
        assert "--receipt-file" in body, f"{path} 补账没有消费 PushPlus 流水号"
        assert "找到 PushPlus 流水号" in body and "--record" in body
        assert "没有平台流水号" in body and "--uncertain" in body
        assert "pushed.json" in body, f"{path} accepted marker 没有提交"


def test_记已推送要排在发微信之后():
    """反过来（先记后发）的话，推送失败会留下一个「已经发过」的假标记，
    这条采访从此再也发不出去，而且不吭声。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert body.index("--stage page") < body.index("--record"), (
        "复制页写在了记标记之后")
    send = body.index("TENNISLIVE_ASSET_REV")
    assert send < body.index("--record"), "记已推送排到了发微信前面"


def test_等复制页的窗口要装得进job的超时():
    """**60 × 40s = 40 分钟**，照抄 `interview-clip.yml`（这条线的 Pages
    实测能慢到 14 分钟以上）。而 job 的 `timeout-minutes` 必须比它大——
    小了的话等待还没走完 job 就被砍，**砍掉的时机正好在「复制页已提交、
    微信一个字没发」那一段**，而且没有任何「已发过」标记会记下这件事。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    attempts = int(re.search(r'TENNISLIVE_COPYPAGE_ATTEMPTS:\s*"(\d+)"',
                             body).group(1))
    delay = int(re.search(r'TENNISLIVE_COPYPAGE_RETRY_SECONDS:\s*"(\d+)"',
                          body).group(1))
    timeout = int(re.search(r"timeout-minutes:\s*(\d+)", body).group(1))
    assert timeout * 60 > attempts * delay, (
        f"等复制页最长 {attempts * delay}s，而 job 只给 {timeout * 60}s——"
        "等待走不完就会被砍在「已提交、没发消息」那一段")


def _tracked_slugs(pattern: str) -> set[str]:
    """`output/interviews/<slug>/…` 里被 git 跟踪的 slug 集合。

    ⚠️ 用 `git ls-files` 不用 `Path.glob`：CI 的稀疏检出把 `output/` 挡在外面，
    而索引里的条目只是被标了 skip-worktree——`glob` 在 CI 上恒空，而**空集合和
    「一条都没有」长得一模一样**。
    """
    out = subprocess.run(["git", "ls-files", pattern],
                         capture_output=True, text=True, check=True)
    return {line.split("/")[2] for line in out.stdout.split() if line}


def _ledger_slugs() -> set[str]:
    """`data/interview_publish_ledger/<slug>.json` 里被 git 跟踪的 slug 集合。

    和 `_tracked_slugs` 是同一个理由（sparse checkout、`git ls-files` 不用
    `glob`），但路径形状不同——账本不挂在 `output/interviews/<slug>/` 下面，
    是 `data/interview_publish_ledger/<slug>.json` 这一层，slug 是文件名去掉
    后缀，不是路径第三段。
    """
    out = subprocess.run(
        ["git", "ls-files", "data/interview_publish_ledger/*.json"],
        capture_output=True, text=True, check=True)
    return {Path(line).stem for line in out.stdout.split() if line}


def test_推过而没记下的采访不许开自动推送():
    """**这条线上唯一能造成重发的动作，就是给「推过、却没有记下」的那些开 `auto`。**

    闸 3（没推过）查的是**发布账本**（`data/interview_publish_ledger/<slug>.json`，
    `auto_push_interview_gate.LEDGER_DIR`）——不是 `pushed.json`。判据是产物：
    复制页是推送流程写的，`copy.html` 在仓库里就说明这条走过那条路
    （`swiatek-shnaider-tor2026-qf` 没有，它只到 `--stage subs`）。

    ⚠️ **这条测试自己就是「主语没了就得换判据」的一个实例，2026-08-24 抓到的
    ——但只对了一半，第一版把范围收窄错了。** 原来判「没推过」只查
    `output/interviews/<slug>/pushed.json`，而 `fils-tiafoe-cin2026-final`／
    `gauff-pegula-cin2026-final` 这次会话真推送成功、账本里都有
    `status: "sent"` 的记录，却因为没有 `pushed.json` 被判成「推过而没记下」——
    `auto_push_interview_gate.py` 自己的 docstring 写着「独立发布账本的同一
    成片键没有 sending/sent/uncertain；旧 `<outdir>/pushed.json` **仍兼容拦截**」，
    权威信号已经是账本，只查 `pushed.json` 落后了一步。**第一版的修法把它改成
    只查账本**，本地全量当场抓出反例：`gauff-kostyuk-cincinnati-2026-qf` 只有
    `pushed.json`（`{"at": "2026-08-22T12:26:23Z", "run": "…32572945050"}`，
    真实的发送记录）、没有账本文件，被新判据当成「没推过」——**同一个错误的
    镜像版，这次是把还在被真实产线（`wants_auto_push` 里 `marker = outdir /
    MARKER` 那一段）当场认可的旧标记当成不存在了**。查 `wants_auto_push` 的
    实现才看清楚：它是**两条都查、任一条命中就算已推过**（`tracked(marker)` +
    账本），不是账本取代了 `pushed.json`——「仍兼容拦截」那句话说的就是并集，
    不是账本优先、`pushed.json` 归零。判据因此是两个集合的并集，不能收窄成
    其中一个。

    ⚠️ **主语是算出来的，不是一张手写名单。** 原来这儿冻着一份 17 条的
    `_ALREADY_PUSHED` 外加一条「名单要完整」的自检，**一天之内被 CI 抓红六次**，
    每次的修法都是「加一行」。注释上写着「只许减不许加」，可那是注释不是判据——
    实测加一行两条测试双双转绿。按这条线 2~8 条/天的到货节奏，几周之内它就退化
    成一张许可证。**改成集合差之后，「加一行」这个动作根本不存在。**

    补第五、六行那次，补的人自己在注释里写下了结论：「⚠️ 一天之内同一个自检
    抓到两批，说明**漏的不是记性是流程**」——对，而流程这一头没法靠更用力地
    记住来修：出片那个提交本来就不该负责往一张测试文件里的名单添名字。

    ⚠️ **而那张名单还锁死了这套机制本身。** 一条新采访开 `auto` 推成功之后，
    工作流先提交 `copy.html`（`--stage page`）、发完微信再落发布账本——于是它
    同时有了两样。名单那版的自检会要求把它补进名单，而补进去之后另一条又要求
    它 `auto is not True`：**两条互斥，从第一条自动推送成功那天起谁也满足不了。**
    减掉旧标记那一半就自然放行——标记一落库，闸 3 接管，`auto` 留着完全正常，
    正是这套机制该有的样子。
    """
    published = _tracked_slugs("output/interviews/*/copy.html")
    # **判据自己的判据。** 主语没了（目录改名、glob 写错、`output/` 真被清空）
    # 的样子就是这个集合为空，而那时这条测试会安安静静地全绿。
    assert len(published) >= 10, (
        f"只数到 {len(published)} 条有复制页的采访，判据失效了")

    already_recorded = _ledger_slugs() | _tracked_slugs("output/interviews/*/pushed.json")
    suspects = sorted(published - already_recorded)
    orphan, checked = [], 0
    for slug in suspects:
        spec = Path("specs/interviews") / f"{slug}.json"
        if not spec.is_file():
            orphan.append(slug)
            continue
        checked += 1
        push = json.loads(spec.read_text(encoding="utf-8")).get("push") or {}
        assert push.get("auto") is not True, (
            f"{slug} 推过微信了，而仓库里既没有它的发布账本也没有 pushed.json"
            "——闸 3 拦不住，开了 auto 就是把同一条消息再发一遍，而消息收不回来")
    if orphan:
        # 产物在、spec 没了。它开不了 auto（没有 spec 可写），所以不算错；
        # 但**要说一声**——不然「跳过了 N 条」和「查过 N 条」在日志上一样。
        print(f"  [跳过] 这些采访有复制页却没有 spec：{orphan}")
    print(f"  推过而没记下的 {len(suspects)} 条，真查了 {checked} 条")


def test_只add自己那一格():
    """`git add --sparse`，而且只 add 本次那个 outdir。

    ⚠️ **`--sparse` 不能漏**：稀疏模式下裸的 `git add` 对 cone 外的路径只
    警告、退出码 0，然后 `git diff --cached --quiet` 说「没有变化」——
    `pushed.json` 静默丢掉，下一次触发就再发一遍。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8")).replace("\\\n", " ")
    adds = [l.strip() for l in body.splitlines() if l.strip().startswith("git add")]
    assert adds, "工作流里一句 git add 都没有？"
    for line in adds:
        assert "--sparse" in line, f"稀疏检出下 git add 要带 --sparse：{line}"
        assert ("steps.gate.outputs.outdir" in line
                or "data/interview_publish_ledger/${{ steps.gate.outputs.slug }}.json" in line), (
            f"add 的不是本次产物或本次独立账本：{line}")

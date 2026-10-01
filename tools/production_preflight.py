"""Run the publisher's own cheap checks before any media/model work."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tools_on_path() -> None:
    """`absolute_claims` 在 tools/ 下；只插一次——一趟 build 逐条请求都走这里，
    `interview_preflight` 也逐条 spec 调 `check_interview_spec_claims`。"""
    tools = str(ROOT / 'tools')
    if tools not in sys.path:
        sys.path.insert(0, tools)


def check_copy(copy: Path, column: str, *, date: str = '', quiet: bool = False) -> None:
    # quiet：把 push_reel 的输出收进异常里，不写到 stdout——
    # `interview_preflight` 被 `pick_interview_renders` 调，后者的 stdout 是 dispatch 名单。
    date = date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    subprocess.run([sys.executable, str(ROOT / 'tools/push_reel.py'), '--stage', 'check',
                    '--copy', str(copy), '--outdir', 'output/preflight',
                    '--column', column, '--date', date], check=True,
                   **({'capture_output': True, 'text': True} if quiet else {}))


class RequestNotReady(ValueError):
    """请求本身没过 `check_request`——**确定性的**：不改请求，每一趟都一样红。

    `build_interview_request --write` 见到它只把这一条留在待生成名单、报一句
    `::warning::`，**不让整个 step 红**：那一步后面的「配结尾／提交／dispatch」只挂着
    `if: steps.gate.outputs.work == 'true'`，隐式的 success() 会把它们一起跳过——
    一条请求的解读卡写长了，就把**别的 spec** 的提交和 dispatch 每 10 分钟卡一趟，
    直到有人改这条请求（review 那条）。网络、ASR、翻译那类失败照旧让 step 红。

    带 `--failed-list`（interview-auto-render 就是这么调的）时它和别的失败一样记进失败清单：
    那一步本来就退 0、不连坐，清单让提交／dispatch 跳过这条的上一版正式 spec，最后一步
    写进 run 摘要并标红——没过前置检查的请求不会只剩一句被人略过的 warning。"""


def check_taste(spec: dict, *, auto: bool | None = None) -> None:
    """账号所有者的口味闸（采访线）：标题和推送标题的数字一致（硬）；封面大标题的
    术语（账号所有者 2026-09-27 答复做硬：手写的硬、自动链没核没发的只报，见
    `taste_gates.interview_taste_findings`）。

    `auto=False`：人工请求那条路（`check_request`）——标题是人写在请求里的，一律按手写判，
    哪怕「只改元数据」那条路上铺进来的现有 spec 带着自动链的章。

    2026-09-27「形成一个通用的规则在做视频前就拦掉，而不是说做了一半又返工」——
    所以它排在任何下载、ASR、渲染之前。判据单一出处 tools/taste_gates.py。
    """
    _tools_on_path()
    from taste_gates import interview_taste_findings  # noqa: PLC0415
    hard, soft = interview_taste_findings(spec, auto=auto)
    for note in soft:
        print(f"[口味] {spec.get('slug', '?')} 只报：{note}")
    if hard:
        # 请求自己的文案问题，确定性的——和解读卡、全称断言同一类（`RequestNotReady`，
        # 它是 ValueError 的子类，原来按 ValueError 接的地方照旧接得住）
        raise RequestNotReady('不合账号所有者的口味：' + '；'.join(hard))


def check_request(req: dict) -> None:
    """请求预检（任何下载之前）。

    ⚠️ 口味闸读的必须是**这一趟真会写进 spec 的**标题和推送标题：调用方传进来的
    `req` 在「只改元数据」那条路上是 `{**请求, **按请求差量改过的现有 spec}`
    （现有 spec 手改过的标题赢），在重建那条路上就是请求本身（`build_spec` 原样
    抄请求的 cover/push）。所以这里不另去读 specs/ 下的旧稿。
    """
    # No download, fonts, browser or ASR import required here.
    check_taste(req, auto=False)
    # 出片那一趟 `build_interview_clip.main()` 开头还有两道**只读 spec 文本**的闸：
    # 比分赢家视角（`check_score_orientation`）和另一半口味闸（`check_taste_extra`）。
    # 原来请求这一步不查它们——`interview-auto-render` 用 GITHUB_TOKEN 把 spec 直推 main
    # （CI 不跑），render 那道闸挡住了片子，而全库测试（`test_全库顶栏比分都是赢家视角`、
    # `test_全库已发的spec一条都不红`）要到下一个 PR 才把 main 打红（批次 4 复审 BLOCKING；
    # 先例：`zheng-rybakina-us-open-2026-qf-presser` 请求里的输家视角「6-3 1-6 4-6」）。
    # 同一份判据、不另写：判据 `test_请求预检拦比分输家视角和总分差`。
    _tools_on_path()
    from interview_spec_gates import score_orientation_problem  # noqa: PLC0415
    if (problem := score_orientation_problem(req)):
        raise RequestNotReady(problem)
    from taste_gates_extra import interview_taste_extra  # noqa: PLC0415
    hard, _soft = interview_taste_extra(req, str(req.get('xhs') or '') or None)
    if hard:
        raise RequestNotReady('；'.join(hard))
    cov = req.get('cover') or {}
    zoom, focus = float(cov.get('zoom', 1)), float(cov.get('focus_y', .5))
    if not 1 <= zoom <= 2.4 or not 0 <= focus <= 1:
        raise RequestNotReady('cover zoom/focus_y 超出安全范围')
    if cov.get('shot_type') == 'close_up' and zoom < 1.5:
        raise RequestNotReady('close_up 封面 zoom 必须至少1.5')
    start, end = float(req.get('start') or 0), req.get('end')
    if start < 0 or (end is not None and float(end) <= start):
        raise RequestNotReady('正文时间窗无效')
    # 全称断言：人工请求**不经过草稿**，`build_interview_request` 直接写正式 spec，
    # 所以这道闸要在 build 这一刻（ASR／翻译之前）查，别等 render 前置检查
    # （`check_interview_claims`）才红。`_claims` 写在请求里，`build_spec` 原样带进 spec。
    _tools_on_path()
    from absolute_claims import interview_problem  # noqa: PLC0415
    slug = str(req.get('slug') or '')
    problem = interview_problem(req, slug, where=f'requests/interviews/{slug}.json')
    if problem:
        raise RequestNotReady(problem)
    # （排在全称断言后面：runner 上也是「发布文案前置检查」先、出片那一趟的 check_takeaway 后。）
    # 收尾卡那一句要一行放得下——和 render 的 `check_takeaway`、picker 的预检**同一份
    # 判据**（`interview_spec_gates.takeaway_point_problems`，含豁免表和 `_wrap_ok`）。
    # 原来请求里写长了，要等自动链把它建成 spec、picker 预检报红才知道，多花一整趟循环。
    # 只要 PIL ＋ 仓库里的字体，不下载、不开浏览器。
    if problems := _takeaway_wrap(req):
        raise RequestNotReady('解读卡的字放不下一行：' + '；'.join(problems))
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / 'request'
        base.with_suffix('.json').write_text(json.dumps(req, ensure_ascii=False))
        copy = base.with_suffix('.xhs.txt')
        copy.write_text(str(req.get('xhs') or ''), encoding='utf-8')
        try:
            check_copy(copy, '赛后开麦', quiet=True)
        except subprocess.CalledProcessError as exc:
            # 文案超限（tag > 5、标题 > 20 字位）是**确定性的**请求问题——不改请求每一趟都一样红，
            # 和解读卡、全称断言同一类：`RequestNotReady`，只红这一条、不连坐别的 spec 的
            # 提交和 dispatch（复审 nit：原来抛 CalledProcessError，算 failed、整趟退 1）。
            # 判「判据红」还是「工具崩了」用和 `interview_preflight.copy_problem`／`CRASHED`
            # 同一个办法：输出里有 Traceback 就是崩了，原样往上抛（照旧让 step 红）。
            out = f"{exc.stdout or ''}{exc.stderr or ''}"
            if 'Traceback (most recent call last)' in out:
                sys.stderr.write(out)
                raise
            tail = ' / '.join(out.strip().splitlines()[-3:]) or f'退出码 {exc.returncode}'
            raise RequestNotReady(f'发布文案过不了 push_reel --stage check：{tail}') from exc


def _takeaway_wrap(req: dict) -> list[str]:
    if not req.get('takeaway'):
        return []
    _tools_on_path()
    try:
        from interview_spec_gates import takeaway_point_problems  # noqa: PLC0415
        return takeaway_point_problems(
            {'slug': str(req.get('slug') or ''), 'takeaway': req['takeaway']})
    except (ImportError, OSError) as exc:
        # 判不了要出声，但不在这儿拦：render 的 `check_takeaway` 是同一道闸，照样会跑。
        print(f'[预检] 收尾卡一行放不放得下这次判不了（{type(exc).__name__}: {exc}），'
              '留给 render 那道同样的闸', file=sys.stderr)
        return []


def check_interview_claims(spec_path: Path) -> None:
    """采访线的全称断言要认领两个独立源——和竖版短片、解说片同一份判据。

    来路：这道闸原来只装在竖版短片那条线上（`build_match_reel.validate_spec`），
    采访线一道都没有；2026-09-27 扫出 2 份已发的采访 spec 带着没认领的断言
    （挂在 `absolute_claims.INTERVIEW_LEGACY`）。引号里的话是受访者说的，不算。

    ⚠️ **自动转正的采访 spec 也硬拦，没有竖版短片那种「自动 spec 只报」的分流**——
    那一刀是因为模型写不了 `_claims`，而采访线**没有模型写的文案**：
    `draft_interview_spec` 不写 push/cover/takeaway，`promote_interview_draft` 只填模板
    （模板里没有全称断言，`test_采访线自动转正的模板文案过得了全称断言那道闸` 钉着）。
    人写的文案走两条路，各在自己的入口先查同一道闸，不会走到这儿才红：
    - **人工请求**（`requests/interviews/*.json`）不经过草稿，`build_interview_request`
      直接写正式 spec——`check_request` 在 build 那一刻查，`_claims` 写在请求里、
      `build_spec` 原样带进 spec；
    - **手改过的草稿**（`.draft.json` 里有人补了 push/cover/takeaway）——
      `promote_interview_draft.promote_all` 转正前查，没认领就留草稿。
    哪天草稿开始带模型写的文案，先在 promote 那一关分流。
    """
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    check_interview_spec_claims(spec, spec_path.stem)


def check_interview_spec_claims(spec: dict, slug: str = '') -> None:
    """同一道闸，吃 spec 本身（`slug` 不给就取 `spec["slug"]`）。

    `interview_preflight` 在 dispatch 之前调它——runner「发布文案前置检查」那一步
    先跑 `check_interview_claims`，预检漏了它就是一条假绿：picker 投出去、runner
    第一步就红、stale 规则每 70 分钟再投一次。只要标准库，探针也跑。"""
    _tools_on_path()
    from absolute_claims import interview_problem  # noqa: PLC0415

    problem = interview_problem(spec, slug or str(spec.get('slug') or ''))
    if problem:
        raise SystemExit(problem)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--column', required=True)
    args = ap.parse_args()
    path = Path(args.spec)
    if args.column == '赛场之上' and path.is_file():
        _tools_on_path()
        from winners_ue_gate import require
        require(json.loads(path.read_text(encoding='utf-8')))
    if args.column in {'赛场之上', '网球有故事'} and path.is_file():
        _tools_on_path()
        from production_style import match_footage_problem
        from foreground_audio_gate import require as require_audio_review
        spec = json.loads(path.read_text(encoding='utf-8'))
        if issue := match_footage_problem(spec):
            raise SystemExit(issue)
        require_audio_review(spec)
    if args.column == '赛后开麦' and path.is_file():
        check_interview_claims(path)
        check_taste(json.loads(path.read_text(encoding='utf-8')))
    check_copy(path.with_suffix('.xhs.txt'), args.column)


if __name__ == '__main__':
    main()

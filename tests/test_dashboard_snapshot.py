import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[1] / "tools/build_dashboard_snapshot.py"
SPEC = importlib.util.spec_from_file_location("dashboard_snapshot", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

class DashboardSnapshotTest(unittest.TestCase):
    def test_dashboard_does_not_claim_phone_delivery_from_provider_acceptance(self):
        app = (Path(__file__).parents[1] / "dashboard/app.js").read_text(encoding="utf-8")
        self.assertIn("平台已接收", app)
        self.assertIn("不等于手机送达", app)
        self.assertNotIn("24h 已推送", app)

    def test_snapshot_reconciles_render_qc_push_and_sla(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reel_publish_ledger").mkdir(parents=True)
            (root / "data/reel-dispatch-queue").mkdir(parents=True)
            (root / "specs/reel").mkdir(parents=True)
            (root / "output/2026-08-26/reel/demo").mkdir(parents=True)
            (root / "data/orchestration_state.json").write_text('{"dispatched":{"demo":{}},"last_dispatch_at":"2026-08-26T00:00:00Z"}')
            (root / "specs/reel/demo.json").write_text('{}')
            (root / "output/2026-08-26/reel/demo/render.json").write_text(json.dumps({"qc_attestation_sha256":"abc","production_sla":{"slug":"demo","met":True,"elapsed_seconds":120,"artifact_ready_at":"2026-08-26T01:02:00Z"}}))
            accepted_at = module.datetime.now(module.timezone.utc).isoformat().replace("+00:00", "Z")
            (root / "data/reel_publish_ledger/demo.json").write_text(json.dumps({"slug":"demo","attempts":[{"status":"sent","at":accepted_at,"run":"https://github.com/run/1"}]}))
            with patch.object(module, "github_runs", return_value=[]):
                data = module.build(root, None)
            item = data["content"][0]
            self.assertTrue(all(item[k] for k in ("discovered", "orchestrated", "spec", "rendered", "qc", "pushed")))
            self.assertEqual(item["platform_status"], "accepted")
            self.assertEqual(item["delivery_status"], "unverified")
            self.assertEqual(data["summary"]["accepted_24h"], 1)
            self.assertNotIn("published_24h", data["summary"])
            self.assertEqual(data["summary"]["sla_rate"], 100)

    def test_failed_workflow_drives_red_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/reel-dispatch-queue").mkdir(parents=True)
            (root / "data/orchestration_state.json").write_text('{"dispatched":{}}')
            now = module.datetime.now(module.timezone.utc).isoformat()
            runs = [{"name":"orchestrate","status":"completed","conclusion":"failure","created_at":now,"updated_at":now,"html_url":"https://github.com/run/2"}]
            with patch.object(module, "github_runs", return_value=runs):
                data = module.build(root, None)
            self.assertEqual(data["health"]["status"], "failed")
            self.assertEqual(data["stages"][1]["status"], "failure")

if __name__ == "__main__":
    unittest.main()


# ════════════════════════════════════════════════════════════════════════════
# UI 评审 WP1（2026-09-27）：看板 3.1 表里的 clear_fix 全部落判据。
# 账号所有者同一轮的两个决定：Q9 阻塞推微信（判据在 tests/test_pipeline_health.py）、
# Q10 主题跟随系统（tokens.css 生成，判据在 tests/test_design_tokens.py）。
# ════════════════════════════════════════════════════════════════════════════
import re  # noqa: E402
import sys  # noqa: E402
from datetime import timedelta  # noqa: E402

from tennislive import design_tokens as T  # noqa: E402

ROOT = Path(__file__).parents[1]
DASH = ROOT / "dashboard"
PAGES = ROOT / ".github/workflows/pages.yml"


def _iso(minutes_ago=0):
    at = module.datetime.now(module.timezone.utc) - timedelta(minutes=minutes_ago)
    return at.isoformat().replace("+00:00", "Z")


def _run(wf, minutes_ago, conclusion="success", *, status="completed", rid=None, name=None, title=None):
    rid = rid or abs(hash((wf, minutes_ago, conclusion))) % 10**8
    return {"id": rid, "name": name or wf, "path": f".github/workflows/{wf}.yml",
            "status": status, "conclusion": conclusion if status == "completed" else None,
            "created_at": _iso(minutes_ago + 5), "updated_at": _iso(minutes_ago),
            "html_url": f"https://github.com/o/r/actions/runs/{rid}", "display_title": title or name or wf,
            "event": "workflow_dispatch"}


def _root(tmp_path):
    (tmp_path / "data/reel-dispatch-queue").mkdir(parents=True)
    (tmp_path / "data/orchestration_state.json").write_text('{"dispatched":{}}')
    return tmp_path


def _build(root, runs, **kw):
    with patch.object(module, "github_runs", return_value=runs):
        return module.build(root, None, **kw)


def test_采访产物目录是复数也只出一条_类型是interview(tmp_path):
    """采访的产物目录是复数 `output/interviews/<slug>/`。原来按单数 `interview`
    去认，认不出就落成 reel——同一个 slug 出两条、两条状态还互相矛盾
    （评审截图 live_failed_m390_1：12 个 slug 各重复一次）。"""
    root = _root(tmp_path)
    (root / "data/interview_publish_ledger").mkdir(parents=True)
    (root / "data/interview_publish_ledger/x-y-z.json").write_text(json.dumps(
        {"slug": "x-y-z", "attempts": [{"status": "sent", "at": _iso(5), "run": "https://github.com/run/9"}]}))
    (root / "output/interviews/x-y-z").mkdir(parents=True)
    (root / "output/interviews/x-y-z/render.json").write_text(json.dumps(
        {"qc_attestation_sha256": "a", "production_sla": {"slug": "x-y-z", "met": True}}))
    data = _build(root, [])
    rows = [c for c in data["content"] if c["slug"] == "x-y-z"]
    assert len(rows) == 1, rows
    assert rows[0]["type"] == "interview" and rows[0]["rendered"] and rows[0]["pushed"]


def test_看板不监控自己_pages和本趟run都不算(tmp_path):
    """pages 占了最近 run 的一半，本趟 pages 永远是「运行中」——于是「运行中」
    恒 ≥1、首屏恒报「正在运行」、监控那一格恒蓝（评审截图 live_failed_m390_2）。"""
    root = _root(tmp_path)
    runs = [
        _run("pages", 0, status="in_progress", rid=1),
        _run("pages", 30, "failure", rid=2),               # pages 自己红了也不算流水线阻塞
        _run("pipeline-health", 1, status="in_progress", rid=42),   # 本趟 run 按 id 排除
        _run("match-reel", 20, rid=3),
    ]
    data = _build(root, runs, self_run_id="42")
    assert data["summary"]["active"] == 0
    assert data["health"]["status"] == "healthy", data["health"]
    assert all(w["workflow"] != "pages" for w in data["workflows"])
    monitor = next(s for s in data["stages"] if s["label"] == "监控")
    assert monitor["detail"] != "pages" and monitor["status"] != "running", monitor
    # 反向：不给 self_run_id，那条 pipeline-health 就是真在跑
    assert _build(root, runs)["summary"]["active"] == 1


def test_阶段按工作流文件认_名字和文件名不一样的两条也认得出来(tmp_path):
    """explainer.yml 的 `name:` 是 explainer-video。原来按 `name` 认，解说片失败
    进不了首屏。

    ⚠️ Spec 那一格原来挂的是 probe.yml（`probe-data-sources`）——手动跑的数据源
    覆盖率诊断，不是写 spec 的那一步，它红了微信会报「阻塞：Spec」；真正把 pending
    草稿提升成 spec 的 reel-auto-ready 反而没人盯（复核 FIX ROUND 1 的 nit）。"""
    root = _root(tmp_path)
    (root / "data/explainer_publish_ledger").mkdir(parents=True)
    (root / "data/explainer_publish_ledger/ranking-math.json").write_text('{"slug":"ranking-math","attempts":[]}')
    runs = [_run("reel-auto-ready", 10),
            _run("probe", 3, "failure", name="probe-data-sources"),
            _run("explainer", 5, "failure", name="explainer-video", title="explainer-video · ranking-math")]
    data = _build(root, runs)
    spec = next(s for s in data["stages"] if s["label"] == "Spec")
    assert spec["status"] == "success" and spec["detail"] == "reel-auto-ready"
    assert [b["workflow"] for b in data["health"]["blocked"]] == ["explainer"], "诊断工具红了不是流水线阻塞"
    assert data["health"]["blocked"][0]["slug"] == "ranking-math"


def test_取消的run不算阻塞_也不遮住后面的真失败(tmp_path):
    """cancel-in-progress 的线重渲一版旧 run 就被取消——和
    `pipeline_health.workflow_health`（#573）同一个口径：取消既不算失败，
    也不许把它前面那条真失败盖掉。"""
    root = _root(tmp_path)
    runs = [_run("auto-push-reel", 1, "cancelled"), _run("auto-push-reel", 20),
            _run("match-reel", 1, "cancelled"), _run("match-reel", 9, "failure")]
    data = _build(root, runs)
    assert [b["workflow"] for b in data["health"]["blocked"]] == ["match-reel"]
    push = next(s for s in data["stages"] if s["label"] == "推送")
    assert push["status"] == "success", push
    row = next(w for w in data["workflows"] if w["workflow"] == "auto-push-reel")
    assert (row["status"], row["status_label"]) == ("cancelled", "已取消"), "取消不许标成「失败」"
    # 超过 24 小时的失败不再算阻塞（和原来一样的窗口）
    old = [_run("match-reel", 25 * 60, "failure")]
    assert _build(root, old)["health"]["status"] != "failed"


def test_阻塞列出阶段_卡住的slug和run链接(tmp_path):
    """首屏失败态要说清三件事：哪个阶段、哪条卡住、点哪儿看 run（Q9 推微信用的
    是同一份 `blocked`）。主按钮指向最早那条失败——后面的常常是它的连带。"""
    root = _root(tmp_path)
    (root / "data/reel_publish_ledger").mkdir(parents=True)
    (root / "data/reel_publish_ledger/bu-majchrzak-hangzhou-2026-r2.json").write_text(json.dumps(
        {"slug": "bu-majchrzak-hangzhou-2026-r2", "attempts": [{"status": "sent", "at": _iso(600)}]}))
    runs = [_run("orchestrate", 3, "failure", rid=7),
            _run("match-reel", 8, "failure", rid=8,
                 title="match-reel · render · bu-majchrzak-hangzhou-2026-r2")]
    data = _build(root, runs)
    h = data["health"]
    assert h["status"] == "failed"
    assert [b["workflow"] for b in h["blocked"]] == ["match-reel", "orchestrate"], "最早的排前"
    assert h["action_url"].endswith("/8")
    assert h["blocked"][0]["stages"] == ["渲染", "质检"]
    assert h["blocked"][0]["slug"] == "bu-majchrzak-hangzhou-2026-r2"
    assert h["blocked"][1]["slug"] is None, "run 标题里没写就是 None，不猜"
    assert "渲染" in h["message"] and "编排" in h["message"]
    item = next(c for c in data["content"] if c["slug"] == "bu-majchrzak-hangzhou-2026-r2")
    assert item["failed_stage"] == "rendered"
    render = next(s for s in data["stages"] if s["label"] == "渲染")
    assert render["status"] == "failure" and render["url"].endswith("/8")


def test_slug只认run标题里真写了的_不猜():
    slug_of = module.slug_of
    assert slug_of("match-reel · render · bu-majchrzak-hangzhou-2026-r2") == "bu-majchrzak-hangzhou-2026-r2"
    assert slug_of("auto-push-reel") is None, "三段的工作流名不是 slug"
    assert slug_of("interview-auto-render") is None
    assert slug_of("赛后开麦 alcaraz-fritz：剪掉片尾板") is None, "两段的短名不够格"
    assert slug_of("x a-b-c-d a-b-c", known={"a-b-c"}) == "a-b-c", "仓库里真有的 slug 优先"
    assert slug_of("explainer-video · ranking-math", known={"ranking-math"}) == "ranking-math", \
        "两段的真 slug 认得出来（仓库里有）"
    assert slug_of("probe-data-sources", exclude={"probe-data-sources"}) is None, "工作流的 name 不是 slug"


def test_卡片标题读cover_topic_同名spec按栏目认(tmp_path):
    """卡片主行原来是 slug。同一个 stem 在 reels/ 和 interviews/ 各有一份是常态
    （同一场球两条线），标题只认自己这条线的。"""
    root = _root(tmp_path)
    for kind in ("reel", "interview"):
        (root / f"data/{kind}_publish_ledger").mkdir(parents=True)
        (root / f"data/{kind}_publish_ledger/a-b-c.json").write_text('{"slug":"a-b-c","attempts":[]}')
    (root / "specs/reels").mkdir(parents=True)
    (root / "specs/interviews").mkdir(parents=True)
    (root / "specs/reels/a-b-c.json").write_text(json.dumps({"cover": {"topic": "ATP250 杭州 第二轮 · 甲 VS 乙"}}))
    (root / "specs/interviews/a-b-c.json").write_text(json.dumps({"cover": {"title": ["钩子一", "钩子二"]}}))
    data = _build(root, [])
    titles = {c["type"]: c["title"] for c in data["content"]}
    assert titles == {"reel": "ATP250 杭州 第二轮 · 甲 VS 乙", "interview": "钩子一 钩子二"}
    app = (DASH / "app.js").read_text(encoding="utf-8")
    assert "x.title || x.slug" in app, "页面要先用标题，没有才退回 slug"


def test_没有成片数据时达标率是空_页面显示破折号(tmp_path):
    data = _build(_root(tmp_path), [])
    assert data["summary"]["sla_rate"] is None, "没有样本是「不知道」，不是 0%"
    app = (DASH / "app.js").read_text(encoding="utf-8")
    assert "s.sla_rate != null" in app and '"—"' in app


def test_自动任务每个工作流只留最新一条_失败排前面(tmp_path):
    root = _root(tmp_path)
    runs = [_run("match-reel", 1, status="in_progress", rid=11), _run("match-reel", 5, rid=12),
            _run("match-reel", 9, rid=13), _run("orchestrate", 30, "failure"), _run("reel-auto-ready", 0)]
    rows = _build(root, runs)["workflows"]
    assert [r["workflow"] for r in rows] == ["orchestrate", "match-reel", "reel-auto-ready"], rows
    reel = rows[1]
    assert reel["status"] == "running" and reel["url"].endswith("/11"), "要的是最新那一条"


# ── 前端静态判据 ───────────────────────────────────────────────────────────
def _css():
    return (DASH / "styles.css").read_text(encoding="utf-8")


def _css_no_comments():
    return re.sub(r"/\*.*?\*/", "", _css(), flags=re.S)


def _blocks(css, at_rule):
    """某个 @media 块的正文（花括号配平）。"""
    out = []
    for m in re.finditer(re.escape(at_rule) + r"\s*\{", css):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[m.end():i - 1])
    return out


def test_页面没有空锚点_没链接就渲div():
    """阶段卡原来 `href="${s.url || '#'}"`——没有 URL 也是个链接，点了跳回页首，
    还带着浏览器默认的紫色下划线（评审截图 detail_stages_d1280）。"""
    app = (DASH / "app.js").read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", app)
    assert not re.search(r"""['"]#['"]""", code), "还有指向 # 的兜底链接"
    assert "linkOrDiv(s.url" in code and "linkOrDiv(x.url" in code and "linkOrDiv(w.url" in code
    assert ": `<div class=" in code, "没有 URL 时要渲 <div>"
    css = _css_no_comments()
    for sel in (".stage {", ".row {", ".fail-item {"):
        body = css.split(sel, 1)[1].split("}", 1)[0]
        assert "color: inherit" in body and "text-decoration: none" in body, sel


def test_样式字阶不小于12_字重只用400_500_600_数字等宽():
    css = _css_no_comments()
    px = [int(v) for v in re.findall(r"font-size:\s*(\d+)px", css)]
    assert all(v >= 12 for v in px), px
    used = re.findall(r"font-size:\s*var\((--tl-text-[\w-]+)\)", css)
    assert used, "判据失效：一个 token 字号都没扫到"
    for name in used:
        assert T.TEXT_WEB[name.removeprefix("--tl-text-")] >= 12, name
    assert min(T.TEXT_WEB.values()) >= 12
    weights = set(re.findall(r"font-weight:\s*(\w+)", css))
    assert weights and weights <= {"400", "500", "600"}, weights
    body = css.split("body {", 1)[1].split("}", 1)[0]
    assert "font-variant-numeric: tabular-nums" in body


def test_hover只写在指针设备里_按压97_不写transition_all():
    css = _css_no_comments()
    hover_media = "@media (hover: hover) and (pointer: fine)"
    inside = "".join(_blocks(css, hover_media))
    assert ":hover" in inside, "判据失效：hover 块里一条都没有"
    outside = css
    for block in _blocks(css, hover_media):
        outside = outside.replace(block, "")
    assert ":hover" not in outside, "有 :hover 写在了指针设备媒体查询外面（触屏上会粘住）"
    assert not re.search(r"transition:\s*all\b", css)
    assert "transform: scale(.97)" in css and "var(--tl-duration-press)" in css
    assert ":focus-visible" in css and "var(--tl-ring)" in css


def test_运行中的点用光环扩散_减少动态时扫光和光环都停():
    css = _css_no_comments()
    ring = css.split("@keyframes tl-ring", 1)[1].split("}", 2)[:2]
    assert "transform: scale(" in "".join(ring), "光环要靠 transform 扩散"
    assert "@keyframes pulse" not in css
    dot_rule = css.split('.dot[data-status="running"] {', 1)[1].split("}", 1)[0]
    assert "animation" not in dot_rule, "点本身不许呼吸变淡（原来淡到 40%，2.39:1）"
    reduced = "".join(_blocks(css, "@media (prefers-reduced-motion: reduce)"))
    assert ".sk" in reduced and ".dot::after" in reduced and "animation: none" in reduced
    assert "transition: none" in reduced
    assert "animation: tl-shimmer" in css, "骨架屏要有扫光"
    html = (DASH / "index.html").read_text(encoding="utf-8")
    assert html.count('class="sk') + html.count("sk-block") >= 6, "骨架占位要预渲在 HTML 里"


def test_样式只用tl变量且浅深两套主题都定义了():
    """styles.css 只写 var(--tl-…)，而且每一个都要在浅、深两套里都有——
    只在深色里定义的画布角色（hero-glow / fill / chart-*）在浅色下会是空的。"""
    css = _css_no_comments()
    assert not re.search(r"^\s*--[\w-]+\s*:", css, re.M), "看板不再自己定义变量"
    used = set(re.findall(r"var\((--[\w-]+)", css))
    assert used and all(v.startswith("--tl-") for v in used), sorted(used)
    tokens = (DASH / "tokens.css").read_text(encoding="utf-8")
    base = tokens.split(':root[data-theme="dark"]', 1)[0]
    dark = tokens.split(':root[data-theme="dark"]', 1)[1].split("}", 1)[0]
    light = tokens.split(':root[data-theme="light"]', 1)[1].split("}", 1)[0]
    for v in sorted(used):
        assert f"{v}:" in base or (f"{v}:" in dark and f"{v}:" in light), f"{v} 不是两套主题都有"


def test_看板品牌与主题跟着token走():
    html = (DASH / "index.html").read_text(encoding="utf-8")
    assert "TENNIS JETLAG · 流水线" in html and "TIMEZONE" not in html
    assert 'rel="icon"' in html and 'rel="apple-touch-icon"' in html
    assert html.index("tokens.css") < html.index("styles.css"), "token 要先于样式加载"
    metas = dict(re.findall(
        r'<meta name="theme-color" media="\(prefers-color-scheme: (\w+)\)" content="(#[0-9a-f]{6})">', html))
    assert metas == {"light": T.LIGHT["background"], "dark": T.DARK["background"]}, metas
    assert '<meta name="color-scheme" content="light dark">' in html


def test_分段控件有aria_pressed_筛选不重建按钮():
    html = (DASH / "index.html").read_text(encoding="utf-8")
    seg = html.split('id="filters"', 1)[1].split("</div>", 1)[0]
    assert seg.count("aria-pressed") == 4 and 'aria-pressed="true"' in seg
    app = (DASH / "app.js").read_text(encoding="utf-8")
    assert '$("filters").innerHTML' not in app, "重建按钮会把键盘焦点丢掉"
    assert 'setAttribute("aria-pressed"' in app
    css = _css_no_comments()
    seg_css = css.split(".segmented {", 1)[1].split("}", 1)[0]
    assert "height: 40px" in seg_css


def test_刷新失败保留上次状态并标过期():
    app = (DASH / "app.js").read_text(encoding="utf-8")
    catch = app.split("} catch (error) {", 1)[1].split("}", 1)[0]
    assert "if (snapshot) markStale(error)" in catch, "有旧数据时只能标过期，不许抹掉"
    stale = app.split("function markStale(error) {", 1)[1].split("\n}", 1)[0]
    assert "render(snapshot)" in stale, "过期时要按缓存快照重渲，相对时间不许冻住"
    assert "data-retry" in app and "data-retry" in (DASH / "index.html").read_text(encoding="utf-8")


def _pages_run_script():
    import yaml  # noqa: PLC0415

    spec = yaml.safe_load(PAGES.read_text(encoding="utf-8"))
    steps = spec["jobs"]["deploy"]["steps"]
    return spec, steps


def test_看板页面引用的本地文件pages都拷过去了():
    """index.html 引用的每个本地文件（tokens.css、图标……）都要被 pages.yml 拷进
    `_site/dashboard/`，源文件还得在稀疏检出里——少一样线上就是 404，本地看不出来。"""
    html = (DASH / "index.html").read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r'(?:href|src)="\./([^"]+)"', html)))
    assert {"tokens.css", "styles.css", "app.js", "favicon.png", "icon-180.png"} <= set(refs), refs
    _, steps = _pages_run_script()
    copy = next(s["run"] for s in steps if "cp dashboard/" in (s.get("run") or ""))
    sparse = next(s["with"]["sparse-checkout"] for s in steps if "sparse-checkout" in (s.get("with") or {}))
    lines = [ln for ln in copy.splitlines() if ln.strip().startswith("cp ") and "_site/dashboard" in ln]
    copied = {}
    for ln in lines:
        for src in ln.split()[1:-1]:
            copied[Path(src).name] = src
    for ref in refs:
        assert ref in copied, f"pages.yml 没把 {ref} 拷进 _site/dashboard/"
        src = copied[ref]
        assert (ROOT / src).is_file(), src
        assert src.startswith("dashboard/") or src in sparse.split(), f"{src} 不在稀疏检出里"


def test_pages把本趟run_id交给快照():
    _, steps = _pages_run_script()
    build = next(s["run"] for s in steps if "build_dashboard_snapshot.py" in (s.get("run") or ""))
    assert '--self-run-id "$GITHUB_RUN_ID"' in build


def test_看板阶段表点名的工作流文件都存在_pages按名字订阅它们():
    """`workflow_run.workflows` 认的是 `name:`。原来写成文件名 `explainer`，
    而它的名字是 explainer-video——跑完从来没触发过部署。"""
    import yaml  # noqa: PLC0415

    def name_of(stem):
        spec = yaml.safe_load((ROOT / f".github/workflows/{stem}.yml").read_text(encoding="utf-8"))
        return spec["name"]

    spec, _ = _pages_run_script()
    subscribed = spec[True]["workflow_run"]["workflows"]  # yaml 把 on: 读成 True
    names = {p.stem: name_of(p.stem) for p in (ROOT / ".github/workflows").glob("*.yml")}
    assert set(subscribed) <= set(names.values()), sorted(set(subscribed) - set(names.values()))
    for stem in sorted(module.MONITORED):
        assert stem in names, f"阶段表点名了不存在的工作流文件 {stem}.yml"
        assert names[stem] in subscribed, f"{stem}.yml（name: {names[stem]}）跑完不会触发看板重建"
    assert "explainer" in module.MONITORED and names["explainer"] == "explainer-video", \
        "判据失效：这条本来就是为名字≠文件名写的"
    assert {"reel-auto-ready", "interview-clip"} <= module.MONITORED, \
        "Spec 那一格盯提升草稿的 reel-auto-ready；手动拨的采访片出片线红了也要进阻塞"
    assert "probe" not in module.MONITORED, "probe.yml 是手动的数据源诊断，它红了不是「阻塞：Spec」"


# ── 真渲一遍：阻塞态、窄屏失败排前、刷新失败保留、筛选保焦点 ──────────────
def test_看板真渲出来_阻塞态_窄屏失败排前_刷新失败保留(tmp_path):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    from tennislive.chromium import launch_chromium  # noqa: PLC0415

    root = _root(tmp_path)
    runs = [_run("match-reel", 8, "failure", rid=8, title="match-reel · render · bu-majchrzak-hangzhou-2026-r2"),
            _run("orchestrate", 30), _run("pipeline-health", 12)]
    snap = {"body": json.dumps(_build(root, runs), ensure_ascii=False).encode()}
    files = {p.name: p for p in DASH.glob("*") if p.suffix in (".html", ".css", ".js")}
    files["favicon.png"] = ROOT / "assets/logo/brand/favicon.png"
    files["icon-180.png"] = ROOT / "assets/logo/brand/icon-180.png"
    types = {".html": "text/html", ".css": "text/css", ".js": "application/javascript", ".png": "image/png"}

    def handle(route):
        name = route.request.url.split("?")[0].rsplit("/", 1)[-1]
        if name == "snapshot.json":
            if snap["body"] is None:
                return route.fulfill(status=500, body="boom")
            return route.fulfill(status=200, body=snap["body"], content_type="application/json")
        if name in files:
            return route.fulfill(status=200, body=files[name].read_bytes(),
                                 content_type=types[files[name].suffix])
        return route.fulfill(status=404, body="")

    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.route("https://dash.local/**", handle)
        page.goto("https://dash.local/dashboard/index.html")
        page.wait_for_selector('#hero[data-status="failed"]')
        assert page.eval_on_selector("#hero .btn-primary", "a => a.href").endswith("/8")
        assert "bu-majchrzak-hangzhou-2026-r2" in page.inner_text("#hero")
        # 390 宽下卡住的 slug 要整条看得见：折行，不许被省略号吃掉（复核 failed_themes_m390）
        assert page.eval_on_selector(".fail-slug", "e => e.scrollWidth <= e.clientWidth"), "slug 被截断了"
        assert page.eval_on_selector_all('a[href="#"]', "xs => xs.length") == 0
        # 窄屏：阶段是竖向列表，失败的排最前
        tops = page.eval_on_selector_all(
            "#stages .stage", "xs => xs.map(x => [x.dataset.status, x.getBoundingClientRect().top])")
        assert len({round(t[1]) for t in tops}) == len(tops), "窄屏要竖排，不是横向滚动"
        assert min(tops, key=lambda t: t[1])[0] == "failure", tops
        # 最小字号 12
        small = page.evaluate("""() => [...document.querySelectorAll('body *')]
            .filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
            .filter(e => e.getClientRects().length)
            .map(e => parseFloat(getComputedStyle(e).fontSize)).filter(v => v < 12)""")
        assert small == [], small
        # 筛选：aria-pressed 跟着走，焦点留在按下的那一个上
        page.focus('#filters button[data-type="interview"]')
        page.keyboard.press("Enter")
        assert page.get_attribute('#filters button[data-type="interview"]', "aria-pressed") == "true"
        assert page.evaluate("document.activeElement.dataset.type") == "interview"
        # 刷新失败：阻塞态原样留着，标过期、给重试
        snap["body"] = None
        # 刷新失败也要按缓存快照重渲：相对时间不许冻在上一次渲染的那一刻（复核 refreshfail_m390）
        page.evaluate("document.querySelector('#hero .stamp').dataset.probe = 'old'")
        page.click("#refresh")
        page.wait_for_selector("#stale:not([hidden])", timeout=5000)
        assert page.eval_on_selector("#hero .stamp", "e => e.dataset.probe || ''") == "", "过期时没重渲"
        assert page.get_attribute("#hero", "data-status") == "failed"
        assert "is-stale" in page.get_attribute("#freshness", "class")
        assert page.is_visible("#stale [data-retry]")
        browser.close()


def test_手动拨的出片工作流run标题带slug():
    """「哪条卡住」只能从 run 标题里读——REST 的 run 对象不带 dispatch 输入。
    原来手动拨的 match-reel 标题就是一个 `match-reel`，看板和阻塞微信（Q9）
    都只能说「run 标题里没写是哪条」。凡是被监控、只由 workflow_dispatch 触发、
    带 `slug` 输入的工作流，`run-name` 都要带上 `inputs.slug`（推导，不维护名单）。"""
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tools"))
    import pipeline_health  # noqa: PLC0415

    watched = set(module.MONITORED) | {w.removesuffix(".yml") for w in pipeline_health.DEFAULT_WORKFLOWS}
    checked = []
    for stem in sorted(watched):
        spec = yaml.safe_load((ROOT / f".github/workflows/{stem}.yml").read_text(encoding="utf-8"))
        on = spec[True]
        if not isinstance(on, dict) or set(on) != {"workflow_dispatch"}:
            continue
        if "slug" not in ((on["workflow_dispatch"] or {}).get("inputs") or {}):
            continue
        checked.append(stem)
        assert "inputs.slug" in str(spec.get("run-name") or ""), f"{stem}.yml 的 run 标题里没有 slug"
    assert {"match-reel", "explainer", "interview-clip"} <= set(checked), checked


# ── FIX ROUND 1：两段的 slug、mode 决定阶段 ─────────────────────────────────
def test_出片run按run_name段位读slug_两段的也认得出_mode决定阶段(tmp_path):
    """复核量出来：`pipeline_health` 调 `blocked_runs(runs)` 不给 `known`，而
    `slug_of` 的启发式只认三段以上的连字符词——自动链的 pending 草稿 126 条里
    114 条、reel spec 305 条里 144 条、解说片账本 15 份里 7 份是两段的
    （`zverev-sonego`、`ranking-math`），于是微信摘要照样说「run 标题里没写是哪条」，
    而 run-name 明明写了。出片那三条的标题是我们写死的，按段位读，不猜。
    同一个标题里的 mode 决定阶段：match-reel 的 probe 红了是 Spec 卡住。"""
    runs = [_run("match-reel", 8, "failure", rid=8, title="match-reel · probe · zverev-sonego"),
            _run("explainer", 6, "failure", rid=6, name="explainer-video",
                 title="explainer-video · ranking-math"),
            _run("interview-clip", 4, "failure", rid=4, title="interview-clip · render · eala-zheng"),
            _run("auto-push-reel", 2, "failure", rid=2, title="reel: 预占推送 alcaraz-fritz")]
    got = {b["workflow"]: b for b in module.blocked_runs(runs)}  # 不给 known：pipeline_health 就是这么调的
    assert (got["match-reel"]["slug"], got["match-reel"]["mode"], got["match-reel"]["stages"]) == \
        ("zverev-sonego", "probe", ["Spec"])
    assert (got["explainer"]["slug"], got["explainer"]["stages"]) == ("ranking-math", ["渲染", "质检"])
    assert (got["interview-clip"]["slug"], got["interview-clip"]["stages"]) == ("eala-zheng", ["渲染", "质检"])
    assert got["auto-push-reel"]["slug"] is None, "不是我们写死的 run-name：照旧不猜两段的短名"
    # 单段的老解说片 slug 也认（hawkeye / roof）；改 run-name 之前的老标题切不出东西
    one = _run("explainer", 1, "failure", name="explainer-video", title="explainer-video · hawkeye")
    assert module.blocked_runs([one])[0]["slug"] == "hawkeye"
    old = _run("match-reel", 1, "failure", title="match-reel")
    assert module.blocked_runs([old])[0]["slug"] is None
    assert module.blocked_runs([old])[0]["stages"] == ["渲染", "质检"], "认不出 mode 退回默认阶段"
    # 段数不对、首段不是 name、slug 段不像 slug：都不认
    for title in ("match-reel · zverev-sonego", "other · probe · zverev-sonego",
                  "match-reel · probe · Zverev Sonego"):
        assert module.run_name_fields(_run("match-reel", 1, "failure", title=title)).get("slug") is None, title
    # 看板首屏：probe 红了是 Spec 那一格红，渲染那一格不跟着红
    data = _build(_root(tmp_path), runs[:1] + [_run("match-reel", 30, rid=30, title="match-reel · render · a-b")])
    stage = {s["label"]: s for s in data["stages"]}
    assert stage["Spec"]["status"] == "failure" and stage["Spec"]["slug"] == "zverev-sonego"
    assert stage["渲染"]["status"] == "success", stage["渲染"]


def test_run标题的段位表和工作流里写的run_name对得上():
    """`RUN_NAME_FIELDS` 和 yml 里的 `run-name` 是同一件事的两处写法——改了一边
    不改另一边，段位就读错位（把 mode 当成 slug）。每个 mode 选项也都要认得出阶段。"""
    import yaml  # noqa: PLC0415

    for stem, fields in module.RUN_NAME_FIELDS.items():
        spec = yaml.safe_load((ROOT / f".github/workflows/{stem}.yml").read_text(encoding="utf-8"))
        parts = str(spec["run-name"]).split(" · ")
        assert parts[0] == spec["name"], f"{stem}.yml 的 run-name 第一段要是 name"
        assert len(parts) == 1 + len(fields), f"{stem}.yml 的 run-name 段数和 RUN_NAME_FIELDS 对不上"
        for field, part in zip(fields, parts[1:]):
            assert f"inputs.{field}" in part, f"{stem}.yml run-name 第 {fields.index(field) + 2} 段不是 {field}"
        inputs = spec[True]["workflow_dispatch"]["inputs"]
        for mode in (inputs.get("mode") or {}).get("options") or []:
            assert mode in module.MODE_STAGES, f"{stem}.yml 的 mode={mode} 红了不知道算哪个阶段"
    labels = {label for label, _ in module.WORKFLOW_GROUPS}
    assert all(set(v) <= labels for v in module.MODE_STAGES.values())

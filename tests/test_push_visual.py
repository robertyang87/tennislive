"""微信推送正文和复制页的视觉判据——UI / VI 评审 3.2（WP2）。

来路（2026-09-27 评审量出来的，截图在那轮 scratchpad 的 `ui/push-and-copy-pages/`）：

- 推送正文和复制页之间 22 个 hex，**一个都没共享**；提示灰 #7a8580 白底只有 3.82:1
- 复制失败也弹「已复制」；连点两次第二条 toast 只停约 400ms；深色 toast 和页面底 1.00:1
- 「网球有故事」两条产线推出来长得不一样（药丸、标题提示行、按钮文案）
- 复制按钮 42px、回退链接 15px 高；推送片段没有 `lang`，全角逗号字形出错；图片不留高度
- 账号所有者 Q8：浅底上药丸和按钮**黄绿实底 + 墨色字**，链接**中性灰**
- ⚠️⚠️ **红按钮 #ff2442 逐字节不动**（账号所有者 2026-08-31「微信推送的红色按钮不要改了」）

这份文件钉：① 红按钮两处产出和金样逐字节相等；② 推送只用浅色 token、Q8 的角色分工；
③ 两条「网球有故事」推送同一套样子；④ 整块可选、`lang`、图片预留比例、回退链接；
⑤ 字卡推送的 2 万字预算没被样式挤掉；⑥ 复制页样式只写 token 变量；
⑦ 复制页在 Chromium 里真的：失败说失败、连点重新计时、深色 toast 看得见、按钮 44px、有焦点环。
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import sys
from fractions import Fraction
from pathlib import Path

from tennislive import design_tokens as T
from tennislive.render import push_style as ps
from tennislive.render.knowledge import knowledge_push_html_from_parts
from tennislive.render.pushmsg import copy_page_fingerprint, to_copy_page

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import push_reel  # noqa: E402

COPY = "https://p.invalid/output/2026-09-26/copy.html"
VIDEO = "https://v.invalid/explainer.mp4"
POSTER = "https://gcore.jsdelivr.net/gh/o/r@main/output/2026-09-26/reel/x/poster.jpg"
STAT = "https://gcore.jsdelivr.net/gh/o/r@main/output/2026-09-26/reel/x/stat_card.jpg"
XHS = "9.26 网球有故事 | 标题一行\n\n正文第一段。\n\n正文第二段，带一个数 7-6(4)。\n\n#网球时差"


def _reel(column: str = "赛场之上", *, stat: bool = True) -> str:
    return push_reel.build_html(VIDEO, COPY, "", XHS, POSTER, column,
                                stat_card=STAT if stat else "")


def _slides(n: int = 3) -> list[str]:
    return [f"https://gcore.jsdelivr.net/gh/o/r@main/output/2026-09-26/explainer/x/slide_{i:02d}.jpg"
            for i in range(n)]


def _knowledge(n: int = 3) -> str:
    return knowledge_push_html_from_parts(image_urls=_slides(n), xhs_text=XHS,
                                          copy_url=COPY, video_url=VIDEO)


def _explainer(tmp_path: Path, n: int = 3) -> str:
    """走真调用方 `explainer_push_html`——药丸和按钮文字原来就是从它那儿传进去才分叉的。"""
    from tennislive.video.explainer import explainer_push_html

    outdir = tmp_path / "output/2026-09-26/explainer/x"
    outdir.mkdir(parents=True)
    return explainer_push_html([None] * n, outdir, date=_dt.date(2026, 9, 26),
                               xhs_text=XHS, copy_url=COPY)


# ── ① 红按钮 ──────────────────────────────────────────────────────────────
#: 两处红按钮的金样，取自改动之前两个函数的真产出（2026-09-27，wp/ui-tokens-2 @432891c2）。
#: ⚠️ 两份**本来就差一个分号**（`margin:0 0 7px` 后面知识帖那份多一个 `;`）——那也不动。
_RED_REEL = ('<a href="{u}" style="display:block;background-color:#ff2442;color:#ffffff;'
             'text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;'
             'border-radius:6px;margin:0 0 7px">分别复制标题 / 正文</a>')
_RED_KNOWLEDGE = ('<a href="{u}" style="display:block;background-color:#ff2442;color:#ffffff;'
                  'text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;'
                  'border-radius:6px;margin:0 0 7px;">分别复制标题 / 正文 / 置顶评论</a>')


def _red(body: str) -> str:
    m = re.search(rf'<a href="{re.escape(COPY)}"[^>]*>.*?</a>', body, re.S)
    assert m, "推送里找不到复制页那颗按钮"
    return m.group(0)


def test_推送红按钮逐字节不动_两处产出都钉金样(tmp_path):
    """账号所有者 2026-08-31：「微信推送的红色按钮不要改了」。这一轮把推送的颜色全换成
    token、按钮换成黄绿——**唯独这一颗一个字节都不许动**，两处产出都拿真函数渲、
    和改之前的金样逐字节比（不比「包含 #ff2442」——改了圆角、字重、文案都照样包含）。"""
    for body in (_reel(), _reel("赛后开麦", stat=False), _reel("网球有故事")):
        assert _red(body) == _RED_REEL.format(u=COPY)
    for body in (_knowledge(), _explainer(tmp_path)):
        assert _red(body) == _RED_KNOWLEDGE.format(u=COPY)
    # 卡片顶上那条 5px 红边是同一支红（参照那条知识解说推送），也还在
    for body in (_reel(), _knowledge()):
        assert "border-top:5px solid #ff2442" in body


# ── ② 一套浅色 token，Q8 的角色分工 ────────────────────────────────────────
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def test_推送正文只用浅色token一套色():
    """推送是 PushPlus 那一页里的内联样式——只有浅色，所以每个颜色都得是 `LIGHT`
    里的某个角色（红按钮／红边那一支除外）。原来这里有 #e7f5ea / #087747 / #7a8580 /
    #102d23 / #25342e 五支各配各的，**提示灰 #7a8580 白底只有 3.82:1**。"""
    allowed = {v.lower() for v in T.LIGHT.values()} | {"#ff2442", "#ffffff"}
    for body in (_reel(), _knowledge()):
        used = {h.lower() for h in _HEX.findall(body)}
        stray = used - allowed
        assert not stray, f"推送里有不属于浅色 token 的颜色：{sorted(stray)}"
        assert not re.search(r"(?i)\b(rgba?|hsla?)\(", body), "推送里有字面的颜色函数"
        assert "#7a8580" not in body, "提示灰还是 3.82:1 的那支"


def _style_of(body: str, text: str, tag: str = "div") -> str:
    m = re.search(rf'<{tag}(?: href="[^"]*")? style="([^"]*)">{re.escape(text)}</{tag}>', body)
    assert m, f"找不到「{text}」那个 <{tag}>"
    return m.group(1)


def _prop(style: str, name: str) -> str:
    m = re.search(rf"(?:^|;){re.escape(name)}:([^;]+)", style)
    return m.group(1).strip() if m else ""


def test_Q8药丸和按钮是黄绿实底墨色字_链接和提示是中性灰():
    """账号所有者 2026-09-27 Q8：「药丸和按钮用黄绿实底 + 墨色字；链接用中性灰」。
    黄绿 #c6f65a 白底只有 1.26:1——**永远不当字色**，只当底。"""
    L = T.LIGHT
    for body, column in ((_reel(), "赛场之上"), (_knowledge(), "网球有故事")):
        for style in (_style_of(body, column), _style_of(body, ps.VIDEO_BUTTON_TEXT, "a")):
            assert _prop(style, "background-color") == L["primary"], style
            assert _prop(style, "color") == L["primary-foreground"], style
            assert T.contrast(L["primary"], L["primary-foreground"]) >= 7
        for link in re.findall(r'<a href="[^"]*" style="([^"]*)">原图 ↗</a>', body):
            assert _prop(link, "color") == L["link"] == L["muted-foreground"], link
        for hint in (ps.TITLE_HINT_TEXT, ps.BODY_HINT_TEXT):
            assert _prop(_style_of(body, hint), "color") == L["muted-foreground"]
        assert L["primary"] not in {_prop(s, "color") for s in re.findall(r'style="([^"]*)"', body)}, (
            "黄绿被当成了字色（白底 1.26:1）")


# ── ③ 两条「网球有故事」推送同一套样子 ─────────────────────────────────────
def test_两条网球有故事推送长得一样_药丸是栏目名_有标题提示行_按钮文案一致(tmp_path):
    """同一栏目的剪辑片（`push_reel.build_html`）和字卡（`explainer_push_html` →
    `knowledge_push_html_from_parts`）原来一个写「网球有故事」、一个写「知识解说视频 · 9.26」；
    一个有「☝️ 标题，长按这一行即可复制」、一个没有；按钮一个「▶ 打开竖版成片」、一个
    「▶ 打开 9:16 成片」。**判据比的是两份真产出里那几个元素的样式和文字，不比源码**。"""
    clip, deck = _reel("网球有故事", stat=False), _explainer(tmp_path)
    assert _style_of(clip, "网球有故事") == _style_of(deck, "网球有故事")
    assert _style_of(clip, ps.TITLE_HINT_TEXT) == _style_of(deck, ps.TITLE_HINT_TEXT)
    btn = re.compile(r'<a href="[^"]*" style="([^"]*)">(▶[^<]*)</a>')
    assert btn.findall(clip) == btn.findall(deck) == [(ps.VIDEO_BUTTON, "▶ 打开竖版成片")]
    for gone in ("知识解说视频", "9:16 成片", "· 9.26</div>"):
        assert gone not in deck, f"字卡推送里还有老样子：{gone}"
    # 标题提示行紧跟在大标题下面（复制页打不开时标题的出口），两条都是
    for body in (clip, deck):
        after_title = body.split("9.26 网球有故事 | 标题一行", 1)[1]
        assert after_title.index(ps.TITLE_HINT_TEXT) < 200


# ── ④ 整块可选、lang、图片预留比例、回退链接 ─────────────────────────────
def test_推送标题正文整块可选_片段声明中文():
    """在推送里复制正文原来要手指拖着选一千字；`user-select:all` 让长按一下选中整段。
    片段没有 `lang` 时全角逗号按西文字形排（评审 `zoom_punct_push_vs_copy.jpg`）。"""
    for body in (_reel(), _knowledge()):
        assert body.startswith('<div lang="zh-CN" '), body[:60]
        title = _style_of(body, "9.26 网球有故事 | 标题一行")
        text = re.search(r'<div style="([^"]*)">正文第一段', body).group(1)
        for style in (title, text):
            assert "user-select:all" in style and "-webkit-user-select:all" in style, style


def _img_ratios(body: str) -> list[tuple[int, int]]:
    return [(int(w), int(h)) for w, h in
            re.findall(r"<img [^>]*aspect-ratio:auto (\d+)/(\d+)", body)]


def test_推送图片预留的比例和出图的画布对得上():
    """`aspect-ratio` 让图没下完时先占住高度，页面不跳。写成 `auto w/h`：比例万一
    对不上也按图自己的比例排、不会压扁——但预留得不对，下完还是会跳，所以比例要和
    出图模块的画布常量对得上。"""
    import render_stat_card  # noqa: PLC0415
    import versus_poster  # noqa: PLC0415
    from tennislive.video import explainer  # noqa: PLC0415

    assert Fraction(*ps.POSTER_RATIO) == Fraction(versus_poster.VIDEO_W, versus_poster.VIDEO_H)
    assert Fraction(*ps.STAT_CARD_RATIO) == Fraction(render_stat_card.W, render_stat_card.H)
    assert render_stat_card.VARIANTS["poster"] == (render_stat_card.W, render_stat_card.H)
    assert Fraction(*ps.SLIDE_RATIO) == Fraction(explainer.W, explainer.H)

    assert _img_ratios(_reel()) == [ps.POSTER_RATIO, ps.STAT_CARD_RATIO]
    assert _img_ratios(_knowledge(4)) == [ps.SLIDE_RATIO] * 4
    for body in (_reel(), _knowledge()):
        assert len(_img_ratios(body)) == body.count("<img "), "有图没预留比例"


def test_图下回退链接是灰色原图_点击区40px():
    """原来是一行 13px 的绿字「封面没显示？点此打开原图」，只有 15px 高；字卡推送每张图
    挂一条，满屏绿链接。现在每张图下面一条灰色「原图 ↗」，行高 40px（次要操作 ≥40）。
    （真渲出来量高度的那一半在 `test_复制页和推送在浏览器里真的量得到` 里。）"""
    for body, n in ((_reel(), 2), (_knowledge(4), 4)):
        links = re.findall(r'<a href="([^"]*)" style="([^"]*)">原图 ↗</a>', body)
        imgs = re.findall(r'<img src="([^"]*)"', body)
        assert [u for u, _ in links] == imgs and len(imgs) == n, "每张图下面一条，指向它自己"
        for _, style in links:
            assert _prop(style, "display") == "inline-block" and _prop(style, "line-height") == "40px"
        for old in ("点此打开原图", "没显示？", "未显示？"):
            assert old not in body


def test_数据图小标题不贴着正文最后一行():
    """「📊 数据统计对照」原来离正文最后一行（#话题）只有 4px（正文底边距 4 和小标题
    上边距 4 折叠成一个），读着像正文的一部分（评审 3.2，`reel_push.light.part1.jpg`）。
    现在上边距 20，和复制页 `section` 的间距一样。（真渲出来量距离的那一半在
    `test_复制页和推送在浏览器里真的量得到` 里。）"""
    body = _reel()
    m = re.search(r'<div style="([^"]*)"><div style="[^"]*">📊 数据统计对照</div></div>', body)
    assert m, "找不到数据图的小标题"
    top = int(_prop(m.group(1), "margin").split()[0].removesuffix("px"))
    assert top >= 20, m.group(1)


def test_复制页台头不写贴图_四条线都说得通():
    """复制页是四条线共用的出口（`to_copy_page` 的 docstring），其中三条发的是视频——
    台头原来写「贴图发布文案」、页签写「复制贴图文案」，「贴图」只对知识帖成立
    （评审 3.2「用词不对」）。台头仍然是一个常量：指纹不读它，读 `textarea#title`
    （`test_复制页的textarea_id没改_指纹读得到`）。"""
    a, b = to_copy_page(XHS), to_copy_page("9.27 赛后开麦 | 另一条\n\n正文")
    for page in (a, b):
        assert re.search(r"<h1>(.*?)</h1>", page).group(1) == "发布文案"
        assert re.search(r"<title>(.*?)</title>", page).group(1) == "复制发布文案"
        assert "贴图" not in page


# ── ⑤ 2 万字预算 ─────────────────────────────────────────────────────────
#: 改之前 `fils-tokyo-qualifying`（10 页）走完整条发送路量的：每张图 697 字符 =
#: 3 条钉过版本的 URL（各 127）+ 其余 316（图的属性、alt 里整句标题、回退链接）。
#: 改之后其余那部分是 301（alt 只写「第 N 页」，链接没有外边距、没有横向内边距）。
_OLD_PER_IMAGE_OVERHEAD = 316


def test_字卡推送图多也装得下_每张图不比改之前更贵(tmp_path, monkeypatch):
    """PushPlus 正文上限 2 万字（`pushplus.check_content_length`），字卡推送每张图一组
    「图 + 原图链接」，**样式每多一个字就乘以图数**。仓库里最多的一条是
    `shelton-ncaa-story` 25 页——这一轮加了 `aspect-ratio`、40px 的点击区之后，
    它（按正文上限 1000 字算）必须照样发得出去，每张图也不许比改之前更贵。
    走的是真发送那条路：`pin_asset_revision → prepare_image_delivery → check_content_length`。"""
    from tennislive.cdn import pin_ref
    from tennislive.publish import pushplus
    from tennislive.render.pushmsg import pin_asset_revision

    sha = "741e7a6449b4198ddb26f1e15b57d08b80a5d9df"
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", sha)
    monkeypatch.delenv("PUSHPLUS_SECRET_KEY", raising=False)
    monkeypatch.delenv("PUSHPLUS_ACCESS_KEY", raising=False)
    rel = "output/2026-09-14/explainer/shelton-ncaa-story"
    (tmp_path / rel).mkdir(parents=True)
    urls = [f"https://gcore.jsdelivr.net/gh/robertyang87/tennislive@main/{rel}/slide_{i:02d}.jpg"
            for i in range(26)]
    for u in urls:
        (tmp_path / rel / u.rsplit("/", 1)[1]).write_bytes(b"x")
    xhs = "🎾9.14 网球有故事｜谢尔顿为什么在大学多读了一年\n\n" + "字" * 1000

    def sent(n: int) -> str:
        body = knowledge_push_html_from_parts(
            image_urls=urls[:n], xhs_text=xhs, copy_url=COPY, video_url=VIDEO)
        body = pin_asset_revision(body, sha)
        body, provider = pushplus.prepare_image_delivery(body, asset_dir=tmp_path, token="t")
        assert provider == "jsdelivr"
        return body

    full = sent(25)
    pushplus.check_content_length(full)  # 25 页 + 1000 字正文：照样发得出去
    pinned_url = urls[0].replace("@main/", f"@{pin_ref(sha)}/")
    assert pinned_url in full, "没走到钉版本那一步，量的不是发送那一份"
    per_image = len(sent(25)) - len(sent(24))
    overhead = per_image - 3 * len(pinned_url)
    assert overhead <= _OLD_PER_IMAGE_OVERHEAD, (
        f"每张图除 URL 外 {overhead} 字符，比改之前的 {_OLD_PER_IMAGE_OVERHEAD} 贵——"
        "乘以 25 张就是能发的图变少")


# ── ⑥ 复制页样式只写 token 变量 ───────────────────────────────────────────
def _styles(page: str) -> list[str]:
    return re.findall(r"<style>(.*?)</style>", page, re.S)


def test_复制页自己的样式只用token变量():
    """复制页原来自己配了一套色（按钮 #0a7d43、深色 #b8e986、toast #10201a……），和推送
    零共享。现在第一块 `<style>` 是 token 生成的（和看板 `tokens.css` 同一个函数，跟随
    系统浅／深），第二块是页面自己的——**第二块里一个色值都不许有，用到的每个变量在
    浅、深两个主题里都要有声明**（用到只有深色的画布角色，浅色下 `var()` 落空）。"""
    page = to_copy_page(XHS, pinned_comment="你选谁？")
    tokens, own = _styles(page)
    assert tokens.strip() == ps.copy_page_tokens().strip()
    assert own.strip() == ps.COPY_PAGE_CSS.strip()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b(?![\w-])", re.sub(r"#(title|body|comment|toast)\b", "", own))
    assert not re.search(r"(?i)\b(rgba?|hsla?|oklch|oklab|color-mix)\(", own)
    assert not re.search(r"(?i)\b(white|black)\b", own)
    used = set(re.findall(r"var\((--[\w-]+)\)", own + ps.COPY_PAGE_JS))
    assert {"--tl-primary", "--tl-primary-foreground", "--tl-foreground", "--tl-background",
            "--tl-ring", "--tl-duration-press"} <= used
    light = T.css_vars("light") + T.css_base()
    dark = T.css_vars("dark") + T.css_base()
    for theme, block in (("light", light), ("dark", dark)):
        declared = set(re.findall(r"(--[\w-]+)\s*:", block))
        assert used <= declared, f"{theme} 主题里没声明：{sorted(used - declared)}"
    # 跟着系统走：没钉 data-theme 的深色块在 prefers-color-scheme 里
    assert "@media (prefers-color-scheme: dark)" in tokens
    assert 'viewport-fit=cover' in page, "toast 的安全区要 viewport-fit=cover 才生效"


def test_复制页的textarea_id没改_指纹读得到(tmp_path):
    """`copy_page_fingerprint` 按 `<textarea id="title">` 认「是不是这一版」——样式换了，
    这两个 id 一个都不能动。"""
    page = tmp_path / "copy.html"
    page.write_text(to_copy_page(XHS), encoding="utf-8")
    assert copy_page_fingerprint(page) == "9.26 网球有故事 | 标题一行"
    assert '<textarea id="body" readonly>' in page.read_text(encoding="utf-8")


# ── ⑦ 真渲出来量 ─────────────────────────────────────────────────────────
#: 假计时器：把 setTimeout / clearTimeout 换成手动推进的，「连点两次、1.5 秒后还在不在」
#: 就不靠真等、也不会在 -n 并发下抖。
_FAKE_TIMERS = """
(() => {
  let id = 0; window.__now = 0; window.__timers = [];
  window.setTimeout = (fn, ms) => { id += 1; window.__timers.push({id, at: window.__now + (ms || 0), fn}); return id; };
  window.clearTimeout = (x) => { window.__timers = window.__timers.filter(t => t.id !== x); };
  window.__advance = (ms) => {
    const end = window.__now + ms;
    for (;;) {
      window.__timers.sort((a, b) => a.at - b.at);
      const t = window.__timers[0];
      if (!t || t.at > end) break;
      window.__timers.shift(); window.__now = t.at; t.fn();
    }
    window.__now = end;
  };
})();
"""
_CLIPBOARD_OK = """
Object.defineProperty(navigator, 'clipboard', {configurable: true,
  value: {writeText: () => Promise.resolve()}});
"""
_CLIPBOARD_FAIL = """
Object.defineProperty(navigator, 'clipboard', {configurable: true,
  value: {writeText: () => Promise.reject(new Error('denied'))}});
document.execCommand = () => false;
"""
_CONTRAST_JS = """(el) => {
  const L = (c) => { const m = c.match(/[\\d.]+/g).map(Number);
    const f = (v) => { v /= 255; return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
    return .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]); };
  const r = (a, b) => { const x = L(a), y = L(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const cs = getComputedStyle(el), page = getComputedStyle(document.body).backgroundColor;
  return [r(cs.backgroundColor, cs.color), r(cs.backgroundColor, page)];
}"""


def _toast(tab) -> list:
    return tab.evaluate("() => { const t = document.getElementById('toast');"
                        " return [t.textContent, t.classList.contains('show')]; }")


def test_复制页和推送在浏览器里真的量得到(tmp_path):
    """评审 3.2 那几条交互毛病，拿 Chromium 真点一遍（390×844，浅／深）：

    - **复制失败要说失败**：剪贴板接口拒绝、`execCommand` 也返回 false 时，原来照样弹
      「标题已复制」。现在说「复制失败，已帮你选中，长按拷贝」，并且真把那一格整段选中
    - **连点两次重新计时**：原来第一次的计时没清，第二条 toast 只停约 400ms
    - **深色 toast 看得见**：原来底色和深色页面一样（1.00:1）；现在反色，≥7
    - 复制按钮 ≥44px、成功后显示「已复制」、键盘焦点有 2px 的环
    - 推送里「原图 ↗」的点击区真有 40px 高
    """
    from playwright.sync_api import sync_playwright

    from tennislive.chromium import launch_chromium

    page_file = tmp_path / "copy.html"
    page_file.write_text(to_copy_page(XHS, pinned_comment="你选谁？"), encoding="utf-8")
    push_file = tmp_path / "push.html"
    push_file.write_text('<!doctype html><meta charset="utf-8"><body style="margin:0">'
                         + _knowledge(2) + "</body>", encoding="utf-8")
    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=["--no-sandbox"])
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, color_scheme=scheme)
            ctx.add_init_script(_FAKE_TIMERS)
            tab = ctx.new_page()
            tab.goto(page_file.as_uri())
            heights = tab.evaluate("() => [...document.querySelectorAll('button')]"
                                   ".map(b => b.getBoundingClientRect().height)")
            assert heights and min(heights) >= 44, heights

            # 成功：toast + 按钮「已复制」，1.4 秒后还原
            tab.evaluate(_CLIPBOARD_OK)
            tab.click("button[data-copy=body]")
            tab.wait_for_function("document.getElementById('toast').classList.contains('show')")
            assert _toast(tab) == ["正文已复制", True]
            assert "已复制" in tab.inner_text("button[data-copy=body]")
            ink, against_page = tab.evaluate(_CONTRAST_JS, tab.query_selector("#toast"))
            assert ink >= 7 and against_page >= 7, (scheme, ink, against_page)
            tab.evaluate("__advance(1500)")
            assert _toast(tab)[1] is False
            assert tab.inner_text("button[data-copy=body]") == "复制正文"

            # 连点两次：第二次点完 0.5 秒（第一次点完 1.5 秒）toast 还得在
            tab.click("button[data-copy=title]")
            tab.wait_for_function("document.getElementById('toast').classList.contains('show')")
            tab.evaluate("__advance(1000)")
            tab.click("button[data-copy=title]")
            tab.wait_for_function("window.__timers.some(t => t.at >= window.__now + 1000)")
            tab.evaluate("__advance(500)")
            assert _toast(tab) == ["标题已复制", True], "第二次点的 toast 被第一次的计时提前收走了"
            tab.evaluate("__advance(1000)")
            assert _toast(tab)[1] is False

            # 失败：说失败，并且真的整段选中
            tab.evaluate(_CLIPBOARD_FAIL)
            tab.click("button[data-copy=title]")
            tab.wait_for_function("document.getElementById('toast').classList.contains('show')")
            assert _toast(tab) == [ps.COPY_FAILED_TEXT, True]
            sel = tab.evaluate("() => { const f = document.getElementById('title');"
                               " return [document.activeElement.id, f.selectionStart,"
                               " f.selectionEnd, f.value.length]; }")
            assert sel[0] == "title" and sel[1] == 0 and sel[2] == sel[3] > 0, sel
            assert "已复制" not in tab.inner_text("button[data-copy=title]")

            # 键盘焦点：2px 的环
            tab.evaluate("() => document.activeElement.blur()")
            tab.keyboard.press("Tab")
            ring = tab.evaluate("() => { const cs = getComputedStyle(document.activeElement);"
                                " return [document.activeElement.tagName, cs.outlineStyle, cs.outlineWidth]; }")
            assert ring[0] in ("BUTTON", "TEXTAREA") and ring[1:] == ["solid", "2px"], ring
            ctx.close()

        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        tab = ctx.new_page()
        tab.goto(push_file.as_uri())
        links = tab.evaluate("() => [...document.querySelectorAll('a')]"
                             ".filter(a => a.textContent === '原图 ↗')"
                             ".map(a => a.getBoundingClientRect().height)")
        assert len(links) == 2 and min(links) >= 40, links

        # 赛场之上那条：「📊 数据统计对照」和正文最后一行之间真有 ≥20px（原来 8px）
        reel_file = tmp_path / "reel.html"
        reel_file.write_text('<!doctype html><meta charset="utf-8"><body style="margin:0">'
                             + _reel() + "</body>", encoding="utf-8")
        tab.goto(reel_file.as_uri())
        gap = tab.evaluate("""() => {
          const divs = [...document.querySelectorAll('div')];
          const label = divs.find(d => d.textContent === '📊 数据统计对照');
          const body = divs.find(d => getComputedStyle(d).whiteSpace === 'pre-wrap');
          return label.getBoundingClientRect().top - body.getBoundingClientRect().bottom; }""")
        assert gap >= 20, gap
        ctx.close()
        browser.close()


def test_推送正文里的文案一字不少():
    """样式换了，文案本身（标题、正文每一行）照样整段在推送里、只印一遍。"""
    for body in (_reel(), _knowledge()):
        for line in (ln.strip() for ln in XHS.splitlines()[2:]):
            if line:
                assert body.count(_html.escape(line)) == 1, line

"""Shared content-directed transition cards for every tennis video column.

Editorial owns semantic lines and fact-bound visual relationships. This module
owns adaptive geometry, motion, browser overflow checks and reusable silent clips.
No match-specific facts, scratch paths, TTS, source-audio processing or publication.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import html
import importlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

from ..design_tokens import DARK

VERSION = 2
ROOT = Path(__file__).resolve().parents[3]
KINDS = ("turn", "score_progress", "comparison", "chronology", "person", "comparison_groups")
SIDECAR_SUFFIX = ".transition.json"


def _tc():
    try:
        return importlib.import_module("render_title_card")
    except ModuleNotFoundError:
        return importlib.import_module("tools.render_title_card")


def validate_content(content: dict | None) -> dict:
    """Reject unsupported data before rendering; never invent missing evidence."""
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ValueError("transition_card 必须是对象")
    unknown = content.keys() - {"scores", "events", "comparison", "comparisons", "photo", "highlight", "summary", "entry_process"}
    if unknown:
        raise ValueError(f"transition_card 不支持的字段：{sorted(unknown)}")
    if "entry_process" in content:
        item = content["entry_process"]
        scenes = {"identity", "deadline", "queue", "late_entry", "schedule", "motivation", "reserved", "locals", "insert", "unused", "seeding", "alcaraz", "summary"}
        if (set(content) != {"entry_process"} or not isinstance(item, dict)
                or item.keys() - {"scene", "source", "cues", "case"} or item.get("scene") not in scenes
                or not isinstance(item.get("source"), str) or not item["source"].startswith("https://")):
            raise ValueError("规则演示必须有已知scene及正式source")
        case = item.get("case")
        required = {"player", "seed", "event", "locals", "peer", "peer_seed", "peer_event", "deadline", "postponed_from", "postponed_to", "news_date", "goal", "draw_size"}
        if (not isinstance(case, dict) or set(case) != required or case.get("draw_size") != 32
                or type(case.get("seed")) is not int or not 1 <= case["seed"] <= 8
                or type(case.get("peer_seed")) is not int or not 1 <= case["peer_seed"] <= 8
                or not isinstance(case.get("locals"), list) or len(case["locals"]) != 3
                or any(not isinstance(v, str) or not v.strip() for v in case["locals"])
                or any(not isinstance(case[k], str) or not case[k].strip()
                       for k in required - {"seed", "peer_seed", "draw_size", "locals"})):
            raise ValueError("规则演示需要完整且已核实的32席案例参数")
        cues = item.get("cues", [.15, .4, .65, .83])
        if (not isinstance(cues, list) or len(cues) != 4
                or any(type(c) not in (int, float) or not math.isfinite(c) for c in cues)
                or not 0 < cues[0] < cues[1] < cues[2] < cues[3] < 1):
            raise ValueError("规则演示时序必须递增且位于配音窗口内")
        return json.loads(json.dumps(content, ensure_ascii=False))
    kinds = [k for k in ("scores", "events", "comparison", "comparisons", "photo") if k in content]
    if len(kinds) > 1:
        raise ValueError("一张转场卡只表达一种信息关系 请编辑拆卡")
    if "highlight" in content and not isinstance(content["highlight"], str):
        raise ValueError("highlight 必须是当前标题中的完整短语")
    nodes = []
    if "scores" in content or "events" in content:
        nodes = content.get("scores", content.get("events"))
    elif "comparison" in content:
        comparison = content["comparison"]
        if (not isinstance(comparison, dict) or set(comparison) != {"metric", "nodes"}
                or not isinstance(comparison["metric"], str) or not comparison["metric"].strip()):
            raise ValueError("comparison 必须写清 metric 和 nodes")
        nodes = comparison["nodes"]
    if kinds and kinds[0] not in {"photo", "comparisons"}:
        if not isinstance(nodes, list) or not 2 <= len(nodes) <= 5:
            raise ValueError("推进或对照需要2到5个节点 更多内容请分卡")
        for node in nodes:
            if (not isinstance(node, dict) or node.keys() - {"label", "value", "source", "winning"}
                    or any(not isinstance(node.get(k), str) or not node[k].strip()
                           for k in ("label", "value", "source"))):
                raise ValueError("每个节点必须有 label value 和已核实的 source")
            if "winning" in node and type(node["winning"]) is not bool:
                raise ValueError("winning 必须是布尔值")
            if any("\n" in node[k] for k in ("label", "value")):
                raise ValueError("节点不能自动拆行 请缩短完整语义")
            if "scores" in content and not re.fullmatch(r"[0-9]+[–:比-][0-9]+", node["value"]):
                raise ValueError("比分节点必须是完整比分 且 label 写明盘次")
    if "comparisons" in content:
        groups = content["comparisons"]
        if not isinstance(groups, list) or not 1 <= len(groups) <= 3:
            raise ValueError("comparisons 需要1到3组指标 更多内容请拆卡")
        labels = None
        for group in groups:
            if (not isinstance(group, dict) or set(group) != {"metric", "scope", "unit", "nodes"}
                    or any(not isinstance(group.get(k), str) or not group[k].strip() for k in ("metric", "scope", "unit"))):
                raise ValueError("每组对照必须有 metric scope unit nodes")
            validate_content({"comparison": {"metric": group["metric"], "nodes": group["nodes"]}})
            if any(not re.fullmatch(r"\d+(?:\.\d+)?", n["value"]) or not math.isfinite(float(n["value"])) for n in group["nodes"]):
                raise ValueError("分组对照数值必须是有限非负数")
            current = [n["label"] for n in group["nodes"]]
            if labels is not None and current != labels:
                raise ValueError("逐组对照必须保留相同双方与顺序")
            labels = current
    if "summary" in content:
        summary = content["summary"]
        if ("scores" not in content or not isinstance(summary, dict) or set(summary) != {"value", "label", "source"}
                or any(not isinstance(summary[k], str) or not summary[k].strip() for k in summary)):
            raise ValueError("比分总结必须写 value label source 且来自核实事实")
    if "photo" in content:
        photo = content["photo"]
        if (not isinstance(photo, dict) or (not {"path", "source"} <= photo.keys() or photo.keys() - {"path", "source", "result"})
                or any(not isinstance(photo.get(k), str) or not photo[k].strip() for k in ("path", "source"))):
            raise ValueError("photo 必须有仓库相对 path 和正式来源 source")
        if "result" in photo:
            result = photo["result"]
            if (not isinstance(result, dict) or not {"value", "source"} <= result.keys()
                    or result.keys() - {"value", "source", "label"}
                    or any(not isinstance(result.get(k), str) or not result[k].strip() for k in ("value", "source"))
                    or ("label" in result and not isinstance(result["label"], str))):
                raise ValueError("照片赛果必须有 value source 可选完整 label")
        path = Path(photo["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("photo.path 必须是仓库内的相对路径")
    return json.loads(json.dumps(content, ensure_ascii=False))


def plan(text: str, content: dict | None = None, *, size=(1080, 1440), kicker="") -> dict:
    c = validate_content(content)
    if "comparison" in c and c["comparison"]["metric"] not in text:
        kicker = c["comparison"]["metric"]
    tc = _tc()
    if "entry_process" in c:
        return {"canvas_width": size[0], "kind": "entry_process", "lines": text.splitlines(),
                "font_px": 62, "nodes": [], "content": c, "safe_bottom": size[1]-170,
                "notes": [], "photo": None, "direction": "horizontal", "kicker": kicker,
                "highlight": "", "groups": [], "proof_h": 850}
    if problem := tc.length_problem(text):
        raise ValueError(problem)
    lines = tc.semantic_lines(text)
    if not 1 <= len(lines) <= 2:
        raise ValueError("转场标题必须按完整语义写成一到两行")
    w, h = size
    if w < 540 or h < 800:
        raise ValueError("转场卡画面区过小")
    px = tc.title_px(lines, size)
    if h < 1200 and any(k in c for k in ("scores", "events", "comparison", "comparisons", "photo")):
        px = min(px,72)
    highlight = c.get("highlight", "")
    if highlight and not any(highlight in line for line in lines):
        raise ValueError("highlight 不能拆开语义行 且必须来自当前标题")
    kind, nodes = "turn", []
    notes = []
    if "scores" in c:
        kind, nodes = "score_progress", c["scores"]
    elif "events" in c:
        kind, nodes = "chronology", c["events"]
    elif "comparison" in c:
        kind, nodes = "comparison", c["comparison"]["nodes"]
    groups = c.get("comparisons", [])
    if groups:
        kind = "comparison_groups"
    photo = None
    if "photo" in c:
        from PIL import Image
        path = ROOT / c["photo"]["path"]
        if path.is_file():
            with Image.open(path) as im:
                iw, ih = im.size
                im.verify()
            photo = {"path": str(path), "width": iw, "height": ih}
            kind = "person"
        else:
            notes.append("照片不存在 回退简洁转折卡")
    direction = "vertical" if kind == "chronology" or len(nodes) > 3 else "horizontal"
    top, bottom = (160 if h >= 1200 else 96), h - (196 if h >= 1200 else 110)
    title_h = len(lines) * px * 1.28
    has_kicker = bool(kicker and kicker not in tc.COLUMN_LABELS)
    lead = (84 if h >= 1200 else 64) if has_kicker else 0
    proof_gap = 68 if h >= 1200 else 40
    node_height = 140 if kind == "chronology" and h >= 1200 else 86
    proof_h = (len(nodes) * node_height if direction == "vertical" else 218) if nodes else 0
    if groups:
        proof_h = sum((60 if h >= 1200 else 44) + (68 if h >= 1200 else 48) * len(g["nodes"]) for g in groups)
    if "summary" in c:
        proof_h += 174
    total = lead + title_h + (proof_gap + proof_h if nodes or groups else 64)
    start = top + (bottom - top - total) / 2
    headline_y = start + lead
    proof_y = headline_y + title_h + proof_gap
    if photo:
        start = 118 if h >= 1200 else 80
        headline_y = start + lead
        photo_top = headline_y + title_h + 40
        photo_h = bottom - photo_top - (58 if c["photo"].get("result") else 0)
        if photo_h < 230 or min((w - 140) / photo["width"], photo_h / photo["height"]) > 1.6:
            notes.append("照片空间或清晰度不足 回退简洁转折卡")
            return {**plan(text, {k: v for k, v in c.items() if k != "photo"}, size=size, kicker=kicker), "notes": notes}
        photo.update(top=photo_top, height=photo_h)
    if (not photo and start < top - 1) or proof_y + proof_h > bottom + 1:
        raise ValueError("转场内容无法在字幕安全区上方排下 请精简或拆卡")
    return {"canvas_width": w, "kind": kind, "lines": lines, "font_px": px, "nodes": nodes,
            "direction": direction, "groups": groups, "proof_h": proof_h, "node_height": node_height, "kicker_y": start, "headline_y": headline_y,
            "proof_y": proof_y, "safe_bottom": bottom, "photo": photo,
            "highlight": highlight, "kicker": kicker, "content": c, "notes": notes}


def build(text: str, *, content=None, kicker="", size=(1080, 1440),
          handle_bottom=None, story_label=None, seconds=6.0, header=None) -> str:
    """One HTML source for previews and motion, preserving the native brand rail."""
    tc = _tc()
    p = plan(text, content, size=size, kicker=kicker)
    if p["kind"] == "entry_process":
        from .transition_motion import entry_process
        return entry_process(p["content"]["entry_process"], text=text, size=size, seconds=seconds, header=header)
    page = tc.build(text, kicker=p["kicker"], size=size, handle_bottom=handle_bottom, story_label=story_label)
    e = html.escape
    lines = []
    for i, line in enumerate(p["lines"]):
        value = e(line)
        if p["highlight"]:
            value = value.replace(e(p["highlight"]), "<em>" + e(p["highlight"]) + "</em>")
        lines.append(f'<div class="transition-line" style="--dx:{80 if i % 2 == 0 else -80}px;--delay:{.3+i*.16}s">{value}</div>')
    page = re.sub(r'(<div class="thesis">).*?(</div>)', lambda m: m[1]+"".join(lines)+m[2], page, count=1, flags=re.S)
    w, h = size
    proof = ""
    maximum = None
    if p["kind"] == "comparison":
        vals = [n["value"] for n in p["nodes"]]
        if all(re.fullmatch(r"\d+(?:\.\d+)?", v) for v in vals):
            maximum = max(map(float, vals))
    for i, node in enumerate(p["nodes"]):
        ratio = float(node["value"])/maximum if maximum else 0
        proof += (f'<div class="transition-node" style="--delay:{.85+i*.28}s;--ratio:{ratio};--dx:{-90 if i%2==0 else 90}px">'
                  f'<div class="node-label">{e(node["label"])}</div><div class="node-value {"winning" if node.get("winning") else ""}">{e(node["value"])}</div>'
                  + ('<div class="comparison-bar"></div>' if maximum else '') + '</div>')
    proof = f'<section class="transition-proof {p["kind"]} {p["direction"]}">{proof}</section>' if proof else ""
    photo = ""
    if p["photo"]:
        from .explainer import _data_uri
        photo = (f'<img class="transition-photo" src="{_data_uri(Path(p["photo"]["path"]))}" '
                 f'style="top:{p["photo"]["top"]}px;height:{p["photo"]["height"]}px">')
    css = f'''<style>
.wrap{{inset:auto;top:{p['kicker_y']}px;left:0;width:{w}px;justify-content:flex-start}}
.wrap .kicker{{font-size:36px;letter-spacing:4px;line-height:1;margin-bottom:28px;padding:9px 20px;border-width:1px;animation:tc-kicker .45s .18s both}}
.wrap .thesis{{font-size:{p['font_px']}px;position:fixed;top:{p['headline_y']}px;left:70px;width:{w-140}px;max-width:{w-140}px}}
.transition-line{{white-space:nowrap;animation:tc-enter .48s var(--delay) both}}
em{{position:relative;font-style:normal;color:{DARK['primary']}}}
em:after{{content:'';position:absolute;left:0;right:0;bottom:-6px;height:3px;background:currentColor;transform-origin:left;animation:tc-grow .5s 1.25s both}}
.transition-proof{{position:absolute;left:90px;right:90px;top:{p['proof_y']}px}}
.transition-proof.horizontal{{display:flex;gap:32px}}
.transition-node{{position:relative;min-width:0;flex:1;text-align:center;animation:tc-node .5s var(--delay) both}}
.node-label{{font-family:'TL Sans SC',sans-serif;font-size:28px;line-height:1.4;white-space:nowrap;color:{DARK['muted-foreground']}}}
.node-value{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:78px;line-height:1.25;white-space:nowrap;margin-top:12px;animation:tc-fold .48s calc(var(--delay) + .14s) both}}
.winning{{color:{DARK['success']}}}
.chronology .node-value{{font-family:'TL Sans SC',sans-serif;font-size:40px}}
.vertical .transition-node{{display:flex;justify-content:space-between;align-items:center;text-align:left;height:86px;padding:0 36px;border-bottom:1px solid #6e93be33}}
.vertical .node-value{{margin-top:0;font-size:40px}}
.score_progress:after{{content:'';position:absolute;left:10%;right:10%;bottom:-24px;height:2px;background:{DARK['info']};transform-origin:left;animation:tc-grow 1.3s .8s both}}
.chronology:after{{content:'';position:absolute;left:0;top:24px;bottom:24px;width:2px;background:{DARK['info']};transform-origin:top;animation:tc-vgrow 1.3s .8s both}}
.comparison .transition-node{{padding:24px 16px;background:{DARK['card']};border-radius:14px;border-top:2px solid #4bb8ff66;animation-name:tc-side}}
.comparison-bar{{height:6px;position:absolute;left:16px;right:16px;bottom:-25px;background:#4bb8ff22}}
.comparison-bar:after{{content:'';display:block;width:calc(var(--ratio)*100%);height:100%;background:{DARK['info']};transform-origin:left;animation:tc-grow .9s 1.6s both}}
.transition-photo{{position:absolute;left:70px;width:{w-140}px;object-fit:contain;animation:tc-photo 2.5s both}}
.tc-glow{{position:absolute;top:-180px;right:-140px;width:700px;height:700px;border-radius:50%;background:radial-gradient(ellipse,#4bb8ff12,transparent 67%);animation:tc-light 2.6s both;pointer-events:none}}
.tc-court{{position:absolute;inset:0;width:100%;height:100%;fill:none;stroke:{DARK['info']};stroke-width:1.5;opacity:.065;stroke-dasharray:2000;stroke-dashoffset:2000;animation:tc-court 1.8s .2s both;pointer-events:none}}
@keyframes tc-enter{{from{{opacity:0;transform:translate(var(--dx),18px)}}to{{opacity:1;transform:none}}}}
@keyframes tc-node{{from{{opacity:0;transform:translateY(26px)}}to{{opacity:1;transform:none}}}}
@keyframes tc-side{{from{{opacity:0;transform:translateX(var(--dx))}}to{{opacity:1;transform:none}}}}
@keyframes tc-fold{{from{{opacity:0;transform:scaleY(.08)}}to{{opacity:1;transform:scaleY(1)}}}}
@keyframes tc-kicker{{from{{opacity:0;transform:translateY(-20px)}}to{{opacity:1;transform:none}}}}
@keyframes tc-grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@keyframes tc-vgrow{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes tc-photo{{from{{opacity:0;transform:translateY(26px) scale(.96)}}to{{opacity:1;transform:none}}}}
@keyframes tc-light{{from{{transform:translate(-80px,-40px);opacity:.3}}to{{transform:translate(0,40px);opacity:1}}}}
@keyframes tc-court{{to{{stroke-dashoffset:0}}}}
</style>'''
    graphics = ('<div class="tc-glow"></div><svg class="tc-court" viewBox="0 0 1080 1440" preserveAspectRatio="none">'
                '<path d="M190 1210L412 176H668L890 1210ZM300 700H780M255 910H825M540 176V1210"/></svg>')
    # Background graphics precede real copy and the existing fixed brand rail.
    page = page.replace('<div class="bar">', graphics+'<div class="bar">', 1)
    clock = '''<script>window.setTransitionTime=(seconds)=>{document.getAnimations().forEach(a=>{a.pause();a.currentTime=seconds*1000});};</script>'''
    if header is not None:
        if (not isinstance(header, dict) or set(header) != {"brand", "topic"}
                or any(not isinstance(v, str) or not v.strip() for v in header.values())):
            raise ValueError("解说台头需要完整品牌与主题")
        from .explainer import _data_uri
        from .outro_page import ICON
        if not ICON.is_file():
            raise ValueError("解说台头缺少正式账号logo")
        page += ('<div class="explainer-head" style="position:absolute;z-index:20;left:70px;right:70px;top:44px;'
                 'display:flex;align-items:center;gap:14px;color:#edf1f5;line-height:1.2">'
                 '<img class="brand-icon" style="width:52px;height:52px;object-fit:contain" src="'+_data_uri(ICON)+'">'
                 '<div><div class="brand" style="font-family:TL Display SC;font-size:38px;font-weight:400;letter-spacing:1px">' + e(header["brand"]) + '</div>'
                 '<span class="topic" style="display:block;white-space:nowrap;font-family:TL Sans SC;font-size:27px;font-weight:700;'
                 'color:#c1ccd6;margin-top:2px">' + e(header["topic"]) + '</span></div></div>')
    from .transition_motion import enhance
    return enhance(page + css + photo + proof + clock, p, size=size, seconds=seconds)


def check_page(page, p: dict) -> dict:
    if p["kind"] == "entry_process":
        proof = page.evaluate("""() => ({slots:document.querySelectorAll('.draw-slot').length,
            brand: getComputedStyle(document.querySelector('.brand')).fontFamily,
            heading: getComputedStyle(document.querySelector('.process-heading')).fontFamily,
            logo: document.querySelector('.brand-icon').naturalWidth,
            notes: document.querySelector('.process-note').scrollWidth <= 940,
            labels: [...document.querySelectorAll('.process-label')].every(e => {
                const r=e.getBoundingClientRect();return r.left>=20 && r.right<=1060 && r.top>=340 && r.bottom<=1210;})})""")
        if (proof['slots'] not in (0,32) or not proof['logo'] or not proof['notes']
                or 'TL Display SC' not in proof['brand'] or 'TL Display SC' not in proof['heading']
                or not proof['labels']):
            raise ValueError('规则演示的名额 字体 logo 或安全区不合格：'+str(proof))
        return proof
    evidence = page.evaluate('''()=>{
      const rect=el=>el.getBoundingClientRect().toJSON();
      return {boxes:[...document.querySelectorAll('.transition-line,.node-label,.node-value,.metric-title,.chart-label,.chart-value,.result-label,.result-value,.summary-label,.summary-value')].map(el=>({text:el.innerText,width:el.clientWidth,scroll:el.scrollWidth,rect:rect(el)})),
        content:[...document.querySelectorAll('.thesis,.transition-proof,.kicker,.transition-photo,.motion-result,.motion-summary')].map(rect),
        story:document.querySelector('.story-label')?rect(document.querySelector('.story-label')):null};}''')
    header_boxes = page.evaluate("[...document.querySelectorAll('.explainer-head,.explainer-head .topic')].map(e=>({w:e.clientWidth,s:e.scrollWidth,b:e.getBoundingClientRect().bottom}))")
    if any(b["s"] > b["w"] + 1 or b["b"] > 152 for b in header_boxes):
        raise ValueError("解说台头溢出顶部安全区")
    if any(b["scroll"] > b["width"] + 1 or b["rect"]["left"] < 48 or b["rect"]["right"] > p["canvas_width"] - 48 for b in evidence["boxes"]):
        raise ValueError("转场实际排版文字溢出 请缩短完整语义")
    if any(b["bottom"] > p["safe_bottom"] + 30 for b in evidence["content"]):
        raise ValueError("转场实际排版侵入字幕安全区")
    if evidence["story"] and any(b["top"] < evidence["story"]["bottom"] + 24 for b in evidence["content"]):
        raise ValueError("转场标题与既有故事角标安全区冲突")
    return evidence


def render_clip(text: str, out: Path, *, seconds: float, fps=25, content=None,
                kicker="", size=(1080, 1440), handle_bottom=None, story_label=None, header=None) -> Path:
    """Cache exact silent movie bytes; animate once then hold for full narration."""
    from PIL import Image
    import io
    from playwright.sync_api import sync_playwright
    from ..chromium import launch_chromium
    out = Path(out)
    rate = float(Fraction(str(fps)))
    if not math.isfinite(seconds) or seconds <= 0 or not 1 <= rate <= 60:
        raise ValueError("转场需要有效的完整停留时长和帧率")
    p = plan(text, content, size=size, kicker=kicker)
    document = build(text, content=content, kicker=kicker, size=size,
                     handle_bottom=handle_bottom, story_label=story_label, seconds=seconds, header=header)
    motion_window = (max(.1, seconds - .16) if p["kind"] == "entry_process"
                     else min(6.0, max(.1, seconds - .3)))
    engine_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    key = hashlib.sha256((str(VERSION)+engine_sha+document+json.dumps([seconds,str(fps),p['content']],ensure_ascii=False)).encode()).hexdigest()
    receipt = out.with_suffix('.transition-render.json')
    if out.is_file() and receipt.is_file():
        old = json.loads(receipt.read_text())
        if old.get('key') == key and old.get('sha256') == hashlib.sha256(out.read_bytes()).hexdigest():
            return out
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_movie = out.with_name(out.stem+'.tmp.mp4')
    w, h = size
    frame_count = math.ceil(seconds * rate)
    # The native dissolve supplies the exit. Static hold never cuts actual TTS;
    # after all entrance animations settle, repeated browser work is unnecessary.
    with tempfile.TemporaryDirectory(prefix='tennis-transition-') as directory:
        source = Path(directory)/'card.html';source.write_text(document)
        with sync_playwright() as pw:
            browser = launch_chromium(pw,args=['--no-sandbox'])
            try:
                page = browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
                page.goto(source.as_uri());page.evaluate('document.fonts.ready')
                page.wait_for_function('window.transitionMotion || window.transitionMotionError')
                page.evaluate('document.fonts.ready')
                if issue := page.evaluate('window.transitionMotionError || null'):
                    raise ValueError(issue)
                page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
                page.evaluate('(t)=>window.setTransitionTime(t)',motion_window)
                evidence = check_page(page,p)
                page.screenshot(path=str(out.with_suffix('.jpg')),type='jpeg',quality=95)
                process = subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
                    '-s',f'{w}x{h}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','veryfast',
                    '-crf','20','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(temp_movie)],stdin=subprocess.PIPE)
                try:
                    last = None
                    for i in range(frame_count):
                        t = min(i/rate,motion_window)
                        if t < motion_window or last is None:
                            page.evaluate('(t)=>window.setTransitionTime(t)',t)
                            last = Image.open(io.BytesIO(page.screenshot(type='jpeg',quality=95))).convert('RGB').tobytes()
                        process.stdin.write(last)
                    process.stdin.close()
                    if process.wait():
                        raise RuntimeError('转场视频编码失败')
                except BaseException:
                    process.kill();process.wait();temp_movie.unlink(missing_ok=True)
                    raise
            finally:
                browser.close()
    temp_movie.replace(out)
    receipt.write_text(json.dumps({'version':VERSION,'key':key,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
        'seconds':frame_count/rate,'fps':str(fps),'size':list(size),'plan':p,'browser_evidence':evidence,
        'review_scope':'deterministic browser geometry and encoding; not full visual/audio review'},ensure_ascii=False,indent=2))
    return out


def export_hyperframes(text: str, directory: Path, *, seconds: float, fps=25, content=None, kicker="", size=(1080,1440)) -> Path:
    """Export the very same offline page/GSAP clock as an editable HF project."""
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("HyperFrames 导出需要实际完整时长")
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    page = build(text, content=content, kicker=kicker, size=size, seconds=seconds)
    width, height = size
    entry = directory / "index.html"
    entry.write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><div id="report" data-composition-id="main" data-start="0" data-duration="{seconds:g}" data-fps="{fps}" data-width="{width}" data-height="{height}">{page}</div></body></html>')
    (directory / "reference.json").write_text(json.dumps({"version": VERSION,"text":text,"content":validate_content(content),"seconds":seconds,"fps":str(fps),"size":list(size)},ensure_ascii=False,indent=2))
    return entry

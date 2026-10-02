"""微信链接网页全局主题契约：2026-09-30，系统浅色 ⇄ 深色，不看钟点。

测真实模板产出和浏览器计算样式，不拿 CSS 字符串存在冒充生效。
仅验证我们控制的正文／复制页；PushPlus 样式过滤和微信系统偏好传递需真实发布另验。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from tennislive import design_tokens as T
from tennislive.chromium import launch_chromium
from tennislive.render import push_style as ps
from tennislive.render.knowledge import knowledge_push_html_from_parts
from tennislive.render.pushmsg import to_copy_page

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import push_reel  # noqa: E402

COPY = "https://copy.invalid/"
VIDEO = "https://video.invalid/"
TEXT = "9.30 赛场之上 | 系统主题测试\n\n正文，中文与 English。\n\n#网球时差"
IMAGE = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='40'%3E%3C/svg%3E"


def _fragment(route):
    if route == "字卡":
        return knowledge_push_html_from_parts(image_urls=[IMAGE], xhs_text=TEXT,
                                              copy_url=COPY, video_url=VIDEO)
    return push_reel.build_html(VIDEO, COPY, "导语", TEXT, IMAGE, route,
                                stat_card=IMAGE if route == "赛场之上" else "")


def _document(fragment):
    # 模拟宿主的固定浅色；正文必须自己跟随系统，不能误改宿主。
    return ('<!doctype html><meta charset="utf-8"><body style="background:#fff;color:#000">'
            '<div id="host" style="background-color:#ffffff;color:#17251f">宿主</div>'
            + fragment + '</body>')


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        instance = launch_chromium(pw, args=["--no-sandbox"])
        yield instance
        instance.close()


def _rgb(value):
    value = value.lstrip("#")
    channels = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    if len(value) == 8:
        return f"rgba({', '.join(map(str, channels))}, {int(value[6:], 16) / 255:.3f})"
    return f"rgb({', '.join(map(str, channels))})"


def _palette(page):
    return page.evaluate("""() => {
      const root = document.querySelector('.tl-push');
      const divs = [...root.querySelectorAll('div')];
      const style = el => getComputedStyle(el);
      const byText = text => divs.find(el => el.textContent === text);
      const card = root.querySelector('div');
      const body = divs.find(el => style(el).whiteSpace === 'pre-wrap');
      const title = divs.find(el => el.textContent.startsWith('9.30赛场之上|') && style(el).userSelect === 'all');
      const hint = byText('☝️ 标题，长按这一行即可复制');
      const original = [...root.querySelectorAll('a')].find(el => el.textContent === '原图 ↗');
      const divider = divs.find(el => style(el).borderTopWidth === '1px');
      const video = root.querySelector('a[href="https://video.invalid/"]');
      const red = root.querySelector('a[href="https://copy.invalid/"]');
      return {page: [style(root).backgroundColor, style(root).color],
        card: style(card).backgroundColor, title: style(title).color, body: style(body).color,
        hint: style(hint).color, original: style(original).color,
        divider: style(divider).borderTopColor,
        video: [style(video).backgroundColor, style(video).color],
        red: [style(red).backgroundColor, style(red).color],
        imageFilter: style(root.querySelector('img')).filter,
        host: [style(document.querySelector('#host')).backgroundColor, style(document.querySelector('#host')).color]};
    }""")


def _assert_theme(page, theme):
    t = T.DARK if theme == "dark" else T.LIGHT
    got = _palette(page)
    # CSSOM 可把 #ffffff1a 序列化成 .1 或 .102；比较通道与 8-bit alpha，
    # 不让浏览器序列化小数位成为主题回归的假红。
    border = [float(x) for x in re.findall(r"[\d.]+", got.pop("divider"))]
    value = t["border"].lstrip("#")
    assert border[:3] == [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    alpha = border[3] if len(border) == 4 else 1
    assert alpha == pytest.approx(int(value[6:], 16) / 255 if len(value) == 8 else 1,
                                 abs=1 / 255)
    assert got == {
        "page": [_rgb(t["background"]), _rgb(t["foreground"])],
        "card": _rgb(t["card"]), "title": _rgb(t["foreground"]),
        "body": _rgb(t["foreground"]), "hint": _rgb(t["muted-foreground"]),
        "original": _rgb(t["link"]),
        "video": [_rgb(t["primary"]), _rgb(t["primary-foreground"])],
        "red": [_rgb("#ff2442"), _rgb("#ffffff")], "imageFilter": "none",
        "host": [_rgb("#ffffff"), _rgb("#17251f")],
    }


@pytest.mark.parametrize("route", ["赛场之上", "赛后开麦", "网球有故事", "字卡"])
def test_所有栏目推送打开后跟随系统浅深浅切换(browser, route):
    page = browser.new_page(viewport={"width": 390, "height": 844}, color_scheme="light")
    try:
        page.set_content(_document(_fragment(route)))
        for theme in ("light", "dark", "light", "dark"):
            page.emulate_media(color_scheme=theme)
            _assert_theme(page, theme)
        assert page.locator('.tl-push').inner_text().count('正文，中文与 English。') == 1
    finally:
        page.close()


@pytest.mark.parametrize("fallback", ["no-preference", "unknown-media", "style-filtered"])
def test_旧WebView或平台过滤样式仍有可读的浅色兜底(browser, fallback):
    fragment = _fragment("赛场之上")
    if fallback == "unknown-media":
        fragment = fragment.replace("prefers-color-scheme", "x-unknown-color-scheme")
    elif fallback == "style-filtered":
        fragment = re.sub(r'<style>.*?</style>', '', fragment, flags=re.S)
    page = browser.new_page(color_scheme="no-preference" if fallback == "no-preference" else "dark")
    try:
        page.set_content(_document(fragment))
        _assert_theme(page, "light")
    finally:
        page.close()


def test_反向验证去掉主题规则会重现深色系统里的浅色正文(browser):
    fragment = _fragment("赛场之上").replace(ps.system_theme_style(), "")
    page = browser.new_page(color_scheme="dark")
    try:
        page.set_content(_document(fragment))
        with pytest.raises(AssertionError):
            _assert_theme(page, "dark")
        _assert_theme(page, "light")
    finally:
        page.close()


def test_所有栏目共用的复制页同样即时跟随系统(browser):
    page = browser.new_page(color_scheme="light")
    try:
        page.set_content(to_copy_page(TEXT))
        for theme in ("light", "dark", "light"):
            page.emulate_media(color_scheme=theme)
            t = T.DARK if theme == "dark" else T.LIGHT
            got = page.evaluate("""() => {const b = getComputedStyle(document.body);
              const c = getComputedStyle(document.querySelector('textarea'));
              return [b.backgroundColor,b.color,c.backgroundColor,c.color];}""")
            assert got == [_rgb(t["background"]), _rgb(t["foreground"]),
                           _rgb(t["card"]), _rgb(t["foreground"])]
    finally:
        page.close()

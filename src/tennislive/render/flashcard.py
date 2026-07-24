"""Single-image tennis news flash card — a lightweight, timely post format.

Unlike the four-card knowledge deck (verified cover + story + explainer +
today), a flash card is one vertical image built to react to the day's tennis
news fast. It is structured so a reader gets the whole story at a glance:

  - a FLASH chip + hook headline (why you should care),
  - a when / where / who meta strip (the facts, stated plainly),
  - a "what happened" event panel (the specific event),
  - a punch line (the shareable, emotional hook).

No external player photo, so it skips the heavy photo-verification loop and
can ship the same day. Sensitive topics must be gated upstream via
``render.sensitivity`` before an item is auto-published. Nothing here invents
facts — callers supply verified text.
"""

from __future__ import annotations

import html
from pathlib import Path

from .webcards import _FOOTER, _masthead, _screenshot_pages

W, H = 1080, 1440


def _meta_cell(label: str, value: str) -> str:
    label_style = (
        "color:#37e29a;font-size:22px;font-weight:700;letter-spacing:2px;"
        "margin-bottom:8px;"
    )
    value_style = "color:#f4fbf7;font-size:33px;font-weight:700;line-height:1.28;"
    return (
        '<div style="flex:1;min-width:0;padding:0 4px;">'
        f'<div style="{label_style}">{html.escape(label)}</div>'
        f'<div style="{value_style}">{html.escape(value)}</div></div>'
    )


def flash_card_body(
    headline: str,
    *,
    event: str,
    when: str = "",
    where: str = "",
    who: str = "",
    punch: str = "",
    source_label: str,
    date_label: str,
    kicker: str = "网球快讯 · FLASH",
) -> str:
    """Build one structured, vertical flash-card HTML body.

    ``headline`` is the hook; ``when``/``where``/``who`` populate the meta
    strip (omit any that are blank); ``event`` is the specific what-happened
    panel; ``punch`` is the optional shareable closer. All text is escaped;
    the layout is self-contained inline CSS.
    """
    hook = html.escape(headline).replace("，", "，<br>", 1)
    bg = (
        "position:absolute;inset:0;z-index:0;"
        "background:radial-gradient(125% 85% at 50% 8%,#155a41 0%,#0b3a2a 46%,#061c14 100%);"
    )
    # Decorative texture so the canvas isn't a flat slab: a large translucent
    # ring (tennis-ball motif) bleeding off the top-right corner.
    ring = (
        "position:absolute;top:-180px;right:-180px;width:560px;height:560px;"
        "border-radius:50%;border:60px solid rgba(55,226,154,.10);z-index:0;"
    )
    ring2 = (
        "position:absolute;bottom:-160px;left:-200px;width:520px;height:520px;"
        "border-radius:50%;border:44px solid rgba(255,255,255,.04);z-index:0;"
    )
    stage = (
        "position:relative;z-index:2;flex:1;display:flex;flex-direction:column;"
        "justify-content:center;gap:34px;"
    )
    chip = (
        "display:inline-block;align-self:flex-start;background:#ff4d5e;"
        "color:#fff;font-size:24px;font-weight:800;letter-spacing:3px;"
        "padding:10px 20px;border-radius:999px;"
    )
    h1_style = (
        "color:#f4fbf7;font-size:78px;line-height:1.22;font-weight:800;margin:0;"
    )
    accent = "width:96px;height:9px;background:#37e29a;border-radius:6px;"

    meta_cells = [
        _meta_cell(label, value)
        for label, value in (("时间", when), ("地点", where), ("人物", who))
        if value
    ]
    meta_strip = ""
    if meta_cells:
        joined = '<div style="width:2px;background:rgba(255,255,255,.14);"></div>'.join(
            meta_cells
        )
        meta_strip = (
            '<div style="display:flex;gap:22px;padding:26px 30px;'
            "background:rgba(255,255,255,.05);border-radius:16px;"
            f'align-items:stretch;">{joined}</div>'
        )

    event_style = (
        "padding:30px 34px;background:rgba(6,28,20,.5);"
        "border-left:8px solid #37e29a;border-radius:16px;color:#eaf5ef;"
        "font-size:38px;line-height:1.5;font-weight:600;"
    )
    event_block = f'<div style="{event_style}">{html.escape(event)}</div>'

    punch_block = ""
    if punch:
        punch_style = (
            "color:#ffe08a;font-size:44px;line-height:1.4;font-weight:800;"
        )
        punch_block = f'<div style="{punch_style}">{html.escape(punch)}</div>'

    source_style = "position:relative;z-index:2;color:#9fb4aa;font-size:24px;"
    return (
        '<div class="poster cover knowledge-page" data-visual="flash-card">'
        f'<div style="{bg}"></div><div style="{ring}"></div><div style="{ring2}"></div>'
        + _masthead(date_label)
        + f'<div style="{stage}">'
        f'<span style="{chip}">{html.escape(kicker)}</span>'
        f'<div style="{accent}"></div>'
        f'<h1 style="{h1_style}">{hook}</h1>'
        f"{meta_strip}"
        f"{event_block}"
        f"{punch_block}"
        "</div>"
        f'<div style="{source_style}">{html.escape(source_label)}</div>'
        + _FOOTER
        + "</div>"
    )


def generate_flash_card(
    headline: str,
    *,
    event: str,
    when: str = "",
    where: str = "",
    who: str = "",
    punch: str = "",
    source_label: str,
    date_label: str,
    out_path: str | Path,
    theme: str = "dark",
    kicker: str = "网球快讯 · FLASH",
) -> Path:
    """Render a structured flash-card body to a 1080x1440 image and save it."""
    from .image_output import save_social_image

    body = flash_card_body(
        headline,
        event=event,
        when=when,
        where=where,
        who=who,
        punch=punch,
        source_label=source_label,
        date_label=date_label,
        kicker=kicker,
    )
    (_kind, image), = _screenshot_pages([("flash", body)], theme)
    return save_social_image(image, out_path)

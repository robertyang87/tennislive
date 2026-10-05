"""Original, quiet tennis illustrations for evidence-backed rule pages."""
from __future__ import annotations

import html


_IVORY = '#d2dde5'
_LIME = '#c9f45e'


def _icon(label: str, paths: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="94" height="94" '
            f'viewBox="0 0 100 100" role="img" aria-label="{html.escape(label)}" '
            f'fill="none" stroke="{_IVORY}" stroke-width="2.8" '
            'stroke-linecap="round" stroke-linejoin="round">'
            f'<title>{html.escape(label)}</title>{paths}</svg>')


_WARNING = _icon('裁判示意提醒', f'''
<circle cx="47" cy="21" r="7.5"/>
<path d="M40 36h15v24H39M55 41l16-9V18"/>
<path d="M38 43v20h30M44 61l-7 25M62 61l8 25M40 75h27"/>
<path d="M71 18v-7" stroke="{_LIME}"/>
''')

_POINT = _icon('记分板中的单分', f'''
<rect x="15" y="22" width="70" height="58" rx="4"/>
<path d="M15 51h70M29 37h17M29 65h17M55 22v58"/>
<circle cx="70" cy="37" r="7.5" stroke="{_LIME}"/>
<path d="M64 32c6 1 9 5 11 10" stroke="{_LIME}" stroke-width="2"/>
''')

_GAME = _icon('一局比赛的小球场', f'''
<path d="M22 12h56v76H22zM31 12v76M69 12v76M31 33h38M31 67h38M50 33v34"/>
<path d="M19 50h62"/>
<circle cx="61" cy="77" r="5.5" stroke="{_LIME}"/>
<path d="M58 73c4 1 6 4 7 7" stroke="{_LIME}" stroke-width="1.8"/>
''')

_POINTS = _icon('巡回赛排名积分', f'''
<path d="M21 19h44l14 14v52H21zM65 19v14h14"/>
<path d="M38 45h25M38 59h25M38 73h25"/>
<circle cx="29" cy="45" r="2"/>
<circle cx="29" cy="59" r="2"/>
<circle cx="29" cy="73" r="2"/>
<path d="M42 19v-8M58 19v-8" stroke="{_LIME}"/>
''')

_PRIZE = _icon('赛事奖金', f'''
<path d="M54 20a28 28 0 0 1 17 51M66 76a28 28 0 0 1-14 5"/>
<circle cx="42" cy="48" r="27"/>
<circle cx="42" cy="48" r="20" stroke-opacity=".55" stroke-width="2"/>
<path d="M30 37c13 1 23 11 24 23M30 59c12-1 21-10 23-22" stroke="{_LIME}" stroke-width="2.2"/>
''')


def _node(label: str, svg: str) -> str:
    return ('<div class="tl-rule-graphic-node">' + svg
            + '<span>' + html.escape(label) + '</span></div>')


def _arrow() -> str:
    return (f'<svg class="tl-rule-graphic-arrow" width="80" height="30" '
            f'viewBox="0 0 80 30" aria-hidden="true" fill="none" stroke="{_IVORY}" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'stroke-opacity=".55"><path d="M7 15h64M62 6l9 9-9 9"/></svg>')


def rule_graphic_html(kind: str) -> str:
    """Return a transparent 940 px-wide evidence-backed explanatory diagram.

    Labels inherit the project's original TL Sans SC at regular weight. The
    drawings explain the concepts; the caller keeps real rulebook evidence
    below them and provides the relevant qualification in the page copy.
    """
    if kind == 'penalty-ladder':
        content = (_node('警告', _WARNING) + _arrow()
                   + _node('罚一分', _POINT) + _arrow()
                   + _node('罚一局', _GAME))
        label = '常规行为违例处罚：警告、罚一分、罚一局'
        modifier = 'ladder'
    elif kind == 'event-consequences':
        content = (f'<span class="tl-rule-graphic-origin">失格</span>'
                   f'<svg class="tl-rule-graphic-branch" width="940" height="66" '
                   f'viewBox="0 0 940 66" aria-hidden="true" fill="none" '
                   f'stroke="{_IVORY}" stroke-width="2" stroke-linecap="round" '
                   f'stroke-linejoin="round"><path d="M286 62V24H654V62" '
                   f'stroke-opacity=".65"/><path d="M470 2V24" stroke="{_LIME}"/>'
                   '</svg><div class="tl-rule-graphic-outputs">'
                   + _node('本站积分', _POINTS) + _node('本站奖金', _PRIZE)
                   + '</div>')
        label = '本站该项目的积分与奖金'
        modifier = 'consequences'
    else:
        raise ValueError(f'Unknown tennis rule graphic: {kind}')
    return f'''<style>
.tl-rule-graphic{{width:940px;max-width:100%;position:relative;display:flex;align-items:flex-start;justify-content:space-between;background:transparent}}
.tl-rule-graphic.ladder{{height:240px;padding-top:20px}}
.tl-rule-graphic-node{{width:180px;display:flex;flex-direction:column;align-items:center;gap:18px}}
.tl-rule-graphic-node svg{{flex:none;display:block}}
.tl-rule-graphic.ladder .tl-rule-graphic-node svg{{width:110px;height:110px}}
.tl-rule-graphic-node span{{font-family:'TL Sans SC','Noto Sans CJK SC',sans-serif;font-size:30px;font-weight:400;line-height:1.4;letter-spacing:1px;color:{_IVORY};white-space:nowrap}}
.tl-rule-graphic-arrow{{margin-top:40px;flex:none}}
.tl-rule-graphic.consequences{{display:block;height:260px}}
.tl-rule-graphic-origin{{display:block;text-align:center;font-family:'TL Sans SC','Noto Sans CJK SC',sans-serif;font-size:28px;font-weight:400;line-height:40px;letter-spacing:1px;color:{_IVORY}}}
.tl-rule-graphic-branch{{position:absolute;top:40px;left:0}}
.tl-rule-graphic-outputs{{position:absolute;top:108px;left:0;right:0;display:flex;justify-content:center;gap:128px}}
.tl-rule-graphic-outputs .tl-rule-graphic-node{{width:240px;gap:12px}}
.tl-rule-graphic-outputs .tl-rule-graphic-node svg{{width:96px;height:96px}}
</style><div class="tl-rule-graphic {modifier}" role="group" aria-label="{label}">{content}</div>'''

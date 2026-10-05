"""Reproducible native evidence graphics for the LED replay story.

Uses the project's shared navy palette and embedded official fonts. Text is
based on event-evidence.md and rules-history.md; photos retain provenance.
"""
from pathlib import Path
import base64
from playwright.sync_api import sync_playwright
from tennislive.chromium import launch_chromium
from tennislive.design_tokens import DARK, CARD_BACKGROUND_CSS
from tennislive.render.webcards import _font_css

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'assets/reel/sun-gauff-led-replay-story-2026'
PORTRAIT = 'data:image/jpeg;base64,' + base64.b64encode((OUT / 'portrait.jpg').read_bytes()).decode()

CSS = _font_css() + f"""
*{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1180px;overflow:hidden}}
body{{background:{CARD_BACKGROUND_CSS};color:{DARK['foreground']};font-family:'TL Sans SC',sans-serif}}
.page{{position:relative;padding:64px 70px;height:1180px}}
.eyebrow{{font-family:'Barlow Condensed','TL Sans SC';font-size:27px;letter-spacing:3px;color:{DARK['info']};margin-bottom:26px}}
h1{{font-size:64px;line-height:1.25;letter-spacing:-2px;margin:0 0 28px;font-weight:700}}
h2{{font-size:44px;line-height:1.3;margin:0 0 12px}}p{{font-size:36px;line-height:1.6;margin:0}}
.muted{{color:{DARK['muted-foreground']}}}.accent{{color:{DARK['primary']}}}
.panel{{background:{DARK['card']}dd;border:1px solid {DARK['border']};border-radius:22px;padding:24px 34px;margin-bottom:22px}}
.rule{{height:1px;background:{DARK['border']};margin:24px 0}}
.meta{{font-size:27px;line-height:1.6;letter-spacing:1px;color:{DARK['muted-foreground']}}}
.foot{{position:absolute;left:70px;right:70px;bottom:42px;font-size:24px;line-height:1.55;color:{DARK['muted-foreground']};border-top:1px solid {DARK['border']};padding-top:18px}}
.score{{font-family:'TL Score';font-size:132px;line-height:1.1;letter-spacing:-5px}}
.rows{{display:grid;grid-template-columns:1fr 150px 170px;gap:18px;align-items:center}}
.label{{font-size:32px;line-height:1.5}}.num{{font-family:'TL Score';font-size:76px;line-height:1;text-align:center}}
.step{{display:grid;grid-template-columns:88px 1fr;gap:20px;align-items:center;margin-bottom:28px}}
.index{{font-family:'Barlow Condensed';font-size:64px;color:{DARK['info']}}}
.tag{{display:inline-block;font-size:26px;color:{DARK['primary']};border:1px solid {DARK['border']};border-radius:30px;padding:8px 20px}}
.small{{font-size:30px;line-height:1.45}}.quote{{font-size:46px;line-height:1.6}}
"""

def page(kicker, title, body, footer):
    return '<!DOCTYPE html><html lang="zh"><meta charset="utf-8"><style>'+CSS+'</style><body><main class="page"><div class="eyebrow">'+kicker+'</div><h1>'+title+'</h1>'+body+'<div class="foot">'+footer+'</div></main></body></html>'

PAGES = {
    'score-before': page('BEIJING 2026 · 这一分发生时', '孙心然领先<br>高芙正在发球', '''
      <div class="panel"><div class="rows meta"><span>首盘</span><span style="text-align:center">局分</span><span style="text-align:center">小分</span></div>
      <div class="rule"></div><div class="rows"><span class="label">孙心然</span><span class="num accent">5</span><span class="num">15</span></div>
      <div class="rows" style="margin-top:20px"><span class="label">高芙 · 发球</span><span class="num">4</span><span class="num">15</span></div></div>
      <div class="panel"><div class="meta">孙心然原本赢下的这一分</div><div class="score accent" style="font-size:105px;margin:16px 0">15–15 → 15–30</div><p class="small">小分按发球方高芙的视角排列</p></div>
      <span class="tag">尚未到盘点</span>''', '事件及比分：WTA 官方赛后报道 · 2026.10.05'),
    'score-replay': page('VIDEO REVIEW · 比分怎样退回', '原得分被取消<br>这一分从头再来', '''
      <div class="step"><div class="index">01</div><div><h2>侧边 LED 广告屏闪烁</h2><p class="muted">高芙提出干扰 · 回看支持申诉</p></div></div>
      <div class="panel"><div class="meta">重打前 · 恢复小分</div><div class="score accent" style="margin:14px 0">15–15</div><p class="small">孙心然原本可取得的 15–30 不计入</p></div>
      <div class="step"><div class="index">02</div><div><h2>高芙赢下重打的一分</h2><p class="muted">随后保发 · 首盘局分来到 5–5</p></div></div>
      <p class="small">整场结果：孙心然 5–7、1–6 高芙</p>''', '所有小分均按高芙视角 · 依据 WTA / TennisNow 互证'),
    'rulings': page('RULES · 不同妨碍，怎样判', '外部干扰成立<br>判的是整分重打', '''
      <div class="panel"><div class="meta">本事件适用的判断</div><h2 class="accent">外部、不可控的干扰</h2><p>认定妨碍成立 → 整分重打<br>重新从一发开始</p></div>
      <div class="panel"><h2>对手故意造成妨碍</h2><p class="muted">受影响的球员获得这一分</p></div>
      <div class="panel"><h2>妨碍未被认定成立</h2><p class="muted">原来的得分结果有效</p></div>''', 'WTA VII.H.2.b · ITF Rules 23 / 26<br>2026 WTA Rulebook（7月27日版）'),
    'history': page('PRECEDENTS · 两个相近的旧例', '场外的突然变化<br>也曾让好球重打', '''
      <div class="panel"><div class="meta">2025.05.12 · 罗马</div><h2 style="margin-top:16px">安德列娃 vs 陶森</h2><p>回合中场灯突然开启<br><span class="accent">制胜球被判重打</span></p><div class="rule"></div><p class="small muted">安德列娃一度争论、落泪，最终获胜。</p></div>
      <div class="panel"><div class="meta">2026.10.04 · 中网</div><h2 style="margin-top:16px">兹维列夫 vs 德约科维奇</h2><p>LED 广告变化引发申诉<br><span class="accent">视频复核后重打</span></p></div>''', '罗马：Tennis Channel 原片 / TennisActu<br>中网：Reuters · 10月4日'),
    'advertising': page('TOURNAMENT STANDARDS · 广告切换细则', '准备发球之后<br>广告不得切换', '''
      <div class="panel"><div class="meta">侧墙广告</div><h2 style="margin-top:14px">可以在<span class="accent">两分之间</span>切换</h2></div>
      <div class="panel"><div class="meta">底线后方广告</div><h2 style="margin-top:14px">只能在<span class="accent">两局之间</span>切换</h2></div>
      <div class="panel" style="border-color:#4bb8ff77;margin-top:32px"><div class="meta">两种位置共同的限制</div><h2 class="accent" style="margin-top:16px">球员准备发球后，必须稳定</h2><p class="small muted" style="margin-top:22px">“banners must not change<br>once a player is ready to serve.”</p></div>''', 'WTA XVIII.A.9.c.iii · Court Signage / Banners<br>书页 319 · PDF 第322页'),
    'responsibility': page('ACCOUNTABILITY · 责任不能止于重打', '裁判处理这一分<br>赛事方保障比赛', '''
      <div class="panel"><div class="meta">裁判层面</div><h2 style="margin-top:8px">判断干扰 · 决定重打</h2><p class="small muted">处理场上已经发生的事件</p></div>
      <div class="panel"><div class="meta">赛事运行层面</div><h2 style="margin-top:8px">说明原因 · 排除问题</h2><p class="small muted">确保广告稳定，防止再次发生</p></div>
      <div class="panel"><div class="meta">规则提供的追责机制</div><h2 class="accent" style="margin-top:8px">调查、整改及相应处罚</h2><p class="small muted">包括警告、罚款等；本场处分尚未证实。</p></div>''', '广告标准：XVIII.A.9 · 违规程序：XVIII.A.53<br>责任单位与故障原因仍需赛事方说明'),
    'sun-words': page('SUN XINRAN · 把她的声音留下', '遗憾是真实的<br>期待也来自她自己', f'''
      <div style="display:flex;gap:38px;align-items:center;margin-bottom:24px"><img src="{PORTRAIT}" style="width:270px;height:270px;border-radius:20px;object-fit:cover;object-position:42% 28%"><div style="flex:1"><div class="meta">孙心然 · 咪咕赛后采访</div><p class="quote" style="margin-top:16px">“看到机会<br>从眼前流失”</p></div></div>
      <div class="panel"><p class="small">她把落泪解释为：那一局有机会，<br>却因自己的原因未能拿下。<br>她也说，第二盘情绪受到影响。</p></div>
      <div class="panel"><div class="meta">关于下一次 · 赛后发布会转述</div><h2 class="accent" style="margin-top:14px">吸取经验，会做得更好</h2></div>
      ''', '文字依据：咪咕体育官方采访及赛后发布会<br>本场照片：WTA / Lintao Zhang · Getty Images'),
}

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = launch_chromium(p)
        tab = browser.new_page(viewport={'width':1080,'height':1180}, device_scale_factor=1)
        for name, html in PAGES.items():
            tab.set_content(html)
            tab.evaluate('document.fonts.ready')
            overflow = tab.evaluate('''() => [...document.querySelectorAll('h1,h2,p,.foot')].filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.innerText)''')
            bottoms = tab.evaluate('''() => {const foot=document.querySelector('.foot').getBoundingClientRect().top;return [...document.querySelector('.page').children].filter(e=>!e.classList.contains('foot') && e.getBoundingClientRect().bottom>foot-15).map(e=>e.innerText)}''')
            if bottoms:
                raise ValueError((name, 'footer overlap', bottoms))
            if overflow:
                raise ValueError((name, overflow))
            tab.screenshot(path=str(OUT / (name+'.jpg')), type='jpeg', quality=96)
            print(name)
        browser.close()

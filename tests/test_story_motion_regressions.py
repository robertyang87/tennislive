"""Regressions from independent native checks of the story composer."""
from pathlib import Path

import pytest

from tennislive.video import transition_cards as cards


def _headline(*, start=0, duration=3, frame=None, lines=None):
    return {'kind': 'headline', 'start': start, 'duration': duration,
            'frame': frame or [70, 300, 940, 360],
            'lines': lines or ['冠军之后', '仍要继续比赛'],
            'source': 'https://example.org/review-fixture'}


@pytest.mark.parametrize('path', ['/etc/passwd.jpg', '../private.jpg',
                                  'assets/clip.mp4', 'https://example.org/a.jpg'])
def test_photo_path_is_rejected_by_plan_before_any_file_or_browser_work(path):
    block = {'kind': 'photo', 'start': 0, 'duration': 3, 'pages': [{
        'path': path, 'source': 'https://example.org/review-fixture',
        'date': '2026.01', 'event': '测试摄影'}]}
    with pytest.raises(ValueError, match='图片路径'):
        cards.plan('摄影', {'scene': {'blocks': [block]}})


@pytest.fixture
def native_browser(monkeypatch):
    if not Path('/usr/bin/chromium').is_file():
        pytest.skip('native Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    monkeypatch.setenv('CHROMIUM_PATH', '/usr/bin/chromium')
    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=['--no-sandbox'])
        try:
            yield browser
        finally:
            browser.close()


def _page(browser, block):
    page = browser.new_page(viewport={'width': 1080, 'height': 1440})
    page.set_content(cards.build('测试', content={'scene': {'blocks': [block]}}, seconds=3))
    page.wait_for_function('window.transitionMotion || window.transitionMotionError')
    assert page.evaluate('window.transitionMotionError || null') is None
    page.evaluate('window.setTransitionTime(1.5)')
    return page


def test_local_frame_clipping_fails_even_when_all_global_text_boxes_are_safe(native_browser):
    clipped = _page(native_browser, _headline(frame=[70, 400, 940, 70]))
    try:
        # Both text boxes remain inside the full-canvas brand/subtitle limits;
        # only the component's overflow:hidden cuts the actual glyphs away.
        assert clipped.eval_on_selector_all('.story-line',
            'nodes => nodes.every(n => {const r=n.getBoundingClientRect(); return r.top>=160 && r.bottom<=1244;})')
        with pytest.raises(ValueError, match='frame裁掉内容'):
            cards.check_page(clipped, {'kind': 'scene'})
    finally:
        clipped.close()
    roomy = _page(native_browser, _headline(frame=[70, 400, 940, 300]))
    try:
        # Entrance transforms may paint below the reveal mask briefly. Natural
        # layout fits; those intentional hidden glyphs are not clipped copy.
        for time in (.2, .5, 1.5):
            roomy.evaluate('(t)=>window.setTransitionTime(t)', time)
            assert cards.check_page(roomy, {'kind': 'scene'})['visible_text']
    finally:
        roomy.close()


def test_native_renderer_checks_timeline_summary_after_its_midpoint(tmp_path, monkeypatch):
    if not Path('/usr/bin/chromium').is_file():
        pytest.skip('native Chromium unavailable')
    monkeypatch.setenv('CHROMIUM_PATH', '/usr/bin/chromium')
    timeline = {'kind': 'timeline', 'start': 0, 'duration': 4,
                'events': [{'date': '2025-01-01', 'label': '起点',
                            'source': 'https://example.org/start'},
                           {'date': '2025-02-01', 'label': '回归',
                            'source': 'https://example.org/end'}],
                'resume_label': '回到赛场', 'summary': ['继续出发'*30]}
    # Its late summary appears after the midpoint; the following headline also
    # means the film's last-frame check cannot see the earlier bad summary.
    scene = {'blocks': [timeline, _headline(start=4, duration=2, lines=['下一个阶段'])]}
    target = tmp_path/'overflow.mp4'
    with pytest.raises(ValueError, match='溢出'):
        cards.render_clip('时间线', target, content={'scene': scene}, seconds=6, fps=1)
    assert not target.exists()


@pytest.mark.parametrize('scene', [False, True])
def test_scene_and_legacy_card_both_validate_the_same_native_header(native_browser, scene):
    content = {'scene': {'blocks': [_headline(lines=['重新出发'])]}} if scene else None
    plan = cards.plan('重新出发', content)
    for topic, rejected in [('测试主题', False), ('超出顶部画布的测试主题'*20, True)]:
        page = native_browser.new_page(viewport={'width': 1080, 'height': 1440})
        try:
            page.set_content(cards.build('重新出发', content=content, seconds=3,
                header={'brand': '网球时差 · 网球有故事', 'topic': topic}))
            page.wait_for_function('window.transitionMotion || window.transitionMotionError')
            assert page.evaluate('window.transitionMotionError || null') is None
            page.evaluate('window.setTransitionTime(1.5)')
            if rejected:
                with pytest.raises(ValueError, match='台头溢出'):
                    cards.check_page(page, plan)
            else:
                cards.check_page(page, plan)
        finally:
            page.close()


def test_explainer_scene_after_six_seconds_renders_visible_static_preview(tmp_path, monkeypatch):
    if not Path('/usr/bin/chromium').is_file():
        pytest.skip('native Chromium unavailable')
    from PIL import Image
    from tennislive.video.explainer import ExplainerSegment, render_explainer_slides
    monkeypatch.setenv('CHROMIUM_PATH', '/usr/bin/chromium')
    scene = {'blocks': [_headline(duration=2, lines=['故事起点']),
                        _headline(start=7, duration=2, lines=['再次来到赛场'])]}
    segment = ExplainerSegment(kind='beat', label='新阶段', title='重新出发', narration='测试旁白',
                               visual={'layout': 'transition', 'content': {'scene': scene}})
    inspected = []
    original_check = cards.check_page

    def capture_check(page, plan):
        evidence = original_check(page, plan)
        inspected.extend(row['text'] for row in evidence['visible_text'])
        return evidence

    monkeypatch.setattr(cards, 'check_page', capture_check)
    [target] = render_explainer_slides([segment], tmp_path)
    assert '再次来到赛场' in inspected
    assert '故事起点' not in inspected
    with Image.open(target) as image:
        image = image.convert('RGB')
        sx, sy = image.width / 1080, image.height / 1440
        title = image.crop((int(70*sx), int(300*sy), int(1010*sx), int(660*sy)))
        # Both approved white and yellow-green title glyphs are bright in G;
        # the navy card background is not. The crop excludes brand/footer.
        assert sum(title.getchannel('G').histogram()[180:]) > 1000


def test_second_photo_label_can_enter_from_mask_but_wide_copy_still_fails(tmp_path, monkeypatch, native_browser):
    import shutil
    # A tracked photographic fixture is copied into a temporary repository;
    # this does not depend on locally cached production photos being in CI.
    fixture = Path(__file__).parent/'fixtures/faces/tien-cobolli-poster-aa052bf0.jpg'
    (tmp_path/'assets').mkdir()
    shutil.copyfile(fixture, tmp_path/'assets/photo.jpg')
    monkeypatch.setattr(cards, 'ROOT', tmp_path)
    for event, issue in [('测试摄影', None), ('测'*26, 'label_canvas_margin'), ('测'*60, 'label_overflow')]:
        pages = [{'path': 'assets/photo.jpg', 'source': 'https://example.org/photo-fixture',
                  'date': '2026.01', 'event': text} for text in ('第一张摄影', event)]
        block = {'kind': 'photo', 'start': 0, 'duration': 3, 'pages': pages}
        page = native_browser.new_page(viewport={'width': 1080, 'height': 1440})
        try:
            page.set_content(cards.build('摄影', content={'scene': {'blocks': [block]}}, seconds=3))
            page.wait_for_function('window.transitionMotion || window.transitionMotionError')
            assert page.evaluate('window.transitionMotionError || null') is None
            page.evaluate('window.setTransitionTime(1.51)')
            assert page.eval_on_selector('.spm-page[data-page="1"] .spm-date',
                                         'el=>el.getBoundingClientRect().left') < 0
            if issue is None:
                cards.check_page(page, {'kind': 'scene'})
                assert page.evaluate('window.storyPhotoChecks.flatMap(check=>check())') == []
            else:
                issues = page.evaluate('window.storyPhotoChecks.flatMap(check=>check())')
                assert issue in {row['kind'] for row in issues}
                with pytest.raises(ValueError, match='摄影组件排版溢出'):
                    cards.check_page(page, {'kind': 'scene'})
        finally:
            page.close()

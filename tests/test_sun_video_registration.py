import json
from pathlib import Path
from tools import taste_preflight as T, explainer_preflight as P
from tennislive.video import explainer as E

def test_production_explainer_is_discovered_without_fake_reel():
    kind,path=T.find_spec('sun-xinran-coming-of-age-2026')
    assert kind=='explainer' and path.name.endswith('.production.json')
    assert T.line_of(kind,json.loads(path.read_text()))=='网球有故事'

def test_video_only_exemption_does_not_skip_fact_or_copy_checks():
    rows=dict(P.preflight('sun-xinran-coming-of-age-2026'))
    assert '全称断言' in rows and '假词' in rows and '小红书正文 1000 字' in rows
    assert '每屏要点（无正文字卡，不适用）' in rows
    assert sum(len(b[3]) for b in E._EXTERNAL_VIDEO_SCRIPTS['sun-xinran-coming-of-age-2026'])==1156


def test_external_video_is_not_a_card_deck_or_auto_story():
    from tennislive.render.tournament_story import STORIES, find_story_by_slug
    slug="sun-xinran-coming-of-age-2026"
    assert slug not in E._SCRIPTS
    assert slug not in E._OPENINGS and slug not in E._CAPTIONS and slug not in E._CLAIMS
    assert E.opening_metadata(slug)["question"] == "16岁写进历史\n这一步，她走了很多年"
    assert all(s.slug != slug for s in STORIES)
    assert find_story_by_slug(slug) is not None
    assert len(E._EXTERNAL_VIDEO_SCRIPTS[slug]) == 8


def test_external_narration_places_and_names_keep_locked_identity():
    from tennislive.render.tournament_story import find_story_by_slug
    story=find_story_by_slug("sun-xinran-coming-of-age-2026")
    beats=E.explainer_script(story)[1:]
    assert "贝尔格莱德" in beats[1].narration
    assert all("贝尔格拉弗" not in b.narration and "贝尔格斯" not in b.narration for b in beats)
    assert "孙心然" in story.aliases
    assert [b.narration for b in beats] == [row[3] for row in E._EXTERNAL_VIDEO_SCRIPTS[story.slug]]


def test_external_cover_source_and_publication_registration_are_explicit():
    from tennislive.render.tournament_story import find_story_by_slug
    slug='sun-xinran-coming-of-age-2026'
    story=find_story_by_slug(slug)
    episode=json.loads((Path(E.__file__).parent/'episodes'/f'{slug}.json').read_text())
    assert slug in E.AUTO_PUSH_SLUGS
    assert episode['native_card_render_authorized'] is False
    assert episode['opening']['playback_cover'] is False
    assert episode['opening']['canvas']=='3:4'
    assert episode['opening']['image']==str(story.image)
    assert not Path(episode['opening']['image']).is_absolute()
    assert story.image_source_url=='https://www.tim91.com/en/post/xinran-sun-1'
    assert story.source_url.startswith('https://www.wtatennis.com/news/')
    assert len(episode['source_script_sha256'])==64
    production=json.loads((Path(E.__file__).parents[3]/'specs/explainers'/f'{slug}.production.json').read_text())
    assert [b['narration'] for b in episode['beats']]==[c['narration'] for c in production['chapters']]


def test_external_body_rejects_card_renderer_before_creating_output(tmp_path):
    import pytest
    from tennislive.render.tournament_story import find_story_by_slug
    segments=E.explainer_script(find_story_by_slug("sun-xinran-coming-of-age-2026"))
    assert segments[0].visual is None  # native external poster remains independent
    assert all(s.visual["native_card_render_authorized"] is False for s in segments[1:])
    outdir=tmp_path/"should-not-exist"
    with pytest.raises(ValueError,match="外部视频正文禁止渲染字卡"):
        E.render_explainer_slides(segments,outdir)
    assert not outdir.exists()

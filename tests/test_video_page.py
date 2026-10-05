from datetime import date
from html.parser import HTMLParser
import json
from types import SimpleNamespace

from tennislive.video import explainer as E


class Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_selected_cover_is_player_poster_and_push_opens_that_player(tmp_path, monkeypatch):
    slug = "selected-cover-story"
    outdir = tmp_path / "output" / "2026-10-06" / "explainer" / slug
    outdir.mkdir(parents=True)
    release = "https://github.com/example/repo/releases/download/story/video.mp4"
    (outdir / "render.json").write_text(json.dumps({"video_url": release}))
    monkeypatch.setitem(E._OPENINGS, slug, {"playback_cover": True})
    segment = E.ExplainerSegment("cover", "", "选定的封面", "旁白")
    push = E.explainer_push_html([segment], outdir, date=date(2026, 10, 6),
                               xhs_text="标题\n\n正文")
    tags = Elements((outdir / "watch.html").read_text()).tags
    player = next(attrs for tag, attrs in tags if tag == "video")
    source = next(attrs for tag, attrs in tags if tag == "source")
    assert player["poster"].endswith(f"/explainer/{slug}/slide_00.jpg")
    assert "autoplay" not in player
    assert player["preload"] == "none"
    assert source["src"] == release
    assert f"/explainer/{slug}/watch.html" in push
    assert release not in push


def test_missing_published_player_blocks_message_before_send(tmp_path, monkeypatch):
    from tennislive.cli import cmd_publish_pushplus
    from tennislive.render import pushmsg
    from tennislive.publish import pushplus

    (tmp_path / "push.html").write_text('<a href="https://example.com/watch.html">播放</a>')
    (tmp_path / "watch.html").write_text("approved player page")
    monkeypatch.setattr(pushmsg, "drop_dead_copy_button", lambda markup, **kwargs: (markup, None))
    probes = []

    def unavailable(url, **kwargs):
        probes.append((url, kwargs["expect"]))
        return False

    def must_not_send(*args, **kwargs):
        raise AssertionError("unpublished player must not be sent")

    monkeypatch.setattr(pushmsg, "_probe_page", unavailable)
    monkeypatch.setattr(pushplus, "push", must_not_send)
    assert cmd_publish_pushplus(SimpleNamespace(dir=str(tmp_path), receipt_out="")) == 1
    assert probes == [("https://example.com/watch.html", "approved player page")]

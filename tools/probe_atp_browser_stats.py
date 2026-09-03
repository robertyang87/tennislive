"""Fetch real per-match ATP stats (aces, serve %, break points...) without any paid token.

Every "free" HTTP route to ATP stats is walled: api.protennislive.com wants a
token (401), SofaScore's API 403-blocks datacenter IPs, and atptour.com greets
curl with a Cloudflare JS challenge. But a *real Chromium* passes that
challenge quietly, and once inside, the site's own same-origin JSON feed
serves complete match statistics with no key at all:

    https://www.atptour.com/-/Hawkeye/MatchStats/Complete/{year}/{eventId}/{matchId}

(matchId like "ms002"; the mapping match->id sits on the tournament results
page next to each score line as a /en/scores/stats-centre/archive/... link.)

The catch is entirely environmental, and each piece below was verified here:
  - the MITM proxy cannot digest Chromium's default TLS1.3 ClientHello
    -> launch arg --ssl-version-max=tls1.2 (plus --disable-http2/quic);
  - the proxy CA must be in NSS (~/.pki/nssdb, nickname ccr-agent-proxy);
    context ignore_https_errors covers the request-replay leg as well;
  - the Hawkeye feed itself is behind Cloudflare: plain curl = 403
    "Just a moment...". So the flow is: load one atptour.com page in the
    browser (Cloudflare sets cf_clearance / __cf_bm cookies), then replay
    the JSON URL through the same browser context. Cookies live ~30 min
    (__cf_bm) / hours (cf_clearance); do not cache them across days.

Usage (verified 2026-07-25, Kitzbuhel SF Bublik d. Etcheverry 6-3 6-4):

    python3 tools/probe_atp_browser_stats.py \
        --date 2026-07-24 --event-id 319 --slug kitzbuhel \
        --players bublik etcheverry --out /tmp/atp_stats.json

    # tournament id unknown? let it read the year's results archive first:
    python3 tools/probe_atp_browser_stats.py \
        --date 2026-07-24 --tournament kitzbuhel --players bublik etcheverry

    # match id already known? skips discovery, one page load total:
    python3 tools/probe_atp_browser_stats.py \
        --year 2026 --event-id 319 --match-id ms002

Prints a two-column summary and writes {summary, raw} JSON. Not for
republication: numbers feed research/fact-checking; rights stay with ATP.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWikKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36").replace("AppleWikKit", "AppleWebKit")
BASE = "https://www.atptour.com"
HAWKEYE = BASE + "/-/Hawkeye/MatchStats/Complete/{year}/{event}/{match}"
STATS_LINK = re.compile(r"/scores/stats-centre/archive/(\d{4})/([^/]+)/(ms\d+)", re.I)


def chromium_path() -> str:
    env = os.environ.get("ATP_CHROMIUM")
    if env:
        return env
    # 找 Chromium 只有一份出处（tennislive.chromium）；原来这儿写死 chromium-1194
    # 又只认旧目录名 chrome-linux
    from tennislive.chromium import find_chromium  # noqa: PLC0415
    exe = find_chromium(ask_playwright=False)
    if exe:
        return exe
    raise SystemExit("no chromium found; set ATP_CHROMIUM or CHROMIUM_PATH")


def launch(pw):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return pw.chromium.launch(
        executable_path=chromium_path(),
        headless=True,
        proxy={"server": proxy} if proxy else None,
        args=["--no-sandbox", "--ssl-version-max=tls1.2", "--disable-http2",
              "--disable-quic", "--disable-blink-features=AutomationControlled"],
    )


def goto(page, url: str, label: str) -> None:
    """Navigate and, if Cloudflare interjects, give its JS a moment to clear us."""
    print(f"[load] {label}: {url}", file=sys.stderr)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    for _ in range(6):
        if "just a moment" not in (page.title() or "").lower():
            break
        page.wait_for_timeout(4_000)
    else:
        raise SystemExit(f"Cloudflare challenge did not clear on {url}")
    page.wait_for_timeout(2_500)


def discover_event(page, year: int, tournament: str) -> tuple[str, str]:
    """results-archive page -> (event_id, slug) for a tournament name substring."""
    goto(page, f"{BASE}/en/scores/results-archive?year={year}", "results archive")
    hrefs = page.eval_on_selector_all(
        "a[href*='/scores/archive/']", "els => els.map(e => e.getAttribute('href'))")
    want = tournament.lower()
    for h in hrefs or []:
        m = re.search(r"/scores/archive/([^/]+)/(\d+)/(\d{4})", h or "")
        if m and want in m.group(1).lower():
            return m.group(2), m.group(1)
    raise SystemExit(f"tournament '{tournament}' not found in {year} archive "
                     f"({len(hrefs or [])} archive links scanned)")


def discover_match(page, year: int, event_id: str, slug: str, players: list[str]) -> str:
    """Tournament results page -> the msNNN sitting closest to all wanted names.

    The page is one long hydrated blob, so "which stats link belongs to which
    score card" is answered by character distance: for each stats-centre link,
    take the farthest of the nearest occurrences of every wanted name. On a
    real page the link's own card scores ~100-300, the neighbouring card
    ~1300+, so the minimum is unambiguous; we still demand a 2x margin.
    """
    urls = [f"{BASE}/en/scores/current/{slug}/{event_id}/results",
            f"{BASE}/en/scores/archive/{slug}/{event_id}/{year}/results"]
    html = ""
    for url in urls:
        goto(page, url, "results page")
        html = page.content().lower()
        if STATS_LINK.search(html):
            break
    want = [p.lower() for p in players]
    occ = {p: [m.start() for m in re.finditer(re.escape(p), html)] for p in want}
    missing = [p for p, v in occ.items() if not v]
    if missing:
        raise SystemExit(f"player name(s) {missing} nowhere on the results page "
                         f"— wrong tournament/week, or spell like the site does")
    best: dict[str, int] = {}
    for m in STATS_LINK.finditer(html):
        score = max(min(abs(o - m.start()) for o in occ[p]) for p in want)
        ms = m.group(3).lower()
        if score < 5_000 and score < best.get(ms, 10**9):
            best[ms] = score
    ranked = sorted(best.items(), key=lambda kv: kv[1])
    if not ranked:
        raise SystemExit(f"no stats link within reach of all of {players}")
    if len(ranked) > 1 and ranked[0][1] * 2 > ranked[1][1]:
        raise SystemExit(f"ambiguous between {ranked[:3]}; pass --match-id explicitly")
    return ranked[0][0]


def fetch_stats(ctx, page, year: int, event_id: str, match_id: str) -> dict:
    """Open the match's Stats Centre page and *sniff its own* Hawkeye JSON.

    Replaying the URL out-of-band fails in two instructive ways: ctx.request
    rides Playwright's Node TLS stack (wrong fingerprint for the Cloudflare
    clearance -> 403), and even an in-page fetch() from a *different*
    atptour page 403s — the clearance seems scoped tighter than the cookie
    jar. What always works is letting the Stats Centre page make its own
    request and lifting the response off the wire with page.on('response').
    """
    url = HAWKEYE.format(year=year, event=event_id, match=match_id)
    hit: dict = {}

    def on_response(resp):
        if "/-/Hawkeye/MatchStats/Complete/" in resp.url and not hit:
            try:
                hit["status"] = resp.status
                hit["body"] = resp.body()
                hit["url"] = resp.url
            except Exception as e:  # body already gone, keep the reason
                hit["err"] = str(e)

    page.on("response", on_response)
    try:
        goto(page, f"{BASE}/en/scores/stats-centre/archive/{year}/{event_id}/{match_id}",
             "stats centre")
        for _ in range(20):
            if hit:
                break
            page.wait_for_timeout(1_000)
    finally:
        page.remove_listener("response", on_response)

    if not hit:
        # last resort: ask from inside the page we are now on (same-origin fetch)
        print("[warn] page never called Hawkeye itself; trying in-page fetch", file=sys.stderr)
        res = page.evaluate(
            """async (url) => {
                 const r = await fetch(url, {headers: {accept: 'application/json, text/plain, */*'},
                                             credentials: 'include'});
                 return {status: r.status, text: await r.text()};
               }""", url)
        hit = {"status": res["status"], "body": res["text"].encode(), "url": url}
    if hit.get("status") != 200 or not hit.get("body"):
        raise SystemExit(f"Hawkeye feed failed: {hit.get('status')} {hit.get('err', '')} ({url})")
    data = json.loads(hit["body"])
    data["_source_url"] = hit["url"]
    return data


def _leaf(v):
    if not isinstance(v, dict):
        return v
    if "Percent" in v and v.get("Divisor") is not None:
        return {"pct": v["Percent"], "won": v["Dividend"], "of": v["Divisor"],
                "text": f'{v["Percent"]}% ({v["Dividend"]}/{v["Divisor"]})'}
    if "Number" in v:
        return v["Number"]
    return v


def summarize(data: dict) -> dict:
    m = data["Match"]
    t = data.get("Tournament", {})
    out = {
        "tournament": t.get("EventDisplayName"), "event_id": t.get("EventId"),
        "year": t.get("EventYear"), "round": m.get("RoundName"),
        "match_id": m.get("MatchId"), "status": m.get("MatchStatus"),
        "duration": m.get("MatchTime"), "winner_id": m.get("Winner"),
        "message": (m.get("Message") or "").replace("\r\n", " ").strip(),
        "players": [],
    }
    for side in ("PlayerTeam", "OpponentTeam"):
        team = m.get(side) or {}
        ply = team.get("Player") or {}
        sets = team.get("SetScores") or []
        total = next((s for s in sets if s.get("SetNumber") == 0), None)
        stats = {}
        if total and total.get("Stats"):
            for grp in ("ServiceStats", "ReturnStats", "PointStats"):
                for k, v in (total["Stats"].get(grp) or {}).items():
                    if isinstance(v, dict) and ("Number" in v or "Percent" in v):
                        stats[k] = _leaf(v)
        out["players"].append({
            "name": f'{ply.get("PlayerFirstName", "")} {ply.get("PlayerLastName", "")}'.strip(),
            "id": ply.get("PlayerId"), "country": ply.get("PlayerCountry"),
            "sets": [s.get("SetScore") for s in sets if s.get("SetNumber", 0) > 0],
            "stats": stats,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", help="match date YYYY-MM-DD (fixes the season year)")
    ap.add_argument("--year", type=int, help="season year (default: from --date, else today)")
    ap.add_argument("--tournament", help="tournament name substring, for event-id discovery")
    ap.add_argument("--event-id", help="ATP event id, e.g. 319 for Kitzbuhel")
    ap.add_argument("--slug", help="tournament url slug (default: --tournament value)")
    ap.add_argument("--players", nargs="*", default=[],
                    help="player-name substrings that must all appear on the score card")
    ap.add_argument("--match-id", help="msNNN if already known; skips discovery")
    ap.add_argument("--out", help="write {summary, raw} JSON here")
    a = ap.parse_args()

    year = a.year or (dt.date.fromisoformat(a.date).year if a.date else dt.date.today().year)
    if not a.match_id and not a.players:
        ap.error("need --players (to find the match) or --match-id")
    if not a.event_id and not a.tournament:
        ap.error("need --event-id or --tournament")

    with sync_playwright() as pw:
        browser = launch(pw)
        ctx = browser.new_context(user_agent=UA, locale="en-US",
                                  viewport={"width": 1440, "height": 900},
                                  ignore_https_errors=True)
        page = ctx.new_page()
        try:
            event_id, slug = a.event_id, (a.slug or (a.tournament or "").lower().replace(" ", "-"))
            if not event_id:
                event_id, slug = discover_event(page, year, a.tournament)
                print(f"[info] event id {event_id}, slug {slug}", file=sys.stderr)
            if a.match_id:
                match_id = a.match_id.lower()
                # one page load to earn the Cloudflare cookies before the replay
                goto(page, f"{BASE}/en/scores/stats-centre/archive/{year}/{event_id}/{match_id}",
                     "stats centre")
            else:
                match_id = discover_match(page, year, event_id, slug, a.players)
                print(f"[info] match id {match_id}", file=sys.stderr)
            raw = fetch_stats(ctx, page, year, event_id, match_id)
            cookies = [{"name": c["name"], "expires": c.get("expires")}
                       for c in ctx.cookies(BASE) if "cf" in c["name"].lower()]
        finally:
            browser.close()

    summary = summarize(raw)
    summary["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    summary["source_url"] = raw.get("_source_url")
    summary["cf_cookies"] = cookies

    print(f'\n{summary["tournament"]} {summary["year"]} {summary["round"]} '
          f'({summary["match_id"]}, {summary["duration"]}, status {summary["status"]})')
    print(summary["message"])
    ps = summary["players"]
    if len(ps) == 2:
        keys = [k for k in ps[0]["stats"] if k in ps[1]["stats"]]
        w = max((len(k) for k in keys), default=10)
        print(f'{"":{w}}  {ps[0]["name"]:>24}  {ps[1]["name"]:>24}')
        for k in keys:
            def cell(v):
                return v["text"] if isinstance(v, dict) else str(v)
            print(f'{k:{w}}  {cell(ps[0]["stats"][k]):>24}  {cell(ps[1]["stats"][k]):>24}')

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps({"summary": summary, "raw": raw},
                                          ensure_ascii=False, indent=1))
        print(f"\n[out ] {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

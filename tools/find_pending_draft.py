#!/usr/bin/env python3
"""开工之前先查：这一场球自动链是不是已经 probe 过、草稿卡在哪儿。

来路（2026-09-03 全库 review）：最近发出的 30 条「赛场之上」里 29 条是会话
手写的 spec，而编排器在旁边为同一批比赛跑了 57 次 probe、留下 49 份 pending
草稿——两条路互不复用。`zverev-sonego` 那一场同一天里 `output/2026-09-02/reel/`
下躺着两个目录（`zverev-sonego` 是自动链的，`zverev-sonego-us-open-2026-r1`
是会话的），同一条 1080p 源片下了两遍、缩略图墙拼了两遍、逐分和统计各查了
一遍。probe 那一趟 3~5 分钟，是整条快路里最贵的一步。

用法（按两个姓认，别按 slug 猜——草稿的 slug 是短的）::

    python3 tools/find_pending_draft.py --who Wu,Duckworth
    python3 tools/find_pending_draft.py --slug zverev-sonego
    python3 tools/find_pending_draft.py --who Wu,Duckworth --url <源片地址>   # 连 origin/* 一起按视频 id 认

打出来的每一行都是产物路径，不是推断：草稿文件、它的源片、已落库的
probe 目录（缩略图墙 / 切点 / 死球 / 静音区都在里面）、结构化赛果和统计
在不在、封面落没落、以及 `promote_reel_draft.waiting_reasons` 报的卡点。
找到了就**接着用**：`assemble_spec` 产的 `_match` / `stats` / `_hit_data` /
`_turning_points` 直接搬进正式 spec，probe 目录直接指给 `--dry-run`。

退出码：0 找到了能接着用的——工作区 pending 里的草稿，或 origin/* 上最近
`REF_DAYS` 天动过的同一场的 spec／草稿；2 没有——**没有也要出声**，「没找到」和
「没查」在会话里长得一模一样。**不算「找到」的**（照样列出来，只是不改退出码）：
按姓认出、最近没动过的老 spec（两人上一次交手），以及只在**当前分支自己的**
`origin/<分支>` 上的那份（会话自己推上去的，不是别人做的）。

⭐ 2026-09-27（P6）：**工作区里的 pending 只是三处里的一处。** 还要翻
`origin/main` 和最近几天动过的 `origin/*` 分支上的正式 spec 和草稿——按两个姓、
源片的视频 id（`--url`）、flashscore id（`--fs-id`）认，并把各处用的封面按像素
排一遍。来路：

- `putintseva-bencic`：自动链 23:18Z 就把一张 Getty 本场实拍（843 KB）落在草稿
  里（56e113c3），会话 22 分钟后提交的正式 spec（2fa95f43）**删了那份草稿**，
  用的却是一张 139 KB 的特写——好图就在它删掉的那个文件里，后来重渲一趟才换回来
- `swiatek-bouzkova`：另一份 spec 只在一个 PR 分支上（9d076372 / 38609d98），
  白渲了一趟（908bfe70）

分支上的东西工作区里没有，**没有 ≠ 不存在**（CLAUDE.md「空结果 ≠ 不存在」）：
默认先 `git fetch origin`，读的是 git 对象，不切分支、不动工作区。
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import re
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "specs" / "reels" / "pending"
#: 分支只看最近几天动过的——几十条早就合掉或弃掉的老分支，翻它们只是噪音。
REF_DAYS = 3


def _surnames(draft: dict) -> list[str]:
    out = []
    for p in (draft.get("cover") or {}).get("matchup") or []:
        en = str(p.get("name_en") or "").strip().lower()
        if en:
            out.append(en.split()[-1])
    return out


def _slug_words(slug: str) -> set[str]:
    return set(re.split(r"[-_.]+", slug.lower()))


def matches(draft: dict, slug: str, who: list[str], want_slug: str) -> bool:
    """按**整个姓**认，不按子串——第一版 `n in w` 让 slug 里的单字母 `j`
    命中了 `Nothing`，于是随便两个姓都能「找到」`bublik-j.j.`。"""
    if want_slug:
        return want_slug.lower() in slug.lower()
    names = {n for n in set(_surnames(draft)) | _slug_words(slug) if len(n) >= 2}
    return all(w.lower() in names for w in who)


def probe_dirs(slug: str) -> list[Path]:
    hits = [Path(p).parent for p in glob.glob(str(ROOT / "output" / "*" / "reel" / slug / "probe.json"))]
    return sorted(hits)


def waiting(draft: dict) -> list[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import promote_reel_draft  # noqa: E402
    except Exception as exc:  # pragma: no cover - 环境缺依赖时别把查找一起带崩
        return [f"（waiting_reasons 跑不起来：{type(exc).__name__}: {exc}）"]
    with redirect_stdout(io.StringIO()):
        try:
            return list(promote_reel_draft.waiting_reasons(draft))
        except Exception as exc:
            return [f"（waiting_reasons 崩了：{type(exc).__name__}: {exc}）"]


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def report(path: Path, draft: dict) -> None:
    slug = draft.get("slug") or path.name.replace(".draft.json", "")
    prod = draft.get("_production") or {}
    match = draft.get("_match") or {}
    cover = draft.get("cover") or {}
    portrait = (cover.get("portrait") or {}).get("image")
    print(f"=== {_rel(path)}")
    print(f"    slug {slug} · received_at {prod.get('received_at') or '?'} · "
          f"event {prod.get('event') or '?'} round {prod.get('round') or '（空）'} court {prod.get('court') or '（空）'}")
    print(f"    源片 {draft.get('source_url') or '?'}")
    dirs = probe_dirs(slug)
    if dirs:
        for d in dirs:
            sheets = len(glob.glob(str(d / "contact_*.jpg")))
            print(f"    probe ✅ {_rel(d)}（缩略图墙 {sheets} 张）")
    else:
        print("    probe ❌ 没有落库的 probe.json（这一场还得自己 probe）")
    print(f"    赛果 {match.get('status') or '（无）'}"
          + (f"：{match.get('winner')} {match.get('winner_result')} {match.get('loser')}" if match.get('winner') else "")
          + f" · 统计 {'✅' if draft.get('stats') else '❌'} · 狠数据 {'✅' if draft.get('_hit_data') else '❌'}"
          + f" · 转折点 {'✅' if draft.get('_turning_points') else '❌'}")
    print(f"    封面 {'✅ ' + str(portrait) if portrait and Path(str(portrait)).is_file() else '❌ 官方实拍还没落'}")
    reasons = waiting(draft)
    print(f"    promote 卡点 {len(reasons)} 条" + (f"：{'；'.join(reasons[:4])}{'…' if len(reasons) > 4 else ''}" if reasons else "——可以直接转正"))


class RefHit:
    """别的 ref 上的同一场：一份正式 spec 或草稿。同一个 blob 出现在几个 ref 上只算一条。

    ⚠️ 不用 `@dataclass`：测试按文件路径 `exec_module` 载入这个工具、不进
    `sys.modules`，而 dataclass 解析字符串注解要回 `sys.modules` 找模块，当场炸。
    """

    def __init__(self, path: str, slug: str, by: str) -> None:
        self.path, self.slug, self.by = path, slug, by   # by：两个姓 / 视频 id / flashscore id
        self.refs: list[str] = []
        self.cover = ""                                  # cover.portrait.image
        self.cover_px: tuple[int, int] | None = None
        self.cover_ref = ""
        self.recent = True       # 按姓认出的老 spec 为 False：只列出来，不比封面
        self.column = ""         # spec／草稿自己说的栏目（probe_claims.spec_column）
        self.own = False         # 只在当前分支自己的 origin/<分支> 上：不算「找到」

    @property
    def reusable(self) -> bool:
        """算不算「找到了」（退出码 0）：最近动过、又不是会话自己推上去的那份。"""
        return self.recent and not self.own

    @property
    def match_column(self) -> bool:
        """栏目看不出（老 spec 两样都没写）或者就是赛场之上——封面只在这些里比。"""
        import probe_claims  # noqa: PLC0415
        return self.column in ("", probe_claims.MATCH_COLUMN)


def _spec_urls(doc: dict) -> list[str]:
    urls = [doc.get("source_url"), doc.get("url")]
    for v in (doc.get("sources") or {}).values() if isinstance(doc.get("sources"), dict) else []:
        urls.append(v.get("url") if isinstance(v, dict) else v)
    return [str(u) for u in urls if u]


def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _cover_image(doc: dict) -> str:
    """`cover.portrait.image`；老 spec 里 portrait 有写成字符串的，读不出就当没有。"""
    return str(_dict(_dict(doc.get("cover")).get("portrait")).get("image") or "")


def _pair(doc: dict) -> set[str]:
    """`cover.matchup` 里**所有人**的姓（双打一边两个人，用「/」连）。"""
    out = set()
    for p in _dict(doc.get("cover")).get("matchup") or []:
        for person in str(_dict(p).get("name_en") or "").split("/"):
            if person.strip():
                out.add(person.strip().lower().split()[-1])
    return out


def _match_by(doc: dict, slug: str, who: list[str], keys: set[str], fs_ids: set[str]) -> str:
    """同一场才算：视频 id／flashscore id 精确相等；按姓认时，`matchup` 里的姓
    要**正好**是这两个——双打那份（阿尔卡拉斯/门西克 vs 布勃利克/弗里茨）两个姓
    都带着，却不是这一场（第一版就把它的封面报成了「更大的封面」）。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import probe_claims  # noqa: PLC0415
    if keys and keys & {probe_claims.video_key(u) for u in _spec_urls(doc)}:
        return "视频 id"
    if fs_ids and str((doc.get("_match") or {}).get("flashscore_id") or "") in fs_ids:
        return "flashscore id"
    if who:
        pair = _pair(doc)
        if pair:
            return "两个姓" if pair == {w.lower() for w in who} else ""
        if matches(doc, slug, who, "") and "doubles" not in _slug_words(slug):
            return "两个姓"
    return ""


def _touched_within(ref: str, path: str, days: int, cwd: Path) -> bool:
    """这个文件在这个 ref 上最近 `days` 天改过没有。按姓认出来的老 spec（同两个人
    几个月前那一场）只列出来，不拿去比封面；浅克隆里查不到时间就当是新的。"""
    import git_blobs  # noqa: PLC0415
    try:
        ts = git_blobs.git("log", "-1", "--format=%ct", ref, "--", path, cwd=cwd).strip()
    except git_blobs.GitError:
        return True
    return not ts.isdigit() or int(ts) >= time.time() - days * 86400


def _image_px(raw: bytes | None) -> tuple[int, int] | None:
    if not raw:
        return None
    try:
        from PIL import Image  # noqa: PLC0415
        return Image.open(io.BytesIO(raw)).size
    except Exception:  # 读不出尺寸不许把查找带崩——报「?」就行
        return None


def own_ref(cwd: Path = ROOT) -> str:
    """当前分支自己的 `origin/<分支>`；main／detached 没有（main 上的是合并过的，不是「自己的」）。"""
    import subprocess  # noqa: PLC0415
    res = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=cwd,
                         capture_output=True, text=True)
    branch = res.stdout.strip()
    if res.returncode != 0 or not branch or branch in ("main", "master"):
        return ""
    return f"refs/remotes/origin/{branch}"


def recent_refs(days: int = REF_DAYS, cwd: Path = ROOT) -> list[str]:
    """`origin/main` 打头，再加最近 `days` 天动过的 `origin/*` 分支。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import git_blobs  # noqa: PLC0415
    out = git_blobs.git("for-each-ref", "--format=%(refname) %(committerdate:unix)",
                        "refs/remotes/origin", cwd=cwd)
    cutoff = time.time() - days * 86400
    refs = ["refs/remotes/origin/main"] if git_blobs.rev("refs/remotes/origin/main", cwd=cwd) else []
    for line in out.splitlines():
        ref, _, ts = line.rpartition(" ")
        if ref.endswith("/HEAD") or ref in refs:
            continue
        if ts.isdigit() and int(ts) >= cutoff:
            refs.append(ref)
    return refs


def ref_hits(refs: list[str], who: list[str], keys: set[str], fs_ids: set[str],
             cwd: Path = ROOT) -> list[RefHit]:
    """按 git 对象扫这些 ref 上的 `specs/reels/*.json` 和 pending 草稿。

    几十个 ref × 几百份 spec 大多是同一个 blob：先按 oid 去重、按原文里带不带
    姓／id 粗筛，只 `json.loads` 粗筛命中的那几份。
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import git_blobs  # noqa: PLC0415
    import probe_claims  # noqa: PLC0415
    mine = own_ref(cwd)
    where: dict[str, list[tuple[str, str]]] = {}
    for ref in refs:
        for oid, path in git_blobs.ls_tree(ref, ["specs/reels"], cwd=cwd):
            if re.fullmatch(r"specs/reels/(pending/[^/]+\.draft|[^/]+)\.json", path):
                where.setdefault(oid, []).append((ref, path))
    needles = [n.lower().encode() for n in (*keys, *fs_ids)]
    raw = git_blobs.read_blobs(list(where), cwd=cwd)
    hits: dict[tuple[str, str], RefHit] = {}
    for oid, body in raw.items():
        low = body.lower()
        if not (any(n in low for n in needles)
                or (who and all(w.lower().encode() in low for w in who))):
            continue
        try:
            doc = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for ref, path in where[oid]:
            slug = str(doc.get("slug") or Path(path).name.replace(".draft.json", "").replace(".json", ""))
            by = _match_by(doc, slug, who, keys, fs_ids)
            if not by:
                continue
            hit = hits.setdefault((path, oid), RefHit(path=path, slug=slug, by=by))
            hit.refs.append(ref)
            hit.column = probe_claims.spec_column(doc)
            img = _cover_image(doc)
            if img and not hit.cover:
                hit.cover, hit.cover_ref = img, ref
    for hit in hits.values():
        hit.own = bool(mine) and set(hit.refs) == {mine}
        if hit.by == "两个姓":
            hit.recent = _touched_within(hit.refs[0], hit.path, REF_DAYS, cwd)
        if hit.cover:
            hit.cover_px = _image_px(git_blobs.show(hit.cover_ref, hit.cover, cwd=cwd))
    return sorted(hits.values(), key=lambda h: (h.path, h.refs[0]))


def _short(ref: str) -> str:
    return ref.replace("refs/remotes/", "")


def report_refs(hits: list[RefHit], local_cover: tuple[str, tuple[int, int] | None] | None) -> None:
    """打出别的 ref 上的同一场；封面按像素排，比工作区 spec 用的那张大就喊出来。"""
    print(f"=== 别的 ref 上的同一场（{len(hits)} 份）")
    for h in hits:
        px = f"{h.cover_px[0]}×{h.cover_px[1]}" if h.cover_px else "?"
        refs = "、".join(_short(r) for r in h.refs[:3]) + ("…" if len(h.refs) > 3 else "")
        old = "" if h.recent else f"；最近 {REF_DAYS} 天没动过，多半是两人上一次交手"
        own = "；当前分支自己推上去的" if h.own else ""
        col = "" if h.match_column else f"；{h.column}，不是赛场之上"
        print(f"    {h.path}（{refs}；按{h.by}认出{old}{own}{col}）封面 {h.cover or '（无）'} {px if h.cover else ''}")
    # 只拿「同一场的赛场之上」的封面比：按姓（正好这两个人）或 flashscore id 认出、栏目
    # 不是别的。只按视频 id 认出的多半是故事片借了这条源片——它的封面讲的是另一件事
    # （全库回放：按视频 id 一起比，41 条正式 spec 里大半的「更大的封面」是这种串台）；
    # 按姓认出的也可能是网球有故事（matchup 正好这两个人），同理不比
    covers = [h for h in hits if h.cover_px and h.recent and h.by != "视频 id" and h.match_column]
    if not covers:
        return
    best = max(covers, key=lambda h: h.cover_px[0] * h.cover_px[1])
    area = best.cover_px[0] * best.cover_px[1]
    if local_cover is None:
        print(f"    封面最大的一张：{_short(best.cover_ref)}:{best.cover} "
              f"{best.cover_px[0]}×{best.cover_px[1]}（{best.path}）——写封面之前先看它")
        return
    path, px = local_cover
    if best.cover != path and (px is None or area > px[0] * px[1]):
        mine = f"{px[0]}×{px[1]}" if px else "尺寸读不出"
        print(f"::warning::有一张更大的封面：{_short(best.cover_ref)}:{best.cover} "
              f"{best.cover_px[0]}×{best.cover_px[1]}（{best.path}），"
              f"工作区 spec 用的是 {path}（{mine}）——换之前先打开看情绪对不对题")


def local_cover(who: list[str], keys: set[str], fs_ids: set[str]) -> tuple[str, tuple[int, int] | None] | None:
    """工作区里同一场的正式 spec 用的封面（会话正在写的那份：同一场里最近改过的）。
    只认按姓／flashscore id 认出的——按视频 id 认出的可能是借源的故事片。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import probe_claims  # noqa: PLC0415
    best = None
    for p in (ROOT / "specs" / "reels").glob("*.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if _match_by(doc, p.stem, who, set(), fs_ids) not in ("两个姓", "flashscore id"):
            continue
        if probe_claims.spec_column(doc) not in ("", probe_claims.MATCH_COLUMN):
            continue
        img = _cover_image(doc)
        if img and (best is None or p.stat().st_mtime > best[0]):
            best = (p.stat().st_mtime, img)
    if best is None:
        return None
    f = ROOT / best[1]
    return best[1], _image_px(f.read_bytes()) if f.is_file() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--who", default="", help="两个姓，逗号分隔（英文，按 name_en 的姓认）")
    ap.add_argument("--slug", default="", help="按草稿 slug 的子串认")
    ap.add_argument("--url", action="append", default=[],
                    help="源片地址（按视频 id 认别的 ref 上的 spec；可给多次）")
    ap.add_argument("--fs-id", action="append", default=[], help="flashscore 比赛 id")
    ap.add_argument("--no-refs", action="store_true", help="只看工作区的 pending，不翻 origin/*")
    ap.add_argument("--no-fetch", action="store_true", help="翻 origin/* 之前不先 git fetch")
    args = ap.parse_args()
    who = [w.strip() for w in args.who.split(",") if w.strip()]
    if not who and not args.slug and not args.url and not args.fs_id:
        ap.error("要么 --who A,B，要么 --slug / --url / --fs-id")
    sys.path.insert(0, str(ROOT / "tools"))
    import probe_claims  # noqa: PLC0415
    keys = {k for k in (probe_claims.video_key(u) for u in args.url) if k}
    fs_ids = {f.strip() for f in args.fs_id if f.strip()}
    found = 0
    if who or args.slug:
        for path in sorted(PENDING.glob("*.draft.json")):
            try:
                draft = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"⚠️ {path.name} 读不出来：{exc}")
                continue
            if matches(draft, path.name.replace(".draft.json", ""), who, args.slug):
                report(path, draft)
                found += 1
        if not found:
            print(f"pending 里没有匹配 {who or args.slug} 的草稿（扫了 {len(list(PENDING.glob('*.draft.json')))} 份）——"
                  "这一场自动链没 probe 过，或者草稿已经清掉；自己 probe 之前先 `ls output/*/reel/` 再确认一次")
    if not args.no_refs and (who or keys or fs_ids):
        found += _refs_section(who, keys, fs_ids, fetch=not args.no_fetch)
    return 0 if found else 2


def _refs_section(who: list[str], keys: set[str], fs_ids: set[str], *, fetch: bool) -> int:
    """翻 origin/*，返回**算「找到」的**那几份（`RefHit.reusable`）的份数。"""
    import git_blobs  # noqa: PLC0415
    if fetch:
        try:
            git_blobs.git("fetch", "--quiet", "--prune", "origin", cwd=ROOT)
        except git_blobs.GitError as exc:
            print(f"⚠️ git fetch origin 失败，下面按本地已有的 origin/* 查（可能是旧的）：{exc}")
    try:
        refs = recent_refs(cwd=ROOT)
        hits = ref_hits(refs, who, keys, fs_ids, cwd=ROOT)
    except git_blobs.GitError as exc:
        print(f"⚠️ 翻 origin/* 没翻成（{exc}）——这一半**没查**，不是查过没有")
        return 0
    if not hits:
        print(f"origin/main 和最近 {REF_DAYS} 天动过的 {max(len(refs) - 1, 0)} 个分支上"
              "都没有这一场的 spec 或草稿（按姓／视频 id／flashscore id 查过）")
        return 0
    report_refs(hits, local_cover(who, keys, fs_ids))
    reusable = sum(h.reusable for h in hits)
    if not reusable:
        print(f"    上面 {len(hits)} 份都不算能接着用的（最近 {REF_DAYS} 天没动过的老交手，"
              "或只在当前分支自己的那份）")
    return reusable


if __name__ == "__main__":
    sys.exit(main())

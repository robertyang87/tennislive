#!/usr/bin/env python3
"""拿两档英文转写（`data/source_asr/<视频 id>/`）排窗口、查 spec、生成原声审听包。

来路（2026-10-12 `wangxiyu-wangxinyu-wuhan-2026-r1`）：转写拿回来之后，「哪几秒没有英文、
旁白能放在哪」是对着两份转写用眼睛排的，审听包是临时脚本手搓的，前后十几分钟。
`foreground_audio_gate` 的三条硬规矩（TTS 窗口不许有英文、不许切断英文句子、每句英文都要
中英字幕）都能拿转写在写 spec 时就查，不必等 render 的审听闸。

三个用法::

    # ① 排旁白：这段源片里哪几截没有英文解说（够长的才列）
    python3 tools/asr_plan.py gaps --video-id y9d6IHw0cZk --from 0 --to 300

    # ② 查 spec：TTS 窗口里的英文、切断的句子、没配字幕的英文，一次全报
    python3 tools/asr_plan.py check --spec specs/reels/<slug>.json

    # ③ ② 全过之后生成审听包和索引（data/audio_reviews/<slug>.json + 逐窗口证据）
    python3 tools/asr_plan.py write-review --spec specs/reels/<slug>.json

⚠️ 这是**转写交叉核对**（`method: asr_cross_checked`），不是人工听审，包里照实写。
字幕的英文和中文仍由写 spec 的人定（`quote`），这个工具只核「转写听到的每一句都被字幕盖住」。
⚠️ 时间码按 ±0.3 秒算：whisper 的句子边界本来就有这么大的抖动。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

MODELS = ("small.en", "medium.en")
#: 句子边界的抖动（秒）：重叠／伸出不到这么多不算
SLACK = 0.3
#: 只有一档听到、且置信度低于它的句子，按「疑似幻听」只报不拦
HALLUCINATION_LOGPROB = -1.0


#: whisper 常把句首／句尾那个词拉长去吃掉静音（`is.` 13.56–15.00、`And` 264.82–266.22），
#: 一个词按最多 0.7 秒算
MAX_WORD = 0.7


@dataclass
class Sentence:
    model: str
    start: float
    end: float
    text: str
    logprob: float

    def label(self) -> str:
        return f"{self.start:.2f}–{self.end:.2f}s「{self.text[:70]}」（{self.model}）"


def asr_dir(video_id: str, root: Path = ROOT) -> Path:
    return root / "data/source_asr" / video_id


def load(video_id: str, root: Path = ROOT) -> tuple[dict[str, dict], str]:
    """两档转写 ＋ 它们共同的源片 sha256。缺一档、或两档转的不是同一份字节，直接报错。"""
    docs = {}
    for model in MODELS:
        path = asr_dir(video_id, root) / f"{model}.json"
        if not path.is_file():
            raise SystemExit(f"没有 {path}——先跑 source-asr.yml（probe 用上 Release 存档时会自动派发）")
        docs[model] = json.loads(path.read_text(encoding="utf-8"))
    shas = {d.get("source_sha256") for d in docs.values()}
    if len(shas) != 1:
        raise SystemExit(f"两档转写的源片字节不一样：{shas}")
    return docs, shas.pop()


def sentences(docs: dict[str, dict]) -> list[Sentence]:
    """逐词时间码按句末标点切句，每档各切各的（两档的句子边界不一样，硬并会连成一大坨）。"""
    out: list[Sentence] = []
    for model, doc in docs.items():
        words: list[tuple[float, float, str, float]] = []

        def flush() -> None:
            if words:
                out.append(Sentence(model, words[0][0], words[-1][1],
                                    "".join(w[2] for w in words).strip(), min(w[3] for w in words)))
                words.clear()

        for seg in doc.get("segments") or []:
            lp = float(seg.get("avg_logprob", 0.0))
            for w in seg.get("words") or []:
                s, e = float(w["s"]), float(w["e"])
                s, e = max(s, e - MAX_WORD), min(e, s + MAX_WORD)
                words.append((s, max(s, e), str(w["w"]), lp))
                if str(w["w"]).strip().endswith((".", "?", "!")):
                    flush()
            flush()   # 段尾没有句号也收：下一段可能隔了很久
    return sorted(out, key=lambda x: x.start)


def _overlaps(x: Sentence, others: list[Sentence]) -> bool:
    return any(min(x.end, o.end) - max(x.start, o.start) > 0 for o in others)


def doubtful(sent: Sentence, all_sents: list[Sentence]) -> bool:
    """只有一档听到、而且置信度低——疑似幻听（片尾颁奖背景里 medium.en 编出来的那几句）。"""
    other = [o for o in all_sents if o.model != sent.model]
    return sent.logprob < HALLUCINATION_LOGPROB and not _overlaps(sent, other)


def gaps(sents: list[Sentence], start: float, end: float, min_gap: float = 2.5) -> list[tuple[float, float]]:
    """[start, end) 里两档都没有英文的几截（两头各让 0.2 秒），短于 `min_gap` 的不列。疑似幻听不算英文。"""
    out, cursor = [], start
    for u in (u for u in sents if not doubtful(u, sents)):
        if u.end <= start or u.start >= end:
            continue
        a, b = cursor, min(u.start, end)
        if b - a >= min_gap:
            out.append((round(a + 0.2, 2), round(b - 0.2, 2)))
        cursor = max(cursor, u.end)
    if end - cursor >= min_gap:
        out.append((round(cursor + 0.2, 2), round(end - 0.2, 2)))
    return out


def _primary(spec: dict) -> str:
    return next(iter(spec.get("sources") or {"": ""}))


def _windows(spec: dict, source: str | None = None) -> list[tuple[int, dict]]:
    """取源片的段；给了 `source` 就只要这一条源的（多源片子各自对各自的转写）。"""
    primary = _primary(spec)
    return [(i, seg) for i, seg in enumerate(spec.get("segments") or [])
            if "start" in seg and "end" in seg and not seg.get("image")
            and (source is None or str(seg.get("source", primary)) == source)]


def _cues(seg: dict) -> list[tuple[float, float, str, str]]:
    """这一段的原声字幕，换算成源片绝对秒：`(起, 止, 英文, 中文)`。"""
    from foreground_audio_gate import _quote_windows  # noqa: PLC0415  同一套 at/end 解析
    start, speed = float(seg["start"]), float(seg.get("speed") or 1)
    out = []
    for at, until, text in _quote_windows(seg) if seg.get("quote") else []:
        en, _, zh = str(text).partition("\n")
        out.append((start + at * speed, start + until * speed, en.strip(), zh.strip()))
    return out


def _covered(lo: float, hi: float, cues: list[tuple[float, float, str, str]]) -> bool:
    """[lo, hi) 被双语字幕盖住：一句话常跨两条相邻字幕，按并集算，字幕之间留不到 0.6 秒的缝不算漏。"""
    cursor = lo + SLACK
    for a, b, en, zh in sorted(cues):
        if not (en and zh):
            continue
        if a > cursor + 0.6:
            break
        cursor = max(cursor, b)
    return cursor >= hi - SLACK


def _issues(spec: dict, sents: list[Sentence], model: str, everyone: list[Sentence],
            source: str | None = None) -> list[tuple]:
    """这一档转写看到的问题：`(段序号, 类型, 起, 止, 说明)`。"""
    found = []
    for i, seg in _windows(spec, source):
        a, b = float(seg["start"]), float(seg["end"])
        narrated = bool(str(seg.get("narration") or "").strip())
        try:
            cues = _cues(seg)
        except (KeyError, TypeError, ValueError) as exc:   # 字幕时间越出片段、重叠——审听闸同样红
            found.append((i, "cue", a, b, f"原声字幕本身不合规：{exc}"))
            cues = []
        for u in (x for x in sents if x.model == model):
            if min(b, u.end) - max(a, u.start) <= SLACK or doubtful(u, everyone):
                continue
            if u.start < a - SLACK or u.end > b + SLACK:
                edge = f"start 挪到 {u.start - 0.2:.2f}" if u.start < a - SLACK else f"end 挪到 {u.end + 0.2:.2f}"
                found.append((i, "cut", u.start, u.end, f"切断了英文句子 {u.label()}——{edge}，或把这句整个让出去"))
            elif narrated:
                found.append((i, "tts", u.start, u.end,
                              f"配了中文旁白，而窗口里有英文 {u.label()}——英文那几秒单独分段配双语字幕，"
                              "或把窗口收到英文之外（`gaps` 列出能放旁白的空当）"))
            elif not _covered(max(a, u.start), min(b, u.end), cues):
                speed = float(seg.get("speed") or 1)
                found.append((i, "uncued", u.start, u.end,
                              f"这句英文没有中英字幕盖住 {u.label()}——补一条 quote："
                              f"at≈{(max(a, u.start) - a) / speed:.2f} end≈{(min(b, u.end) - a) / speed:.2f}"))
    return found


def check(spec: dict, sents: list[Sentence], source: str | None = None) -> tuple[list[str], list[str]]:
    """`(硬伤, 只报)`：两档转写**都**看到的问题算硬伤（render 的审听闸必红的那几类），
    只有一档看到的只报——那正是交叉核对要人去对一下原话的地方。

    `source`：多源片子只查这一条源的段（`sents` 是这条源的转写）。"""
    per = {m: _issues(spec, sents, m, sents, source) for m in MODELS}
    hard, soft = [], []
    for model in MODELS:
        other = [x for m in MODELS if m != model for x in per[m]]
        for i, kind, lo, hi, msg in per[model]:
            agreed = any(o[0] == i and o[1] == kind and min(hi, o[3]) - max(lo, o[2]) > 0 for o in other)
            line = f"第 {i + 1} 段 {float(spec['segments'][i]['start']):.2f}–{float(spec['segments'][i]['end']):.2f}s：{msg}"
            if not agreed:
                soft.append(line + "（另一档没看到，写之前对一下原话）")
            elif model == MODELS[-1]:
                hard.append(line)        # 两档都看到的，只按 medium.en 那句报一次
    return hard, soft


def _evidence(video_id: str, sha: str) -> str:
    paths = [f"data/source_asr/{video_id}/{m}.json" for m in MODELS]
    return (f"两档 faster-whisper 转写（{' / '.join(MODELS)}，逐词时间码，源片 sha256 {sha}，"
            f"存于 {' 与 '.join(paths)}），由 tools/asr_plan.py 逐句对照：窗口内转写听到的每一句"
            f"都被一条中英字幕盖住、没有句子被切断、配音窗口里没有英文")


def write_review(spec: dict, video_id: str | dict[str, tuple[str, str]], sha: str = "",
                 root: Path = ROOT) -> Path:
    """按 spec 当前的计划写审听包：每个保留原声的窗口一份，`foreground_english` 取自 `quote`。

    单源给 `video_id, sha`；多源给 `{源键: (视频 id, sha)}`，每个窗口挂它自己那条源的证据。"""
    from foreground_audio_gate import plan_hash  # noqa: PLC0415

    slug = str(spec["slug"])
    folder = root / "data/audio_reviews" / slug
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    urls = spec.get("sources") or {"": spec.get("source_url")}
    primary = next(iter(urls))
    ids = video_id if isinstance(video_id, dict) else {k: (video_id, sha) for k in urls}
    entries = []
    for i, seg in _windows(spec):
        key = str(seg.get("source", primary))
        vid, vsha = ids[key]
        evidence = _evidence(vid, vsha)
        a, b = float(seg["start"]), float(seg["end"])
        said = [{"start": round(c[0], 2), "end": round(c[1], 2), "en": c[2], "zh": c[3]} for c in _cues(seg)]
        packet = {"source_url": urls[key], "source_sha256": vsha,
                  "method": "asr_cross_checked",
                  "reviewer": "tools/asr_plan.py（两档 ASR 交叉核对；未声称人工听审）",
                  "reviewed_at": now, "reviewed_from": a, "reviewed_to": b, "status": "complete",
                  "uncertain_spans": [], "foreground_english": said, "evidence": evidence}
        if not said:
            packet["no_foreground_english_reason"] = (f"{evidence}。{a:.2f}–{b:.2f}s 两档转写都没有英文句子"
                                                      "（疑似幻听的单档低置信句不计）。")
        name = f"{i:02d}-{a:.2f}-{b:.2f}.json"
        path = folder / name
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        entries.append({"index": i, "transcript_path": path.relative_to(root).as_posix(),
                        "transcript_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    index = root / "data/audio_reviews" / f"{slug}.json"
    index.write_text(json.dumps({"schema": "tennislive.foreground-audio-review.v1",
                                 "plan_sha256": plan_hash(spec), "segments": entries},
                                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index


def source_ids(spec: dict) -> dict[str, str]:
    """`{源键: 视频 id}`——每条源各自对自己的转写（`data/source_asr/<视频 id>/`）。"""
    from probe_claims import video_key  # noqa: PLC0415

    urls = spec.get("sources") or {"": spec.get("source_url")}
    used = {str(seg.get("source", _primary(spec))) for _i, seg in _windows(spec)}
    ids = {}
    for key in sorted(used):
        vid = video_key(str(urls.get(key) or ""))
        if not vid:
            raise SystemExit(f"源 {key!r}（{urls.get(key)}）认不出视频 id——只认 YouTube 地址或 Release 存档直链")
        ids[key] = vid
    return ids


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gaps")
    g.add_argument("--video-id", required=True)
    g.add_argument("--from", dest="start", type=float, default=0.0)
    g.add_argument("--to", dest="end", type=float, default=0.0)
    g.add_argument("--min-gap", type=float, default=2.5)
    for name in ("check", "write-review"):
        p = sub.add_parser(name)
        p.add_argument("--spec", required=True, type=Path)
    args = ap.parse_args()

    if args.cmd == "gaps":
        docs, _sha = load(args.video_id)
        utts = sentences(docs)
        end = args.end or max(float(d.get("duration") or 0) for d in docs.values())
        print(f"{args.start:.1f}–{end:.1f}s 里没有英文解说、≥{args.min_gap}s 的空当（可放中文旁白）：")
        for a, b in gaps(utts, args.start, end, args.min_gap):
            print(f"  {a:7.2f} – {b:7.2f}  （{b - a:.1f}s）")
        return 0

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    hard, soft, evidence = [], [], {}
    for key, vid in source_ids(spec).items():
        docs, sha = load(vid)
        evidence[key] = (vid, sha)
        h, s_ = check(spec, sentences(docs), key)
        hard += h
        soft += s_
    for line in soft:
        print(f"  [只报] {line}")
    if hard:
        print(f"\n{len(hard)} 处过不了原声审听闸：")
        for line in hard:
            print(f"  ✗ {line}")
        return 1
    if args.cmd == "check":
        print("原声窗口全过：配音窗口没有英文、没有切断的句子、每句英文都有中英字幕")
        return 0
    index = write_review(spec, evidence)
    print(f"已写审听包：{index}（逐窗口证据在 {index.with_suffix('')}/）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

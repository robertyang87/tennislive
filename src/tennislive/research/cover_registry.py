"""Which cover-image channels actually deliver, remembered across runs.

Every run already writes a per-run `cover_visual.json` with a full provider
breakdown, but that file is thrown away the moment the next run starts. So the
same question got re-asked every morning and answered the same way: the four
stock libraries were queried, returned nothing, and the package fell back to
the branded background -- with no record that they had *also* returned nothing
the previous eight mornings for exactly this kind of match.

This registry is that record. It accumulates, per channel:

  runs        -- how many packages queried it
  candidates  -- how many images it ever handed back
  selections  -- how many times one of those images became the cover

`selections` is the only number that matters for ranking; a channel that
returns fifty thumbnails that never survive the identity and pixel checks is
worth less than one that returns a single usable photo. `barren_channels()`
names the ones that have been asked repeatedly, errored never, and produced
nothing -- proof the source simply has no coverage of these players rather
than proof it is broken. That distinction is what lets the resolver stop
walking the same dead end and reach for a wider channel instead.

The file lives in `data/` and rides along on the workflow's `git add data/`,
so the memory survives the ephemeral runner.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "data" / "cover_source_registry.json"

# 连续查过这么多期仍然 0 候选、0 报错，就认定这个源对这类比赛没有覆盖
BARREN_RUN_THRESHOLD = 3
SCHEMA_VERSION = 1


@dataclass
class ChannelRecord:
    """One image channel's cumulative track record."""

    channel: str
    runs: int = 0
    # 只有带 provider_results 记账的那几期才算数：更早的报告里"被查过"和
    # "查了返回 0 张"长得一样，拿它当证据会把没量过的源冤枉成没覆盖。
    measured_runs: int = 0
    candidates: int = 0
    selections: int = 0
    errors: int = 0
    retired: bool = False
    first_seen: str = ""
    last_run: str = ""
    last_candidate: str = ""
    last_selected: str = ""
    last_error: str = ""
    # 最近一次中选时用的是哪条比赛，方便人工复核"这个渠道真的取到过现场图"
    last_selected_match: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_proven(self) -> bool:
        return self.selections > 0 and not self.retired

    @property
    def is_barren(self) -> bool:
        return (
            self.measured_runs >= BARREN_RUN_THRESHOLD
            and self.candidates == 0
            and self.errors == 0
        )


def _default_registry() -> dict:
    return {"schema_version": SCHEMA_VERSION, "channels": {}}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, ChannelRecord]:
    """Read the registry; a missing or corrupt file is an empty memory."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        logger.warning("封面渠道台账读取失败，按空台账处理: %s", exc)
        return {}
    channels = raw.get("channels")
    if not isinstance(channels, dict):
        return {}
    out: dict[str, ChannelRecord] = {}
    for name, row in channels.items():
        if not isinstance(row, dict):
            continue
        fields = {f for f in ChannelRecord.__dataclass_fields__ if f != "channel"}
        kwargs = {k: v for k, v in row.items() if k in fields}
        notes = kwargs.get("notes")
        kwargs["notes"] = [str(n) for n in notes] if isinstance(notes, list) else []
        try:
            out[str(name)] = ChannelRecord(channel=str(name), **kwargs)
        except TypeError as exc:  # 台账结构变化不该拖垮出片
            logger.warning("封面渠道台账条目 %s 解析失败，已跳过: %s", name, exc)
    return out


def save_registry(records: dict[str, ChannelRecord], path: Path = REGISTRY_PATH) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "channels": {
            name: {k: v for k, v in asdict(record).items() if k != "channel"}
            for name, record in sorted(records.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass
class _ChannelRun:
    """One channel's contribution to one run."""

    candidates: int = 0
    error: str = ""
    # False 时只记 runs，不记 measured_runs：这一期没量过它的产出
    measured: bool = False


def _channels_in_report(report: dict) -> dict[str, _ChannelRun]:
    """Per channel: candidates returned, first error, and whether it was measured."""
    queried = [str(name) for name in report.get("providers_queried", []) or []]
    out: dict[str, _ChannelRun] = {name: _ChannelRun() for name in queried}
    results = report.get("provider_results") or {}
    if isinstance(results, dict):
        for name, stat in results.items():
            if not isinstance(stat, dict):
                continue
            errors = stat.get("errors") or []
            out[str(name)] = _ChannelRun(
                candidates=int(stat.get("candidates") or 0),
                error=str(errors[0])[:200] if isinstance(errors, list) and errors else "",
                measured=True,
            )
    # 这几条不走 provider_results，但报告里各自有自己的计数字段
    for name, key in (
        ("official-recap-search", "official_recap_candidates"),
        ("wta-video-hub", "wta_video_hub_candidates"),
        ("official-match-media", "editorial_source_urls"),
    ):
        found = report.get(key)
        if found is None:
            continue
        run = out.get(name)
        if run is None or not run.measured:
            out[name] = _ChannelRun(candidates=int(found or 0), measured=True)
    return out


def record_cover_run(
    report: dict,
    *,
    today: date,
    path: Path = REGISTRY_PATH,
) -> dict[str, ChannelRecord]:
    """Fold one run's cover report into the registry and persist it."""
    if str(report.get("status", "")) in {"disabled", ""}:
        return load_registry(path)

    records = load_registry(path)
    stamp = today.isoformat()
    selected = str(report.get("provider", "")).strip()
    match_id = str(report.get("match_id", ""))

    # 台账按"期"记账，不按"运行次数"。同一天重跑（改完文案重出一版）不该
    # 让这几个源看起来又被证伪了一次——barren 判定靠的是连着多少期没货，
    # 一天之内跑三遍并不构成三期证据。
    for name, run in _channels_in_report(report).items():
        record = records.get(name) or ChannelRecord(channel=name, first_seen=stamp)
        if record.last_run == stamp:
            continue
        record.runs += 1
        record.last_run = stamp
        if run.measured:
            record.measured_runs += 1
        record.candidates += run.candidates
        if run.candidates:
            record.last_candidate = stamp
        if run.error:
            record.errors += 1
            record.last_error = f"{stamp} {run.error}"
        records[name] = record

    if selected:
        record = records.get(selected) or ChannelRecord(channel=selected, first_seen=stamp)
        already = record.last_selected == stamp and record.last_selected_match == match_id
        if not already:
            # 中选的渠道可能没进 providers_queried（比如从官方页扩展出来的候选）
            if record.last_run != stamp:
                record.runs += 1
                record.last_run = stamp
            record.selections += 1
            record.last_selected = stamp
            record.last_selected_match = match_id
        records[selected] = record

    try:
        save_registry(records, path)
    except OSError as exc:  # 写不进台账不该拖垮出片
        logger.warning("封面渠道台账写入失败: %s", exc)
    return records


def proven_channels(path: Path = REGISTRY_PATH) -> tuple[str, ...]:
    """Channels that have produced a published cover, best track record first."""
    records = load_registry(path)
    return tuple(
        name
        for name, record in sorted(
            records.items(),
            key=lambda row: (row[1].selections, row[1].last_selected),
            reverse=True,
        )
        if record.is_proven
    )


def barren_channels(path: Path = REGISTRY_PATH) -> tuple[str, ...]:
    """Channels repeatedly queried without error that never returned an image."""
    records = load_registry(path)
    return tuple(sorted(name for name, record in records.items() if record.is_barren))


def should_widen_search(
    stock_channels: tuple[str, ...],
    path: Path = REGISTRY_PATH,
) -> bool:
    """True when history says the default channels will not deliver today.

    Every stock library having been asked at least `BARREN_RUN_THRESHOLD` times
    and never once answered is not bad luck -- it is coverage those libraries do
    not have. Going out to the tour newsroom costs one extra request and is the
    difference between a real match photo and the branded background.
    """
    if not stock_channels:
        return False
    barren = set(barren_channels(path))
    return all(name in barren for name in stock_channels)


def registry_summary(path: Path = REGISTRY_PATH) -> dict:
    """Compact view for the run log and the cover report.

    Read at the moment it is called. The resolver calls it before searching, so
    the snapshot in `cover_visual.json` is the history the widen decision was
    made on -- it does not include the run that report describes.
    """
    records = load_registry(path)
    return {
        "as_of": "run-start",
        "proven": list(proven_channels(path)),
        "barren": list(barren_channels(path)),
        "channels": {
            name: {
                "runs": record.runs,
                "candidates": record.candidates,
                "selections": record.selections,
                "errors": record.errors,
                "last_selected": record.last_selected,
            }
            for name, record in sorted(records.items())
        },
    }

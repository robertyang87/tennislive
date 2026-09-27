"""已推送的采访，推送之后 spec 又改了——算不算一次要重渲重推的修订。

## 来路

`tien-cobolli-laver-cup-2026-interview` 9/26 18:57 推上微信，11 分钟后
9ae8918f 收掉片尾板、换了封面帧——**然后 5 小时 43 分钟没人管**，到 9/27 00:51
才重渲重推。同一个提交也改了 `ruud-cerundolo-laver-cup-2026-presser`（19:02 推送、
19:08 换封面帧），重渲在 00:56，5 小时 53 分钟（发布账本 / git log 量的）。
原因在 `pick_interview_renders.todo_slugs`：目录里有 `pushed.json` 的一律
`continue`，除非 spec 带着 `_publication_revision`——**不报、不记、不进等待名单**，
而手改 spec 的会话根本不知道要写那个标记。

那道跳过本来是对的，防的是「过期的生成器改了 spec 的字节」被当成一次新请求
（`build_interview_request` 已经不许改受保护的 spec，但别的批量改动仍然会改字节）。
CLAUDE.md 09-22 又定了「**重渲之后默认就是重推**」。两头合起来，判据是：

| 推送之后改了什么 | 怎么办 |
|---|---|
| 只改了 `_` 开头的注解（`_why`、`_facts`…） | 成片不会变，**不重渲**（照旧跳过） |
| 改了会进成片的字段，且推送不到 `AUTO_REVISION_HOURS` | **当成一次修订**，自动重渲 → 自动重推 |
| 改了内容，但推送已经过了那个窗口 | 不自动重渲，**进等待名单说清楚**：要重渲就写 `_publication_revision` |
| spec 写了 `_publication_revision`（显式修订） | 照原来的规矩：`base_film_sha256` 对得上才放行 |

「改没改内容」拿**内容指纹**比：spec 去掉所有 `_` 开头的键（逐层）之后的规范 JSON
的 sha256，出片那一趟由 `check_interview_landed.write_attestation` 记进
`qc_attestation.json["spec_content_sha256"]`。**只有新出的片子有这个指纹**——
它上线之前的产物一律按原来的规矩走（不猜、不批量唤醒旧片）。

窗口取 24 小时：上面两次滞后的修订，spec 都是推送后 6～11 分钟就改完的；
而全库量过，现在有 7 条已推送的 spec 推送之后改过会进成片的字段（`event`、`opening`、
`zh`/`en_fixed`、`cover`/`push`、`source_verification`），其中 6 条推送于 9/5～9/25——
**不该**因为一次几天后的改动把一条旧片子重新推一遍微信。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

AUTO_REVISION_HOURS = 24


def _strip_notes(value):
    if isinstance(value, dict):
        return {k: _strip_notes(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_strip_notes(v) for v in value]
    return value


def content_sha256(spec: dict) -> str:
    """去掉所有 `_` 开头的键之后的规范 JSON 的 sha256——「会进成片的那部分」的指纹。"""
    blob = json.dumps(_strip_notes(spec), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _parse_at(raw: str) -> datetime | None:
    try:
        return datetime.strptime(str(raw), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def post_push_edit(spec: dict, pushed: dict, qc: dict | None,
                   now: datetime) -> tuple[bool, str]:
    """(要不要当成修订重渲, 不重渲时给等待名单的一句话——空＝安静跳过)。"""
    if not qc or qc.get("film_sha256") != pushed.get("film_sha256"):
        return False, ""        # 推出去的不是这份 QC 的片子，推不出推送时的 spec
    recorded = str(qc.get("spec_content_sha256") or "")
    if not recorded:
        return False, ""        # 内容指纹上线之前的产物：照原来的规矩，不批量唤醒
    if content_sha256(spec) == recorded:
        return False, ""        # 只改了注解，成片不会变
    at = _parse_at(pushed.get("at") or "")
    if at is not None and now - at <= timedelta(hours=AUTO_REVISION_HOURS):
        return True, ""
    return False, (f"已推送（{pushed.get('at') or '时刻没记'}），推送之后改了会进成片的字段，"
                   f"但已过 {AUTO_REVISION_HOURS} 小时的自动修订窗口——要重渲重推就写 "
                   "`_publication_revision`（id ＋ base_film_sha256＝pushed.json 的 film_sha256）")

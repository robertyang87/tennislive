"""用维基百科核验 PLAYER_ZH 译名（CI 运行，本地网络不可达）.

批量接口：en.wikipedia langlinks 每请求 50 个标题（全量仅 ~8 请求，
避免逐条请求触发限流），中文标题用 zhconv 本地转为简体后比对。

输出三类：
  MISMATCH  维基有中文条目且与词典不一致 → 需人工复核
  NO_PAGE   维基无中文条目 → 保留拟译（低排位球员常见）
  OK        一致

注意：中文维基部分条目用词与大陆媒体不同（如 兹维列夫/兹韦列夫），
MISMATCH 仅作复核线索，不自动改写；大陆媒体用法优先。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests
from zhconv import convert

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.zh.players import PLAYER_ZH  # noqa: E402

S = requests.Session()
S.headers["User-Agent"] = "tennislive-name-check/2.0 (github.com/robertyang87/tennislive)"

API = "https://en.wikipedia.org/w/api.php"


def batch_langlinks(titles: list[str]) -> dict[str, str]:
    """英文标题（≤50 个）→ 中文条目标题；含重定向/规范化回溯."""
    for attempt in range(4):
        r = S.get(
            API,
            params={
                "action": "query", "format": "json", "prop": "langlinks",
                "lllang": "zh", "lllimit": "max", "redirects": 1,
                "titles": "|".join(titles),
            },
            timeout=30,
        )
        if r.status_code == 200:
            try:
                data = r.json()
                break
            except ValueError:
                pass
        time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"API 连续失败: HTTP {r.status_code}")

    q = data.get("query", {})
    # 请求名 → 页面名 的映射链（normalized + redirects）
    trace: dict[str, str] = {}
    for n in q.get("normalized", []) or []:
        trace[n["from"]] = n["to"]
    for rd in q.get("redirects", []) or []:
        trace[rd["from"]] = rd["to"]

    def resolve(name: str) -> str:
        seen = set()
        while name in trace and name not in seen:
            seen.add(name)
            name = trace[name]
        return name

    by_title: dict[str, str] = {}
    for page in (q.get("pages") or {}).values():
        for ll in page.get("langlinks", []) or []:
            by_title[page.get("title", "")] = ll.get("*", "")
    return {t: by_title.get(resolve(t), "") for t in titles}


def main() -> int:
    names = list(PLAYER_ZH)
    mapping: dict[str, str] = {}
    for i in range(0, len(names), 50):
        chunk = names[i : i + 50]
        mapping.update(batch_langlinks(chunk))
        time.sleep(1.5)

    mismatch, no_page, ok = [], [], 0
    for en, ours in PLAYER_ZH.items():
        wiki = mapping.get(en) or ""
        if not wiki:
            no_page.append(en)
            continue
        cn = convert(wiki, "zh-cn")
        if ours.replace("·", "") in cn.replace("·", ""):
            ok += 1
        else:
            mismatch.append((en, ours, cn))

    print(f"\n=== 结果：OK {ok} / MISMATCH {len(mismatch)} / NO_PAGE {len(no_page)} ===\n")
    print("--- MISMATCH（需人工复核，大陆用法优先） ---")
    for en, ours, wiki in mismatch:
        print(f"MISMATCH | {en} | 词典={ours} | 维基zh-cn={wiki}")
    print("\n--- NO_PAGE（维基无中文条目，保留拟译） ---")
    for en in no_page:
        print(f"NO_PAGE | {en} | {PLAYER_ZH[en]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

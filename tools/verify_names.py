"""用维基百科核验 PLAYER_ZH 译名（CI 运行，本地网络不可达）.

对每个英文名：en.wikipedia langlinks → 中文条目 → zh-cn 变体显示标题，
与词典值比对（词典多为姓氏，比对采用"词典值是否为维基标题的子串"）。

输出三类：
  MISMATCH  维基有中文条目且与词典不一致 → 需人工复核
  NO_PAGE   维基无中文条目 → 保留拟译（低排位球员常见）
  OK        一致

注意：中文维基部分条目偏港台用法，MISMATCH 仅作复核线索，
不自动改写；大陆媒体（新华社/百度百科）用法优先。
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.zh.players import PLAYER_ZH  # noqa: E402

S = requests.Session()
S.headers["User-Agent"] = "tennislive-name-check/1.0 (github.com/robertyang87/tennislive)"


def zh_title(en_name: str) -> str | None:
    r = S.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query", "format": "json", "prop": "langlinks",
            "lllang": "zh", "titles": en_name, "redirects": 1, "lllimit": "max",
        },
        timeout=20,
    )
    for page in (r.json().get("query", {}).get("pages") or {}).values():
        for ll in page.get("langlinks", []) or []:
            return ll.get("*")
    return None


def zh_cn_variant(title: str) -> str:
    r = S.get(
        "https://zh.wikipedia.org/w/api.php",
        params={
            "action": "parse", "format": "json", "page": title,
            "prop": "displaytitle", "variant": "zh-cn",
        },
        timeout=20,
    )
    dt = (r.json().get("parse") or {}).get("displaytitle")
    return re.sub(r"<[^>]+>", "", dt) if dt else title


def main() -> int:
    mismatch, no_page, ok = [], [], 0
    for en, zh in PLAYER_ZH.items():
        try:
            title = zh_title(en)
            if not title:
                no_page.append(en)
            else:
                cn = zh_cn_variant(title)
                # 词典值通常是姓氏（或 中文名 全称），子串匹配即视为一致
                if zh.replace("·", "") in cn.replace("·", "") or zh in cn:
                    ok += 1
                else:
                    mismatch.append((en, zh, cn))
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {en}: {e}")
        time.sleep(0.1)
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

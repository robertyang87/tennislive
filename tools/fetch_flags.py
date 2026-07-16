"""预下载全部国旗小图到 assets/flags/（CI 环境运行，见 assets.yml）.

覆盖 zh/countries.py 中映射到 ISO2 的所有国家/地区，56x42 PNG 每张 1-3KB。
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.render.flags import ASSETS_DIR, FLAG_H, FLAG_W  # noqa: E402
from tennislive.zh.countries import IOC  # noqa: E402


def main() -> int:
    codes = sorted({iso2 for _, iso2 in IOC.values() if iso2})
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, []
    for iso2 in codes:
        path = ASSETS_DIR / f"{iso2.lower()}.png"
        if path.exists():
            ok += 1
            continue
        try:
            resp = requests.get(
                f"https://flagcdn.com/{FLAG_W}x{FLAG_H}/{iso2.lower()}.png",
                timeout=15,
            )
            resp.raise_for_status()
            path.write_bytes(resp.content)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append(f"{iso2}: {e}")
    print(f"flags: {ok}/{len(codes)} ok")
    for line in fail:
        print("FAIL", line)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

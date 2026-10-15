set -x
mkdir -p cover_out
python3 tools/find_cover_photo.py --player Osaka --event Wimbledon --date 2026-07-07 2>&1 | tail -80
python3 tools/find_cover_photo.py --player Muchova --event Wimbledon --date 2026-07-07 2>&1 | tail -60

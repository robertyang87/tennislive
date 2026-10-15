set -x
mkdir -p cover_out
python3 tools/find_cover_photo.py --player Zheng --event "Australian Open" --date 2025-01-09 --zh 郑钦文 --zh 德约科维奇 --city 墨尔本 2>&1 | tail -120

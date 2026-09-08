"""Add source-resolution match-point evidence after the prior audit stopped.

Retain all four full-source sheets and the rejected audit in the draft. This
adds previously unsampled one-second frames; it never edits model verdicts.
"""
from pathlib import Path
from build_match_reel import contact_sheet

out = Path('output/2026-09-09/reel/sabalenka-noskova')
source = out / 'source.mp4'
assert source.is_file(), 'Fresh source required for detailed evidence'
sheets = contact_sheet(source, out / 'payoff-detail', every=1.0,
                       columns=4, tile_w=640, start=166.0, stop=180.0)
assert len(sheets) == 1
(out / 'contact_04_detail.jpg').write_bytes(sheets[0].read_bytes())
print('Added 166–180s source-resolution, 1-second payoff evidence; full-source sheets retained.')

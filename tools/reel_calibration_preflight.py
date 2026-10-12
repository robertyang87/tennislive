"""赛场之上的比分框校准前检；采访入口不依赖此模块。"""
from __future__ import annotations


def check_custom_scoreboxes(spec: dict) -> None:
    """当前赛场之上自定义框的廉价前检；复用 CI 的同源扫描判据。"""
    from probe_sources import dry_run_mode
    if dry_run_mode() in {'cover', 'narration'}:
        return  # 不编码比赛画面，这两档保持既有不依赖 probe 的策略。
    from probe_board import CALIBRATED, custom_scorebox_findings, same_box, scoreboxes_by_url
    from reel_facts import broadcast_profile, spec_tour, us_open_match_line

    line1 = str((spec.get('topbar') or {}).get('line1', ''))
    if spec.get('layout') == 'band':
        profile = 'us-open' if us_open_match_line(line1) else None
    else:
        profile = broadcast_profile(
            line1, str((spec.get('_production') or {}).get('event') or ''), spec_tour(spec))
    if profile not in CALIBRATED:
        return
    urls = spec.get('sources') or {'': spec.get('source_url')}
    owned = scoreboxes_by_url(spec, urls)
    if not any(not any(same_box(box, cal) for cal in CALIBRATED[profile])
               for boxes in owned.values() for box in boxes):
        return
    # 用生产端已有的 URL 认领逻辑；不下载、不解码、不碰其他 slug 的 spec。
    from build_match_reel import probes_for_spec
    probes, _missing = probes_for_spec(spec)
    hard, soft = custom_scorebox_findings(spec, probes, profile=profile)
    for note in soft:
        print(f'[自定义比分框] {note}')
    if hard:
        raise SystemExit('；'.join(hard))

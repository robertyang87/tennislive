"""Exact RNA10 exhibition recipe; no permission to publish without stats."""
def video_without_tour_stats(spec):
    from reviewed_effects_mode import enabled
    cover=spec.get('cover') or {}
    return (spec.get('slug')=='nadal-academy-10th-2026'
        and spec.get('original_audio_mode')=='reviewed_effects'
        and enabled(spec)
        and (spec.get('push') or {}).get('auto') is False
        and (cover.get('scoreboard') or {}).get('result_format')=='team_exhibition'
        and str(spec.get('_stats_availability_why') or '').strip()
        and not spec.get('stats'))

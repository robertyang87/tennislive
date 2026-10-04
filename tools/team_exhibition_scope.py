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


def local_exhibition_context(spec, opening):
    """RNA10 官方只核实当地活动日期，不能编造北京时间或巡回赛轮次。"""
    from reviewed_effects_mode import enabled, SLUG
    if spec.get('slug') != SLUG or not enabled(spec):
        return False
    context = (spec.get('editorial') or {}).get('human_context') or {}
    source = ('https://www.rafanadalacademy.com/en/news/'
              'rafa-nadal-academy-celebrates-its-10th-anniversary-in-style-as-team-rafa-claims-victory/')
    facts = context.get('facts') or []
    return (source in (context.get('sources') or [])
            and any('2026-10-03' in fact and '未核开球时刻' in fact for fact in facts)
            and all(word in opening for word in ('当地十月三日', '马纳科尔', '学院十周年表演赛')))

"""Bounded review routing; URL hints are never evidence of on-court footage."""
import re
from urllib.parse import urlsplit

MAX_REVIEW_BATCH = 5
MAX_UNCERTAIN_BATCH = 2


def trusted_source(item, cfg):
    return next((s for s in cfg['sources'] if s['name'] == item.get('source')
                 and s.get('verified') is True
                 and s.get('provenance') in ('official', 'broadcaster')
                 and not s.get('unofficial') and not item.get('unofficial')), None)


def source_url_hint(item, cfg):
    source = trusted_source(item, cfg)
    if not source or source.get('fetch') != 'tennistv':
        return None
    try:
        url = urlsplit(item.get('url', ''))
        match = re.fullmatch(r'/videos/(\d+)/([a-zA-Z0-9-]+)', url.path)
        if (url.scheme != 'https' or url.netloc != 'www.tennistv.com'
                or url.query or url.fragment or not match
                or item.get('id') != 'tennistv:' + match[1]):
            return None
        words = set(match[2].lower().split('-'))
        if 'interview' in words and not words.intersection({'press', 'conference', 'preview'}):
            return 'official_interview_url'
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def review_reason(item, result, cfg):
    if result.get('decision') == 'source_url_review':
        return 'source_url_hint'
    if result.get('suggestion') == 'interview':
        return 'model_interview'
    if result.get('suggestion') == 'uncertain' and trusted_source(item, cfg):
        return 'model_uncertain'
    return None

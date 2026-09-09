#!/usr/bin/env python3
"""Read-only visual audit of one explicitly requested Zheng press conference.

Only writes its evidence directory and minimax_visual_audit.json; never edits a
spec, render/QC attestation, publication ledger, or sends a notification.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SLUG = 'zheng-rybakina-us-open-2026-qf-presser'
ENDPOINT = 'https://api.minimaxi.com/v1/chat/completions'
MODEL = 'MiniMax-M3'
EXPECTED = {'interviewee': '郑钦文', 'scene': 'press_conference',
            'not_mirrored': True, 'same_program': True, 'cover_clear_frontal_eyes_open': True,
            'bilingual_subtitles_readable': True, 'no_face_obstruction': True,
            'brand_ending': True}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def normalize_result(result):
    normalized = json.loads(json.dumps(result))
    if isinstance(normalized, dict):
        for key, expected in EXPECTED.items():
            row = normalized.get(key)
            if type(expected) is bool and isinstance(row, dict):
                value = row.get('value')
                if type(value) is str and value in ('true', 'false'):
                    row['value'] = value == 'true'
    return normalized


def assess(result):
    issues = []
    for key, expected in EXPECTED.items():
        row = result.get(key, {}) if isinstance(result, dict) else {}
        if not isinstance(row, dict):
            issues.append(key + ': malformed')
            continue
        confidence = row.get('confidence')
        ids = row.get('image_ids')
        valid_ids = (isinstance(ids, list) and bool(ids)
                     and all(type(i) is int and 1 <= i <= 11 for i in ids))
        if key == 'same_program':
            valid_ids = valid_ids and 1 in ids and any(2 <= i <= 7 for i in ids)
        if key == 'not_mirrored':
            valid_ids = valid_ids and any(i in (10, 11) for i in ids)
        if key == 'cover_clear_frontal_eyes_open':
            valid_ids = valid_ids and ids == [1]
        if key == 'bilingual_subtitles_readable':
            valid_ids = valid_ids and any(2 <= i <= 7 for i in ids)
        if key == 'brand_ending':
            valid_ids = valid_ids and 9 in ids
        valid = (isinstance(confidence, (int, float)) and not isinstance(confidence, bool)
                 and math.isfinite(confidence) and .85 <= confidence <= 1)
        if (type(row.get('value')) is not type(expected)
                or row.get('value') != expected or not valid
                or len(str(row.get('evidence', '')).strip()) < 8
                or not valid_ids):
            issues.append(key + ': failed or insufficient evidence/confidence')
    return issues


def run():
    out = ROOT / 'output' / 'interviews' / SLUG
    audit_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    evidence = out / 'minimax_visual_evidence' / audit_id
    evidence.mkdir(parents=True, exist_ok=True)
    report_path = out / 'minimax_visual_audit.json'
    history = out / 'visual_audit_history'
    history.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        shutil.copy2(report_path, history / ('prior-' + digest(report_path) + '.json'))
    spec_path = ROOT / 'specs' / 'interviews' / (SLUG + '.json')
    render_path = out / 'render.json'
    report = {'audit_revision': 'source-attribution-native-crops-v2', 'audit_id': audit_id,
              'slug': SLUG, 'model': MODEL, 'status': 'fail', 'pass': False,
              'created_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'sampled final-film visual evidence; not full-film or audio verification',
              'source_exception': 'User explicitly requested this press conference; press_conference is valid; no lead-in required',
              'issues': []}
    film_dir = Path(tempfile.mkdtemp(prefix='zheng-visual-film-'))
    try:
        spec = json.loads(spec_path.read_text())
        render = json.loads(render_path.read_text())
        report['spec_sha256'] = digest(spec_path)
        report['render_sha256'] = digest(render_path)
        if (spec.get('slug') != SLUG or spec.get('requested_content_type') != 'press_conference'
                or spec.get('opening', {}).get('kind') != 'none'):
            raise ValueError('Unexpected source contract or lead-in for this scoped audit')
        source = spec.get('source_verification', {})
        metadata = spec.get('_request_origin', {}).get('request', {}).get('source_metadata', {})
        if (spec.get('featured_player') != '郑钦文'
                or source.get('source_id') != 'youtube:2C7_q05gGUk'
                or source.get('status') != 'verified'
                or metadata.get('video_id') != '2C7_q05gGUk'
                or metadata.get('channel_id') != 'UCXbboag48Qlr78zzz6SkzkQ'
                or metadata.get('channel') != 'US Open Tennis Championships'):
            raise ValueError('Official source attribution missing or mismatched')
        report['source_attribution'] = {
            'featured_player': spec['featured_player'], 'title': spec.get('source_title'),
            'metadata': metadata, 'verification': source,
            'identity_method': 'official-source attribution, not face recognition'}
        qc = json.loads((out / 'qc_attestation.json').read_text())
        if qc.get('spec_sha256') != report['spec_sha256']:
            raise ValueError('QC spec hash differs from checked-out spec')
        key = os.environ.get('MINIMAX_API_KEY', '').strip()
        if not key:
            raise ValueError('MINIMAX_API_KEY is missing')
        film = film_dir / (SLUG + '.mp4')
        subprocess.run(['gh', 'release', 'download', 'interview-' + SLUG,
                        '--repo', 'robertyang87/tennislive', '--pattern', SLUG + '.mp4',
                        '--dir', str(film_dir), '--clobber'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
        report['film_sha256'] = digest(film)
        if render.get('film_sha256') != report['film_sha256']:
            raise ValueError('Release film hash differs from render metadata')
        duration = float(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(film)], text=True, timeout=30))
        if not 320 <= duration <= 360:
            raise ValueError('Unexpected final film duration')
        samples = [(0.15, 'actual opening cover'), (8, 'press conference opening'),
                   (35, 'body speaker and subtitles'), (75, 'body speaker and subtitles'),
                   (165, 'body speaker and subtitles'), (230, 'body speaker and subtitles'),
                   (295, 'body speaker and subtitles'), (duration - 5, 'closing'),
                   (duration - 2, 'brand ending')]
        images, entries = [], []
        for i, (stamp, role) in enumerate(samples, 1):
            frame = evidence / f'frame_{i:02d}.jpg'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                            '-ss', str(stamp), '-i', str(film), '-frames:v', '1',
                            '-q:v', '2', str(frame)], check=True, capture_output=True, timeout=60)
            entries.append({'image_id': i, 'seconds': stamp, 'role': role,
                            'path': str(frame.relative_to(out)), 'sha256': digest(frame)})
            images.append({'type': 'image_url', 'image_url': {'url':
                'data:image/jpeg;base64,' + base64.b64encode(frame.read_bytes()).decode()}})
        # Native source-backdrop pixels: no overlay subtitles and no upscaling.
        for i, crop, role in [(10, '380:200:700:300', 'source backdrop right text'),
                              (11, '350:300:0:230', 'source backdrop left logo')]:
            frame = evidence / f'frame_{i:02d}.jpg'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                            '-ss', '8', '-i', str(film), '-vf', 'crop=' + crop,
                            '-frames:v', '1', '-q:v', '1', str(frame)],
                           check=True, capture_output=True, timeout=60)
            entries.append({'image_id': i, 'seconds': 8, 'role': role,
                            'crop_whxy': crop, 'derived_from_image_id': 2,
                            'path': str(frame.relative_to(out)), 'sha256': digest(frame)})
            images.append({'type': 'image_url', 'image_url': {'url':
                'data:image/jpeg;base64,' + base64.b64encode(frame.read_bytes()).decode()}})
        report['frames'] = entries
        prompt = '''你是最终成片视觉审核员。视觉属性仅凭所附图片判断；interviewee按官方来源归属核对，不做面部身份识别。不要为了过闸猜测。
本条为用户明确指定的郑钦文2026美网赛后新闻发布会：press_conference是合法内容，
无需获胜冷开场，不能按场上采访模板拒绝新闻发布会。图1才是实际封面；图2-7是正文；
图8-9是结尾。图10-11是图2对应电影时刻的原像素源背景裁切，不含后加字幕，供文字方向核查。
不得用其他正文帧代替图1证明封面双眼睁开。仅审核抽样视觉，不能宣称
完整音频、字幕翻译语义或全片同步已核验。非镜像必须以原拍摄背景可读标志/文字举证，
不能仅以后加中文字幕正常方向推断源画面未镜像。看不清标记unknown且低置信度。
逐项返回JSON对象，每项包含value、confidence(0到1)、evidence(具体可见证据)、image_ids(整数数组)。
必需项及预期值：interviewee="郑钦文"；scene="press_conference"；not_mirrored=true；
same_program=true（封面与正文服装、背景、发布会情境一致，非人脸识别）；
cover_clear_frontal_eyes_open=true（仅图1，清晰正脸且双眼自然睁开）；
bilingual_subtitles_readable=true（正文中英字幕可读、无截字、无明显互相重叠）；
no_face_obstruction=true（封面和正文文字不挡脸）；brand_ending=true（图9网球时差片尾）。
interviewee项不是让你从脸识别人名：核对附带官方标题、频道、视频ID、source_verification及featured_player
是否一致归属于郑钦文发布会，并描述画面发布会语境是否吻合该来源。必须区分官方署名证据与可见场景证据，
不可说从脸认出；来源有冲突、归属不充分则unknown。其他视觉项证据必须来自图片。\n图片映射：'''
        prompt += json.dumps(entries, ensure_ascii=False)
        prompt += '\n官方来源绑定：' + json.dumps(report['source_attribution'], ensure_ascii=False)
        payload = {'model': MODEL, 'messages': [{'role': 'user', 'content':
                    [{'type': 'text', 'text': prompt}] + images}],
                   'max_tokens': 4000, 'thinking': {'type': 'disabled'}}
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read())['choices'][0]['message']['content'].strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        raw_result = json.loads(raw)
        report['raw_result'] = raw_result
        result = normalize_result(raw_result)
        report['result'] = result
        report['issues'] = assess(result)
        report['pass'] = not report['issues']
        report['status'] = 'pass' if report['pass'] else 'fail'
    except Exception as exc:
        # No API response bodies, headers, URLs with credentials, or secret values in logs.
        report['issues'].append('Audit incomplete: ' + type(exc).__name__)
        if isinstance(exc, ValueError):
            report['issues'].append(str(exc)[:200])
    finally:
        shutil.rmtree(film_dir, ignore_errors=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    (history / (audit_id + '.json')).write_text(serialized)
    report_path.write_text(serialized)
    print('MiniMax scoped visual audit: ' + report['status'])
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(run())

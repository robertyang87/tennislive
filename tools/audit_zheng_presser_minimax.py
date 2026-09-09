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
                     and all(type(i) is int and 1 <= i <= 9 for i in ids))
        if key == 'cover_clear_frontal_eyes_open':
            valid_ids = valid_ids and ids == [1]
        if key == 'same_program':
            valid_ids = valid_ids and 1 in ids and any(2 <= i <= 7 for i in ids)
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
    evidence = out / 'minimax_visual_evidence'
    evidence.mkdir(parents=True, exist_ok=True)
    report_path = out / 'minimax_visual_audit.json'
    spec_path = ROOT / 'specs' / 'interviews' / (SLUG + '.json')
    render_path = out / 'render.json'
    report = {'slug': SLUG, 'model': MODEL, 'status': 'fail', 'pass': False,
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
        report['frames'] = entries
        prompt = '''你是最终成片视觉审核员。仅凭所附图片判断，不要为了过闸猜测。
本条为用户明确指定的郑钦文2026美网赛后新闻发布会：press_conference是合法内容，
无需获胜冷开场，不能按场上采访模板拒绝新闻发布会。图1才是实际封面；图2-7是正文；
图8-9是结尾。不得用其他正文帧代替图1证明封面双眼睁开。仅审核抽样视觉，不能宣称
完整音频、字幕翻译语义或全片同步已核验。非镜像必须以原拍摄背景可读标志/文字举证，
不能仅以后加中文字幕正常方向推断源画面未镜像。看不清标记unknown且低置信度。
逐项返回JSON对象，每项包含value、confidence(0到1)、evidence(具体可见证据)、image_ids(整数数组)。
必需项及预期值：interviewee="郑钦文"；scene="press_conference"；not_mirrored=true；
same_program=true（图1与正文图2-7属于同一美网发布会，须具体比较人物、服装及赛事背景，引用图1及正文图号）；
cover_clear_frontal_eyes_open=true（仅图1，清晰正脸且双眼自然睁开）；
bilingual_subtitles_readable=true（正文中英字幕可读、无截字、无明显互相重叠）；
no_face_obstruction=true（封面和正文文字不挡脸）；brand_ending=true（图9网球时差片尾）。
说明必须来自图片，不可把我给的人名/场景信息当视觉证据。\n图片映射：'''
        prompt += json.dumps(entries, ensure_ascii=False)
        payload = {'model': MODEL, 'messages': [{'role': 'user', 'content':
                    [{'type': 'text', 'text': prompt}] + images}],
                   'max_tokens': 2400, 'thinking': {'type': 'disabled'}}
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(),
                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = json.loads(response.read())['choices'][0]['message']['content'].strip()
        if raw.startswith('```'):
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(raw)
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
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('MiniMax scoped visual audit: ' + report['status'])
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    sys.exit(run())

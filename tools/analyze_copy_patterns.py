#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘点 specs/ 下成品 spec 的文案模式，产出统计与例句库（供《完整流程和要求》总文档用）。
用法: python3 tools/analyze_copy_patterns.py
"""
import json, glob, os, re, statistics

REELS = sorted(glob.glob('specs/reels/*.json'))
INTERVIEWS = sorted(glob.glob('specs/interviews/*.json'))
XHS = sorted(glob.glob('specs/**/*.xhs.txt', recursive=True))

def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def cjk_len(s):
    return len(s)

# ---------------- 1. reel 字段结构 ----------------
push_keys, cover_keys = {}, {}
seg_key_sets = {}
with_editorial = []
narration_seg_counts = []   # 每条片子的旁白段数
narration_lens = []         # 每段旁白字数
no_narration = []
for p in REELS:
    d = load(p)
    if 'editorial' in d:
        with_editorial.append((p, d['editorial']))
    pk = tuple(sorted(d.get('push', {}).keys()))
    push_keys[pk] = push_keys.get(pk, 0) + 1
    ck = tuple(sorted(d.get('cover', {}).keys()))
    cover_keys[ck] = cover_keys.get(ck, 0) + 1
    segs = d.get('segments', [])
    narrs = [s.get('narration', '') for s in segs if s.get('narration')]
    narration_seg_counts.append((p.split('/')[-1], len(segs), len(narrs)))
    for s in segs:
        sk = tuple(sorted(s.keys()))
        seg_key_sets[sk] = seg_key_sets.get(sk, 0) + 1
        n = s.get('narration')
        if n:
            narration_lens.append(len(n))
    if not narrs:
        no_narration.append(p.split('/')[-1])

# ---------------- 2. editorial 文案示例 ----------------
ed_examples = []
for p, ed in with_editorial:
    hc = ed.get('human_context', {})
    angle = hc.get('angle', '') if isinstance(hc, dict) else ''
    ed_examples.append({
        'slug': p.split('/')[-1].replace('.json', ''),
        'mode': ed.get('mode'),
        'question': ed.get('question', ''),
        'thesis': ed.get('thesis', ''),
        'angle': angle,
        'beats': ed.get('beats', []),
    })

# ---------------- 4. interview 字段 ----------------
int_with_quote = []
int_with_takeaway = []
int_cover_keys = {}
int_push_keys = {}
for p in INTERVIEWS:
    d = load(p)
    slug = p.split('/')[-1].replace('.json', '')
    if 'human_quote' in d:
        int_with_quote.append((slug, d['human_quote'], d.get('human_quote_ok', '')))
    if 'takeaway' in d:
        int_with_takeaway.append((slug, d['takeaway']))
    ck = tuple(sorted(d.get('cover', {}).keys()))
    int_cover_keys[ck] = int_cover_keys.get(ck, 0) + 1
    pk = tuple(sorted(d.get('push', {}).keys()))
    int_push_keys[pk] = int_push_keys.get(pk, 0) + 1

# ---------------- 5. xhs 结构 ----------------
xhs_samples = {}
for p in XHS:
    with open(p, encoding='utf-8') as f:
        t = f.read()
    slug = p.replace('specs/', '').replace('.xhs.txt', '')
    lines = [l for l in t.split('\n')]
    hashtags = [l for l in lines if l.strip().startswith('#')]
    xhs_samples[slug] = {'text': t, 'n_lines': len(lines), 'hashtags': hashtags}

# ---------------- 6. 手法例句库 ----------------
# 收集所有旁白 + hook + push.lead + question + thesis 为语料
corpus = []
def add(slug, kind, text):
    if text:
        corpus.append((slug, kind, text))
for p in REELS:
    d = load(p)
    slug = p.split('/')[-1].replace('.json', '')
    if 'editorial' in d:
        ed = d['editorial']
        add(slug, 'question', ed.get('question'))
        add(slug, 'thesis', ed.get('thesis'))
    hook = (d.get('cover') or {}).get('hook', '')
    add(slug, 'hook', hook)
    add(slug, 'push.lead', (d.get('push') or {}).get('lead'))
    for i, s in enumerate(d.get('segments', [])):
        add(slug, f'narration[{i}]', s.get('narration'))

# 手法关键词
num_contrast = []   # 数字反差
suspense = []       # 悬念
bg_one_liner = []   # 一句带过背景

NUM_RE = re.compile(r'[0-9０-９一二三四五六七八九十两]+[^\n]{0,8}[比:：/｜|][^\n]{0,8}[0-9０-９一二三四五六七八九十两]')
SUSPENSE_RE = re.compile(r'[？?]|怎么|为什么|差在哪儿|悬念|居然|竟然|结果|谁想到|没想到|却|反转|反超|翻盘|逆转|惊险|惊呆|爆冷')
BG_RE = re.compile(r'(此前|之前|当时|一年前|两年前|五个月前|伤停|休战|缺席|刚复出|从资格赛|排名第?\d|世界第?\d|刚从|首秀|第一次)')


def pick(container, key, maxn=3, must_contain=None):
    return ''

# 数字反差: 句子里有 X 比 Y / X:Y / 双误四个之类对比
for slug, kind, text in corpus:
    t = text.replace('\n', '')
    if NUM_RE.search(t) and any(w in t for w in ['比', '：', ':', '｜', '|', '/', '双误', '赛点', '破发点', '分']):
        if len(t) <= 120:
            num_contrast.append((slug, kind, t))
# 悬念
for slug, kind, text in corpus:
    t = text.replace('\n', '')
    if SUSPENSE_RE.search(t) and len(t) <= 140 and not t.startswith('⚠'):
        suspense.append((slug, kind, t))
# 一句带过背景
for slug, kind, text in corpus:
    t = text.replace('\n', '')
    if BG_RE.search(t) and len(t) <= 90:
        bg_one_liner.append((slug, kind, t))

print('=== reel 字段结构 ===')
print(f'reel specs: {len(REELS)}')
print(f'含 editorial: {len(with_editorial)} / {len(REELS)}')
print('editorial 子字段集合:')
sub = {}
for p, ed in with_editorial:
    sub[tuple(sorted(ed.keys()))] = sub.get(tuple(sorted(ed.keys())), 0) + 1
for k, n in sorted(sub.items(), key=lambda x: -x[1]):
    print(f'  {n}: {", ".join(k)}')
print('human_context 子字段:')
hcs = {}
for p, ed in with_editorial:
    hc = ed.get('human_context')
    if isinstance(hc, dict):
        hcs[tuple(sorted(hc.keys()))] = hcs.get(tuple(sorted(hc.keys())), 0) + 1
for k, n in sorted(hcs.items(), key=lambda x: -x[1]):
    print(f'  {n}: {", ".join(k)}')
print('push 键组合:')
for k, n in sorted(push_keys.items(), key=lambda x: -x[1])[:6]:
    print(f'  {n}: {", ".join(k)}')
print('cover 键组合 (top 6):')
for k, n in sorted(cover_keys.items(), key=lambda x: -x[1])[:6]:
    print(f'  {n}: {", ".join(k)}')
print('segments 键组合 (top 6):')
for k, n in sorted(seg_key_sets.items(), key=lambda x: -x[1])[:6]:
    print(f'  {n}: {", ".join(k)}')

print()
print('=== 旁白字数 ===')
lens = sorted(narration_lens)
print(f'旁白段总数: {len(lens)}')
print(f'中位数: {statistics.median(lens)}  均值: {statistics.mean(lens):.1f}')
print(f'最短: {lens[0]}  最长: {lens[-1]}')
print('P10/P25/P75/P90:', lens[len(lens)//10], lens[len(lens)//4], lens[3*len(lens)//4], lens[9*len(lens)//10])
nc = [n for _, _, n in narration_seg_counts]
print(f'每条片子 segments 数: 中位 {statistics.median(nc)}, 最小 {min(nc)}, 最大 {max(nc)}')
narr_only = [n for _, s, n in narration_seg_counts if n > 0]
print(f'每条片子带旁白的段数: 中位 {statistics.median(narr_only)}, 最小 {min(narr_only)}, 最大 {max(narr_only)}')
print(f'完全无旁白(纯音乐?)的片子: {len(no_narration)} -> {no_narration[:10]}')
# 最长 5 段旁白
by_len = sorted(narration_lens, reverse=True)[:5]
print('最长旁白长度前 5:', by_len)

print()
print('=== interview 字段 ===')
print(f'interview specs: {len(INTERVIEWS)}')
print(f'含 human_quote: {len(int_with_quote)}')
for slug, q, ok in int_with_quote:
    print(f'  {slug}: {repr(q)[:120]}')
print(f'含 takeaway: {len(int_with_takeaway)}')
print('cover 键组合:')
for k, n in sorted(int_cover_keys.items(), key=lambda x: -x[1])[:5]:
    print(f'  {n}: {", ".join(k)}')
print('push 键组合:')
for k, n in sorted(int_push_keys.items(), key=lambda x: -x[1])[:5]:
    print(f'  {n}: {", ".join(k)}')

print()
print('=== xhs ===')
print(f'xhs 文件数: {len(XHS)}')
for slug, info in list(xhs_samples.items())[:5]:
    print(f'  {slug}: {info["n_lines"]} 行, 标签: {info["hashtags"]}')

print()
print('=== 手法例句库候选 ===')
print(f'数字反差候选: {len(num_contrast)}')
for s, k, t in num_contrast[:8]:
    print(f'  [{s}|{k}] {t}')
print(f'悬念候选: {len(suspense)}')
for s, k, t in suspense[:8]:
    print(f'  [{s}|{k}] {t}')
print(f'一句带过背景候选: {len(bg_one_liner)}')
for s, k, t in bg_one_liner[:8]:
    print(f'  [{s}|{k}] {t}')

# 存全量候选供后续挑选
with open('/tmp/copy_patterns_dump.txt', 'w', encoding='utf-8') as f:
    f.write('===NUM_CONTRAST===\n')
    for s, k, t in num_contrast:
        f.write(f'[{s}|{k}] {t}\n')
    f.write('===SUSPENSE===\n')
    for s, k, t in suspense:
        f.write(f'[{s}|{k}] {t}\n')
    f.write('===BG===\n')
    for s, k, t in bg_one_liner:
        f.write(f'[{s}|{k}] {t}\n')
    f.write('===EDITORIAL===\n')
    for e in ed_examples:
        f.write(f'[{e["slug"]}|mode={e["mode"]}]\nQ: {e["question"]}\nT: {e["thesis"]}\nA: {e["angle"]}\nB: {json.dumps(e["beats"], ensure_ascii=False)}\n---\n')
    f.write('===XHS===\n')
    for slug, info in xhs_samples.items():
        f.write(f'[{slug}]\n{info["text"]}\n====\n')
    f.write('===PUSH_COVER_SAMPLE===\n')
    for p in REELS[:0]:
        pass
    for p in REELS:
        d = load(p)
        slug = p.split('/')[-1].replace('.json', '')
        f.write(f'[{slug}]\nPUSH: {json.dumps(d.get("push", {}), ensure_ascii=False)}\nCOVER: {json.dumps({k: v for k, v in (d.get("cover") or {}).items() if k in ("eyebrow","hook","winner","result","topic","subject","versus")}, ensure_ascii=False)}\n---\n')
print('\ndump 到 /tmp/copy_patterns_dump.txt')

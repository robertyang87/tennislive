from pathlib import Path
import gzip, hashlib, json, shutil

ROOT = Path('/workspace/pegula-finals-production')
HERE = ROOT / 'revision-v3-scope'
REPO = Path('/workspace/tennislive')
DEST = REPO / 'research/pegula-finals-2026/revision-eight-events-v3'
files = [p for p in HERE.rglob('*') if p.is_file() and p.suffix.lower() in {'.json', '.py', '.html', '.txt'} and not any(x in p.parts for x in ('previous-v2', 'narration-final31', 'narration-measured', 'dry-run', 'master', 'review', 'final-metadata'))]
files += [p for p in HERE.rglob('*') if p.is_file() and p.suffix.lower() in {'.jpg', '.png'} and ('contact' in p.name or 'proof' in p.name)]
files += [p for p in ROOT.glob('native-preview-*-fresh-v3/*') if p.is_file() and (p.name == 'preview_manifest.json' or 'contact' in p.name)]
files += [ROOT / 'delivery/佩古拉2026年终之路_八站重点版提纲.pdf']
entries = []
for path in sorted(set(files)):
    if not path.is_file():
        continue
    target = DEST / path.relative_to(ROOT)
    raw = path.read_bytes()
    if path.suffix in {'.txt', '.html'}:
        target = target.with_suffix(target.suffix + '.gz')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(raw, mtime=0) if path.suffix in {'.txt', '.html'} else raw)
    entries.append({'original_path': str(path), 'repository_path': str(target.relative_to(REPO)), 'original_sha256': hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size, 'compression': 'gzip' if path.suffix in {'.txt', '.html'} else None})
(DEST / 'archive-index.json').write_text(json.dumps({'scope': 'Eight featured events; ten terminal match points and three optional complete rallies. Native previews are not final movie QC.', 'files': entries}, ensure_ascii=False, indent=2) + '\n')
print(len(entries), 'files', round(sum(x['bytes'] for x in entries) / 2**20, 2), 'MiB')

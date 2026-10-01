"""Version 2: retained public ATP source windows; evidence only, no audio upload."""
import os
for key in ('ORT_DISABLE_TELEMETRY','HF_HUB_DISABLE_TELEMETRY','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE'):
    if os.environ.get(key) != '1':
        raise SystemExit(f'{key}=1 is required before process startup')

import os

import argparse

from datetime import datetime, timezone

import hashlib

import importlib.metadata

import json

import math

from pathlib import Path

import re

import stat

import subprocess

import urllib.request

import wave

import zipfile

MODEL_ID = 'Systran/faster-whisper-medium.en'

REVISION = 'a29b04bd15381511a9af671baec01072039215e3'

MODEL_FILES = {
    'config.json': (2643, '4a1848ebabe7938d9797c15a2e8e4ce1d36e6fd4a43d096ae5955257c67c7962'),
    'model.bin': (1527904330, '11b220779aea4c6f3ce9d2549c8a95ea869ed84066864b999531ef53e594fe5b'),
    'tokenizer.json': (2128466, '929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df'),
    'vocabulary.txt': (422309, 'ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf'),
}

SOURCES = {'nishikori-tiafoe-tokyo-2026-r1': ('https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 48000, ((0.0, 23.88), (31.95, 57.53), (85.8, 95.48), (99.66, 110.2), (137.0, 179.98))), 'zverev-norrie-beijing-2026-r1': ('https://www.youtube.com/watch?v=eciSHiQTzN8', 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 44100, ((0.0, 19.28), (101.84, 156.44), (181.82, 190.9), (191.78, 215.84), (215.86, 233.28))), 'shang-baez-beijing-2026-r1': ('https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 48000, ((12.2, 23.88), (52.2, 68.58), (86.0, 99.78), (116.5, 124.98), (125.5, 148.03)))}

EXPECTED_WINDOWS = {(slug,a,b) for slug,(_,_,_,windows) in SOURCES.items() for a,b in windows}

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def stamp():
    return datetime.now(timezone.utc).isoformat()

def valid_digest(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None

def download_verified(url,path,size,digest):
    path=Path(path)
    if path.is_file() and path.stat().st_size==size and sha(path)==digest:
        return
    if path.is_symlink():
        raise ValueError('Symlink output rejected')
    path.parent.mkdir(parents=True,exist_ok=True)
    count=0
    request=urllib.request.Request(url,headers={'User-Agent':'tennislive-short-window-review/2'})
    with urllib.request.urlopen(request,timeout=30) as response,path.open('wb') as output:
        while block:=response.read(1024*1024):
            count+=len(block)
            if count>size:
                raise ValueError('Download exceeds exact reviewed size')
            output.write(block)
    if count!=size or sha(path)!=digest:
        raise ValueError('Downloaded bytes failed exact size/SHA256 verification')

def check_wav(path,item):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
        raise ValueError('WAV differs from reviewed input')
    with wave.open(str(path),'rb') as audio:
        actual={'channels':audio.getnchannels(),'sample_width_bytes':audio.getsampwidth(),'sample_rate':audio.getframerate(),'frames':audio.getnframes()}
        if audio.getcomptype()!='NONE' or actual!=item['audio']:
            raise ValueError('WAV PCM properties differ')

def check_model(model_dir):
    for name,(size,digest) in MODEL_FILES.items():
        path=Path(model_dir)/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size!=size or sha(path)!=digest:
            raise ValueError(f'Official model file failed verification: {name}')

def model_download(model_dir):
    for name,(size,digest) in MODEL_FILES.items():
        url=f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}?download=true'
        download_verified(url,Path(model_dir)/name,size,digest)
    check_model(model_dir)

def infer(data,input_dir,model_dir,outdir):
    check_model(model_dir)
    for item in data['items']:check_wav(Path(input_dir)/item['path'],item)
    import numpy as np
    from faster_whisper import WhisperModel
    model=WhisperModel(str(model_dir),device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    versions={name:importlib.metadata.version(name) for name in ('faster-whisper','ctranslate2','onnxruntime','numpy','huggingface-hub','tokenizers','av')}
    completed=[]
    for item in data['items']:
        decoded=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(Path(input_dir)/item['path']),'-vn','-ac','1','-ar','16000','-f','f32le','-'],check=True,capture_output=True,timeout=30)
        audio=np.frombuffer(decoded.stdout,dtype=np.float32)
        segments,info=model.transcribe(audio,language='en',beam_size=5,temperature=0,condition_on_previous_text=False,initial_prompt=None,word_timestamps=True,vad_filter=False)
        rows=[]
        for segment in segments:
            words=[{'word':w.word,'start':w.start,'end':w.end,'source_start':round(item['source_from']+w.start,3),'source_end':round(item['source_from']+w.end,3),'probability':w.probability,'uncertain':w.probability<.8} for w in (segment.words or [])]
            rows.append({'start':segment.start,'end':segment.end,'text':segment.text,'avg_logprob':segment.avg_logprob,'no_speech_prob':segment.no_speech_prob,'compression_ratio':segment.compression_ratio,'words':words})
        report={'schema':'tennislive.asr-evidence-only.retained-v2','created_at':stamp(),'input':item,'model':{'id':MODEL_ID,'revision':REVISION,'model_sha256':MODEL_FILES['model.bin'][1]},'versions':versions,'language':'en','segments':rows,'status':'inference_only_not_verified','empty_output_is_not_silence_proof':not rows,'uncertainty_note':'Model output may omit or hallucinate quiet foreground speech. Cross-check entire window and source timing.','audio_review_pass':False,'publication_eligible':False}
        (outdir/f'{item["id"]}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');completed.append(item['id'])
        print(json.dumps({'completed':item['id'],'segments':len(rows),'review_pass':False}),flush=True)
    (outdir/'batch.json').write_text(json.dumps({'created_at':stamp(),'completed':completed,'source_seconds':309.95,'audio_review_pass':False,'publication_eligible':False},indent=2)+'\n')

import hashlib

import html

import json

import os

import re

import resource

import signal

import subprocess

import sys

import tempfile

import time

from html.parser import HTMLParser

from pathlib import Path

from urllib.parse import urlparse

PUBLIC_SOURCES = {
    "nishikori-tiafoe-tokyo-2026-r1": (
        "https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights",
        144247263,
        "108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02",
    ),
    "shang-baez-beijing-2026-r1": (
        "https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights",
        120347402,
        "f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f",
    ),
    "zverev-norrie-beijing-2026-r1": (
        "https://github.com/robertyang87/tennislive/releases/download/source-eciSHiQTzN8/eciSHiQTzN8.mp4",
        40607227,
        "dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee",
    ),
}

SOURCE_TIMEOUT_SECONDS = 1200

METADATA_MAX_BYTES = 2 * 1024 * 1024

class SourceFetchError(RuntimeError):
    """A fixed, non-sensitive error code; never embed external exception text."""

    def __init__(self, code, returncode=None):
        self.code = code
        self.returncode = returncode if type(returncode) is int else None
        super().__init__(code)

def public_source_error(exc):
    return exc.code if isinstance(exc, SourceFetchError) else "source_fetch_failed"

def source_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def _source_identity(url):
    for source in PUBLIC_SOURCES.values():
        if url == source[0]:
            return source
    raise SourceFetchError("source_url_not_approved")

class _PlayerElements(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.players = []

    def handle_starttag(self, tag, attrs):
        pairs = [(key, value) for key, value in attrs if key in {"data-entry-id", "data-entitlement"}]
        if not any(key == "data-entry-id" for key, _ in pairs):
            return
        if len({key for key, _ in pairs}) != len(pairs):
            raise SourceFetchError("ambiguous_player_attributes")
        self.players.append(dict(pairs))

def _free_current_entry(page):
    # Match the pinned native resolver's first-entry selection exactly.
    decoded = html.unescape(page)
    native_match = re.search(r'data-entry-id="(?P<entry>[^" ]+)"', decoded)
    if not native_match:
        raise SourceFetchError("public_entry_missing")
    entry = native_match.group("entry")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", entry):
        raise SourceFetchError("invalid_public_entry")
    parsed = _PlayerElements()
    parsed.feed(decoded)
    if not parsed.players or parsed.players[0].get("data-entry-id") != entry:
        raise SourceFetchError("current_player_not_identified")
    matching = [item for item in parsed.players if item.get("data-entry-id") == entry]
    if any(item.get("data-entitlement", "").lower() != "free" for item in matching):
        raise SourceFetchError("current_entry_not_explicitly_free")
    return entry

class _PublicResponse:
    def __init__(self, payload):
        self.text = payload.decode("utf-8")

    def raise_for_status(self):
        pass  # The bounded HTTP read has already rejected non-200 responses.

    def json(self):
        return json.loads(self.text)

def _anonymous_session():
    import requests
    class NoAccountAuth(requests.auth.AuthBase):
        def __call__(self, request):
            return request

    session = requests.Session()
    # Explicit no-op auth disables .netrc account lookup while preserving the
    # environment's ordinary proxy/CA route and native anonymous playback token.
    session.auth = NoAccountAuth()
    return session

def _remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise SourceFetchError("source_total_timeout")
    return left

def _metadata_get(session, target, headers, deadline):
    session.cookies.clear()
    with session.get(target, headers=headers, timeout=min(25, _remaining(deadline)),
                     allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise SourceFetchError("public_http_rejected")
        payload = bytearray()
        for block in response.iter_content(chunk_size=65536):
            _remaining(deadline)
            if len(payload) + len(block) > METADATA_MAX_BYTES:
                raise SourceFetchError("public_metadata_too_large")
            payload.extend(block)
    return _PublicResponse(bytes(payload))

def _no_account_post(*args, **kwargs):
    raise SourceFetchError("account_post_forbidden")

def _kill_download_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=10)

def _classify_download_stderr(payload):
    """Map a private bounded buffer to fixed codes; never return error text."""
    text = payload.decode("utf-8", errors="replace").lower()
    if "error while loading shared libraries" in text or "cannot open shared object file" in text:
        return "library_loader"
    if "no module named" in text:
        return "missing_module"
    if "no such option" in text or "unrecognized arguments:" in text:
        return "unknown_option"
    if "requested format is not available" in text:
        return "format_unavailable"
    if any(marker in text for marker in ("signature has expired", "signature expired", "expiredtoken", "request has expired", "requestexpired")):
        return "signature_expired"
    status = re.search(r"\bhttp(?: error)?\s*:?\s+([45][0-9]{2})\b", text)
    if status:
        return "http_" + status.group(1)
    return "unknown"

def _drain_private_stderr(process, tail):
    # Nonblocking and bounded in both work per poll and retained memory. The
    # buffer never enters exceptions, logs, reports, or persistent artifacts.
    for _ in range(8):
        try:
            block = os.read(process.stderr.fileno(), 65536)
        except BlockingIOError:
            break
        if not block:
            break
        tail.extend(block)
        del tail[:-65536]

def _bounded_hls_download(playback_url, dest, expected_bytes, deadline):
    # The native resolver produces an anonymous official-player HLS URL.
    parts = urlparse(playback_url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise SourceFetchError("invalid_public_playback_url")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="public-hls-", dir=dest.parent) as tmp:
        staging = Path(tmp)
        output = staging / "source.mp4"
        # Each file is kernel-limited. Aggregate allowance accommodates separate
        # A/V files, merged output, and ordinary temporary HLS overhead.
        per_file_limit = expected_bytes + 1024 * 1024
        aggregate_limit = 3 * expected_bytes + 8 * 1024 * 1024

        def set_file_limit():
            resource.setrlimit(resource.RLIMIT_FSIZE, (per_file_limit, per_file_limit))

        command = [
            sys.executable, "-I", "-m", "yt_dlp",
            "--ignore-config", "--no-plugin-dirs", "--no-cache-dir",
            "--no-playlist", "--no-progress", "--no-continue",
            "--socket-timeout", "25", "--retries", "0", "--fragment-retries", "0",
            "--abort-on-unavailable-fragments", "--concurrent-fragments", "1",
            "-f", "bestvideo[height=1080]+bestaudio/best[height=1080]",
            "--merge-output-format", "mp4", "-o", str(output), playback_url,
        ]
        # Preserve ordinary proxy/CA routing, but do not pass account secrets or
        # PYTHONPATH. -I also ignores Python user-site and environment overrides.
        env_keys = (
            "PATH", "LANG", "LC_ALL", "TMPDIR", "HTTP_PROXY", "HTTPS_PROXY",
            "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy",
            "no_proxy", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE",
            "SSL_CERT_DIR", "LD_LIBRARY_PATH",
        )
        child_env = {key: os.environ[key] for key in env_keys if key in os.environ}
        process = subprocess.Popen(command, cwd=staging, env=child_env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, start_new_session=True,
                                   preexec_fn=set_file_limit)
        private_stderr = bytearray()
        try:
            os.set_blocking(process.stderr.fileno(), False)
            while True:
                _remaining(deadline)
                _drain_private_stderr(process, private_stderr)
                total = 0
                for item in staging.rglob("*"):
                    try:
                        if item.is_file():
                            total += item.stat().st_size
                    except FileNotFoundError:
                        pass  # yt-dlp may rename a completed part during the scan.
                if total > aggregate_limit:
                    raise SourceFetchError("public_download_size_limit")
                returncode = process.poll()
                if returncode is not None:
                    _drain_private_stderr(process, private_stderr)
                    if returncode:
                        raise SourceFetchError(_classify_download_stderr(private_stderr), returncode)
                    break
                time.sleep(min(0.2, _remaining(deadline)))
        finally:
            _kill_download_group(process)
            process.stderr.close()
            private_stderr.clear()
        if not output.is_file() or output.stat().st_size != expected_bytes:
            raise SourceFetchError("source_size_mismatch")
        output.replace(dest)

def _get_ttv(url, dest, deadline):
    _, expected_bytes, expected_digest = _source_identity(url)
    if urlparse(url).hostname != "www.tennistv.com":
        raise SourceFetchError("source_not_tennistv")
    from tennislive.video.official import OfficialVideoCandidate, fetch_tennistv_video_metadata
    with _anonymous_session() as session:
        first = _metadata_get(session, url, {"User-Agent": "tennislive/0.1"}, deadline)
        entry = _free_current_entry(first.text)
        entitlement_url = "https://api.tennistv.com/entitlementcheck/v1/videoentitlements/" + entry
        playback_url = "https://api.playback.streamamg.com/v1/entry/" + entry

        def safe_get(target, **kwargs):
            if target == url:
                return first
            if target not in {entitlement_url, playback_url}:
                raise SourceFetchError("resolver_endpoint_not_approved")
            headers = dict(kwargs.get("headers") or {})
            if target == entitlement_url and any(key.lower() in {"authorization", "cookie"} for key in headers):
                raise SourceFetchError("account_auth_forbidden")
            return _metadata_get(session, target, headers, deadline)

        meta = fetch_tennistv_video_metadata(
            OfficialVideoCandidate(title="", url=url, tour="ATP"),
            get=safe_get, post=_no_account_post, jwt_token="", refresh_token="", timeout=25,
        )
    _bounded_hls_download(meta.playback_url, dest, expected_bytes, deadline)
    if source_sha256(dest) != expected_digest:
        raise SourceFetchError("source_sha256_mismatch")

def get_ttv(url, dest):
    """Fetch a fixed free entry, sequentially on the Linux runner main thread."""
    def alarm_expired(signum, frame):
        raise SourceFetchError("source_total_timeout")

    try:
        # requests' socket timeout alone does not cap a continuously slow body.
        # The process timer also bounds imports, redirects, body reads, and SHA.
        if signal.getitimer(signal.ITIMER_REAL)[0]:
            raise SourceFetchError("conflicting_source_timer")
        previous_handler = signal.signal(signal.SIGALRM, alarm_expired)
        try:
            signal.setitimer(signal.ITIMER_REAL, SOURCE_TIMEOUT_SECONDS)
            return _get_ttv(url, dest, time.monotonic() + SOURCE_TIMEOUT_SECONDS)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    except SourceFetchError:
        raise
    except Exception:
        raise SourceFetchError("public_fetch_failed") from None

"""Fixed public plan and local excerpts; included in the frozen runner helper."""
OFFICIAL_RESOLVER_SHA256 = '1b345431dccf751614f88ebfce93f38fce3126e52fa7d7ba42a9f4eb84ae1e04'


def acquire_sources(outdir, report_path):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    rows=[];paths={}
    resolver=Path('src/tennislive/video/official.py')
    if not resolver.is_file() or sha(resolver)!=OFFICIAL_RESOLVER_SHA256:
        raise ValueError('Native public resolver differs from the reviewed code')
    for slug,(url,size,digest) in PUBLIC_SOURCES.items():
        target=outdir/f'{slug}.mp4'
        row={'slug':slug,'public_url':url,'expected_bytes':size,'expected_sha256':digest,'status':'not_started'}
        try:
            if target.exists() or target.is_symlink():
                raise SourceFetchError('source_output_already_exists')
            if slug.startswith('zverev-'):
                # Ordinary read of the existing public archive; no API token.
                deadline=time.monotonic()+300;count=0
                class HttpsRedirect(urllib.request.HTTPRedirectHandler):
                    def redirect_request(self,req,fp,code,msg,headers,newurl):
                        parsed=urlparse(newurl)
                        if parsed.scheme!='https' or parsed.hostname not in {'github.com','release-assets.githubusercontent.com'} or parsed.username or parsed.password:
                            raise SourceFetchError('public_archive_redirect_rejected')
                        return super().redirect_request(req,fp,code,msg,headers,newurl)
                opener=urllib.request.build_opener(HttpsRedirect())
                req=urllib.request.Request(url,headers={'User-Agent':'tennislive-public-source-review/1'})
                with opener.open(req,timeout=25) as response,target.open('wb') as output:
                    while block:=response.read(1024*1024):
                        _remaining(deadline);count+=len(block)
                        if count>size:raise SourceFetchError('public_archive_size_limit')
                        output.write(block)
            else:
                get_ttv(url,target)
            row.update(actual_bytes=target.stat().st_size,actual_sha256=sha(target))
            if row['actual_bytes']!=size or row['actual_sha256']!=digest:
                raise SourceFetchError('source_size_or_sha256_mismatch')
            row['status']='exact_source_verified';paths[slug]=target
        except Exception as exc:
            row['status']='blocked';row['reason']=public_source_error(exc)
            if type(getattr(exc,'returncode',None)) is int:
                row['returncode']=exc.returncode
            rows.append(row)
            Path(report_path).write_text(json.dumps({'sources':rows,'audio_inference_started':False,'raw_audio_uploaded':False,'audio_review_pass':False,'publication_eligible':False},indent=2)+'\n')
            raise SourceFetchError('source_acquisition_incomplete') from None
        rows.append(row)
    Path(report_path).write_text(json.dumps({'sources':rows,'audio_inference_started':False,'raw_audio_uploaded':False,'audio_review_pass':False,'publication_eligible':False},indent=2)+'\n')
    return paths


def read_plan(path, expected_sha):
    if not valid_digest(expected_sha) or sha(path) != expected_sha:
        raise ValueError('Plan differs from reviewed SHA256')
    data=json.loads(Path(path).read_text())
    if data.get('schema') != 'tennislive.approved-retained-window-plan.v2' or data.get('source_seconds') != 309.95:
        raise ValueError('Unexpected approved public-window schema or total')
    items=data.get('items',[])
    if len(items)!=15:
        raise ValueError('Exactly fifteen approved windows are required')
    seen=set()
    for index,item in enumerate(items,1):
        slug=item.get('slug')
        if slug not in SOURCES:
            raise ValueError('Unapproved source match')
        url,digest,rate,windows=SOURCES[slug]
        if (item.get('source_url'),item.get('source_sha256'))!=(url,digest):
            raise ValueError('Source identity differs from approved public source')
        start,end=item.get('source_from'),item.get('source_to')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in (start,end)):
            raise ValueError('Invalid source times')
        key=(slug,start,end)
        if key not in EXPECTED_WINDOWS or key in seen:
            raise ValueError('Changed, duplicate or unapproved source window')
        seen.add(key)
        wanted={'id':f'clip-{index:02d}-{slug}','slug':slug,'source_url':url,'source_sha256':digest,'source_from':start,'source_to':end,'audio':{'channels':2,'sample_width_bytes':2,'sample_rate':rate,'frames':round((end-start)*rate)}}
        if item != wanted:
            raise ValueError('Clip ID, PCM properties or fields differ from reviewed plan')
    if seen != EXPECTED_WINDOWS or round(sum(x['source_to']-x['source_from'] for x in items),2)!=309.95:
        raise ValueError('Audio scope differs from the exact 309.95-second plan')
    return data


def extract_windows(plan, paths, input_dir):
    expected={slug:digest for slug,(_,digest,_,_) in SOURCES.items()}
    if set(paths)!=set(expected):
        raise ValueError('Exactly the three approved source files are required')
    for slug,digest in expected.items():
        path=Path(paths[slug])
        if path.is_symlink() or not path.is_file() or sha(path)!=digest:
            raise ValueError('Original source SHA256 mismatch before clipping')
    input_dir=Path(input_dir)
    if input_dir.is_symlink():
        raise ValueError('Symlink input directory rejected')
    items=[]
    for original in plan['items']:
        item=dict(original);rel=f'clips/{item["id"]}.wav';dest=input_dir/rel
        if dest.is_symlink() or not dest.resolve().is_relative_to(input_dir.resolve()):
            raise ValueError('Clip output escapes its isolated input directory')
        dest.parent.mkdir(parents=True,exist_ok=True)
        cmd=['ffmpeg','-nostdin','-v','error','-ss',str(item['source_from']),'-i',str(paths[item['slug']]),'-t',str(round(item['source_to']-item['source_from'],3)),'-map','0:a:0','-vn','-c:a','pcm_s16le','-y',str(dest)]
        result=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45)
        if result.returncode:
            raise ValueError('Bounded local PCM extraction failed')
        item.update(path=rel,bytes=dest.stat().st_size,sha256=sha(dest))
        check_wav(dest,item);items.append(item)
    return {'schema':'tennislive.runtime-retained-excerpts.v2','items':items,'source_seconds':309.95,'raw_audio_uploaded':False,'audio_review_pass':False,'publication_eligible':False}


def read_runtime(path, plan, input_dir):
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='tennislive.runtime-retained-excerpts.v2' or data.get('source_seconds')!=309.95:
        raise ValueError('Unexpected local runtime evidence')
    items=data.get('items',[])
    if len(items)!=15:
        raise ValueError('Runtime excerpt count differs')
    for expected,item in zip(plan['items'],items):
        if set(item)!=set(expected)|{'path','bytes','sha256'} or any(item[k]!=v for k,v in expected.items()):
            raise ValueError('Runtime source window differs from fixed plan')
        if item['path']!=f'clips/{item["id"]}.wav' or not valid_digest(item['sha256']):
            raise ValueError('Unsafe runtime path or SHA')
        if type(item['bytes']) is not int or not 44<item['bytes']<=expected['audio']['frames']*4+4096:
            raise ValueError('Unbounded runtime PCM size')
        path=Path(input_dir)/item['path']
        if not path.resolve().is_relative_to(Path(input_dir).resolve()):
            raise ValueError('Runtime excerpt escapes its isolated input directory')
        check_wav(path,item)
    if any(data.get(k) is not False for k in ('raw_audio_uploaded','audio_review_pass','publication_eligible')):
        raise ValueError('Runtime evidence cannot declare publication or review approval')
    return data


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['inputs','acquire','download-model','infer'],required=True)
    parser.add_argument('--plan',type=Path,default=Path('assets/asr-review-20261001/retained-source-windows-v2.json'))
    parser.add_argument('--plan-sha256',required=True)
    parser.add_argument('--workdir',type=Path)
    parser.add_argument('--outdir',type=Path)
    args=parser.parse_args()
    plan=read_plan(args.plan,args.plan_sha256)
    if args.mode=='inputs':
        print(json.dumps({'clips':15,'source_seconds':309.95,'validated_plan':args.plan_sha256}));return
    if args.workdir is None or args.outdir is None:
        parser.error('--workdir and --outdir are required')
    if args.workdir.is_symlink() or args.outdir.is_symlink():
        raise ValueError('Symlink runtime directories rejected')
    args.workdir.mkdir(parents=True,exist_ok=True);args.outdir.mkdir(parents=True,exist_ok=True)
    input_dir=args.workdir/'inputs';model_dir=args.workdir/'model';runtime=args.outdir/'runtime-inputs.json'
    if args.mode=='acquire':
        paths=acquire_sources(args.workdir/'sources',args.outdir/'sources.json')
        data=extract_windows(plan,paths,input_dir)
        runtime.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');return
    if args.mode=='download-model':
        read_runtime(runtime,plan,input_dir)
        model_download(model_dir);return
    data=read_runtime(runtime,plan,input_dir)
    infer(data,input_dir,model_dir,args.outdir)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        # Transient public-player tokens and local paths never enter artifacts/logs.
        print(json.dumps({'status':'blocked','error_type':type(exc).__name__,'audio_review_pass':False,'publication_eligible':False}),flush=True)
        raise SystemExit(1) from None

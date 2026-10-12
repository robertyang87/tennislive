# Eala / Shi current-episode audio evidence

This bundle prepares and audits the frozen `eala-shi` narration. It never
renders, publishes or sends messages. Its episode-specific fingerprint comes
from the final approved spec; an old episode's audio or verdict is not input.

```bash
python tools/eala_voice_review.py --stage prepare \
  --expected-fingerprint '<frozen-narration-sha256>' \
  --outdir /workspace/scratch/eala-voice
python tools/eala_voice_review.py --stage analyze \
  --expected-fingerprint '<same-frozen-narration-sha256>' \
  --outdir /workspace/scratch/eala-voice
```

The narration fingerprint hashes the UTF-8 JSON list of each spoken segment's
`edit_id`, `narration` and `voice`, with sorted keys and compact separators.
Preparation snapshots native MP3, matching cache ZIP and WordBoundary marks.
The audit enumerates all dictionary polyphones plus every declared name and
numeral occurrence. Fresh same-sentence correct and confusable homophones use
MFCC/F0 contrasts and leave-one-out calibration. A per-reference process lock
keeps MP3 and marks paired when several targets request the same control.

Unknown, low confidence, unreliable or unsupported readings remain explicitly
unresolved. ASR only supports word recognition. No human listening or complete
pronunciation pass is claimed.

For the two-sentence revision, prepare a separate directory using the revised
frozen fingerprint, then reuse only byte-identical current-episode controls:

```bash
python tools/eala_voice_review/reuse_unchanged.py \
  --old /workspace/scratch/eala-voice \
  --new /workspace/scratch/eala-voice-v2 \
  --changed-id first_set_pressure --changed-id long_rally_context
```

Run `analyze` against the new directory and fingerprint. It verifies the full
utterance, native MP3 and paired marks plus occurrence and reference identities
before skipping a copied measurement. The two revised utterances are always
new audio and new comparisons; their original results remain nonfinal history.

After the actual master and native QC exist, use the immutable master's SHA:

```bash
export EALA_VOICE_REVIEW_DIR=/workspace/scratch/eala-voice
python tools/eala_voice_review/restore_final_sidecars.py '<native-output-dir>'
python tools/eala_voice_review/seal_final.py specs/reels/eala-shi.json \
  '<native-output-dir>' '<actual-final-master-sha256>'
python tools/eala_voice_review/archive_voice_evidence.py
```

Sidecar restoration checks the actual production MP3 against matching native
ZIP audio before copying exact ZIP marks; it does not change speech or master
video. Sealing checks actual MP3 against the reviewed frozen speech, correlates
the actual final AAC waveform, hashes full-channel PCM and binds the same spec,
ASS, render inputs and successful native QC. The ZIP is a prepared evidence
archive; remote transport and delivery still require separate verification.

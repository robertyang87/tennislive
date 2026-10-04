# Source audio cross-check — s3mqDeV5E_w

Source bytes: `/workspace/scratch/source/s3mqDeV5E_w.mp4`, SHA256 `ce7320181adea751842fe58f500e6fa5f788e1c547fe064d11a775d0292a5efd`, duration 308.802 seconds. Extracted original mono PCM at 16 kHz using ffmpeg; no synthetic audio or substituted track.

Installed faster-whisper 1.2.1 into scratch only; downloaded Systran small.en model. CPU int8, four threads, language en, beam 5, word timestamps, VAD enabled on full 0–308.802 second audio. Model ran against decoded PCM numpy input because bundled PyAV 19 lacks metadata_errors argument used by faster-whisper; this changed input decoding only, not recognition or gate behavior. See run_asr.py and original asr.log.

Inspected all supplied provider-auto-caption lines and full second ASR word timing/text. Provider text is captions.txt supplied by parent; provider retrieval provenance belongs to parent, not independently fetched by this agent. Ran targeted crops of 147–154,168–173,175–181,189–194,214–220,237–243,253–258 seconds without VAD to check discrepancies. The cropped model uses the same small.en model and is not a third independent recognizer. See check_chunks.py / targeted-small-en.json / targeted.log.

The bilingual JSON is a partial evidence draft, not a completed gate record. No actual listening was performed by this agent. Names are normalized to project's established spelling but ambiguous speech at 177 seconds remains unresolved. Automated speech recognition cannot prove absence of audible omitted score calls. Complete final source/mix listening and resolving uncertainty remains a production gap.

No repository gate, workflow, production file, or publishing state was changed. All artifacts are in scratch.

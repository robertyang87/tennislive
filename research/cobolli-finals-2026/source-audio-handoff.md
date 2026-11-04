# Cobolli selected-source audio handoff

8 selected windows, 7 actual official sources, 14 bilingual cues. All packet and raw-ASR files are frozen under `required-copy-files.json` (8 packets +21 unique raw JSONs). Copy only its named JSONs into the real feature branch; do not copy an old film approval or the sandbox index.

| Window | Actual source ID | Final source seconds | English cues |
|---|---|---:|---:|
| AO R1 | dSafV4sp0OM |436.10–471.80|4|
| Acapulco final |4459713 native01d711…a9bd|129.30–143.40|3|
| Munich final |GwHNGXakf8s|430.30–445.90|2|
| RG fourth-set tiebreak |WfxpIK_TvEQ|422.40–441.30|0|
| RG final match point |WfxpIK_TvEQ|640.30–665.30|0|
| Wimbledon QF |05ZtcEHhYqM|461.50–477.40|2|
| Cincinnati SF |hL72qAXJWOY|96.48–105.78|1|
| US R3 |nYClQO4RiIw|674.20–689.80|2|

Each packet has absolute source utterance times. Convert them into each actual native segment's quote `at/end` by subtracting that segment's source start. Current native-source window/quote-only reference recipe is `eight-window-native-gate-sandbox/spec.json`; it is not the whole narrative film spec. All nominal source audio stays original at unit gain. `audio_tail:silence` only suppresses additional dissolve continuation after the nominal window, never speech inside the nominal window.

## Evidence limits and decisions

- Method is `asr_cross_checked`, not human listening. Known source-recognizer variants remain in raw documents and packet notes.
- AO keeps the extended source and first-serve fault+second serve in full. Root accepted `Fery's second break in the third set` as bounded ASR/context editorial normalization after three actual model outputs, not word-perfect hearing or an official subtitle. Leading `So` is omitted only from display as filler. Raw alternate function words and the large-v3 JSON are preserved; no audio was muted to hide uncertainty.
- Acapulco must bind the actual native archive SHA `01d711954a47ee48c9c054c582ff65fef8c6f25f4b4020264597ca6ec060a9bd`, not the earlier `04ce…` local mux or the rejected unofficial long video. Canonical source URL remains the official Tennis TV page.
- RG windows have court/crowd/French-umpire audio, with no verified English; low-confidence inconsistent forced-English hallucinations are not printed. Existing same-SHA historical RG overlap evidence is exact and hash-bound. No-English does not mean silent.
- Wimbledon461.50 and US674.20 starts have exact-frame confirmation of pre-toss serving preparation. Tight ASR excludes the prior sentence rather than bringing in a previous partial point.
- Munich430.30 is pre-toss and complete. Tight441–446 evidence supports retaining the whole runner-up sentence then ending445.90 before the following Make/Made sentence; root accepted this bounded alignment interpretation.

## Checks actually run

`eight-window-native-gate-check.json` records PASS of native `foreground_audio_gate.require` against all7 actual local source files, exact ASR hash/source-SHA checks for21 unique raw documents and `quote_overflow_rows` for all14 translated cues. This does not validate final segment indices, TTS, burned ASS or the final movie. After integrating the actual final story spec, regenerate the native review index with its true segment indices/plan hash, run the native preflight, then check the actual encoded film and sealed ASS. Do not claim whole-film playback or human listening from these source checks.

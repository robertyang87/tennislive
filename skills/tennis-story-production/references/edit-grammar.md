# Edit grammar

Every device here is optional and every one of them costs attention. Use one when it carries meaning the cut alone cannot.

## Speed

`seg.speed`, 0.4–2.5. Below 1 is slow motion, above 1 is fast. `start`/`end` stay source-window seconds; the segment occupies `(end-start)/speed` in the film and every downstream account follows automatically.

Slow motion belongs on the moment the story turns — a match point landing, a face after a loss, a hand on a trophy. It buys the viewer time to read an expression.

Fast belongs on transit: walking on, changing ends, a montage of years passing. It says “this part is connective tissue” without a line saying so.

Neither bound is a technical limit. Slower than 0.4 and continuous motion falls apart into frames; faster than 2.5 and the eye loses the ball. Re-render and look before widening either.

The dissolve tail a segment consumes on the source side scales with speed. That accounting is why fast playback was blocked before 2026-08-27, and it is handled in code — do not re-derive it in a spec.

## Music

`spec.music`, added 2026-08-27. It is a bed **under** the live sound, ducked by narration along with the live sound. It is never the thing holding the film up.

- Licence four-set — title, artist, licence, source URL — all required.
- Measured, not guessed: the track must sit at least 8 dB below the live sound after both gains. A gain multiplier says nothing on its own because masters differ by more than ten dB.
- A film declaring `silent_source` may not have music at all. With no live sound, music becomes the only bed, which is exactly the “simple processing” that got this column penalised in the first place.
- The track must be at least as long as the film. No automatic looping: a loop seam is audible, and this column dissolves even its picture cuts.
- Quote segments do not duck. Check those by ear — a track whose energy sits in the speech band will fight the subject's own voice there even when it behaves everywhere else.

## Story text

`inset` of kind `story_text`, at most three per film. Short green rule, headline, optional rank or hard number, one line of evidence. No slab panel over a real face.

Use it for what the ear cannot hold: a date, a ranking, a count. Never restate the narration.

## Primary documents as evidence

Screenshot real pages. Capture the page, record url, timestamp, page title, selector, and a hash beside the image. Never draw a mock-up of a post — that is fabricating a record, whatever the intent.

A screenshot enters the film as a full-screen evidence segment, not as a corner sticker: the viewer is being asked to read it.

Crop to the block that carries the claim, and record why anything visible was cropped away. If a page contradicts the narration on a checkable fact, resolve the fact first; only then decide what appears on screen.

Two things decide whether the card is usable, and both are measured before the render, not after.

**Height.** The card is centred and fits inside 94% × 88% of the canvas; the subtitle is
top-anchored. A width-limited card clears the subtitle only when `height / width ≤ 1.111`.
A tall page therefore never fits whole — decide what to drop and record that the drop was
forced, not preferred.

**Legibility.** On-canvas glyph height is `page CSS size × 1015 ÷ layout CSS width`.
The screenshot's pixel count appears nowhere in that expression: a sharper capture of the
same layout renders exactly the same text size. To enlarge the text, narrow the layout so
the page rewraps. Beware mobile emulation on a page with no `<meta name="viewport">` —
the engine falls back to a 980 CSS px layout and scales it down, so no viewport width
changes the layout width, and the text can never grow. Check the page for that tag; when
it is absent, capture in desktop mode at a narrow viewport instead. Verify by resizing the
crop to its real on-canvas scale and reading it; the full-size crop always looks fine.

Nothing that changes between captures — a like count, a view count — belongs in the
narration, for the same reason nothing cropped away does.

## Cuts

Dissolve, never cut to black. Cut after the ball is dead, not mid-rally, when the source kept the whole point. Keep a segment inside one shot unless the spec says why crossing is right. Trim a broadcaster's end card and keep its bug out of the crop window.

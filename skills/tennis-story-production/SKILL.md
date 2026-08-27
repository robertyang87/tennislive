---
name: tennis-story-production
description: Produce “网球有故事” video-format story films from real footage — evergreen human arcs cut from multiple official sources, with copy written against the timeline, speed ramps, a licensed music bed, story_text bands, and primary-document screenshots as full-screen evidence. Use for story-film planning, spec authoring, edit grammar, or quality gates on this column.
---

# Tennis Story Production

“网球有故事” tells one person's arc, not one match's result. It is evergreen: nothing in it expires when the next round is played. The account owner ruled on 2026-08-27 that this column ships as **video cut from real footage**, not as card slideshows — cards were judged “太简单或者太平淡”.

Cards are not banned outright; they lose whenever real footage exists. Since official channels carry the footage for nearly every story worth telling, in practice this column is always a video cut.

## Pipeline

1. **Choose the arc.** One person, one turn, a landing point that does not depend on a result still to come. Reject anything that is really a match preview or a match review — those are other columns.
2. **Build the fact base before writing a line.** Four source classes, checked in this order: structured feeds, editorial copy from the event or tour, on-screen self-evidence burned into the footage, and primary documents the subject published. Every absolute claim needs two independent sources.
3. **Collect footage.** Official tour, event, or broadcaster channels only, verified by four elements (who, where, when, what) from the channel and the picture itself, never from the title alone. 1080p or better; wait rather than settle for 720p.
4. **Write copy and cuts as one artefact.** Load `references/narrative.md`. The line and the window are decided together; neither is finished before the other.
5. **Apply edit grammar.** Load `references/edit-grammar.md` for speed, music, `story_text`, screenshots-as-evidence, dissolves, and cut points.
6. **Capture primary documents.** Screenshot real pages only; never draw something that looks like a post.
7. **Run the local gates in order** (`references/quality-gates.md`) before spending a render.
8. **Render, pull the film back, look at it and measure it.** Frames for picture, levels for audio.
9. Merge, then push.

## Ownership

The narrative decides which second of footage exists for a reason. Deterministic code owns window arithmetic, dissolve accounting, subtitle alignment, loudness, licence fields, and every schema. Neither may cover for the other: a beautiful line over the wrong picture fails, and a valid spec that says nothing also fails.

Footage, facts, and licences never come from a model. When evidence is missing the film waits.

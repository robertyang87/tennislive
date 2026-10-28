"""Approved compact video headers, shared by reels and post-match interviews.

2026-10-25: transparent background; 40px main line, original 38px context
and 40px scores. A sharp edge and a soft, text-shaped shadow replace the scrim.
2026-10-28: owner asked「字号是不是要再大一点」; compared 40 / +10% / +20% / +30%
on a phone-scale sheet and took +20% (48 / 46 / 48). Tops, ink split and height
were re-measured from real libass ink rows, keeping the old proportions:
head ink 11..50, body ink 54..82 (was 11..42 / 46..69, height 80).
Keep imports standard-library-only: the interview scheduler imports this module.
"""

HEAD_SIZE = 48
BODY_SIZE = 46
SCORE_SIZE = 48
HEAD_TOP = 8
BODY_TOP = 42
ICON_H = 34
HEIGHT = 96
OUTLINE = 2.2
SHADOW = 1.2
INK_SPLIT_Y = 52
_HALO = r"\1a&HFF&\3a&H90&\4a&H70&\bord3\blur2\xshad0\yshad2"


def ass_events(start: str, end: str, style: str, text: str, *, layer: int = 1) -> list[str]:
    """Render a soft halo below sharp text; preserve all runs and animation.

    An ASS reset inside an icon or mixed-font run also resets alpha and blur.
    Reapply the halo after each reset rather than accidentally drawing two fills.
    """
    halo = "{" + _HALO + "}" + text.replace(r"\r", r"\r" + _HALO)
    foreground = text.replace(r"\bord0\shad0", r"\bord0.8\shad1")
    return [f"Dialogue: 0,{start},{end},{style},,0,0,0,,{halo}",
            f"Dialogue: {layer},{start},{end},{style},,0,0,0,,{foreground}"]


def draw_text(image, xy, text, *, font, fill, anchor="mt") -> None:
    """The pre-rasterized subject-header path uses the same text-bound shadow."""
    from PIL import Image, ImageDraw, ImageFilter

    halo = Image.new("RGBA", image.size)
    ImageDraw.Draw(halo).text((xy[0], xy[1] + 2), text, font=font, anchor=anchor,
                             fill=(0, 0, 0, 112), stroke_width=3,
                             stroke_fill=(0, 0, 0, 112))
    image.alpha_composite(halo.filter(ImageFilter.GaussianBlur(2)))
    ImageDraw.Draw(image).text(xy, text, font=font, fill=fill, anchor=anchor,
                              stroke_width=2, stroke_fill=(0, 0, 0, 255))

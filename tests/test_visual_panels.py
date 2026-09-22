import base64
import io
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from analyze_reel_visuals import contact_panels


def test_endgame_panels_keep_original_coordinates_and_pixels(tmp_path):
    sheet = Image.new("RGB", (2190, 1034))
    for row in range(5):
        for col in range(6):
            sheet.paste((row * 40, col * 40, 70),
                        (col * 366, row * 208, col * 366 + 360, row * 208 + 202))
    path = tmp_path / "contact.png"
    sheet.save(path)
    panels = contact_panels(path)
    assert len(panels) == 9
    for i, panel in enumerate(panels):
        image = Image.open(io.BytesIO(base64.b64decode(panel["image_url"]["url"].split(",")[1])))
        x, y = (i % 3) * 732, (i // 3) * 416
        expected = sheet.crop((x, y, min(x + 726, 2190), min(y + 410, 1034)))
        assert image.tobytes() == expected.tobytes()
        assert panel["image_url"]["detail"] == "high"


def test_unknown_sheet_geometry_is_never_reinterpreted(tmp_path):
    path = tmp_path / "custom.png"
    Image.new("RGB", (1920, 1200), "red").save(path)
    panels = contact_panels(path)
    assert len(panels) == 1
    assert base64.b64decode(panels[0]["image_url"]["url"].split(",")[1]) == path.read_bytes()

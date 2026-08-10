import os, tempfile
from PIL import Image

def test_detect_zones():
    from backend.app.services.segmentation import detect_zones_heuristic, segment_page
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "page.png")
        im = Image.new("RGB", (768,1024), color="white")
        # draw a fake stamp rectangle bottom-right
        from PIL import ImageDraw
        draw = ImageDraw.Draw(im)
        draw.rectangle([600,850,760,1000], outline="black", width=2)
        im.save(path)
        zones = detect_zones_heuristic(path)
        assert "stamp" in zones
        assert "graphic_views" in zones
        assert all("bbox" in v for v in zones.values())
        # segment
        seg = segment_page(path, 1, 1)
        assert "crops" in seg
        assert "stamp" in seg["crops"]
        # check files exist
        for v in seg["crops"].values():
            assert os.path.exists(v["path"])

def test_crop_zone():
    from backend.app.services.segmentation import crop_zone
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        dst = os.path.join(tmp, "dst.png")
        im = Image.new("RGB", (1000,1000), color="blue")
        im.save(src)
        out = crop_zone(src, [0.5,0.5,0.25,0.25], dst)
        assert os.path.exists(out)
        im2 = Image.open(out)
        assert im2.size==(250,250)
